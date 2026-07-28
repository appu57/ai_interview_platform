from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from backend.db.models import User

class UserSignUp(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True

class TokenResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True


class RespondRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Candidate's answer text (transcribed if spoken).")
    code_in_editor: Optional[str] = None
    whiteboard_snapshot: Optional[str] = None
    code_submission: Optional[dict] = None
    execution_result: Optional[dict] = None