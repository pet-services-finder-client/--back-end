from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.animal_type import AnimalType
from src.models.associations import business_animal_types, business_services
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.business_hours import BusinessHours
from src.models.enums import BusinessStatus
from src.models.service import Service


async def validate_category(db: AsyncSession, category_id: int) -> BusinessCategory:
    result = await db.execute(
        select(BusinessCategory).where(
            BusinessCategory.id == category_id,
            BusinessCategory.is_active.is_(True),
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or inactive category_id: {category_id}",
        )
    return category


async def validate_animal_types(db: AsyncSession, ids: list[int]) -> list[AnimalType]:
    result = await db.execute(
        select(AnimalType).where(
            AnimalType.id.in_(ids),
            AnimalType.is_active.is_(True),
        )
    )
    animal_types = list(result.scalars().all())
    if len(animal_types) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more animal_type_ids are invalid or inactive",
        )
    return animal_types


async def validate_services(
    db: AsyncSession, ids: list[int], category_id: int
) -> list[Service]:
    if not ids:
        return []
    result = await db.execute(
        select(Service).where(
            Service.id.in_(ids),
            Service.is_active.is_(True),
        )
    )
    services = list(result.scalars().all())
    if len(services) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more service_ids are invalid or inactive",
        )
    wrong = [s.slug for s in services if s.category_id != category_id]
    if wrong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Services do not belong to the selected category: "
                f"{', '.join(wrong)}"
            ),
        )
    return services


async def load_business_with_relations(
    db: AsyncSession, business_id: int, *, only_approved: bool = False
) -> Business | None:
    stmt = (
        select(Business)
        .where(Business.id == business_id)
        .options(
            selectinload(Business.animal_types),
            selectinload(Business.services),
            selectinload(Business.hours),
            selectinload(Business.owner),
        )
    )
    if only_approved:
        stmt = stmt.where(Business.status == BusinessStatus.APPROVED)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def build_business_search_query(
    *,
    category_id: int | None = None,
    accepts_emergencies: bool | None = None,
    emergency_24_7: bool | None = None,
    animal_type_id: int | None = None,
    service_id: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    q: str | None = None,
    open_now: bool | None = None,
):
    filters = [Business.status == BusinessStatus.APPROVED]

    if category_id is not None:
        filters.append(Business.category_id == category_id)
    if accepts_emergencies is not None:
        filters.append(Business.accepts_emergencies == accepts_emergencies)
    if emergency_24_7 is not None:
        filters.append(Business.emergency_24_7 == emergency_24_7)

    if q is not None:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Business.name.ilike(pattern),
                Business.description.ilike(pattern),
            )
        )

    distance_km_expr = None
    if lat is not None and lon is not None and radius_km is not None:
        distance_km_expr = 6371 * func.acos(
            func.cos(func.radians(lat))
            * func.cos(func.radians(Business.latitude))
            * func.cos(func.radians(Business.longitude) - func.radians(lon))
            + func.sin(func.radians(lat)) * func.sin(func.radians(Business.latitude))
        )
        filters.append(distance_km_expr <= radius_km)

    if distance_km_expr is not None:
        stmt = select(Business, distance_km_expr.label("distance_km")).where(*filters)
    else:
        stmt = select(Business).where(*filters)

    if animal_type_id is not None:
        stmt = stmt.join(
            business_animal_types,
            Business.id == business_animal_types.c.business_id,
        ).where(business_animal_types.c.animal_type_id == animal_type_id)
    if service_id is not None:
        stmt = stmt.join(
            business_services,
            Business.id == business_services.c.business_id,
        ).where(business_services.c.service_id == service_id)

    if open_now:
        kyiv_now = datetime.now(ZoneInfo("Europe/Kyiv"))
        today_weekday = kyiv_now.weekday()
        today_time = kyiv_now.time()

        yesterday = kyiv_now - timedelta(days=1)
        yesterday_weekday = yesterday.weekday()

        today_open = and_(
            BusinessHours.day_of_week == today_weekday,
            BusinessHours.is_closed.is_(False),
            or_(
                BusinessHours.is_24h.is_(True),
                and_(
                    BusinessHours.open_time <= BusinessHours.close_time,
                    BusinessHours.open_time <= today_time,
                    BusinessHours.close_time >= today_time,
                ),
                and_(
                    BusinessHours.open_time > BusinessHours.close_time,
                    or_(
                        BusinessHours.open_time <= today_time,
                        BusinessHours.close_time >= today_time,
                    ),
                ),
            ),
        )

        yesterday_carryover = and_(
            BusinessHours.day_of_week == yesterday_weekday,
            BusinessHours.is_closed.is_(False),
            BusinessHours.is_24h.is_(False),
            BusinessHours.open_time > BusinessHours.close_time,
            BusinessHours.close_time >= today_time,
        )

        stmt = stmt.join(
            BusinessHours, BusinessHours.business_id == Business.id
        ).where(or_(today_open, yesterday_carryover))

    if animal_type_id is not None or service_id is not None or open_now:
        stmt = stmt.distinct()

    return stmt, distance_km_expr
