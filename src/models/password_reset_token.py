from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.user import User


class PasswordResetToken(Base):
    """Single-use token for password reset flow.

    Flow:
    1. User requests password reset → we generate a random token, store its hash
    2. We email the user the raw token in a reset link
    3. User clicks link, submits new password with the token
    4. We hash the submitted token, look it up here, verify it's not expired or used
    5. Update user's password, mark token as used (used_at)

    Why store a hash and not the raw token:
        If our DB is ever compromised, an attacker should NOT be able to use stored
        tokens directly. Same principle as password hashing.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 hex digest of the raw token — 64 characters
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )

    # When this token stops being valid (we set it to now + 1 hour on creation)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # When this token was used to reset a password (null = not used yet)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Backref to user (not strictly needed, but useful for joins and admin views)
    user: Mapped["User"] = relationship("User", backref="password_reset_tokens")

    def __str__(self) -> str:
        return f"PasswordResetToken(user_id={self.user_id}, expires_at={self.expires_at})"
