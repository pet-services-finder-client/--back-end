from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.business_category import BusinessCategory
from src.schemas.business_category import BusinessCategoryRead


router = APIRouter(prefix="/business-categories", tags=["business-categories"])


@router.get("", response_model=list[BusinessCategoryRead])
async def list_business_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BusinessCategory]:
    """Return all active business categories, sorted for display."""
    result = await db.execute(
        select(BusinessCategory)
        .where(BusinessCategory.is_active == True)  # noqa: E712
        .order_by(BusinessCategory.sort_order, BusinessCategory.name)
    )
    return list(result.scalars().all())
