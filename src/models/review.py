from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.business import Business
    from src.models.user import User


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        # A user can leave at most one review per business.
        UniqueConstraint(
            "business_id", "author_id", name="uq_review_business_author"
        ),
        CheckConstraint(
            "rating BETWEEN 1 AND 5", name="ck_review_rating_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Relationships (FK)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship(back_populates="reviews")
    author: Mapped["User"] = relationship(back_populates="reviews_written")

    def __str__(self) -> str:
        return f"Review #{self.id} ({self.rating}★)"
