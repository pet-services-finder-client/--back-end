from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.business import Business
from src.models.enums import BusinessStatus
from src.schemas.business import BusinessRead


router = APIRouter(prefix="/businesses", tags=["businesses"])


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
