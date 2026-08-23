"""Authentication business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse, UserResponse


class AuthService:
    """Handles user registration, login, and profile retrieval."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._users = UserRepository(session)
        self._settings = settings

    async def register(self, data: RegisterRequest) -> UserResponse:
        if await self._users.email_exists(data.email):
            raise ConflictError("Email already registered", code="EMAIL_ALREADY_EXISTS")

        user = await self._users.create(
            email=data.email,
            password_hash=hash_password(data.password),
        )
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password", code="INVALID_CREDENTIALS")

        if not user.is_active:
            raise AuthenticationError("User account is inactive", code="INACTIVE_USER")

        token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            settings=self._settings,
        )
        return TokenResponse(access_token=token)

    async def get_profile(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)
