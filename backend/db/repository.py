import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User

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
            id=str(uuid.uuid4()),
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
