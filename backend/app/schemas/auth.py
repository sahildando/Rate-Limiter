"""Authentication request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    """User registration payload."""

    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["securepassword123"])


class LoginRequest(BaseModel):
    """User login payload."""

    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=1, max_length=128, examples=["securepassword123"])


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Authenticated user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
