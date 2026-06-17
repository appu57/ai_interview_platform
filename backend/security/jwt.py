import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import jwt
from backend.core.security import get_settings
settings = get_settings()

jwt_secret: str | None = None
def get_jwt_secret()->str:
    global jwt_secret
    secret = settings.jwt_secret_key
    if not secret:
        if jwt_secret is None:
            jwt_secret = secrets.token_hex(32)
            import logging

            logging.getLogger(__name__).warning(
                "JWT_SECRET_KEY not set — using generated secret. "
                "Tokens will not persist across restarts."
            )
        secret = jwt_secret
    return secret




def create_access_token(data:dict, roles:Optional[list[str]]):
    minutes = settings.access_token_expire_minutes or 15
    expires_delta = timedelta(minutes= minutes)

    now = datetime.now(UTC) #datetime.utcnow()
    expires_in = now + expires_delta
    to_encode = data.copy()
    to_encode.update({
        "sub": data.get("subject"),
        "exp": expires_in,
        "iat": now,
        "type": "access",
    })
    encoded_jwt = jwt.encode(
        to_encode,
        get_jwt_secret(),
        algorithm = "HS256"
    )
    return encoded_jwt

def generate_refresh_token():
    return secrets.token_urlsafe(32)

def generate_password_reset_token():
    return secrets.token_urlsafe(32)  #because shouldnt persist across restarts

def create_csrf_token_hash(csrf_token: str) -> str:
    """
        SHA256 hash of the token
    """
    import hashlib

    return hashlib.sha256(csrf_token.encode()).hexdigest()

def get_email(access_token)->str:
    payload = jwt.decode(access_token, get_jwt_secret(), algorithms=["HS256"])
    email = payload.get("sub") #same while saving access token
    return email