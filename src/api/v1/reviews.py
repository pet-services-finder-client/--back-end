"""Review endpoints — users can post and read reviews about businesses."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_active_user
from src.crud.review import (
    create_review,
    delete_review,
    list_business_reviews,
    update_review,
)
from src.models.review import Review
from src.models.user import User
from src.schemas.review import (
    ReviewCreate,
    ReviewListResponse,
    ReviewRead,
    ReviewUpdate,
)


router = APIRouter(prefix="/businesses/{business_id}/reviews", tags=["reviews"])

review_actions_router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post(
    "",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_business_review(
    business_id: int,
    payload: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Review:
    return await create_review(
        db,
        business_id=business_id,
        author_id=current_user.id,
        rating=payload.rating,
        text=payload.text,
    )


@router.get(
    "",
    response_model=ReviewListResponse,
)
async def list_reviews(
    business_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ReviewListResponse:
    items, total = await list_business_reviews(
        db,
        business_id=business_id,
        limit=limit,
        offset=offset,
    )
    return ReviewListResponse(
        items=[ReviewRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )

@review_actions_router.patch(
    "/{review_id}",
    response_model=ReviewRead,
)
async def edit_review(
    review_id: int,
    payload: ReviewUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Review:
    """Edit your own review.

    Returns 404 if the review doesn't exist or belongs to another user
    (anti-enumeration — don't leak which review IDs are taken).
    """
    return await update_review(
        db,
        review_id=review_id,
        current_user_id=current_user.id,
        rating=payload.rating,
        text=payload.text,
    )


@review_actions_router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_review(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete your own review."""
    await delete_review(
        db,
        review_id=review_id,
        current_user_id=current_user.id,
    )
