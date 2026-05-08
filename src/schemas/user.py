from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared fields used across user-related schemas."""
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for user registration — accepts a plain password."""
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None


class UserRead(UserBase):
    """Schema returned to clients — never includes the password."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime

class UserPublic(BaseModel):
    """Minimal user info safe to expose publicly (e.g., as business owner)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None
    

class Token(BaseModel):
    """JWT tokens returned after successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT contents — used for validating incoming tokens."""
    sub: str | None = None
    type: str | None = None
