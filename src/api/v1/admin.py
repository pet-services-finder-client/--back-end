from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.core.deps import get_current_admin_user
from src.crud.review import (
    hide_review,
    list_all_reviews_for_admin,
    unhide_review,
)
from src.models.review import Review
from src.models.user import User
from src.schemas.review import ReviewAdminListResponse, ReviewAdminRead
from src.schemas.user import UserRead


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=UserRead)
async def admin_whoami(
    current_admin: Annotated[User, Depends(get_current_admin_user)],
) -> User:
    return current_admin

@router.get(
    "/reviews",
    response_model=ReviewAdminListResponse,
)
async def list_all_reviews_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin_user)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ReviewAdminListResponse:

    items, total = await list_all_reviews_for_admin(
        db, limit=limit, offset=offset
    )
    return ReviewAdminListResponse(
        items=[ReviewAdminRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.patch(
    "/reviews/{review_id}/hide",
    response_model=ReviewAdminRead,
)
async def hide_review_endpoint(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin_user)],
) -> Review:
    """Hide a review from public listings. Idempotent."""
    return await hide_review(db, review_id)


@router.patch(
    "/reviews/{review_id}/unhide",
    response_model=ReviewAdminRead,
)
async def unhide_review_endpoint(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin_user)],
) -> Review:
    """Restore a hidden review to public visibility. Idempotent."""
    return await unhide_review(db, review_id)
