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


async def system_design_agent_node(state: InterviewState) -> Dict[str, Any]:
    job_title = state['job_title']
    experience_level = state['experience_level']
    target_company = state.get('target_company') or "a generic high-scale product company"
    interviewer_personality = state['interviewer_personality']
    active_strategy = state.get('active_strategy') or "No blueprint. Default to a standard scalable-system probe."
    whiteboard_snapshot = state.get('whiteboard_snapshot') or "(whiteboard empty)"
    target_company_data = state.get('target_company_data') or {}
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
        "You are the System Design Interviewer Agent for Mock.ai. "
        f"Persona: {interviewer_personality}. "
        "Turn the Planner's blueprint into the ACTUAL next system-design prompt or follow-up. "
        "Calibrate scale/constraints to the experience level and, where relevant, to known "
        "engineering patterns of the target company.\n\n"
        "--- RULES ---\n"
        "1. Output ONLY what you'd say out loud — no markdown, no diagrams in text.\n"
        "2. Reference the candidate's whiteboard sketch when pushing on a specific component "
        "(e.g. 'you've drawn a single Postgres instance here — what happens at 10x write volume?').\n"
        "3. One open-ended question or pointed follow-up per turn, 2-4 sentences."
    )

    user_prompt = f"""
    === STRATEGIC BLUEPRINT (from Planner) ===
    {active_strategy}

    === CANDIDATE PROFILE ===
    - Position: {job_title} ({experience_level})
    - Target Company: {target_company}
    - Target Company Engineering Context: {json.dumps(target_company_data) if target_company_data else "none scraped"}

    === CURRENT ROUND CONFIG ===
    {json.dumps(current_round_config)}

    === RECENT TRANSCRIPT ===
    {transcript_str}

    === CURRENT WHITEBOARD STATE ===
    {whiteboard_snapshot}

    {"Pose the OPENING system design prompt now." if is_opening_turn else "React to the candidate's latest design/whiteboard update and push on a specific weak point."}
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
        logger.info("[System Design Agent] Generated next design-round turn.")
    except Exception as e:
        logger.error(f"[System Design Agent Error] Generation failed: {e}")
        question_text = {}

    new_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": question_text,
        "round": "system_design",
        "timestamp": datetime.now(UTC).isoformat()
    }

    return {
        "pending_question": question_text,
        "active_round_node": "system_design",
        "round_turn_count": round_turn_count + 1,
        "messages": [new_message]
    }