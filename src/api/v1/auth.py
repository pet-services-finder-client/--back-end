from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from src.core.database import get_db
from src.core.deps import get_current_active_user
from src.core.email import send_password_reset_email, send_welcome_email
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from src.models.password_reset_token import PasswordResetToken
from src.models.user import User
from src.schemas.user import (
    ForgotPasswordRequest,
    PasswordChange,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserRead,
    UserUpdate,
)
from typing import Annotated
from src.core.deps import get_current_active_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Register a new user account."""
    # Check if email is already taken
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    # Create and persist the new user
    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    # Send welcome email after successful registration.
    # If the email fails, we still return success — the account is created
    # and the user can still use the app. send_welcome_email logs failures.
    send_welcome_email(to=new_user.email, user_name=new_user.full_name)
    
    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate a user and return access + refresh tokens."""
    # OAuth2 standard uses "username" — we accept email in that field
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )

@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Return the profile of the currently authenticated user."""
    return current_user

@router.patch("/me", response_model=UserRead)
async def update_current_user(
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Update the current user's profile (name, email)."""
    # Get only fields the user actually sent
    update_data = payload.model_dump(exclude_unset=True)

    # If email is changing, check that it's not taken by someone else
    if "email" in update_data and update_data["email"] != current_user.email:
        result = await db.execute(
            select(User).where(User.email == update_data["email"])
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(current_user, field, value)

    try:
        await db.commit()
        await db.refresh(current_user)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )

    return current_user

@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Change the current user's password.

    Requires the current password as confirmation — this prevents an attacker
    with brief access to a logged-in session from locking the user out.
    """
    # Verify the current password
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    # Hash and save the new password
    current_user.hashed_password = hash_password(payload.new_password)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Start the password reset flow.

    Anti-enumeration: we always return the same neutral response, regardless
    of whether the email exists. This prevents an attacker from probing which
    emails are registered.
    """
    neutral_response = {
        "message": "If an account exists for this email, we've sent a password reset link.",
    }

    # Look up the user
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # If no user — silently return success (anti-enumeration)
    if user is None or not user.is_active:
        return neutral_response

    # Generate token: raw goes to email, hash goes to DB
    raw_token, token_hash = generate_reset_token()

    # Save token with 1-hour expiry
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset_token)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        # Don't surface the error to the user — they'd see it as "failed reset"
        # which gives no useful info. Logs will show the real issue.
        return neutral_response

    # Build reset URL and send email
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_password_reset_email(
        to=user.email,
        reset_url=reset_url,
        user_name=user.full_name,
    )

    return neutral_response

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Complete the password reset flow using a token from email.

    All validation failures return the same generic error to prevent leaking
    information about which tokens exist, are expired, or already used.
    """
    generic_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token",
    )

    # Hash the submitted token to look it up in the DB
    token_hash = hash_reset_token(payload.token)

    # Find the token record
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None:
        raise generic_error

    # Check if already used
    if reset_token.used_at is not None:
        raise generic_error

    # Check if expired
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise generic_error

    # Load the associated user
    user_result = await db.execute(
        select(User).where(User.id == reset_token.user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        # User deleted or deactivated since requesting reset
        raise generic_error

    # Update password and mark token as used in a single transaction
    user.hashed_password = hash_password(payload.new_password)
    reset_token.used_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )

