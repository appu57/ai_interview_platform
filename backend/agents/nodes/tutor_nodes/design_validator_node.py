import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.agents.graph.state import TutorSystemDesignState
from backend.agents.nodes.tutor_nodes.local_model_client import call_fine_tuned_model
from backend.agents.nodes.tutor_nodes.groundedness_judge import (
    JudgeOutcome,
    judge_groundedness,
    judge_validation_groundedness,
    record_metric,
    run_judged_generation,
)
from backend.agents.nodes.tutor_nodes.latency_budget import get_or_create_budget
from backend.agents.nodes.tutor_nodes.guardrails import check_input, check_output
from backend.agents.nodes.tutor_nodes.observability import record_guardrail_block

logger = logging.getLogger("mockai-tutor-graph")

UTC = timezone.utc

STOP_MARKER = "<<<END_FEEDBACK>>>"
QA_STOP_MARKER = "<<<END_ANSWER>>>"
CONCEPT_STOP_MARKER = "<<<END_EXPLANATION>>>"

MAX_TOKENS_QA = 300
MAX_TOKENS_CONCEPT = 400
MAX_TOKENS_VALIDATION = 500
MAX_CORRECTION_ATTEMPTS = 2

JUDGE_RESERVE_SECONDS = 10.0
MIN_VIABLE_GENERATE_SECONDS = 10.0

_QA_BUDGET = get_or_create_budget("qa", prior_warm_seconds=8.0, prior_cold_seconds=16.0, floor_seconds=6.0, ceiling_seconds=30.0)
_CONCEPT_BUDGET = get_or_create_budget("concept", prior_warm_seconds=14.0, prior_cold_seconds=24.0, floor_seconds=8.0, ceiling_seconds=38.0)
_VALIDATION_BUDGET = get_or_create_budget("validation", prior_warm_seconds=16.0, prior_cold_seconds=28.0, floor_seconds=8.0, ceiling_seconds=46.0)


VALIDATOR_SYSTEM_PROMPT = """You are a Principal System Design Architect reviewing a Staff-level candidate's whiteboard diagram against their interview question. Speak peer-to-peer: warm but direct.
Respond in PLAIN TEXT, following this exact structure:
GROUNDING: <comma-separated list of every non-empty node label in the diagram JSON. If none are labeled, write NONE>
Then, based only on what's in GROUNDING:
If there's enough to critique:
STATUS: OK
STRENGTHS:
1. <specific thing they got right -- one full sentence, referencing only GROUNDING items>
2. <...>
RISKS:
1. <specific critical risk, blind spot, or omission -- one full sentence>
2. <...>
(3-4 risks total)
If GROUNDING is NONE or there's not enough labeled content:
STATUS: INSUFFICIENT
MESSAGE: <1-2 encouraging sentences on what's missing and inviting them to add more>
Never reference a component, pattern, or technology in STRENGTHS/RISKS that isn't in GROUNDING or the question itself. Each strength/risk is a standalone sentence -- no padding or restating.
Write <<<END_FEEDBACK>>> on its own line right after your last line, then stop."""

QA_SYSTEM_PROMPT = """You are the MockAI system design tutor. The candidate just asked a question out loud mid-session.
Answer it directly in 2-3 short spoken sentences, one flowing paragraph -- no markdown, headers, or lists (this is read aloud via text-to-speech).
For "which X should I use" style questions, give ONE clear recommendation with a brief reason, not a list of options.
Use the problem and their diagram as context if relevant, but don't feel restricted to it -- an empty whiteboard this early is normal, so don't comment on it unless they ask.
Only state facts you're genuinely confident about; hedge briefly if unsure rather than stating it as flat fact.
Write <<<END_ANSWER>>> on its own line right after your answer, then stop."""

CONCEPT_SYSTEM_PROMPT = """You are the MockAI system design tutor. The candidate typed a question into the chat panel.

Start with: CONFIDENCE: HIGH or CONFIDENCE: LOW
Use LOW if any part of your answer relies on technical details you're not fully sure about (exact internal mechanics of a named tool, which component natively supports which feature, etc). If LOW, hedge those specific parts ("typically", "in most implementations") instead of stating them as flat fact.

Then judge the question type:
- Simple factual/logistical ("what's the interview question", "how much time do I have", "what did I already draw") -- answer directly in 1-3 sentences, no padding.
- Genuine concept question ("explain CQRS", "when should I use eventual consistency here") -- write ~180-220 words grounded in their specific problem, as a Principal Architect mentoring a peer: precise, concrete, willing to name real trade-offs.

Always answer what was actually asked -- don't deflect by asking them to draw a diagram first or by describing your own process instead of answering, and don't substitute a different topic for what was asked.
Write <<<END_EXPLANATION>>> on its own line right after your answer, then stop."""

class ValidationFeedbackSchema(BaseModel):
    sufficient_detail: bool
    insufficient_detail_message: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


QA_JUDGE_TEMPLATE = """QUESTION CONTEXT:
{question}

CANDIDATE ASKED:
{user_question}

MODEL'S SPOKEN ANSWER TO CHECK:
{raw_output}

Specifically check: (1) if the candidate asked "which X should I use" or similar, does the answer give ONE clear recommendation rather than listing multiple unrelated options? (2) any confidently-stated technical claim you're sure is wrong?"""

CONCEPT_JUDGE_TEMPLATE = """INTERVIEW PROBLEM:
{question}

CANDIDATE'S CHAT QUESTION:
{user_question}

MODEL'S EXPLANATION TO CHECK:
{raw_output}

Specifically check: (1) does this actually answer what was asked, not a different topic, and does it actually attempt an answer rather than deflecting/asking for clarification it doesn't need? (2) any confidently-stated technical claim about how a specific technology works that you're sure is wrong? (3) any technique described as standard/real that you're confident is invented or misapplied?"""


def _diagram_context_block(structured_json: dict) -> str:
    has_diagram = bool(structured_json.get("nodes"))
    if has_diagram:
        return f"CANDIDATE'S CURRENT DIAGRAM (JSON):\n{json.dumps(structured_json, indent=2)}"
    return "CANDIDATE'S CURRENT DIAGRAM: nothing submitted yet -- they haven't drawn anything on the whiteboard."


def _recent_context_from_conversation_memory(messages: list) -> Optional[str]:
    prior = [m["content"] for m in messages if m.get("role") == "assistant"]
    if not prior:
        return None
    joined = "\n---\n".join(p[:500] for p in prior[-4:])
    return "WHAT YOU'VE ALREADY TOLD THIS CANDIDATE THIS SESSION (avoid repeating verbatim, note if earlier feedback was acted on):\n" + joined


def _build_validation_prompt(question: str, structured_json: dict, correction_feedback: Optional[str] = None, prior_context: Optional[str] = None) -> str:
    base = f"QUESTION:\n{question}\n\nCANDIDATE'S DIAGRAM (JSON):\n{json.dumps(structured_json, indent=2)}"
    if prior_context:
        base = f"{prior_context}\n\n{base}"
    if correction_feedback:
        base += (
            f"\n\nYOUR PREVIOUS ATTEMPT HAD THIS PROBLEM: {correction_feedback}\n"
            "Revise your answer to fix this specific issue. Only reference "
            "components that are actually listed in your own GROUNDING line."
        )
    return base


def _build_qa_prompt(question: str, structured_json: dict, user_question: str, correction_feedback: Optional[str] = None, prior_context: Optional[str] = None) -> str:
    base = f"PROBLEM:\n{question}\n\n{_diagram_context_block(structured_json)}\n\nCANDIDATE'S QUESTION:\n{user_question}"
    if prior_context:
        base = f"{prior_context}\n\n{base}"
    if correction_feedback:
        base += f"\n\nYOUR PREVIOUS ATTEMPT HAD THIS PROBLEM: {correction_feedback}\nRevise your answer to fix this specific issue."
    return base


def _build_concept_prompt(question: str, structured_json: dict, user_question: str, correction_feedback: Optional[str] = None, prior_context: Optional[str] = None) -> str:
    base = f"INTERVIEW PROBLEM:\n{question}\n\n{_diagram_context_block(structured_json)}\n\nCANDIDATE'S CHAT QUESTION:\n{user_question}"
    if prior_context:
        base = f"{prior_context}\n\n{base}"
    if correction_feedback:
        base += f"\n\nYOUR PREVIOUS ATTEMPT HAD THIS PROBLEM: {correction_feedback}\nRevise your answer to fix this specific issue."
    return base


def _make_message(role: str, content: str, kind: Optional[str] = None, verified: Optional[bool] = None) -> dict:
    msg = {"id": str(uuid.uuid4()), "role": role, "content": content, "timestamp": datetime.now(UTC).isoformat()}
    if kind is not None:
        msg["kind"] = kind
    if verified is not None:
        msg["verified"] = verified
    return msg


def _parse_validation_output(text: str) -> Optional[ValidationFeedbackSchema]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    if lines[0].upper().startswith("GROUNDING:"):
        lines = lines[1:]
    if not lines:
        return None

    status_line = lines[0]
    if not status_line.upper().startswith("STATUS:"):
        return None
    status = status_line.split(":", 1)[1].strip().upper()

    if status == "INSUFFICIENT":
        message_parts = []
        capturing = False
        for line in lines[1:]:
            if line.upper().startswith("MESSAGE:"):
                capturing = True
                message_parts.append(line.split(":", 1)[1].strip())
            elif capturing:
                message_parts.append(line)
        message = " ".join(p for p in message_parts if p).strip()
        if not message:
            return None
        return ValidationFeedbackSchema(sufficient_detail=False, insufficient_detail_message=message)

    if status != "OK":
        return None

    strengths_match = re.search(r"STRENGTHS:?\s*(.*?)(?=RISKS:?|$)", text, re.IGNORECASE | re.DOTALL)
    risks_match = re.search(r"RISKS:?\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    item_pattern = re.compile(r"\d+[\.\)]\s*(.*?)(?=\s*\d+[\.\)]|$)", re.DOTALL)

    strengths: List[str] = []
    if strengths_match:
        strengths = [m.strip() for m in item_pattern.findall(strengths_match.group(1)) if m.strip()]

    risks: List[str] = []
    if risks_match:
        risks = [m.strip() for m in item_pattern.findall(risks_match.group(1)) if m.strip()]

    if not strengths and not risks:
        return None

    return ValidationFeedbackSchema(sufficient_detail=True, strengths=strengths[:3], risks=risks[:8])


def _format_validation_feedback(parsed: ValidationFeedbackSchema) -> str:
    lines = ["### What you got right"]
    lines += [f"- {s}" for s in parsed.strengths]
    lines.append("\n### Critical risks & blind spots")
    lines += [f"- {r}" for r in parsed.risks]
    return "\n".join(lines)


def _strip_confidence_line(raw_output: str) -> str:
    lines = raw_output.split(CONCEPT_STOP_MARKER)[0].strip().splitlines()
    if lines and lines[0].upper().startswith("CONFIDENCE:"):
        logger.info("[tutor] Concept explanation confidence: %s", lines[0].split(":", 1)[1].strip())
        lines = lines[1:]
    return "\n".join(lines).strip()


async def design_validator_node(state: TutorSystemDesignState) -> dict:
    node_start = time.monotonic()
    structured_json = state.get("whiteboard_json") or {"nodes": [], "edges": []}
    question = state.get("system_design_question", "")
    action = state.get("user_action")
    user_question = state.get("user_question", "")
    messages = state.get("messages", [])

    if action == "ask_question":
        if not user_question:
            logger.warning("[tutor] design_validator_node got user_action='ask_question' with no user_question set.")
            return {"validation_feedback": "I didn't catch a question there -- could you ask again?"}

        ok, reason = check_input(user_question)
        if not ok:
            logger.error("[tutor] Input guardrail blocked question: %s", reason)
            record_guardrail_block("qa", "input", reason)
            return {"validation_feedback": "That looks like it might contain something I can't process -- could you rephrase it?"}

        prior_context = _recent_context_from_conversation_memory(messages)

        def _parse_qa(raw_output: str) -> Optional[str]:
            text = raw_output.split(QA_STOP_MARKER)[0].strip()
            return text or None

        async def _generate_qa(attempt: int, feedback: Optional[str], call_timeout: float) -> Optional[str]:
            prompt = _build_qa_prompt(question, structured_json, user_question, feedback, prior_context)
            return await call_fine_tuned_model(
                system_prompt=QA_SYSTEM_PROMPT,
                user_content=prompt,
                stop_marker=QA_STOP_MARKER,
                max_tokens=MAX_TOKENS_QA,
                hard_timeout_seconds=call_timeout,
                log_label=f"QA (attempt {attempt}/{MAX_CORRECTION_ATTEMPTS}, {call_timeout:.0f}s budget)",
            )

        async def _run_judge_qa(_raw_text: str, text: str, log_label: str):
            judge_prompt = QA_JUDGE_TEMPLATE.format(question=question, user_question=user_question, raw_output=text)
            return await judge_groundedness(judge_prompt, log_label)

        result = await run_judged_generation(
            node_name="qa",
            question_for_tiebreak=question,
            latency_budget=_QA_BUDGET,
            judge_reserve_seconds=JUDGE_RESERVE_SECONDS,
            min_viable_generate_seconds=MIN_VIABLE_GENERATE_SECONDS,
            generate=_generate_qa,
            parse=_parse_qa,
            format_candidate=lambda _raw, text: text,
            run_judge=_run_judge_qa,
            max_attempts=MAX_CORRECTION_ATTEMPTS,
            parse_failure_feedback="Your previous response came back empty -- answer the question directly this time.",
        )

        if result is None:
            answer, verified = "I had trouble processing that just now. Could you ask again?", False
        else:
            ok, reason = check_output(result.text)
            if not ok:
                logger.error("[tutor] Output guardrail blocked QA answer: %s", reason)
                record_guardrail_block("qa", "output", reason)
                answer, verified = "I wasn't able to produce a clean response there -- please try again.", False
            else:
                answer, verified = result.text, result.verified

        record_metric("node:qa", time.monotonic() - node_start, "validated" if verified else "fallback")
        return {
            "validation_feedback": answer,
            "qa_verified": verified,
            "messages": [_make_message("assistant", answer, kind="voice_qa", verified=verified)],
        }

    if action == "ask_concept":
        if not user_question:
            logger.warning("[tutor] design_validator_node got user_action='ask_concept' with no user_question set.")
            return {"validation_feedback": "I didn't catch a question there -- could you type that again?"}

        ok, reason = check_input(user_question)
        if not ok:
            logger.error("[tutor] Input guardrail blocked question: %s", reason)
            record_guardrail_block("concept", "input", reason)
            return {"validation_feedback": "That looks like it might contain something I can't process -- could you rephrase it?"}

        prior_context = _recent_context_from_conversation_memory(messages)

        def _parse_concept(raw_output: str) -> Optional[str]:
            text = _strip_confidence_line(raw_output)
            return text or None

        async def _generate_concept(attempt: int, feedback: Optional[str], call_timeout: float) -> Optional[str]:
            prompt = _build_concept_prompt(question, structured_json, user_question, feedback, prior_context)
            return await call_fine_tuned_model(
                system_prompt=CONCEPT_SYSTEM_PROMPT,
                user_content=prompt,
                stop_marker=CONCEPT_STOP_MARKER,
                max_tokens=MAX_TOKENS_CONCEPT,
                hard_timeout_seconds=call_timeout,
                log_label=f"Concept (attempt {attempt}/{MAX_CORRECTION_ATTEMPTS}, {call_timeout:.0f}s budget)",
            )

        async def _run_judge_concept(_raw_text: str, text: str, log_label: str):
            judge_prompt = CONCEPT_JUDGE_TEMPLATE.format(question=question, user_question=user_question, raw_output=text)
            return await judge_groundedness(judge_prompt, log_label)

        result = await run_judged_generation(
            node_name="concept",
            question_for_tiebreak=question,
            latency_budget=_CONCEPT_BUDGET,
            judge_reserve_seconds=JUDGE_RESERVE_SECONDS,
            min_viable_generate_seconds=MIN_VIABLE_GENERATE_SECONDS,
            generate=_generate_concept,
            parse=_parse_concept,
            format_candidate=lambda _raw, text: text,
            run_judge=_run_judge_concept,
            max_attempts=MAX_CORRECTION_ATTEMPTS,
            parse_failure_feedback="Your previous response came back empty -- answer the question directly this time.",
        )

        if result is None:
            answer, verified = "I had trouble putting together a verified explanation just now -- could you try asking again?", False
        else:
            ok, reason = check_output(result.text)
            if not ok:
                logger.error("[tutor] Output guardrail blocked concept answer: %s", reason)
                record_guardrail_block("concept", "output", reason)
                answer, verified = "I wasn't able to produce a clean response there -- please try again.", False
            else:
                answer, verified = result.text, result.verified

        record_metric("node:concept", time.monotonic() - node_start, "validated" if verified else "fallback")
        return {
            "validation_feedback": answer,
            "concept_verified": verified,
            "messages": [_make_message("assistant", answer, kind="concept_qa", verified=verified)],
        }

    if not structured_json.get("nodes"):
        feedback_msg = (
            "I don't see anything drawn on the board yet. Take a few "
            "minutes to sketch your components and connections, then hit "
            "review again when you're ready."
        )
        logger.info("[tutor] Skipped validator call for empty board.")
        return {"validation_feedback": feedback_msg, "validation_score": None}

    prior_context = _recent_context_from_conversation_memory(messages)

    def _parse_validation(raw_output: str) -> Optional[ValidationFeedbackSchema]:
        return _parse_validation_output(raw_output)

    def _format_validation_candidate(_raw: str, parsed: ValidationFeedbackSchema) -> str:
        if not parsed.sufficient_detail:
            return parsed.insufficient_detail_message or (
                "I don't have enough detail on the board yet to give you a "
                "real critique -- add some labels and connections and try again."
            )
        return _format_validation_feedback(parsed)

    async def _run_judge_validation(raw_text: str, parsed: ValidationFeedbackSchema, log_label: str):
        if not parsed.sufficient_detail:
            return JudgeOutcome.PASSED, "", []
        return await judge_validation_groundedness(question, structured_json, parsed.strengths, parsed.risks, log_label)

    async def _generate_validation(attempt: int, feedback: Optional[str], call_timeout: float) -> Optional[str]:
        prompt = _build_validation_prompt(question, structured_json, feedback, prior_context)
        return await call_fine_tuned_model(
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            user_content=prompt,
            stop_marker=STOP_MARKER,
            max_tokens=MAX_TOKENS_VALIDATION,
            hard_timeout_seconds=call_timeout,
            log_label=f"Validator (attempt {attempt}/{MAX_CORRECTION_ATTEMPTS}, {call_timeout:.0f}s budget)",
        )

    result = await run_judged_generation(
        node_name="validation",
        question_for_tiebreak=question,
        latency_budget=_VALIDATION_BUDGET,
        judge_reserve_seconds=JUDGE_RESERVE_SECONDS,
        min_viable_generate_seconds=MIN_VIABLE_GENERATE_SECONDS,
        generate=_generate_validation,
        parse=_parse_validation,
        format_candidate=_format_validation_candidate,
        run_judge=_run_judge_validation,
        max_attempts=MAX_CORRECTION_ATTEMPTS,
        parse_failure_feedback="Your response didn't follow the required GROUNDING/STATUS/STRENGTHS/RISKS format exactly -- follow it precisely this time.",
    )

    if result is None:
        record_metric("node:validation", time.monotonic() - node_start, "fallback")
        return {
            "validation_feedback": "I had trouble evaluating your diagram just now -- the tutor model didn't respond. Give it another try.",
            "validation_score": None,
            "validation_verified": False,
        }

    if not result.parsed.sufficient_detail:
        record_metric("node:validation", time.monotonic() - node_start, "insufficient_detail")
        logger.info("[tutor] Model flagged insufficient diagram detail.")
        return {
            "validation_feedback": result.text,
            "validation_score": None,
            "validation_verified": True,
            "messages": [_make_message("assistant", result.text, kind="validation", verified=True)],
        }

    ok, reason = check_output(result.text)
    if not ok:
        logger.error("[tutor] Output guardrail blocked validation feedback: %s", reason)
        record_guardrail_block("validation", "output", reason)
        feedback_text, verified = "I wasn't able to produce a clean response there -- please try again.", False
    else:
        feedback_text, verified = result.text, result.verified

    record_metric("node:validation", time.monotonic() - node_start, "validated" if verified else "fallback")
    logger.info("[tutor] Validated whiteboard.")
    return {
        "validation_feedback": feedback_text,
        "validation_score": None,
        "validation_verified": verified,
        "messages": [_make_message("assistant", feedback_text, kind="validation", verified=verified)],
    }