from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from src.core.database import get_db
from src.core.deps import get_current_active_user
from src.core.email import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_with_verification_email,
)
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    generate_reset_token,
    generate_verification_token,
    hash_password,
    hash_reset_token,
    hash_verification_token,
    verify_password,
)

from src.models.email_verification_token import EmailVerificationToken
from src.models.password_reset_token import PasswordResetToken
from src.models.user import User
from src.schemas.user import (
    EmailVerificationRequest,
    ForgotPasswordRequest,
    PasswordChange,
    ResendVerificationRequest,
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

    raw_token, token_hash = generate_verification_token()
    verification_token = EmailVerificationToken(
        user_id=new_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification_token)
    await db.commit()

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    send_welcome_with_verification_email(
        to=new_user.email,
        user_name=new_user.full_name,
        verification_url=verification_url,
    )
    
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
    neutral_response = {
       "message": (
        "Якщо для цієї пошти існує акаунт, "
        "ми надіслали посилання для скидання паролю."
    ),
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

    if reset_token.used_at is not None:
        raise generic_error

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

@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(
    payload: EmailVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    generic_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token",
    )

    # Hash the submitted token to look it up in the DB
    token_hash = hash_verification_token(payload.token)

    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )
    verification_token = result.scalar_one_or_none()

    if verification_token is None:
        raise generic_error

    # Already used
    if verification_token.used_at is not None:
        raise generic_error

    # Expired
    if verification_token.expires_at < datetime.now(timezone.utc):
        raise generic_error

    # Load the associated user
    user_result = await db.execute(
        select(User).where(User.id == verification_token.user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        # User was deleted or deactivated since requesting verification
        raise generic_error

    # Mark verified + consume the token in one transaction
    user.is_verified = True
    verification_token.used_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email",
        )


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    payload: ResendVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    neutral_response = {
        "message": (
            "Якщо для цієї пошти існує непідтверджений акаунт, "
            "ми надіслали нове посилання для підтвердження."
        ),
    }

    # Look up the user
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # No user, inactive user, or already verified → silent success
    if user is None or not user.is_active or user.is_verified:
        return neutral_response

    # Simple rate limit: if a token was created less than 60 seconds ago,
    # don't issue a new one. Prevents abuse and accidental spam.
    recent_token_stmt = (
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .where(EmailVerificationToken.used_at.is_(None))
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    recent = (await db.execute(recent_token_stmt)).scalar_one_or_none()
    if recent is not None:
        age = datetime.now(timezone.utc) - recent.created_at
        if age.total_seconds() < 60:
            return neutral_response

    # Generate fresh token
    raw_token, token_hash = generate_verification_token()

    new_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(new_token)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        return neutral_response

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    send_verification_email(
        to=user.email,
        user_name=user.full_name,
        verification_url=verification_url,
    )

    return neutral_response
