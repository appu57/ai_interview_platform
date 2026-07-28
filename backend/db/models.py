from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship
from sqlalchemy import ARRAY, String, Boolean, UUID
from typing import List, Optional, AsyncGenerator
import uuid
from backend.db.session import Base
from datetime import UTC, datetime
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable= False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    context_caches = relationship("UserContextCache", back_populates="user", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")
    analytics_ledger = relationship("UserAnalyticsLedger", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserContextCache(Base):
    __tablename__ = "user_context_caches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    context_type: Mapped[str] = mapped_column(String(30), nullable=False) # 'resume' or 'github_repo'
    identifier: Mapped[str] = mapped_column(String(512), nullable=False)  # File name or GitHub repo URL
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # SHA-256 hash of contents
    
    parsed_text: Mapped[str] = mapped_column(Text, nullable=False) # Parsed raw text or scraped repository context markdown
    structured_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Extracted skills, repos, structured JSON map

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(UTC), 
        onupdate=lambda: datetime.now(UTC)
    )
    user = relationship("User", back_populates="context_caches")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    job_title: Mapped[str] = mapped_column(String(100), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False)
    tech_stack: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    target_company: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    voice_model: Mapped[str] = mapped_column(String(50), nullable=False)
    interviewer_personality: Mapped[str] = mapped_column(String(50), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active") # active, completed, abandoned
    # current_round_index: Mapped[int] = mapped_column(Integer, default=0)
    rounds_blueprint: Mapped[dict] = mapped_column(JSON, nullable=False) # Timeline round structure snapshot  
    overall_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    performance_overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(UTC), 
        onupdate=lambda: datetime.now(UTC)
    )

    user = relationship("User", back_populates="interview_sessions")
    messages = relationship("ConversationalMessages", back_populates="session", cascade="all, delete-orphan")

class ConversationalMessages(Base):
    __tablename__ = "conversational_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), 
        nullable=False
    )
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False) # 'interviewer', 'candidate'
    message_text: Mapped[str] = mapped_column(Text, nullable=False) # Conversational text or code block submitted
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True) # Speech reference (if voice enabled)
    ai_feedback_correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Live corrections from AI agent for each conversation
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    session = relationship("InterviewSession", back_populates="messages")

class UserAnalyticsLedger(Base):
    __tablename__ = "user_analytics_ledgers"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True,
        nullable=False
    )
    strengths: Mapped[List[str]] = mapped_column(
        ARRAY(String), 
        default=list, 
        nullable=False
    ) 
    weaknesses: Mapped[List[str]] = mapped_column(
        ARRAY(String), 
        default=list, 
        nullable=False
    )     
    historical_average_score: Mapped[float] = mapped_column(Integer, default=0) # Base running score (scale 0-100)
    behavioral_notes: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True
    )  #AI evaluation on communication and collaboration and style with interviewer
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(UTC), 
        onupdate=lambda: datetime.now(UTC)
    )
    user = relationship("User", back_populates="analytics_ledger")