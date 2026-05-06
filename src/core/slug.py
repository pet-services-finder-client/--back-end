"""Slug generation utilities."""

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.business import Business


def make_slug(text: str) -> str:
    """Generate a URL-friendly slug from arbitrary text.

    Handles Ukrainian/Cyrillic transliteration:
        'АлеВет Клініка' -> 'alevet-klinika'
        'Жовтий Хвостик' -> 'zhovtii-khvostik'
    """
    return slugify(text, max_length=200)


async def generate_unique_business_slug(db: AsyncSession, name: str) -> str:
    """Generate a unique slug for a business by appending -2, -3, etc on collision."""
    base_slug = make_slug(name)
    if not base_slug:
        # Fallback if name has only special characters
        base_slug = "business"

    candidate = base_slug
    counter = 1

    while True:
        result = await db.execute(
            select(Business.id).where(Business.slug == candidate)
        )
        if result.scalar_one_or_none() is None:
            return candidate
        counter += 1
        candidate = f"{base_slug}-{counter}"
