from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.animal_type import AnimalType
from src.schemas.animal_type import AnimalTypeRead


router = APIRouter(prefix="/animal-types", tags=["animal-types"])


@router.get("", response_model=list[AnimalTypeRead])
async def list_animal_types(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AnimalType]:
    """Return all active animal types, sorted for display."""
    result = await db.execute(
        select(AnimalType)
        .where(AnimalType.is_active == True)  # noqa: E712
        .order_by(AnimalType.sort_order, AnimalType.name)
    )
    return list(result.scalars().all())
