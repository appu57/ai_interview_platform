from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import get_settings
from backend.models.pydantic_models import  UserResponse, TokenResponse, UserSignUp, UserLogin
from backend.db.repository import UserRepository
from backend.db.models import User
from backend.db.session import get_db
from backend.security.jwt import create_access_token, generate_refresh_token, get_email, create_csrf_token_hash

import bcrypt

_BCRYPT_ROUNDS=12
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/signup", response_model= TokenResponse, status_code= status.HTTP_201_CREATED,
             summary="Register a new user", description="Create a new user account with email and password",
             dependencies=[])
async def register(body: UserSignUp, request:Request, response:Response,
                   session: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(session)
    existing_user = await user_repo.get_by_email(body.email)
    print(f"User body: {body}")
    if existing_user:
        raise HTTPException(
            status_code= status.HTTP_409_CONFLICT,
            detail="Email already registered", 
        )
    hashed_password = hash_password(body.password)
    user = await user_repo.create(
        email=body.email,
        hashed_password=hashed_password,
        full_name=body.full_name,
    )
    token_data = {"subject": user.email, "uid": str(user.id)}
    access_token = create_access_token(
        data=token_data,
        roles=[user.role],
    )
    refresh_token = generate_refresh_token()
    csrf_token = create_csrf_token_hash(str(uuid.uuid4()))
    _set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in= 15 * 60,
        user_id= str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active
    )

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: Optional[str] = None,
) -> None:
    """Set authentication cookies on response."""
    settings = get_settings()

    access_max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        path="/",
        httponly=True,
        samesite="strict",
    )
    refresh_max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        samesite="strict",
    )

    if csrf_token:
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            max_age=access_max_age,
            path="/",
            httponly=False, 
            samesite="strict",
        )


@router.post(
    "/login", 
    response_model=TokenResponse, 
    status_code=status.HTTP_200_OK,
    summary="Authenticate user", 
    description="Verify user credentials and issue secure session tokens"
)
async def login(
    body: UserLogin, 
    response: Response, 
    session: AsyncSession = Depends(get_db)
):

    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(body.email)
    
    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise invalid_credentials_exception

    # Verify plain password string against stored DB bcrypt string
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
        
    if needs_rehash(user.hashed_password):
        new_hash = hash_password(body.password)
        await user_repo.set_password(user.id, new_hash)

    await user_repo.update_last_login(user)
    token_data = {"subject": user.email, "uid": str(user.id)}
    access_token = create_access_token(
        data=token_data,
        roles=[user.role],
    )
    refresh_token = generate_refresh_token()
    csrf_token = create_csrf_token_hash(str(uuid.uuid4()))
    _set_auth_cookies(response, access_token, refresh_token, csrf_token)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60,
        user_id= str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active
    )

@router.post(
    "/logout", 
    status_code=status.HTTP_200_OK,
    summary="Log out user", 
    description="Clear authentication session cookies"
)
async def logout(response: Response):
    _clear_auth_cookies(response)
    return {"message": "Successfully logged out"}

def _clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    response.delete_cookie(key="csrf_token", path="/")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be rehashed (cost factor changed)."""
    try:
        existing_rounds = int(hashed_password.split("$")[2])
        return existing_rounds != _BCRYPT_ROUNDS
    except (IndexError, ValueError):
        return True

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

@router.get(
    "/me", 
    status_code=status.HTTP_200_OK,
    tags=["Authentication"]
)
async def get_current_user_profile(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active session token missing."
        )

    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email(get_email(access_token)) # we get email using access_token
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with this session no longer exists."
            )
            
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": getattr(user, "role", "user")
        }
        
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or credentials are corrupt."
        )