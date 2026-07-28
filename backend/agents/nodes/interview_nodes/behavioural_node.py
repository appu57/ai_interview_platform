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


async def behavioral_agent_node(state: InterviewState) -> Dict[str, Any]:
    job_title = state['job_title']
    experience_level = state['experience_level']
    target_company = state.get('target_company') or "the target company"
    interviewer_personality = state['interviewer_personality']
    active_strategy = state.get('active_strategy') or "No blueprint. Default to standard leadership/conflict/ownership probes."
    candidate_profile = state.get('candidate_profile') or {}
    additional_doc = state.get('additional_document') or "No resume/document provided."
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
        "You are the Behavioral Interviewer Agent for Mock.ai. "
        f"Persona: {interviewer_personality}. "
        "Turn the Planner's blueprint into the ACTUAL next behavioral question or probing "
        "follow-up. Favor STAR-eliciting prompts (Situation/Task/Action/Result) calibrated to "
        "seniority — push individual contributors on ownership/conflict, push seniors on "
        "leadership/ambiguity/cross-team influence.\n\n"
        "--- RULES ---\n"
        "1. Output ONLY what you'd say out loud — 1-3 sentences, no markdown.\n"
        "2. If the candidate's last answer was vague or lacked a measurable Result, ask a "
        "tightening follow-up instead of moving to a new topic.\n"
        "3. Never repeat a question topic already covered in the transcript."
    )

    user_prompt = f"""
    === STRATEGIC BLUEPRINT (from Planner) ===
    {active_strategy}

    === CANDIDATE PROFILE ===
    - Position: {job_title} ({experience_level})
    - Target Company: {target_company}
    - Parsed Resume/Profile Signals: {json.dumps(candidate_profile) if candidate_profile else "none parsed"}
    - Additional Candidate Document: {additional_doc}

    === CURRENT ROUND CONFIG ===
    {json.dumps(current_round_config)}

    === RECENT TRANSCRIPT ===
    {transcript_str}

    {"Ask the OPENING behavioral question now." if is_opening_turn else "Either tighten a follow-up on the candidate's last answer, or move to the next behavioral theme."}
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6,
            max_tokens=512
        )
        question_text = completion.choices[0].message.content.strip()
        logger.info("[Behavioral Agent] Generated next behavioral-round turn.")
    except Exception as e:
        logger.error(f"[Behavioral Agent Error] Generation failed: {e}")
        question_text = {}

    new_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": question_text,
        "round": "behavioral",
        "timestamp": datetime.now(UTC).isoformat()
    }

    return {
        "pending_question": question_text,
        "active_round_node": "behavioral",
        "round_turn_count": round_turn_count + 1,
        "messages": [new_message]
    }