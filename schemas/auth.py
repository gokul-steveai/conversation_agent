from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""

    name: str = Field(..., min_length=2, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")


class UserLoginRequest(BaseModel):
    """Request schema for user login authentication."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Response schema representing an authenticated user."""

    user_id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    """Response schema for authentication operations (login and registration)."""

    success: bool
    token: Optional[str] = None
    user: Optional[UserResponse] = None
    error: Optional[str] = None
