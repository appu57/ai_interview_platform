from datetime import UTC, datetime
import logging
import io
import json
from typing import Optional
import uuid
import hashlib
import pypdf
from fastapi import APIRouter, Request, Response, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.api.deps import get_interview_graph
from backend.core.security import get_settings
from backend.models.pydantic_models import UserResponse, TokenResponse, UserSignUp, UserLogin, RespondRequest
from backend.db.repository import UserRepository, ConversationRepository
from backend.db.models import InterviewSession, User, UserContextCache
from backend.db.session import get_db
from backend.agents.graph.state import InterviewState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user_preferences", tags=["User preferences"])
interview_router = APIRouter(prefix="/api/interview", tags=["Interview"])


@router.post(
    "/save_preferences",
    status_code=status.HTTP_201_CREATED,
    summary="Save user preferences",
    description="Accepts full user interview parameters and resume attachments, writes configurations to database, and triggers LangGraph's Planner + Scraper nodes.",
)
async def save_user_preferences(
    request: Request,
    response: Response,
    preferences: str = Form(...),
    resume: Optional[UploadFile] = File(None),
    session: AsyncSession = Depends(get_db),
    interview_graph = Depends(get_interview_graph),
):
    try:
        prefs = json.loads(preferences)
        user_uuid = prefs.get("userId")
        if not user_uuid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No authenticated user found in PostgreSQL. Please initialize db tables."
            )
        session_uuid = uuid.uuid4()

        job_title = prefs.get("jobTitle", "Senior Full Stack Engineer")
        experience_level = prefs.get("experienceLevel", "Senior")
        target_company = (prefs.get("targetCompany") or "").strip() or None
        tech_stack = prefs.get("techStack", ["React", "Python", "FastAPI"])
        difficulty = prefs.get("difficulty", "Rigorous (FAANG Style)")
        voice_model = prefs.get("voiceModel", "Kore")
        interviewer_personality = prefs.get("interviewerPersonality", "Balanced")
        selected_language = prefs.get("selectedLanguage", "Python")

        parsed_resume_text = ""
        if resume:
            parsed_resume_text = await extract_resume_text(resume)
            content_hash = hashlib.sha256(parsed_resume_text.encode("utf-8")).hexdigest()

            cache_check = await session.execute(
                select(UserContextCache).where(
                    UserContextCache.user_id == user_uuid,
                    UserContextCache.content_hash == content_hash
                )
            )
            existing_cache = cache_check.scalars().first()

            if not existing_cache:
                logger.info(f"Caching new resume profile hash: {content_hash[:8]}")
                new_cache = UserContextCache(
                    id=uuid.uuid4(),
                    user_id=user_uuid,
                    context_type="resume",
                    identifier=resume.filename or "resume.pdf",
                    content_hash=content_hash,
                    parsed_text=parsed_resume_text,
                    structured_metadata={"parsed_at": datetime.now(UTC).isoformat()}
                )
                session.add(new_cache)
                await session.flush()

        def _duration_to_max_turns(duration_minutes) -> int:
            try:

                digits = "".join(ch for ch in str(duration_minutes) if ch.isdigit())
                if not digits:
                    return 4
                return max(2, round(int(digits) / 3))
            except (TypeError, ValueError):
                return 4

        rounds_blueprint = {
            "rounds": [
                {
                    "id": r.get("id"),
                    "type": r.get("type"),
                    "name": r.get("name"),
                    "duration": r.get("duration"),
                    "max_turns": _duration_to_max_turns(r.get("duration")),
                    "desc": r.get("desc"),
                }
                for r in prefs.get("customRounds", [])
            ]
        }

  
        initial_graph_state = {
            "session_id": session_uuid,
            "user_id": user_uuid,
            "mode": "interview",
            "job_title": job_title,
            "experience_level": experience_level,
            "tech_stack": tech_stack,
            "target_company": target_company,
            "difficulty": difficulty,
            "voice_model": voice_model,
            "interviewer_personality": interviewer_personality,
            "preferred_language": selected_language,
            "code_in_editor": "",
            "whiteboard_snapshot": None,
            "messages": [],
            "current_round_index": 0,
            "rounds_blueprint": rounds_blueprint,
            "overall_score": None,
            "performance_overview": None,
            "additional_document": parsed_resume_text,
            "candidate_profile": None,
            "target_company_data": None,
            "active_round_node": None,
            "round_turn_count": 0,
            "round_awaiting_followup": False,
            "pending_question": None,
            "active_oa_payload": None,
            "code_submission": None,
            "execution_result": None,
            "last_guardrail_flag": None,
            "round_scores": [],
            "active_strategy": None,
            "guardrail_strike_count": 0,
            "session_terminated_early": None,
            "persisted_message_count": 0,
        }

        graph_config = {"configurable": {"thread_id": str(session_uuid)}}
        
        logger.info(f"Invoking compiled LangGraph for Session: {session_uuid}...")
        graph_output = await interview_graph.ainvoke(initial_graph_state, config=graph_config)

        new_session = InterviewSession(
            id=session_uuid,
            user_id=user_uuid,
            job_title=job_title,
            experience_level=experience_level,
            tech_stack=tech_stack,
            target_company=target_company,
            difficulty=difficulty,
            voice_model=voice_model,
            interviewer_personality=interviewer_personality,
            preferred_language=selected_language,
            status="active",
            rounds_blueprint=graph_output.get("rounds_blueprint", rounds_blueprint),
        )
        session.add(new_session)

        await session.commit()
        logger.info(f"Successfully committed InterviewSession {session_uuid} to PostgreSQL database!")


        messages = graph_output.get("messages") or []
        if not rounds_blueprint["rounds"]:
            return {
                "status": "success",
                "message": "No rounds configured — session completed immediately with no interview content.",
                "session_id": str(session_uuid),
                "rounds_blueprint": new_session.rounds_blueprint,
                "overall_score": graph_output.get("overall_score"),
                "performance_overview": graph_output.get("performance_overview"),
            }

        first_agent_question = messages[-1].get("content") if messages else None

        return {
            "status": "success",
            "message": "Preferences saved and Multi-Agent Sandbox configured successfully",
            "session_id": str(session_uuid),
            "rounds_blueprint": new_session.rounds_blueprint,
            "first_agent_question": first_agent_question,
            "oa_problem": _candidate_safe_oa_payload(graph_output),
            "round_turn_count": graph_output.get("round_turn_count", 0),
        }

    except json.JSONDecodeError:
        logger.error("JSON Parsing failed on preferences Form payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode JSON from preferences payload."
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to initialize interview preference session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate and cache interview setup: {str(e)}"
        )


def _candidate_safe_oa_payload(graph_output: dict) -> Optional[dict]:
    payload = graph_output.get("active_oa_payload")
    if not payload:
        return None
    return {k: v for k, v in payload.items() if k != "hidden_test_cases"}


@interview_router.post(
    "/{session_id}/respond",
    status_code=status.HTTP_200_OK,
    summary="Submit a candidate answer and resume the interview graph",
    description=(
        "Feeds the candidate's answer (voice-transcribed or typed) into the LangGraph "
        "checkpoint paused after the active round node, resumes execution, and returns "
        "either the next question/follow-up or the final session feedback if the "
        "interview just completed."
    ),
)
async def respond_to_question(
    session_id: uuid.UUID,
    body: RespondRequest,
    session: AsyncSession = Depends(get_db),
    interview_graph = Depends(get_interview_graph),
):
    session_query = await session.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    interview_session = session_query.scalars().first()

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No interview session found for id={session_id}.",
        )
    if interview_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session {session_id} is '{interview_session.status}', not active — nothing to resume.",
        )

    graph_config = {"configurable": {"thread_id": str(session_id)}}


    current_snapshot = await interview_graph.aget_state(graph_config)
    if current_snapshot is None or not current_snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No paused LangGraph checkpoint found for session {session_id}. "
                   "The interview may not have been started via /save_preferences.",
        )

    candidate_message = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": body.content,
        "round": current_snapshot.values.get("active_round_node"),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    previous_turn_count = current_snapshot.values.get("round_turn_count", 0) or 0

    state_update = {
        "messages": [candidate_message],
    }
    if body.code_in_editor is not None:
        state_update["code_in_editor"] = body.code_in_editor
    if body.whiteboard_snapshot is not None:
        state_update["whiteboard_snapshot"] = body.whiteboard_snapshot
    if body.code_submission is not None:
        state_update["code_submission"] = body.code_submission
    if body.execution_result is not None:
        state_update["execution_result"] = body.execution_result

    try:
        await interview_graph.aupdate_state(graph_config, state_update)

        logger.info(
            f"Resuming LangGraph for session {session_id} "
            f"(round_turn_count was {previous_turn_count} before this turn; "
            f"the round node decides whether to increment it)..."
        )
        graph_output = await interview_graph.ainvoke(None, config=graph_config)
    except Exception as e:
        logger.error(f"Failed to resume interview graph for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process candidate response: {str(e)}",
        )

    rounds_list = graph_output.get("rounds_blueprint", {}).get("rounds", [])
    current_round_index = graph_output.get("current_round_index", 0)
    interview_finished = current_round_index >= len(rounds_list)

    if interview_finished:
        interview_session.status = "completed"
        await session.commit()
        logger.info(f"Session {session_id} completed — final feedback generated.")
        return {
            "status": "completed",
            "session_id": str(session_id),
            "overall_score": graph_output.get("overall_score"),
            "performance_overview": graph_output.get("performance_overview"),
        }

    messages = graph_output.get("messages") or []
    next_question = messages[-1].get("content") if messages else None

    previous_round_index = current_snapshot.values.get("current_round_index", 0)
    round_advanced = current_round_index > previous_round_index

    return {
        "status": "success",
        "session_id": str(session_id),
        "current_round_index": current_round_index,
        "active_round_node": graph_output.get("active_round_node"),
        "next_agent_question": next_question,
        "oa_problem": _candidate_safe_oa_payload(graph_output),
        "round_turn_count": graph_output.get("round_turn_count", 0),
        "round_advanced": round_advanced,
    }

async def extract_resume_text(resume: UploadFile) -> str:
    try:
        content = await resume.read()
        # Reset stream position so it can be re-read if needed downstream
        await resume.seek(0)
        
        if not resume.filename:
            return "[Unparsed File Attachment: Missing Filename]"

        # --- 1. Handle Plain Text Fallback ---
        if resume.filename.endswith(".txt"):
            return content.decode("utf-8")
        
        # --- 2. Production PDF Stream Parsing Line ---
        if resume.filename.endswith(".pdf"):
            pdf_text_buffer = []
            
            # Read bytes straight out of system RAM using an in-memory stream
            with io.BytesIO(content) as pdf_stream:
                reader = pypdf.PdfReader(pdf_stream)
                
                # Loop sequentially through the binary compiled pages
                for page_num, page in enumerate(reader.pages):
                    extracted_text = page.extract_text()
                    
                    if extracted_text:
                        # Normalize formatting spacing anomalies
                        cleaned_page_text = "\n".join(
                            line.strip() for line in extracted_text.splitlines() if line.strip()
                        )
                        if cleaned_page_text:
                            pdf_text_buffer.append(cleaned_page_text)
                    else:
                        logger.info(f"Page {page_num} in {resume.filename} returned empty string (likely scanned image or layout block).")
            
            if not pdf_text_buffer:
                return f"[Empty or Unextractable PDF: {resume.filename} | Vector rendering or OCR required]"
                
            return "\n\n--- Page Break ---\n\n".join(pdf_text_buffer)
            
        return f"[Unsupported Binary Dossier Format: {resume.filename} | Size: {len(content)} bytes]"
        
        
    except Exception as e:
        logger.warning(f"Failed to extract text from file stream for {resume.filename}: {e}", exc_info=True)
        return f"[Unparsed File Attachment: {resume.filename}]"