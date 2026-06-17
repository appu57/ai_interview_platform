from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()
from pydantic import BaseModel, Field
import os


class SecretKeys(BaseModel):
    groq_api_key: str = Field(
        default_factory=lambda: os.getenv("GROQ_API_KEY"),
        description="GROQ API key for interviewer mode"
    )

    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY"),
        description="Gemini API key for interviewer mode"
    )

    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL"),
        description="Database connection URL"
    )

    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY"),
        description="JWT signing secret key"
    )

    jwt_refresh_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_REFRESH_SECRET_KEY"),
        description="JWT refresh token signing secret key"
    )

    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )

    access_token_expire_minutes: int = Field(
        default=15,
        description="Access token expiry time in minutes"
    )

    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiry time in days"
    )

    max_request_size_bytes: int = Field(
        default=2 * 1024 * 1024,
        description="Maximum request size allowed in bytes (2 MB)"
    )

# Global settings instance
settings = SecretKeys()


def get_settings() -> SecretKeys:
    """
    Get application settings.
    """
    return settings