import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

from backend.agents.graph.state import TutorSystemDesignState
from backend.agents.nodes.tutor_nodes.local_model_client import call_fine_tuned_model
from backend.agents.nodes.tutor_nodes.groundedness_judge import (
    judge_hints_groundedness,
    record_metric,
    run_judged_generation,
)
from backend.agents.nodes.tutor_nodes.latency_budget import get_or_create_budget
from backend.agents.nodes.tutor_nodes.guardrails import check_input, check_output
from backend.agents.nodes.tutor_nodes.observability import record_fallback, record_guardrail_block

logger = logging.getLogger("mockai-tutor-system-design")

UTC = timezone.utc

STOP_MARKER = "<<<END_HINTS>>>"
MAX_TOKENS = 500
MAX_CORRECTION_ATTEMPTS = 2
JUDGE_RESERVE_SECONDS = 10.0  # matches groundedness_judge.JUDGE_TOTAL_BUDGET_SECONDS
MIN_VIABLE_GENERATE_SECONDS = 10.0

_HINTS_BUDGET = get_or_create_budget(
    "hints",
    prior_warm_seconds=30.0,
    prior_cold_seconds=45.0,
    floor_seconds=15.0,
    ceiling_seconds=60.0,
)

HINTS_PARSE_FAILURE_FEEDBACK = (
    "Your previous attempt didn't produce all 9 complete, correctly "
    "numbered items -- make sure you write a full 'N. recommendation -- "
    "why: reasoning' line for every item 1 through 9, in order, before stopping."
)


class HintSchema(BaseModel):
    hld: List[str] = Field(..., min_length=3, max_length=3)
    lld: List[str] = Field(..., min_length=3, max_length=3)
    design_patterns: List[str] = Field(..., min_length=3, max_length=3)


def _format_hint_text(hints: HintSchema) -> str:
    lines = ["### HLD"]
    lines += [f"{i + 1}. {point}" for i, point in enumerate(hints.hld)]
    lines.append("\n### LLD")
    lines += [f"{i + 1}. {point}" for i, point in enumerate(hints.lld)]
    lines.append("\n### Design Patterns")
    lines += [f"{i + 1}. {point}" for i, point in enumerate(hints.design_patterns)]
    return "\n".join(lines)


def _fallback_hints(question: str) -> str:
    logger.warning(
        "[HintsNode] Using fully-canned fallback hints for question=%r (total generation failure)",
        question[:120],
    )
    hints = HintSchema(
        hld=[
            "Define your partitioning/sharding strategy — why: uneven key access causes hot partitions if you shard naively.",
            "Pick a consistency model per data path — why: forcing strong consistency everywhere kills latency unnecessarily.",
            "Plan multi-region replication and failover — why: a single region is a single point of failure at scale.",
        ],
        lld=[
            "Make write paths idempotent — why: retries under distributed failure will otherwise double-apply writes.",
            "Add explicit backpressure on ingestion — why: unbounded queues convert slow downstreams into upstream OOM crashes.",
            "Version your schema and message formats — why: rolling deploys will otherwise break service compatibility mid-flight.",
        ],
        design_patterns=[
            "Circuit breaker on external dependencies — why: isolates a failing downstream component instead of letting failures cascade.",
            "CQRS to split read and write paths — why: read and write scaling needs rarely match 1:1 under peak volume.",
            "Saga pattern for cross-service transactions — why: distributed systems cannot rely on a single ACID database boundary.",
        ],
    )
    return _format_hint_text(hints)


_ITEM_LINE_RE = re.compile(r"^(\d{1,2})[\.\):]\s+(.*\S)\s*$")


def _parse_freeform_hints(text: str) -> Optional[HintSchema]:
    items_by_number: dict[int, str] = {}
    last_num: Optional[int] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        cleaned = line.lstrip("*-\u2022 ").strip().replace("**", "")
        match = _ITEM_LINE_RE.match(cleaned)

        if match:
            num = int(match.group(1))
            if 1 <= num <= 9 and num not in items_by_number:
                items_by_number[num] = match.group(2).strip()
                last_num = num
            else:
                last_num = None
        elif last_num is not None:
            items_by_number[last_num] = f"{items_by_number[last_num]} {cleaned}"

    if len(items_by_number) < 9:
        return None

    ordered = [items_by_number[i] for i in range(1, 10)]
    try:
        return HintSchema(hld=ordered[0:3], lld=ordered[3:6], design_patterns=ordered[6:9])
    except ValidationError:
        return None


def _recent_hint_context(messages: list) -> Optional[str]:
    prior = [m["content"] for m in messages if m.get("role") == "assistant" and m.get("kind") == "hints"]
    if not prior:
        return None
    return "PREVIOUSLY GIVEN HINTS THIS SESSION (do not repeat these exact points):\n" + "\n---\n".join(prior[-2:])


async def system_design_hints_node(state: TutorSystemDesignState) -> dict:
    node_start = time.monotonic()
    current_question = state.get("system_design_question")

    if not current_question:
        logger.error("[HintsNode] Missing 'question' in state. Backing off to fallback topic.")
        current_question = "Design a multi-region highly scalable transactional system."

    ok, reason = check_input(current_question)
    if not ok:
        logger.error("[HintsNode] Input guardrail blocked question: %s", reason)
        record_guardrail_block("hints", "input", reason)
        record_metric("node:hints", time.monotonic() - node_start, "input_blocked")
        return {"hints": "I couldn't process that question -- please rephrase it.", "hints_verified": False}

    prior_context = _recent_hint_context(state.get("messages", []))
    _last_raw_attempt: List[str] = []

    system_prompt = (
    "You are a Principal System Design Interviewer evaluating a Staff candidate.\n"
    "Given a system design interview question, return PLAIN TEXT ONLY: a flat numbered list of exactly 9 hints.\n\n"
    "STRUCTURE RULES:\n"
    "- Lines 1-3: High-Level Design (HLD) hints.\n"
    "- Lines 4-6: Low-Level Design (LLD) hints.\n"
    "- Lines 7-9: Design Pattern hints.\n"
    "- DO NOT write markdown headers (no '### HLD'), bold tags, or intro/outro text. Output lines 1 through 9 only.\n\n"
    "LINE FORMAT (STRICT):\n"
    "<NUMBER>. <CONCRETE_RECOMMENDATION> -- why: <TRADE_OFF_OR_FAILURE_MODE_REASONING>\n\n"
    "LENGTH RULE (STRICT -- violating this is the #1 reason your output gets rejected):\n"
    "- Each full line, including the why clause, MUST be 40 words or fewer.\n"
    "- Exactly ONE sentence, ONE clause. No semicolons. No parenthetical lists of alternative technologies "
    "CRITICAL DOMAIN RULE:\n"
    "Every single line MUST be 100 percent custom and relevant ONLY to the specific system described in the candidate's question. "
    "Do NOT invent unrelated concepts or copy boilerplate patterns that do not fit the target question."
    )

    async def _generate(attempt: int, feedback: Optional[str], call_timeout: float) -> Optional[str]:
        user_content = f"Interview question: {current_question}"
        if prior_context:
            user_content = f"{prior_context}\n\n{user_content}"
            
        if feedback:
            prior_attempt_block = ""
            if _last_raw_attempt and feedback != HINTS_PARSE_FAILURE_FEEDBACK:
                prior_attempt_block = (
                    "\n\nYOUR PREVIOUS ATTEMPT:\n"
                    f"{_last_raw_attempt[-1]}\n"
                )
            user_content += (
                f"\n\nYOUR PREVIOUS ATTEMPT HAD THIS PROBLEM: {feedback}\n"
                + ("Revise ONLY the flawed item(s) named above. Keep every other line identical. "
                   "Output all 9 items."
                   if prior_attempt_block else
                   "Write all 9 complete items from scratch, ensuring every line strictly follows 'N. choice -- why: reasoning'.")
            )

        raw = await call_fine_tuned_model(
            system_prompt=system_prompt,
            user_content=user_content,
            stop_marker=STOP_MARKER,
            max_tokens=MAX_TOKENS,
            hard_timeout_seconds=call_timeout,
            log_label=f"Hints (attempt {attempt}/{MAX_CORRECTION_ATTEMPTS}, {call_timeout:.0f}s budget)",
            num_ctx=2048,
        )
        if raw:
            _last_raw_attempt.append(raw)
        return raw

    async def _run_judge(_raw_text: str, hints: HintSchema, log_label: str):
        return await judge_hints_groundedness(
            current_question, 
            hints.hld, 
            hints.lld, 
            hints.design_patterns, 
            log_label
        )

    result = await run_judged_generation(
        node_name="hints",
        question_for_tiebreak=current_question,
        latency_budget=_HINTS_BUDGET,
        judge_reserve_seconds=JUDGE_RESERVE_SECONDS,
        min_viable_generate_seconds=MIN_VIABLE_GENERATE_SECONDS,
        generate=_generate,
        parse=_parse_freeform_hints,
        format_candidate=lambda _raw, hints: _format_hint_text(hints),
        run_judge=_run_judge,
        max_attempts=MAX_CORRECTION_ATTEMPTS,
        parse_failure_feedback=HINTS_PARSE_FAILURE_FEEDBACK,
    )

    used_canned_fallback = False
    if result is None:
        hint_text, hints_verified = _fallback_hints(current_question), False
        used_canned_fallback = True
    else:
        ok, reason = check_output(result.text)
        if not ok:
            logger.error("[HintsNode] Output guardrail blocked generated hints: %s", reason)
            record_guardrail_block("hints", "output", reason)
            record_fallback("hints", f"output guardrail blocked: {reason}")
            hint_text, hints_verified = _fallback_hints(current_question), False
            used_canned_fallback = True
        else:
            hint_text, hints_verified = result.text, result.verified

    if hints_verified:
        outcome_label = "validated"
    elif used_canned_fallback:
        outcome_label = "fallback"
    else:
        outcome_label = "best_effort"

    record_metric("node:hints", time.monotonic() - node_start, outcome_label)

    message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": hint_text,
        "timestamp": datetime.now(UTC).isoformat(),
        "kind": "hints",
        "verified": hints_verified,
    }

    return {"hints": hint_text, "hints_verified": hints_verified, "messages": [message]}