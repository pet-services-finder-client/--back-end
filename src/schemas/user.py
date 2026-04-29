from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared fields used across user-related schemas."""
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for user registration — accepts a plain password."""
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase):
    """Schema returned to clients — never includes the password."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    

class Token(BaseModel):
    """JWT tokens returned after successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT contents — used for validating incoming tokens."""
    sub: str | None = None
    type: str | None = None
