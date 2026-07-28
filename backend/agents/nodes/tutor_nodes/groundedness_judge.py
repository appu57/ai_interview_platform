import asyncio
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Tuple, TypeVar

from groq import AsyncGroq

from backend.agents.nodes.tutor_nodes.local_model_client import MODEL_NAME as LOCAL_GENERATOR_MODEL
from backend.agents.nodes.tutor_nodes.sysdesign_tutor_node import QUESTION_MODEL
from backend.agents.nodes.tutor_nodes.latency_budget import AdaptiveLatencyBudget
from backend.agents.nodes.tutor_nodes.observability import (
    log_event,
    observe_latency,
    record_best_effort_used,
    record_fallback,
    record_judge_decision,
    record_judge_error,
    record_parse_failure,
    record_tiebreak_decision,
)

logger = logging.getLogger("mockai-groundedness-judge")
gen_logger = logging.getLogger("mockai-judged-generation")


class JudgeOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


PRIMARY_JUDGE_MODEL = "qwen/qwen3.6-27b"
BACKUP_JUDGE_MODEL = "openai/gpt-oss-20b"

_GENERATOR_MODELS = {LOCAL_GENERATOR_MODEL, QUESTION_MODEL}

if PRIMARY_JUDGE_MODEL in _GENERATOR_MODELS:
    raise ValueError("primary judge must not share a model with any generator")
if BACKUP_JUDGE_MODEL in _GENERATOR_MODELS:
    raise ValueError("backup judge must not share a model with any generator")
if BACKUP_JUDGE_MODEL == PRIMARY_JUDGE_MODEL:
    raise ValueError("backup judge must differ from primary judge")

_judge_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

PRIMARY_JUDGE_REASONING_EFFORT = "none"
BACKUP_JUDGE_REASONING_EFFORT = "low"

FREEFORM_JUDGE_MAX_TOKENS = 500
ITEMIZED_JUDGE_MAX_TOKENS = 900
PER_CALL_TIMEOUT_SECONDS = 4.0
JUDGE_TOTAL_BUDGET_SECONDS = 10.0
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning_preamble(raw: str) -> str:
    cleaned = _THINK_BLOCK_RE.sub("", raw).strip()
    return cleaned or raw


class _CircuitBreaker:
    """After 3 failures in a row, stop even trying the primary judge for
    60s and go straight to the backup -- otherwise every request pays
    the cost of a doomed primary call before falling back."""
    CONSECUTIVE_FAILURE_THRESHOLD = 3
    COOLDOWN_SECONDS = 60.0

    def __init__(self, name: str):
        self._name = name
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    def allow_primary(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            return (time.monotonic() - self._opened_at) >= self.COOLDOWN_SECONDS

    def record_success(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                logger.info("[groundedness_judge] %s circuit CLOSED -- primary recovered.", self._name)
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.CONSECUTIVE_FAILURE_THRESHOLD and self._opened_at is None:
                self._opened_at = time.monotonic()
                logger.error(
                    "[groundedness_judge] %s circuit OPEN after %d failures -- skipping primary for %.0fs.",
                    self._name, self._consecutive_failures, self.COOLDOWN_SECONDS,
                )


_primary_breaker = _CircuitBreaker("primary judge")


class _LatencyStats:
    def __init__(self, max_samples: int = 500):
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self._outcome_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = threading.Lock()

    def record(self, op: str, seconds: float, outcome: str) -> None:
        with self._lock:
            self._latencies[op].append(seconds)
            self._outcome_counts[op][outcome] += 1

    @staticmethod
    def _percentile(sorted_samples: List[float], pct: float) -> Optional[float]:
        if not sorted_samples:
            return None
        idx = max(0, min(len(sorted_samples) - 1, int(round(pct / 100 * (len(sorted_samples) - 1)))))
        return round(sorted_samples[idx], 3)

    def snapshot(self, op: str) -> dict:
        with self._lock:
            samples = sorted(self._latencies.get(op, ()))
            counts = dict(self._outcome_counts.get(op, {}))
        return {
            "op": op,
            "sample_count": len(samples),
            "p50_s": self._percentile(samples, 50),
            "p95_s": self._percentile(samples, 95),
            "p99_s": self._percentile(samples, 99),
            "outcome_counts_lifetime": counts,
            "total_lifetime": sum(counts.values()),
        }

    def known_ops(self) -> List[str]:
        with self._lock:
            return list(self._latencies.keys())


_metrics = _LatencyStats()


def record_metric(op: str, seconds: float, outcome: str) -> None:
    _metrics.record(op, seconds, outcome)
    observe_latency(op, outcome, seconds)


def get_metrics_snapshot() -> Dict[str, dict]:
    return {op: _metrics.snapshot(op) for op in _metrics.known_ops()}


GROUNDEDNESS_JUDGE_SYSTEM = """You are a strict, skeptical fact-checker with NO external documents or knowledge base to consult. You may ONLY judge using:
(1) The exact grounding context given below -- to check the answer doesn't claim detail that isn't actually there (e.g. describing diagram components that don't appear in the diagram JSON).
(2) Well-established, uncontested facts about named mainstream technologies (Kafka, Redis, RocksDB, CQRS, Saga, sharding, consensus, etc.) -- to catch confidently-stated but wrong technical claims.
If you are not sure whether a claim is right or wrong, do NOT fail it for that reason alone -- only fail for concrete, checkable problems: content invented beyond what the grounding context supports, or a technical claim you are confident is factually wrong, or an answer that doesn't actually address what was asked.
Also extract every named technology, pattern, or protocol the answer asserts as fact (e.g. "CQRS", "Redis", "Raft consensus") into "claims", regardless of whether you judge it correct -- a separate deterministic check will cross-reference these against a verified knowledge base. Keep each claim to its bare name, not the full sentence. Empty list if none.
Respond with ONLY a single valid JSON object, no markdown fences, no commentary:
{"passed": true or false, "issue": "<one specific sentence describing the problem, or empty string if passed>", "claims": ["<term>", ...]}"""


HINTS_ITEMIZED_JUDGE_SYSTEM = """You are a strict, skeptical fact-checker with NO external documents or knowledge base to consult, reviewing a Staff System Design Interviewer's hint list for a candidate.
You will be given the interview question and exactly 9 numbered hints (1-3 High-Level Design, 4-6 Low-Level Design, 7-9 Design Patterns), each already written as a recommendation plus its "why" reasoning.
Judge EACH of the 9 hints independently:
- grounded: true only if (a) the hint actually applies to solving THIS specific question, not a generic unrelated one, AND (b) any named technology/pattern/protocol in it and its reasoning is either well-established/uncontested, or something you're not confident is wrong. Do not fail a hint for mere uncertainty -- only for a claim you're confident is incorrect or misapplied, a hint that plainly doesn't fit this question, or vague filler with no concrete recommendation.
- claim: the bare name of the primary named technology/pattern/protocol this hint asserts (empty string if none).
- issue: one specific sentence naming exactly what's wrong. Empty string if grounded is true.
passed is true only if ALL 9 hints have grounded=true.
Respond with ONLY a single valid JSON object, no markdown fences, no commentary:
{"passed": true or false, "hints": [{"index": 1, "grounded": true or false, "claim": "<term>", "issue": "<sentence or empty>"}, ... exactly 9 entries, index 1 through 9 in order]}"""

HINTS_ITEMIZED_JUDGE_TEMPLATE = """INTERVIEW QUESTION:
{question}
HINTS (numbered 1-9: 1-3 HLD, 4-6 LLD, 7-9 Design Patterns):
{numbered_hints}"""

VALIDATION_ITEMIZED_JUDGE_SYSTEM = """You are a strict, skeptical fact-checker with NO external documents or knowledge base to consult, reviewing a Principal Architect's critique of a candidate's system design whiteboard.
You will be given the interview question, the diagram JSON (the ONLY source of truth for what's actually on the candidate's board), and a numbered list of STRENGTH and RISK statements taken from the critique.
Judge EACH statement independently:
- grounded: true only if the statement doesn't reference any component, pattern, or technology that isn't actually present in the diagram JSON above (a general architectural risk not tied to a specific node is fine if it's a well-established concern that genuinely applies to what IS grounded there), AND any named technology claim in it is either well-established/uncontested or something you're not confident is wrong.
- claim: the bare name of the primary component/technology/pattern this statement references (empty string if none).
- issue: one specific sentence naming exactly what's wrong -- e.g. "references a message queue that doesn't appear anywhere in the diagram JSON". Empty string if grounded is true
passed is true only if EVERY statement has grounded=true.
Respond with ONLY a single valid JSON object, no markdown fences, no commentary:
{"passed": true or false, "items": [{"section": "strength" or "risk", "index": 1, "grounded": true or false, "claim": "<term>", "issue": "<sentence or empty>"}, ...]}"""

VALIDATION_ITEMIZED_JUDGE_TEMPLATE = """QUESTION:
{question}
DIAGRAM JSON (the ONLY source of truth for what's on the board):
{diagram_json}
STATEMENTS TO CHECK:
{numbered_items}"""


TIE_BREAK_JUDGE_SYSTEM = """You are picking between two flawed drafts of the same content -- neither is fully correct. You are NOT approving either as correct. You are only deciding which one has fewer or smaller problems, so it can be shown instead of nothing.
Respond with ONLY a single valid JSON object, no markdown fences, no commentary:
{"choice": 1 or 2, "reason": "<one short sentence>"}"""
TIE_BREAK_JUDGE_TEMPLATE = """QUESTION/CONTEXT:
{question}
CANDIDATE 1:
{candidate_a}
Known issue(s) with candidate 1: {issue_a}
CANDIDATE 2:
{candidate_b}
Known issue(s) with candidate 2: {issue_b}
Which candidate has fewer or smaller problems overall? Consider both the known issues above and your own read of each candidate."""


async def _call_judge_model(
    model: str, system_prompt: str, user_prompt: str, log_label: str,
    max_tokens: int, max_attempts: int, reasoning_effort: str,
) -> Optional[dict]:
    start = time.monotonic()
    last_error: Exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await _judge_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                response_format={"type": "json_object"},
                timeout=PER_CALL_TIMEOUT_SECONDS,
            )
            raw = (response.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("judge returned empty completion content")
            raw = _strip_reasoning_preamble(raw)
            parsed = json.loads(raw)
            observe_latency(f"judge:{log_label}:{model}", "success", time.monotonic() - start)
            return parsed
        except Exception as e:
            last_error = e
            if "invalid_request_error" in str(e):
                logger.error("[groundedness_judge] %s: non-retryable request error on %s: %s", log_label, model, e)
                break
            if attempt < max_attempts:
                logger.warning(
                    "[groundedness_judge] %s attempt %d/%d failed on %s: %s -- retrying.",
                    log_label, attempt, max_attempts, model, e,
                )
                await asyncio.sleep(0.3)

    observe_latency(f"judge:{log_label}:{model}", "error", time.monotonic() - start)
    logger.error("[groundedness_judge] %s: all attempt(s) failed on %s: %s", log_label, model, last_error, exc_info=True)
    return None


async def _call_judge_with_backup(system_prompt: str, user_prompt: str, log_label: str, max_tokens: int) -> Optional[dict]:
    if _primary_breaker.allow_primary():
        result = await _call_judge_model(
            PRIMARY_JUDGE_MODEL, system_prompt, user_prompt, log_label, max_tokens,
            max_attempts=2, reasoning_effort=PRIMARY_JUDGE_REASONING_EFFORT,
        )
        if result is not None:
            _primary_breaker.record_success()
            return result
        _primary_breaker.record_failure()
        logger.warning(
            "[groundedness_judge] primary judge (%s) unavailable for %s -- trying backup (%s).",
            PRIMARY_JUDGE_MODEL, log_label, BACKUP_JUDGE_MODEL,
        )
    else:
        logger.info("[groundedness_judge] %s: primary judge circuit open -- skipping straight to backup.", log_label)

    return await _call_judge_model(
        BACKUP_JUDGE_MODEL, system_prompt, user_prompt, log_label, max_tokens,
        max_attempts=1, reasoning_effort=BACKUP_JUDGE_REASONING_EFFORT,
    )


async def _call_judge(system_prompt: str, user_prompt: str, log_label: str, max_tokens: int) -> Optional[dict]:
    try:
        result = await asyncio.wait_for(
            _call_judge_with_backup(system_prompt, user_prompt, log_label, max_tokens),
            timeout=JUDGE_TOTAL_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("[groundedness_judge] %s: judge round trip exceeded %.0fs hard budget.", log_label, JUDGE_TOTAL_BUDGET_SECONDS)
        record_judge_error(log_label, f"judge round trip exceeded {JUDGE_TOTAL_BUDGET_SECONDS:.0f}s budget")
        return None

    if result is None:
        record_judge_error(log_label, "primary and backup judge both failed (non-timeout)")
    return result


async def judge_groundedness(judge_prompt: str, log_label: str) -> Tuple[JudgeOutcome, str, List[str]]:
    parsed = await _call_judge(GROUNDEDNESS_JUDGE_SYSTEM, judge_prompt, log_label, FREEFORM_JUDGE_MAX_TOKENS)
    if parsed is None:
        return JudgeOutcome.UNAVAILABLE, "", []
    claims = parsed.get("claims") or []
    if not isinstance(claims, list):
        claims = []
    outcome = JudgeOutcome.PASSED if bool(parsed.get("passed")) else JudgeOutcome.FAILED
    return outcome, str(parsed.get("issue", "")), [str(c) for c in claims]


def _outcome_from_graded_items(keyed_items: List[Tuple[Any, dict]], describe_key: Callable[[Any], str]) -> Tuple[JudgeOutcome, str, List[str]]:
    claims = [str(item.get("claim")) for _, item in keyed_items if item.get("claim")]
    flawed = [(key, item) for key, item in keyed_items if not item.get("grounded", True)]

    if not flawed:
        return JudgeOutcome.PASSED, "", claims

    lines = [f"{describe_key(key)}: {item.get('issue') or 'not sufficiently grounded'}" for key, item in flawed]
    feedback = (
        "The following specific items have problems -- revise ONLY these, "
        "keep every other item exactly as it was:\n" + "\n".join(lines)
    )
    return JudgeOutcome.FAILED, feedback, claims


async def judge_hints_groundedness(
    question: str, hld: List[str], lld: List[str], design_patterns: List[str], log_label: str
) -> Tuple[JudgeOutcome, str, List[str]]:
    numbered = (
        [f"{i}. {p}" for i, p in enumerate(hld, start=1)]
        + [f"{i}. {p}" for i, p in enumerate(lld, start=4)]
        + [f"{i}. {p}" for i, p in enumerate(design_patterns, start=7)]
    )
    user_prompt = HINTS_ITEMIZED_JUDGE_TEMPLATE.format(question=question, numbered_hints="\n".join(numbered))

    parsed = await _call_judge(HINTS_ITEMIZED_JUDGE_SYSTEM, user_prompt, log_label, ITEMIZED_JUDGE_MAX_TOKENS)
    if parsed is None:
        return JudgeOutcome.UNAVAILABLE, "", []

    items = parsed.get("hints")
    if not isinstance(items, list) or len(items) != 9:
        logger.error("[groundedness_judge] %s: itemized hints judge response malformed: %r", log_label, parsed)
        return JudgeOutcome.UNAVAILABLE, "", []

    by_index = {}
    for item in items:
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= idx <= 9:
            by_index[idx] = item

    if len(by_index) != 9:
        logger.error("[groundedness_judge] %s: itemized hints judge response missing indices: %r", log_label, parsed)
        return JudgeOutcome.UNAVAILABLE, "", []

    keyed_items = [(i, by_index[i]) for i in range(1, 10)]
    return _outcome_from_graded_items(keyed_items, describe_key=lambda i: f"Hint {i}")


async def judge_validation_groundedness(
    question: str, diagram_json: dict, strengths: List[str], risks: List[str], log_label: str
) -> Tuple[JudgeOutcome, str, List[str]]:
    numbered = (
        [f"strength {i}. {s}" for i, s in enumerate(strengths, start=1)]
        + [f"risk {i}. {r}" for i, r in enumerate(risks, start=1)]
    )
    user_prompt = VALIDATION_ITEMIZED_JUDGE_TEMPLATE.format(
        question=question, diagram_json=json.dumps(diagram_json, indent=2), numbered_items="\n".join(numbered)
    )

    parsed = await _call_judge(VALIDATION_ITEMIZED_JUDGE_SYSTEM, user_prompt, log_label, ITEMIZED_JUDGE_MAX_TOKENS)
    if parsed is None:
        return JudgeOutcome.UNAVAILABLE, "", []

    items = parsed.get("items")
    expected_count = len(strengths) + len(risks)
    if not isinstance(items, list) or len(items) != expected_count:
        logger.error(
            "[groundedness_judge] %s: itemized validation judge response malformed (expected %d items): %r",
            log_label, expected_count, parsed,
        )
        return JudgeOutcome.UNAVAILABLE, "", []

    seen = set()
    keyed_items: List[Tuple[Tuple[str, int], dict]] = []
    for item in items:
        section = item.get("section")
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if section == "strength" and 1 <= idx <= len(strengths):
            key = ("strength", idx)
        elif section == "risk" and 1 <= idx <= len(risks):
            key = ("risk", idx)
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        keyed_items.append((key, item))

    if len(keyed_items) != expected_count:
        logger.error("[groundedness_judge] %s: itemized validation judge response missing/duplicate items: %r", log_label, parsed)
        return JudgeOutcome.UNAVAILABLE, "", []

    return _outcome_from_graded_items(keyed_items, describe_key=lambda key: f"{key[0].capitalize()} {key[1]}")


async def judge_pick_better(
    question: str, candidate_a: str, candidate_b: str, issue_a: str, issue_b: str, log_label: str
) -> Tuple[int, str]:
    user_prompt = TIE_BREAK_JUDGE_TEMPLATE.format(
        question=question, candidate_a=candidate_a, issue_a=issue_a or "none flagged",
        candidate_b=candidate_b, issue_b=issue_b or "none flagged",
    )
    parsed = await _call_judge(TIE_BREAK_JUDGE_SYSTEM, user_prompt, log_label, FREEFORM_JUDGE_MAX_TOKENS)
    if parsed is None:
        logger.warning("[groundedness_judge] %s: tie-break judge unavailable -- defaulting to candidate 1.", log_label)
        return 1, "tie-break judge unavailable -- defaulted to candidate 1"
    choice = parsed.get("choice")
    reason = str(parsed.get("reason", ""))
    if choice not in (1, 2):
        logger.warning("[groundedness_judge] %s: tie-break judge gave invalid choice %r -- defaulting to candidate 1.", log_label, choice)
        return 1, f"tie-break judge returned invalid choice {choice!r} -- defaulted to candidate 1"
    logger.info("[groundedness_judge] %s: tie-break picked candidate %d -- %s", log_label, choice, reason)
    return choice, reason


T = TypeVar("T")


@dataclass
class JudgedGenerationResult(Generic[T]):
    text: str
    parsed: T
    verified: bool = True
    claims: List[str] = field(default_factory=list)


async def run_judged_generation(
    *,
    node_name: str,
    question_for_tiebreak: str,
    latency_budget: AdaptiveLatencyBudget,
    judge_reserve_seconds: float,
    min_viable_generate_seconds: float,
    generate: Callable[[int, Optional[str], float], Awaitable[Optional[str]]],
    parse: Callable[[str], Optional[T]],
    format_candidate: Callable[[str, T], str],
    run_judge: Callable[[str, T, str], Awaitable[Tuple[JudgeOutcome, str, List[str]]]],
    max_attempts: int,
    parse_failure_feedback: str,
) -> Optional[JudgedGenerationResult[T]]:
    start_time = time.monotonic()
    overall_deadline = start_time + max_attempts * (latency_budget.ceiling_seconds + judge_reserve_seconds)

    feedback: Optional[str] = None
    candidates: List[Tuple[str, T, str, List[str]]] = []
    was_cold = latency_budget.is_cold_start()

    for attempt in range(1, max_attempts + 1):
        time_left = overall_deadline - time.monotonic()
        if time_left - judge_reserve_seconds < min_viable_generate_seconds:
            gen_logger.warning(
                "[%s] Only %.1fs left before the overall deadline -- stopping before attempt %d/%d.",
                node_name, time_left, attempt, max_attempts,
            )
            break

        call_timeout = min(latency_budget.get_call_timeout(was_cold), time_left - judge_reserve_seconds)

        gen_start = time.monotonic()
        raw_text = await generate(attempt, feedback, call_timeout)
        gen_elapsed = time.monotonic() - gen_start

        if raw_text is not None:
            latency_budget.record_sample(gen_elapsed, was_cold)
        record_metric(f"generation:{node_name}", gen_elapsed, "success" if raw_text is not None else "timeout_or_error")

        if raw_text is None:
            gen_logger.warning("[%s] Attempt %d produced no output (budget was %.1fs, cold=%s).", node_name, attempt, call_timeout, was_cold)
            continue

        parsed = parse(raw_text)
        if parsed is None:
            gen_logger.error("[%s] Parse failed on attempt %d. Raw output: %r", node_name, attempt, raw_text[:500])
            record_parse_failure(node_name, raw_text)
            feedback = parse_failure_feedback
            continue

        candidate_text = format_candidate(raw_text, parsed)

        judge_start = time.monotonic()
        outcome, issue, claims = await run_judge(raw_text, parsed, f"{node_name} (attempt {attempt}/{max_attempts})")
        judge_elapsed = time.monotonic() - judge_start
        record_metric(f"judge:{node_name}", judge_elapsed, outcome.value)

        log_output_metrics(node_name, attempt, outcome, issue, gen_elapsed, judge_elapsed, was_cold)
        log_percentile_summary()

        if outcome is JudgeOutcome.PASSED:
            record_judge_decision(node_name, True, "", claims)
            return JudgedGenerationResult(text=candidate_text, parsed=parsed, verified=True, claims=claims)

        if outcome is JudgeOutcome.UNAVAILABLE:
            gen_logger.warning("[%s] Attempt %d: judge unavailable, cannot confirm groundedness.", node_name, attempt)
            candidates.append((candidate_text, parsed, "groundedness judge unavailable for this attempt", claims))
            continue

        record_judge_decision(node_name, False, issue, claims)
        gen_logger.warning("[%s] Attempt %d failed groundedness judge: %s", node_name, attempt, issue)
        candidates.append((candidate_text, parsed, issue, claims))
        feedback = issue

    if not candidates:
        gen_logger.warning("[%s] No usable candidate produced by any attempt -- caller must use its own fallback.", node_name)
        record_fallback(node_name, "no candidate produced (total generation failure)")
        return None

    if len(candidates) == 1:
        text, parsed, issue, claims = candidates[0]
        gen_logger.warning("[%s] Only one candidate available (%s) -- serving it instead of a fallback.", node_name, issue)
        record_metric(f"tiebreak:{node_name}", 0.0, "single_candidate")
        record_best_effort_used(node_name, f"only one real candidate produced; served unverified: {issue}")
        record_tiebreak_decision(
            node_name, winner_attempt=1, total_candidates=1, winner_issue=issue,
            all_issues=[issue], reason="only one real candidate produced -- no comparison possible",
        )
        return JudgedGenerationResult(text=text, parsed=parsed, verified=False, claims=claims)

    winner_idx = 0
    best_text, best_parsed, best_issue, best_claims = candidates[0]
    last_reason = ""
    tb_start = time.monotonic()
    for i, (text, parsed, issue, claims) in enumerate(candidates[1:], start=1):
        choice, reason = await judge_pick_better(question_for_tiebreak, best_text, text, best_issue, issue, f"{node_name} tie-break")
        last_reason = reason
        if choice == 2:
            winner_idx = i
            best_text, best_parsed, best_issue, best_claims = text, parsed, issue, claims
    tb_elapsed = time.monotonic() - tb_start
    record_metric(f"tiebreak:{node_name}", tb_elapsed, "compared")
    record_tiebreak_decision(
        node_name, winner_attempt=winner_idx + 1, total_candidates=len(candidates),
        winner_issue=best_issue, all_issues=[issue for _, _, issue, _ in candidates],
        reason=last_reason,
    )

    gen_logger.warning("[%s] Nothing fully validated -- serving tie-break winner. Remaining issue: %s", node_name, best_issue)
    record_best_effort_used(node_name, f"served tie-break winner (not fully validated): {best_issue}")
    return JudgedGenerationResult(text=best_text, parsed=best_parsed, verified=False, claims=best_claims)


def log_output_metrics(node_name: str, attempt: int, outcome: "JudgeOutcome", issue: str,
                        generation_latency_s: float, judge_latency_s: float, cold: bool) -> None:
    payload = {
        "node": node_name,
        "attempt": attempt,
        "outcome": outcome.value,       # "passed" = grounded, "failed" = hallucination caught, "unavailable" = judge couldn't check
        "issue": issue,
        "generation_latency_s": round(generation_latency_s, 2),
        "judge_latency_s": round(judge_latency_s, 2),
        "cold_start": cold,
    }
    logger.info(json.dumps({"event": "output_metrics", **payload}))
    log_event("output_metrics", **payload)


_last_summary_log = 0.0


def log_percentile_summary(min_interval_seconds: float = 300.0) -> None:
    global _last_summary_log
    now = time.monotonic()
    if now - _last_summary_log < min_interval_seconds:
        return
    _last_summary_log = now

    for op in _metrics.known_ops():
        snap = _metrics.snapshot(op)
        if op.startswith("judge:"):
            counts = snap["outcome_counts_lifetime"]
            passed, failed = counts.get("passed", 0), counts.get("failed", 0)
            snap["hallucination_rate"] = round(failed / (passed + failed), 3) if (passed + failed) else None
        logger.info(json.dumps({"event": "latency_summary", **snap}))
        log_event("latency_summary", **snap)