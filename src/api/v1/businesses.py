from typing import Annotated
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.business import Business
from src.models.associations import business_animal_types, business_services
from src.models.enums import BusinessStatus
from src.models.business_hours import BusinessHours
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
    lat: Annotated[
        float | None,
        Query(ge=-90, le=90, description="Latitude of search center"),
    ] = None,
    lon: Annotated[
        float | None,
        Query(ge=-180, le=180, description="Longitude of search center"),
    ] = None,
    radius_km: Annotated[
        float | None,
        Query(gt=0, le=200, description="Search radius in kilometers"),
    ] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=100, description="Text search in name and description"),
    ] = None,
    open_now: Annotated[
        bool | None,
        Query(description="Filter to businesses currently open (Kyiv time)"),
    ] = None,
) -> BusinessListResponse:
    """Return paginated list of approved businesses with optional filters."""
    # Geo parameters must come together — either all three or none
    geo_params = [lat, lon, radius_km]
    if any(p is not None for p in geo_params) and not all(p is not None for p in geo_params):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lat, lon, and radius_km must all be provided together",
        )

    # Start with the base filter — only approved businesses are public
    filters = [Business.status == BusinessStatus.APPROVED]

    # Add simple field filters
    if category_id is not None:
        filters.append(Business.category_id == category_id)
    if accepts_emergencies is not None:
        filters.append(Business.accepts_emergencies == accepts_emergencies)
    if emergency_24_7 is not None:
        filters.append(Business.emergency_24_7 == emergency_24_7)

    # Text search — case-insensitive match in name or description
    if q is not None:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Business.name.ilike(pattern),
                Business.description.ilike(pattern),
            )
        )

    # Geo filter — Haversine formula for distance in kilometers
    if lat is not None and lon is not None and radius_km is not None:
        distance_km = 6371 * func.acos(
            func.cos(func.radians(lat))
            * func.cos(func.radians(Business.latitude))
            * func.cos(func.radians(Business.longitude) - func.radians(lon))
            + func.sin(func.radians(lat)) * func.sin(func.radians(Business.latitude))
        )
        filters.append(distance_km <= radius_km)

    # Build the base statement
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

    # "Open now" filter — check current time against business_hours
    if open_now:
        # Use Kyiv timezone for "now" — all our businesses are in Ukraine
        kyiv_now = datetime.now(ZoneInfo("Europe/Kyiv"))
        today_weekday = kyiv_now.weekday()
        today_time = kyiv_now.time()

        # For night-shift hours that span midnight (e.g. 19:00-03:00),
        # we also need to check yesterday's record with carryover.
        yesterday = kyiv_now - timedelta(days=1)
        yesterday_weekday = yesterday.weekday()

        # Today's record matches if: not closed AND (24h OR currently within hours)
        today_open = and_(
            BusinessHours.day_of_week == today_weekday,
            BusinessHours.is_closed.is_(False),
            or_(
                BusinessHours.is_24h.is_(True),
                # Normal hours (open <= close): open <= now <= close
                and_(
                    BusinessHours.open_time <= BusinessHours.close_time,
                    BusinessHours.open_time <= today_time,
                    BusinessHours.close_time >= today_time,
                ),
                # Night hours (open > close): now is after open OR before close
                and_(
                    BusinessHours.open_time > BusinessHours.close_time,
                    or_(
                        BusinessHours.open_time <= today_time,
                        BusinessHours.close_time >= today_time,
                    ),
                ),
            ),
        )

        # Yesterday's night-shift carryover: open > close, and now is before close
        yesterday_carryover = and_(
            BusinessHours.day_of_week == yesterday_weekday,
            BusinessHours.is_closed.is_(False),
            BusinessHours.is_24h.is_(False),
            BusinessHours.open_time > BusinessHours.close_time,
            BusinessHours.close_time >= today_time,
        )

        base_stmt = base_stmt.join(
            BusinessHours, BusinessHours.business_id == Business.id
        ).where(or_(today_open, yesterday_carryover))

    # If we joined m:n tables OR business_hours, results may have duplicates
    if animal_type_id is not None or service_id is not None or open_now:
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

