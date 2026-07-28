import json
import uuid
import logging
from datetime import datetime, UTC
from typing import Dict, Any
from groq import AsyncGroq

from backend.agents.graph.state import InterviewState
from backend.core.security import get_settings

settings = get_settings()
groq_client = AsyncGroq(api_key=settings.groq_api_key)
logger = logging.getLogger("mockai-adaptive-graph")


async def technical_agent_node(state: InterviewState) -> Dict[str, Any]:
    job_title = state['job_title']
    tech_stack = state['tech_stack']
    difficulty = state['difficulty']
    interviewer_personality = state['interviewer_personality']
    preferred_language = state['preferred_language']
    active_strategy = state.get('active_strategy') or "No blueprint. Default to mid-level array/string/hashmap probing."
    code_in_editor = state.get('code_in_editor') or "(editor empty)"
    messages = state.get('messages', [])

    rounds_list = state['rounds_blueprint'].get("rounds", [])
    current_round_index = state.get("current_round_index", 0)
    current_round_config = (
        rounds_list[current_round_index] if current_round_index < len(rounds_list) else {}
    )

    round_turn_count = state.get("round_turn_count", 0)
    is_opening_turn = round_turn_count == 0

    recent_transcript = messages[-6:] if messages else []
    transcript_str = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in recent_transcript
    ) or "(round just started, no candidate response yet)"

    system_prompt = (
        "You are the Technical/Live-Coding Interviewer Agent for Mock.ai. "
        f"Persona: {interviewer_personality}. "
        "Turn the Planner's blueprint into the ACTUAL next thing you say to the candidate — "
        "the opening problem, a clarifying probe, or a follow-up on their latest code/explanation.\n\n"
        "--- RULES ---\n"
        "1. Output ONLY what you'd say out loud (this is converted to speech) — no markdown, no code blocks.\n"
        "2. If code_in_editor has a bug, do NOT reveal the fix directly — ask a leading question.\n"
        "3. Keep it to 2-4 sentences max per turn."
    )

    user_prompt = f"""
    === STRATEGIC BLUEPRINT (from Planner) ===
    {active_strategy}

    === CANDIDATE PROFILE ===
    - Position: {job_title}
    - Stack: {", ".join(tech_stack)}
    - Difficulty: {difficulty}
    - Language: {preferred_language}

    === CURRENT ROUND CONFIG ===
    {json.dumps(current_round_config)}

    === RECENT TRANSCRIPT ===
    {transcript_str}

    === CURRENT CODE EDITOR STATE ===
    {code_in_editor}

    {"Ask the OPENING technical question now." if is_opening_turn else "React to the candidate's latest response/code and ask the next probing question or follow-up."}
    """


    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=512
        )
        question_text = completion.choices[0].message.content.strip()
        logger.info("[Technical Agent] Generated next interview turn.")
    except Exception as e:
        logger.error(f"[Technical Agent Error] Generation failed: {e}")
        question_text = {}

    new_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": question_text,
        "round": "technical",
        "timestamp": datetime.now(UTC).isoformat()
    }

    return {
        "pending_question": question_text,
        "active_round_node": "technical",
        "round_turn_count": round_turn_count + 1,
        "messages": [new_message]
    }