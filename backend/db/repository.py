import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional, Dict, Any, Literal, List

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User, InterviewSession, ConversationalMessages,UserAnalyticsLedger

class UserRepository:
    def __init__(self, session:AsyncSession):
        self.session = session

    async def create(
        self,
        email: str,
        hashed_password: Optional[str] = None,
        full_name: Optional[str] = None,
        role: str = "user",
    ) -> User:
        """Create a new user."""
        user = User(
            id=uuid.uuid4(),
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    async def update(self, user: User, **kwargs) -> User:
        """Update user fields."""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()

    async def set_verified(self, user: User) -> None:
        """Mark user as verified."""
        user.is_verified = True
        await self.session.flush()

    async def set_password(self, user: User, hashed_password: str) -> None:
        """Set user's password."""
        user.hashed_password = hashed_password
        await self.session.flush()

    async def delete(self, user: User) -> None:
        """Delete a user."""
        await self.session.delete(user)

    async def exists_by_email(self, email: str) -> bool:
        """Check if user exists by email."""
        result = await self.session.execute(
            select(User.id).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none() is not None



class SessionRepository: 
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: uuid.UUID,
        setup_payload: Dict[str,Any],
        mode: Literal["interview", "tutor"],
        rounds_blueprint:Dict[str, Any]
    )-> InterviewSession:

        new_session = InterviewSession(
            id=uuid.uuid4(),
            user_id=user_id,
            job_title=setup_payload.get("job_title", "Software Engineer"),
            experience_level=setup_payload.get("experience_level", "Senior"),
            tech_stack=setup_payload.get("tech_stack", []),
            target_company=setup_payload.get("target_company"),
            difficulty=setup_payload.get("difficulty", "Rigorous (FAANG Style)"),
            voice_model=setup_payload.get("voice_model", "Kore"),
            interviewer_personality=setup_payload.get("interviewer_personality", "Balanced"),
            preferred_language=setup_payload.get("preferred_language", "Python"),
            status="active",
            rounds_blueprint=rounds_blueprint if mode == "interview" else {"tutor_mode": True}
        )
        self.session.add(new_session)
        await self.session.flush()
        return new_session
        

class ConversationRepository: 
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        session_id: uuid.UUID,
        round_index: int,
        role: Literal["interviewer", "candidate"],
        message_text: str,
        audio_path: Optional[str] = None,
        ai_feedback_correction: Optional[str] = None
    )-> ConversationalMessages:
        """Create a new Interview session using inputs sent 
        by langgraph
        rounds_blueprint: How each rounds of an interview is strategised"""

        new_message = ConversationalMessages(
            id=uuid.uuid4(),
            session_id=session_id,
            round_index=round_index,
            role=role,
            message_text=message_text,
            audio_path=audio_path,
            ai_feedback_correction=ai_feedback_correction
        )
        self.session.add(new_message) #after add I am not using commit or rollback because db_initialiser session factory already handles that
        await self.session.flush()
        return new_message
    
    async def bulk_create_messages(
        self,
        session_id: uuid.UUID,
        round_index: int,
        messages: List[Dict[str, Any]],
    ) -> List[ConversationalMessages]:
        
        role_map = {"assistant": "interviewer", "user": "candidate"}
 
        created: List[ConversationalMessages] = []
        for msg in messages:
            mapped_role = role_map.get(msg.get("role"), msg.get("role"))
            new_message = ConversationalMessages(
                id=uuid.uuid4(),
                session_id=session_id,
                round_index=round_index,
                role=mapped_role,
                message_text=msg.get("content", ""),
                audio_path=msg.get("audio_path"),
                ai_feedback_correction=msg.get("correction"),
            )
            self.session.add(new_message)
            created.append(new_message)
 
        await self.session.flush()
        return created

    

class LedgerRepository: 
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        new_strengths: List[str],
        new_weaknesses: List[str],
        session_score:int,
        behavioral_notes:Optional[str]
    )->UserAnalyticsLedger:
        query = select(UserAnalyticsLedger).where(UserAnalyticsLedger.user_id == user_id)
        result = await self.session.execute(query)
        ledger = result.scalar_one_or_none()
        
        if not ledger:
            #If no ledger exists, create a clean initial entry
            ledger = UserAnalyticsLedger(
                id=uuid.uuid4(),
                user_id=user_id,
                strengths=new_strengths,
                weaknesses=new_weaknesses,
                historical_average_score=session_score,
                behavioral_notes=behavioral_notes
            )
            self.session.add(ledger)
        else:
            #Update the existing ledger card dynamically
            # Merge strengths and weaknesses, keeping lists completely unique using set logic
            ledger.strengths = list(set(ledger.strengths + new_strengths))
            ledger.weaknesses = list(set(ledger.weaknesses + new_weaknesses))
            
            ledger.historical_average_score = (ledger.historical_average_score + session_score) / 2.0
            
            if behavioral_notes:
                ledger.behavioral_notes = behavioral_notes
                
            ledger.updated_at = datetime.now(UTC)

        await self.session.flush()
        return ledger
    
    async def close_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        overall_score: int,
        performance_overview: str
    ):
        query = select(InterviewSession).where(InterviewSession.id == session_id)
        result = await self.session.execute(query)
        session_obj = result.scalar_one_or_none()
        
        if session_obj:
            session_obj.status = "completed"
            session_obj.overall_score = overall_score
            session_obj.performance_overview = performance_overview
            session_obj.updated_at = datetime.now(UTC)
            await self.session.flush()
        return session_obj
    
    async def get_historical_performance(self,user_id: uuid.UUID)-> UserAnalyticsLedger:
        result = await self.session.execute(
        select(UserAnalyticsLedger).where(UserAnalyticsLedger.user_id == user_id)
        )
        ledger = result.scalar_one_or_none()
        return ledger

        