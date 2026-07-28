import uuid
from datetime import datetime, UTC
from typing import Annotated, List, Optional, Literal, Dict, Any
from typing_extensions import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from backend.db.models import User, InterviewSession, ConversationalMessages, UserAnalyticsLedger

def merge_messages(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not left:
        return right if right else []
    if not right:
        return left
    return left + right


class InterviewState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    mode: Literal["interview","tutor"]

    job_title: str
    experience_level: str
    tech_stack: List[str]
    target_company: Optional[str]
    difficulty: str
    voice_model: str
    interviewer_personality: str
    preferred_language: str

    code_in_editor: Optional[str]
    whiteboard_snapshot: Optional[str]

    #add_messages function is designed specifically to merge lists of LangChain's native BaseMessage objects
    messages: Annotated[List[Dict[str, Any]], merge_messages]  #Can it be baseMessage with annotated? We are using lightweight, custom reducer function

    current_round_index: int #0 for tutor mode because tutor mode will not have any interview rounds
    rounds_blueprint: Dict[str, Any] #desription on how each rounds process should be taken

    #Never on every conversation between AI-candidate, score will be evaluated over an entire session (means on list of conversation messages accumulated in one interview)
    overall_score: Optional[str]
    performance_overview: Optional[str]
    additional_document: Optional[str]

    #Fields created by nodes during the graph workflow
    candidate_profile: Optional[Dict[str, Any]]  
    target_company_data: Optional[Dict[str, Any]]
    active_round_node: Optional[str]        
    round_turn_count: int                   
    round_awaiting_followup: bool           # set by interviewer_node/swarm_node to request a self-loop
    pending_question: Optional[str]  # candidate-facing text ONLY — never put hidden test cases or internal-only data here, it's the field most likely to get echoed straight to a frontend
    active_oa_payload: Optional[Dict[str, Any]]  # full OA problem (incl. hidden_test_cases) for the code-execution sandbox; NOT candidate-facing, keep separate from pending_question/messages
    code_submission: Optional[str]  
    execution_result: Optional[Dict[str, Any]]  
    last_guardrail_flag: Optional[str] 
    round_scores: Annotated[List[Dict[str, Any]], merge_messages] 
    active_strategy: Optional[str]

    # Guardrail / memory bookkeeping (added for guardrail + durable memory wiring) 
    guardrail_strike_count: int              # cumulative warn/redirect strikes this session
    session_terminated_early: Optional[str]  # set to the triggering flag once terminated, else None
    persisted_message_count: int             # high-water mark of `messages` already flushed to Postgres
    

def _append(existing: list, new: list) -> list:
    return (existing or []) + (new or [])


class TutorSystemDesignState(TypedDict, total=False):
    session_id: str
    user_id: Optional[str]

    system_design_question: Optional[str]
    messages: Annotated[list[dict], _append]
    user_action: Optional[str] 
    user_question: Optional[str]
    whiteboard_image: Optional[str]
    whiteboard_json: Optional[dict]
    validation_feedback: Optional[str]
    hints:Optional[str]
