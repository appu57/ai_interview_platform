import json
import os
import logging
import uuid
from typing import Dict, Any, Literal, List
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from backend.db.repository import SessionRepository, ConversationRepository, LedgerRepository
from backend.agents.graph.state import InterviewState
from backend.core.security import get_settings
from backend.db.session import get_db
from backend.db.models import UserAnalyticsLedger

settings = get_settings()
GROQ_API_KEY = settings.groq_api_key
groq_client = AsyncGroq(api_key=GROQ_API_KEY)
logger = logging.getLogger("mockai-adaptive-graph")


async def get_user_previous_performance(userId):
    async for db_session in get_db():
        if not db_session:
            return None
        try:
            ledger_repo = LedgerRepository(db_session)
            historical_performances: UserAnalyticsLedger = await ledger_repo.get_historical_performance(userId)
            
            historical_performance_notes = ""
            if historical_performances:
                behavior = historical_performances.behavioral_notes or "No behavioral notes recorded."
                weaknesses = ", ".join(historical_performances.weaknesses) if historical_performances.weaknesses else "No flagged weaknesses."
                strengths = ", ".join(historical_performances.strengths) if historical_performances.strengths else "No recorded strengths."
                score = historical_performances.historical_average_score or 0
                
                historical_performance_notes = (
                    f"Candidate historical performances behavior: {behavior}. "
                    f"Historical weaknesses: {weaknesses}. "
                    f"Historical strengths: {strengths}. "
                    f"Historical average score: {score}."
                )
            
            return {"performance_overview": historical_performance_notes if historical_performance_notes else None}
        except Exception as e:
            logger.error(f"Error fetching historical performance: {e}")
            return None

async def planner_agent_node(state:InterviewState)-> Dict[str, Any]:
    rounds_desc = state['rounds_blueprint']
    additional_doc = state['additional_document']
    job_title= state['job_title']
    experience_level= state['experience_level']
    tech_stack =  state['tech_stack']
    target_company= state['target_company']
    difficulty= state['difficulty']
    voice_model= state['voice_model']
    interviewer_personality= state['interviewer_personality']
    preferred_language= state['preferred_language']

    historical_performance_notes =await get_user_previous_performance(state['user_id'])
    historical_notes = historical_performance_notes.get("performance_overview") if historical_performance_notes else "No historical records."

    rounds_list = rounds_desc.get("rounds", [])

    all_round_scores = state.get('round_scores') or []
    just_finished_round = all_round_scores[-1] if all_round_scores else None

    loop_feedback_str = "None — this is the first round, no prior performance to react to."
    targeted_weakness_str = "N/A (first round)."
    if just_finished_round:
        logger.info("Customizing next round strategy based on the just-finished round's weaknesses")
        loop_feedback_str = json.dumps(all_round_scores, indent=2)
        flagged_weaknesses = just_finished_round.get("weaknesses") or ["(none flagged, but score was still weak)"]
        targeted_weakness_str = (
            f"Round '{just_finished_round.get('round')}' (index {just_finished_round.get('round_index')}) "
            f"scored {just_finished_round.get('score')}/100 — WEAK. "
            f"Flagged weaknesses: {', '.join(flagged_weaknesses)}. "
            f"The NEXT round's strategy MUST specifically target these weaknesses, scoped to the "
            f"candidate's selected tech stack ({', '.join(tech_stack)}) — not generic difficulty escalation."
        )

    system_prompt = (
        "You are the Core Strategic Planner Agent for Mock.ai. "
        "Your absolute directive is to curate a highly customized execution strategy for upcoming "
        "interview rounds based on candidate profile data, historical weaknesses, and immediate loopback performance logs.\n\n"
        "--- CRITICAL RULE ---\n"
        "DO NOT write or output any actual interview questions, code, or test cases. "
        "Instead, write a strategic operational blueprint explaining precisely HOW each subsequent node "
        "based on rounds description must function, what specific conceptual patterns they "
        "should target to exploit or patch identified gaps, what level of complexity to enforce, and how they should "
        "design their verification test cases dynamically."
    )
    user_prompt = f"""
    Compile a strategic master plan for the following profile:
    === ROLE PROFILE ===
    - Target Position: {job_title} ({experience_level})
    - Target Company: {target_company}
    - Target Ecosystem Stack: {", ".join(tech_stack)}
    - Difficulty Metric: {difficulty}
    - Environment Core Language: {preferred_language}
    - Persona Constraints: {interviewer_personality}
    - Additional User documents: {additional_doc}

    === PAST HISTORICAL LEDGER SUMMARY (across previous sessions) ===
    {historical_notes}

    === WHY YOU ARE BEING RE-INVOKED RIGHT NOW ===
    {targeted_weakness_str}

    === FULL ROUND-BY-ROUND SCORE HISTORY (THIS SESSION) ===
    {loop_feedback_str}

    === ACTIVE ROUNDS METADATA CONFIGURATION ===
    {json.dumps(rounds_list)}

    === Interviewer TONE ====
    {voice_model}

    Output a comprehensive, step-by-step master plan mapping guidelines for every round.
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1024
        )
        
        generated_strategy = completion.choices[0].message.content
        logger.info("[Planner Agent] Successfully compiled dynamic strategy.")
        return {
            "active_strategy": generated_strategy,
            "current_round_index": state.get("current_round_index", 0)
        }

    except Exception as e:
        logger.error(f"[Planner Agent Error] Strategy compilation failed: {e}")
        return {
            "active_strategy": f"Standard evaluation targeting core {preferred_language} foundations under {difficulty} constraints.",
            "current_round_index": state.get("current_round_index", 0)
        }
