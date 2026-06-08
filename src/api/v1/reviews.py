"""Review endpoints — users can post and read reviews about businesses."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_active_user
from src.crud.review import create_review, list_business_reviews
from src.models.review import Review
from src.models.user import User
from src.schemas.review import ReviewCreate, ReviewListResponse, ReviewRead


router = APIRouter(prefix="/businesses/{business_id}/reviews", tags=["reviews"])


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
