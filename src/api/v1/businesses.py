from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.business import Business
from src.schemas.business_create import BusinessCreate
from src.schemas.business_update import BusinessUpdate
from src.models.enums import BusinessStatus
from src.models.business_hours import BusinessHours
from src.schemas.business import BusinessRead
from src.schemas.business_list import BusinessListItem, BusinessListResponse
from src.core.deps import get_current_active_user
from src.core.slug import generate_unique_business_slug
from src.models.user import User
from src.crud.business import (
    build_business_search_query,
    load_business_with_relations,
    validate_animal_types,
    validate_category,
    validate_services,
)


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
    geo_params = [lat, lon, radius_km]
    if any(p is not None for p in geo_params) and not all(p is not None for p in geo_params):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lat, lon, and radius_km must all be provided together",
        )

    base_stmt, distance_km_expr = build_business_search_query(
        category_id=category_id,
        accepts_emergencies=accepts_emergencies,
        emergency_24_7=emergency_24_7,
        animal_type_id=animal_type_id,
        service_id=service_id,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        q=q,
        open_now=open_now,
    )

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    if distance_km_expr is not None:
        items_stmt = (
            base_stmt
            .order_by(distance_km_expr.asc())
            .limit(limit)
            .offset(offset)
        )
        items_result = await db.execute(items_stmt)
        items = [
            BusinessListItem.model_validate(b).model_copy(
                update={"distance_km": round(d, 2)}
            )
            for b, d in items_result.all()
        ]
    else:
        items_stmt = (
            base_stmt
            .order_by(Business.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items_result = await db.execute(items_stmt)
        items = [
            BusinessListItem.model_validate(b)
            for b in items_result.scalars().all()
        ]

    return BusinessListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=BusinessRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_business(
    payload: BusinessCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Business:
    await validate_category(db, payload.category_id)
    animal_types = await validate_animal_types(db, payload.animal_type_ids)
    services = await validate_services(db, payload.service_ids, payload.category_id)

    slug = await generate_unique_business_slug(db, payload.name)

    business = Business(
        name=payload.name,
        slug=slug,
        description=payload.description,
        category_id=payload.category_id,
        owner_id=current_user.id,
        status=BusinessStatus.PENDING,
        address=payload.address,
        city=payload.city,
        latitude=payload.latitude,
        longitude=payload.longitude,
        phone=payload.phone,
        website=payload.website,
        email=payload.email,
        accepts_emergencies=payload.accepts_emergencies,
        emergency_24_7=payload.emergency_24_7,
        cover_image_url=payload.cover_image_url,
    )

    business.animal_types = animal_types
    business.services = services

    business.hours = [
        BusinessHours(
            day_of_week=h.day_of_week,
            is_closed=h.is_closed,
            is_24h=h.is_24h,
            open_time=h.open_time,
            close_time=h.close_time,
        )
        for h in payload.hours
    ]

    db.add(business)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create business",
        )

    return await load_business_with_relations(db, business.id)


@router.patch("/{business_id}", response_model=BusinessRead)
async def update_business(
    business_id: int,
    payload: BusinessUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Business:
    business = await load_business_with_relations(db, business_id)

    if business is None or business.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.status != BusinessStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved or rejected businesses cannot be edited by the owner. Contact admin.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "category_id" in update_data:
        await validate_category(db, update_data["category_id"])

    if "animal_type_ids" in update_data:
        ids = update_data.pop("animal_type_ids")
        business.animal_types = await validate_animal_types(db, ids)

    if "service_ids" in update_data:
        ids = update_data.pop("service_ids")
        target_category_id = update_data.get("category_id", business.category_id)
        business.services = await validate_services(db, ids, target_category_id)

    if "hours" in update_data:
        new_hours = update_data.pop("hours")
        business.hours = [
            BusinessHours(
                day_of_week=h["day_of_week"],
                is_closed=h["is_closed"],
                is_24h=h["is_24h"],
                open_time=h["open_time"],
                close_time=h["close_time"],
            )
            for h in new_hours
        ]

    if "name" in update_data and update_data["name"] != business.name:
        update_data["slug"] = await generate_unique_business_slug(db, update_data["name"])

    for field, value in update_data.items():
        setattr(business, field, value)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update business",
        )

    return await load_business_with_relations(db, business.id)


@router.delete("/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business(
    business_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    result = await db.execute(
        select(Business).where(Business.id == business_id)
    )
    business = result.scalar_one_or_none()

    if business is None or business.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.status != BusinessStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved or rejected businesses cannot be deleted by the owner. Contact admin.",
        )

    await db.delete(business)
    await db.commit()


@router.get("/{business_id}", response_model=BusinessRead)
async def get_business(
    business_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Business:
    business = await load_business_with_relations(db, business_id, only_approved=True)
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    return business
