import json
import logging
from datetime import datetime, UTC
from typing import Dict, Any, List
from groq import AsyncGroq
from sqlalchemy.future import select

from backend.agents.graph.state import InterviewState
from backend.db.repository import LedgerRepository
from backend.db.models import InterviewSession
from backend.core.security import get_settings
from backend.db.session import get_db

settings = get_settings()
groq_client = AsyncGroq(api_key=settings.groq_api_key)
logger = logging.getLogger("mockai-adaptive-graph")

MAX_LEDGER_TAGS = 20


def _full_transcript(messages: List[Dict[str, Any]]) -> str:
    return "\n".join(
        f"[{m.get('round', 'n/a')}] {m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in messages
    ) or "(no conversation recorded)"


async def feedback_agent_node(state: InterviewState) -> Dict[str, Any]:
    session_id = state["session_id"]
    user_id = state["user_id"]
    messages = state.get("messages", [])
    round_scores = state.get("round_scores", [])
    job_title = state["job_title"]
    experience_level = state["experience_level"]

    transcript_str = _full_transcript(messages)
    round_scores_str = json.dumps(round_scores, indent=2) if round_scores else "No per-round scores recorded."

    system_prompt = (
        "You are the Final Feedback Agent for Mock.ai. You receive the complete transcript and "
        "per-round evaluator scores for one full interview session and must produce a session-level "
        "synthesis — not a re-evaluation of individual turns, but a holistic read on the candidate.\n\n"
        "--- OUTPUT CONTRACT ---\n"
        "Respond with STRICT JSON only, no markdown fences, no commentary:\n"
        "{\n"
        '  "overall_score": int (0-100, weighted holistic judgment, not just an average of round scores),\n'
        '  "performance_overview": string (3-5 sentence narrative summary for this specific session),\n'
        '  "strengths": [string] (3-6 recurring, session-spanning strengths),\n'
        '  "weaknesses": [string] (3-6 recurring, session-spanning weaknesses),\n'
        '  "behavioral_notes": string (1-3 sentences on communication/collaboration style specifically)\n'
        "}"
    )

    early_termination_reason = state.get("session_terminated_early")

    user_prompt = f"""
    === CANDIDATE PROFILE ===
    - Position: {job_title} ({experience_level})

    === PER-ROUND EVALUATOR SCORES ===
    {round_scores_str}

    === EARLY TERMINATION FLAG ===
    {early_termination_reason or "Session completed normally — no early termination."}

    === FULL SESSION TRANSCRIPT ===
    {transcript_str}

    Synthesize the final session-level feedback now. If the session was
    terminated early, factor that into both the score and the narrative —
    do not score it as if all rounds were completed.
    """

    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        result = json.loads(completion.choices[0].message.content)
        logger.info(
            f"[Feedback Agent] Session {session_id} synthesized, "
            f"overall_score={result.get('overall_score')}."
        )
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[Feedback Agent Error] Synthesis failed: {e}")
        result = {}

    if early_termination_reason:
        result["overall_score"] = min(result.get("overall_score", 0), 20)
        forced_weaknesses = set(result.get("weaknesses", []))
        forced_weaknesses.add(
            f"Session ended early due to a policy violation ({early_termination_reason})."
        )
        result["weaknesses"] = list(forced_weaknesses)

    overall_score = result.get("overall_score", 50)
    performance_overview = result.get("performance_overview", "")
    new_strengths = result.get("strengths", [])
    new_weaknesses = result.get("weaknesses", [])
    behavioral_notes = result.get("behavioral_notes", "")

    await _persist_final_evaluation(
        session_id=session_id,
        user_id=user_id,
        overall_score=overall_score,
        performance_overview=performance_overview,
        new_strengths=new_strengths,
        new_weaknesses=new_weaknesses,
        behavioral_notes=behavioral_notes,
    )

    return {
        "overall_score": str(overall_score),
        "performance_overview": performance_overview,
        "active_round_node": None,
        "pending_question": None,
        "active_oa_payload": None,
    }


async def _persist_final_evaluation(
    session_id,
    user_id,
    overall_score: int,
    performance_overview: str,
    new_strengths: List[str],
    new_weaknesses: List[str],
    behavioral_notes: str,
) -> None:
    async for db_session in get_db():
        if not db_session:
            logger.error("[Feedback Agent] No DB session available — final results NOT persisted.")
            return
        try:
            result = await db_session.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            interview_session = result.scalars().first()

            if interview_session:
                interview_session.status = "completed"
                interview_session.overall_score = overall_score
                interview_session.performance_overview = performance_overview
                interview_session.completed_at = datetime.now(UTC)
                logger.info(
                    f"[Feedback Agent] Marked session {session_id} as completed "
                    f"with score {overall_score}."
                )
            else:
                logger.warning(
                    f"[Feedback Agent] InterviewSession {session_id} not found in DB — "
                    "score will not be persisted to the session row."
                )

            ledger_repo = LedgerRepository(db_session)
            existing_ledger = await ledger_repo.get_historical_performance(user_id)

            if existing_ledger:
                merged_strengths = _dedupe_and_cap(
                    list(existing_ledger.strengths or []) + new_strengths
                )
                merged_weaknesses = _dedupe_and_cap(
                    list(existing_ledger.weaknesses or []) + new_weaknesses
                )
                new_avg = round(
                    ((existing_ledger.historical_average_score or 0) + overall_score) / 2
                )
                merged_notes = (
                    f"{existing_ledger.behavioral_notes or ''} | Latest: {behavioral_notes}"
                ).strip(" |")
            else:
                merged_strengths = _dedupe_and_cap(new_strengths)
                merged_weaknesses = _dedupe_and_cap(new_weaknesses)
                new_avg = overall_score
                merged_notes = behavioral_notes

            await ledger_repo.upsert_ledger(
                user_id=user_id,
                strengths=merged_strengths,
                weaknesses=merged_weaknesses,
                historical_average_score=new_avg,
                behavioral_notes=merged_notes,
            )

            await db_session.commit()
            logger.info(
                f"[Feedback Agent] Persisted final results + ledger update for user {user_id}."
            )

        except Exception as e:
            await db_session.rollback()
            logger.error(f"[Feedback Agent] Persistence failed: {e}", exc_info=True)

        break


def _dedupe_and_cap(tags: List[str], cap: int = MAX_LEDGER_TAGS) -> List[str]:
    seen = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    return seen[-cap:]