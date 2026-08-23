"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        201: {"description": "User created successfully"},
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
async def register(
    data: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Create a new user account."""
    return await auth_service.register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain access token",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials or inactive account"},
        422: {"description": "Validation error"},
    },
)
async def login(
    data: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate with email and password to receive a JWT."""
    return await auth_service.login(data.email, data.password)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    responses={
        200: {"description": "Current user profile"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)
