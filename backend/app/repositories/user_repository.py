"""User persistence layer."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    """Data access for users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        result = await self._session.execute(
            select(func.count()).select_from(User).where(User.email == email)
        )
        return (result.scalar_one() or 0) > 0

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        user = User(email=email, password_hash=password_hash, role=role, is_active=True)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
