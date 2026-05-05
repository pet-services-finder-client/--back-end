from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.business import Business
from src.models.enums import BusinessStatus
from src.schemas.business import BusinessRead
from src.schemas.business_list import BusinessListItem, BusinessListResponse


router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=BusinessListResponse)
async def list_businesses(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> BusinessListResponse:
    """Return paginated list of approved businesses."""
    base_filter = Business.status == BusinessStatus.APPROVED

    # Count total matching records (for pagination metadata)
    count_stmt = select(func.count()).select_from(Business).where(base_filter)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch the actual page of records
    items_stmt = (
        select(Business)
        .where(base_filter)
        .order_by(Business.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items_result = await db.execute(items_stmt)
    businesses = list(items_result.scalars().all())

    return BusinessListResponse(
        items=[BusinessListItem.model_validate(b) for b in businesses],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{business_id}", response_model=BusinessRead)
async def get_business(
    business_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Business:
    """Return a single approved business by id, with all related data."""
    result = await db.execute(
        select(Business)
        .where(
            Business.id == business_id,
            Business.status == BusinessStatus.APPROVED,
        )
        .options(
            selectinload(Business.animal_types),
            selectinload(Business.services),
            selectinload(Business.hours),
            selectinload(Business.owner),
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    return business

