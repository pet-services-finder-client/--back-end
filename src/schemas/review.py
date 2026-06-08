from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ReviewBase(BaseModel):
    """Shared fields between create and read schemas."""

    rating: int = Field(ge=1, le=5, description="Star rating from 1 to 5")
    text: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional review text — users can star-rate without writing",
    )


class ReviewCreate(ReviewBase):
    """Payload for POST /businesses/{business_id}/reviews."""


class ReviewAuthor(BaseModel):
    """Minimal author info shown alongside a review. """
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None


class ReviewRead(ReviewBase):
    """Public review representation returned by GET endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    author: ReviewAuthor
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    """Pagination"""
    items: list[ReviewRead]
    total: int
    limit: int
    offset: int
