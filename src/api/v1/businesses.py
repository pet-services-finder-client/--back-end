from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.business import Business
from src.models.associations import business_animal_types, business_services
from src.models.enums import BusinessStatus
from src.schemas.business import BusinessRead
from src.schemas.business_list import BusinessListItem, BusinessListResponse


router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=BusinessListResponse)
async def list_businesses(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
    category_id: Annotated[
        int | None,
        Query(description="Filter by business category id"),
    ] = None,
    accepts_emergencies: Annotated[
        bool | None,
        Query(description="Filter to only businesses accepting emergencies"),
    ] = None,
    emergency_24_7: Annotated[
        bool | None,
        Query(description="Filter to only 24/7 emergency businesses"),
    ] = None,
    animal_type_id: Annotated[
        int | None,
        Query(description="Filter by animal type served"),
    ] = None,
    service_id: Annotated[
        int | None,
        Query(description="Filter by service offered"),
    ] = None,
) -> BusinessListResponse:
    """Return paginated list of approved businesses with optional filters."""
    # Start with the base filter — only approved businesses are public
    filters = [Business.status == BusinessStatus.APPROVED]

    # Add simple field filters
    if category_id is not None:
        filters.append(Business.category_id == category_id)
    if accepts_emergencies is not None:
        filters.append(Business.accepts_emergencies == accepts_emergencies)
    if emergency_24_7 is not None:
        filters.append(Business.emergency_24_7 == emergency_24_7)

    # Build the base statement (used for both count and items)
    base_stmt = select(Business).where(*filters)

    # Add many-to-many filters via JOINs
    if animal_type_id is not None:
        base_stmt = base_stmt.join(
            business_animal_types,
            Business.id == business_animal_types.c.business_id,
        ).where(business_animal_types.c.animal_type_id == animal_type_id)
    if service_id is not None:
        base_stmt = base_stmt.join(
            business_services,
            Business.id == business_services.c.business_id,
        ).where(business_services.c.service_id == service_id)

    # If we joined m:n tables, results may have duplicates — deduplicate
    if animal_type_id is not None or service_id is not None:
        base_stmt = base_stmt.distinct()

    # Count total matching records (for pagination metadata)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch the actual page of records
    items_stmt = (
        base_stmt
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

