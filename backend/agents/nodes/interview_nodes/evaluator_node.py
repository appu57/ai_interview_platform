import json
import logging
from datetime import datetime, UTC
from typing import Dict, Any
from groq import AsyncGroq

from backend.agents.graph.state import InterviewState
from backend.core.security import get_settings

settings = get_settings()
groq_client = AsyncGroq(api_key=settings.groq_api_key)
logger = logging.getLogger("mockai-adaptive-graph")

ROUND_RUBRICS = {
    "oa": "Weight correctness and test-pass-rate heaviest. Penalize time/space complexity that's "
          "worse than optimal for the stated constraints. Communication is secondary here.",
    "technical": "Weight problem-solving approach and communication (talking through tradeoffs) as "
                 "heavily as final code correctness across the round. A candidate who reasoned well "
                 "throughout but had a minor bug should not score much lower than one who got lucky "
                 "with a working brute force on one turn.",
    "system_design": "Weight scalability tradeoff reasoning, handling of ambiguity, and depth across "
                      "the round's follow-up pressure. Penalize hand-waving on bottlenecks once "
                      "explicitly probed.",
    "behavioral": "Weight STAR completeness (Situation/Task/Action/Result) and specificity across "
                  "all answers in the round. Penalize vague, generic, or unverifiable claims with no "
                  "concrete incident behind them.",
}


def _build_full_round_transcript(state: InterviewState) -> str:
    messages = state.get("messages", [])
    round_turn_count = state.get("round_turn_count", 0)
    window = max(round_turn_count * 2, 2)  # AI turn + candidate turn per count
    window_messages = messages[-window:] if messages else []
    return "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in window_messages
    ) or "(no transcript recorded for this round)"


async def evaluator_agent_node(state: InterviewState) -> Dict[str, Any]:
    active_round_node = state.get("active_round_node") or "technical"
    current_round_index = state.get("current_round_index", 0)
    rounds_list = state["rounds_blueprint"].get("rounds", [])
    current_round_config = (
        rounds_list[current_round_index] if current_round_index < len(rounds_list) else {}
    )

    transcript_str = _build_full_round_transcript(state)
    code_submission = state.get("code_submission")
    execution_result = state.get("execution_result")
    whiteboard_snapshot = state.get("whiteboard_snapshot")
    active_oa_payload = state.get("active_oa_payload")

    artifact_block = "(no code/whiteboard artifact submitted this round)"
    if active_round_node == "oa" and (code_submission or execution_result or active_oa_payload):
        hidden_tests_str = (
            json.dumps(active_oa_payload.get("hidden_test_cases", []))
            if active_oa_payload else "(no problem payload recorded)"
        )
        artifact_block = (
            f"--- FINAL CODE SUBMISSION ---\n{code_submission or '(none)'}\n\n"
            f"--- EXECUTION RESULT ---\n{json.dumps(execution_result) if execution_result else '(not executed)'}\n\n"
            f"--- HIDDEN TEST CASES (for grading correctness, not shown to candidate) ---\n{hidden_tests_str}"
        )
    elif active_round_node == "technical" and (code_submission or execution_result):
        artifact_block = (
            f"--- FINAL CODE SUBMISSION ---\n{code_submission or '(none)'}\n\n"
            f"--- EXECUTION RESULT ---\n{json.dumps(execution_result) if execution_result else '(not executed)'}"
        )
    elif active_round_node == "system_design" and whiteboard_snapshot:
        artifact_block = f"--- FINAL WHITEBOARD STATE ---\n{whiteboard_snapshot}"

    rubric = ROUND_RUBRICS.get(active_round_node, ROUND_RUBRICS["technical"])

    system_prompt = (
        "You are the Evaluator Agent for Mock.ai. The candidate has just COMPLETED the entire "
        f"'{active_round_node}' round. Score the round as a whole based on the full transcript below "
        "— do not score individual turns separately.\n\n"
        f"--- RUBRIC FOR THIS ROUND TYPE ---\n{rubric}\n\n"
        "--- OUTPUT CONTRACT ---\n"
        "Respond with STRICT JSON only, no markdown fences, no commentary:\n"
        "{\n"
        '  "score": int (0-100, for this entire round),\n'
        '  "strengths": [string],\n'
        '  "weaknesses": [string],\n'
        '  "feedback_note": string (1-2 sentences, internal — not shown live to candidate),\n'
        '  "guardrail_flag": string | null  // e.g. "plagiarism_suspected", "off_topic", "toxic_language"\n'
        "}"
    )

    user_prompt = f"""
    === FULL ROUND TRANSCRIPT ===
    {transcript_str}

    === FINAL SUBMITTED ARTIFACT ===
    {artifact_block}

    === ROUND CONFIG ===
    {json.dumps(current_round_config)}

    Score this completed round now.
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        result = json.loads(completion.choices[0].message.content)
        logger.info(f"[Evaluator] Round '{active_round_node}' (index {current_round_index}) scored {result.get('score')}.")
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[Evaluator Error] Round scoring failed: {e}")
        result = {}

    score_entry = {
        "round": active_round_node,
        "round_index": current_round_index,
        "score": result.get("score", 50),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "feedback_note": result.get("feedback_note", ""),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    return {
        "round_scores": [score_entry], 
        "last_guardrail_flag": result.get("guardrail_flag"),
        "current_round_index": current_round_index + 1,
        "round_turn_count": 0,
        "pending_question": None,
        "code_submission": None,
        "execution_result": None,
        "active_oa_payload": None,
    }