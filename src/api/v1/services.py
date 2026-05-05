from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.service import Service
from src.schemas.service import ServiceRead


router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceRead])
async def list_services(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: Annotated[
        int | None,
        Query(description="Filter services by category id"),
    ] = None,
) -> list[Service]:
    """Return active services. Optionally filter by category."""
    stmt = (
        select(Service)
        .where(Service.is_active == True)  # noqa: E712
        .order_by(Service.category_id, Service.sort_order)
    )

    if category_id is not None:
        stmt = stmt.where(Service.category_id == category_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())
