from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
 
from src.models.animal_type import AnimalType
from src.models.business_category import BusinessCategory
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
 