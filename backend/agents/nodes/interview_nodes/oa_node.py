import json
import uuid
import logging
import asyncio
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from groq import AsyncGroq

from backend.agents.graph.state import InterviewState
from backend.core.security import get_settings

settings = get_settings()
groq_client = AsyncGroq(api_key=settings.groq_api_key)
logger = logging.getLogger("mockai-adaptive-graph")

MAX_GENERATION_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.5


def _extract_usable_problem(raw_content: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw_content:
        return None
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict) and parsed.get("problem_statement"):
        return parsed
    return None


async def _generate_followup_response(
    state: InterviewState,
    existing_payload: Dict[str, Any],
) -> str:
    messages = state.get("messages", [])
    latest_candidate_msg = ""
    for m in reversed(messages):
        if m.get("role") in ("user", "candidate"):
            latest_candidate_msg = m.get("content", "")
            break

    problem_title = existing_payload.get("title", "the current problem")
    problem_statement = existing_payload.get("problem_statement", "")
    constraints = existing_payload.get("constraints", [])
    code_submission = state.get("code_submission") or ""

    system_prompt = (
        "You are an OA proctor for Mock.ai. The candidate is working on a timed coding problem. "
        "Your job is to respond to their question or progress update WITHOUT revealing the solution "
        "or generating a new problem.\n\n"
        "--- RULES ---\n"
        "1. If they ask a clarifying question about the problem, answer it using only the "
        "   problem statement and constraints — never add new requirements.\n"
        "2. If they seem stuck, give a light conceptual hint (e.g. 'think about what data structure "
        "   gives O(1) lookup') without writing or describing code.\n"
        "3. If they submitted code, acknowledge it briefly and encourage them to verify against the "
        "   sample test cases — do NOT evaluate correctness.\n"
        "4. Keep response to 1-3 sentences. Output only what you'd say out loud."
    )

    user_prompt = f"""
    === CURRENT PROBLEM ===
    Title: {problem_title}
    Statement: {problem_statement}
    Constraints: {json.dumps(constraints)}

    === CANDIDATE'S LATEST MESSAGE ===
    {latest_candidate_msg or "(submitted code without text)"}

    === CANDIDATE'S CURRENT CODE (if any) ===
    {code_submission[:500] if code_submission else "(none)"}

    Respond appropriately now.
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=256,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"[OA Agent] Follow-up response generation failed: {e}")
        return (
            f"Got it — keep working on '{problem_title}'. "
            "Double-check your solution against the sample test cases when you're ready to submit."
        )


async def oa_agent_node(state: InterviewState) -> Dict[str, Any]:
    round_turn_count = state.get("round_turn_count", 0)
    if round_turn_count > 0:
        existing_payload = state.get("active_oa_payload") or {}
        followup_text = await _generate_followup_response(state, existing_payload)

        followup_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": followup_text,
            "round": "oa",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(
            f"[OA Agent] Follow-up turn {round_turn_count + 1} — "
            "reusing existing problem, generated contextual response."
        )

        return {
            "active_round_node": "oa",
            "round_turn_count": round_turn_count + 1,
            "messages": [followup_message],
        }

    job_title = state["job_title"]
    experience_level = state["experience_level"]
    tech_stack = state["tech_stack"]
    difficulty = state["difficulty"]
    preferred_language = state["preferred_language"]
    active_strategy = (
        state.get("active_strategy")
        or "No blueprint. Default to balanced DSA fundamentals."
    )

    rounds_list = state["rounds_blueprint"].get("rounds", [])
    current_round_index = state.get("current_round_index", 0)
    current_round_config = (
        rounds_list[current_round_index] if current_round_index < len(rounds_list) else {}
    )

    system_prompt = (
        "You are the Online Assessment (OA) Generator Agent for Mock.ai. "
        "You receive a strategic blueprint from the Planner Agent and must translate it into "
        "EXACTLY ONE concrete, self-contained coding problem.\n\n"
        "--- OUTPUT CONTRACT ---\n"
        "Respond with STRICT JSON only, no markdown fences, no commentary, matching this schema:\n"
        "{\n"
        '  "title": string,\n'
        '  "problem_statement": string,\n'
        '  "function_signature": string,\n'
        '  "constraints": [string],\n'
        '  "topic_tags": [string],\n'
        '  "sample_test_cases": [{"input": string, "output": string}],\n'
        '  "hidden_test_cases": [{"input": string, "output": string}]\n'
        "}\n"
        "Provide 2-3 sample_test_cases and 4-6 hidden_test_cases. hidden_test_cases must include "
        "edge cases (empty input, max-constraint boundary, duplicates, negatives where relevant).\n"
        "CRITICAL: Do not include markdown JSON blocks (```json ... ```) in your output. Return raw JSON text only."
    )

    user_prompt = f"""
    === STRATEGIC BLUEPRINT (from Planner) ===
    {active_strategy}

    === CANDIDATE PROFILE ===
    - Target Position: {job_title} ({experience_level})
    - Tech Stack: {", ".join(tech_stack)}
    - Difficulty Metric: {difficulty}
    - Required Solution Language: {preferred_language}

    === CURRENT ROUND CONFIG ===
    {json.dumps(current_round_config)}

    Generate the single OA problem now, in {preferred_language}, as strict JSON per the schema.
    """

    problem_json: Dict[str, Any] = {}
    last_error: Optional[str] = None

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            completion = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            raw_content = completion.choices[0].message.content
            usable = _extract_usable_problem(raw_content)

            if usable is not None:
                problem_json = usable
                logger.info(
                    f"[OA Agent] Successfully generated OA problem on attempt {attempt}."
                )
                break

            last_error = (
                f"valid-but-unusable JSON shape (got "
                f"{type(json.loads(raw_content)).__name__ if raw_content else 'NoneType'})"
            )
            logger.warning(
                f"[OA Agent] Attempt {attempt}/{MAX_GENERATION_ATTEMPTS} returned "
                f"unusable content, will retry if attempts remain. raw={raw_content!r}"
            )

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"[OA Agent] Attempt {attempt}/{MAX_GENERATION_ATTEMPTS} raised "
                f"during generation/parsing: {e}"
            )

        if attempt < MAX_GENERATION_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    if not problem_json:
        logger.error(
            f"[OA Agent Error] All {MAX_GENERATION_ATTEMPTS} generation attempts failed. "
            f"Last error: {last_error}. Returning empty problem state."
        )

    new_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": problem_json.get("problem_statement", ""),
        "round": "oa",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    return {
        "pending_question": problem_json.get("problem_statement", ""),
        "active_oa_payload": problem_json,
        "active_round_node": "oa",
        "round_turn_count": 1,
        "code_submission": None,
        "messages": [new_message],
    }

