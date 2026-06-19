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
    

