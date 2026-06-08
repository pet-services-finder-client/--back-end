from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.business import Business
from src.models.enums import BusinessStatus
from src.models.review import Review


async def create_review(
    db: AsyncSession,
    *,
    business_id: int,
    author_id: int,
    rating: int,
    text: str | None,
) -> Review:
    """Create a review for a business, enforcing all business rules.
    - The business must exist and be approved (no reviews on pending / rejected).
    - The author cannot review their own business (conflict of interest).
    - One review per user per business (DB UniqueConstraint catches duplicates).

    Raises 404 if the business doesn't exist or isn't approved (same response
    to prevent enumeration of pending/rejected businesses).
    Raises 400 for self-review attempts.
    Raises 409 for duplicate reviews.
    """
    business_result = await db.execute(
        select(Business).where(Business.id == business_id)
    )
    business = business_result.scalar_one_or_none()

    if business is None or business.status != BusinessStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.owner_id == author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot review your own business",
        )

    review = Review(
        business_id=business_id,
        author_id=author_id,
        rating=rating,
        text=text,
    )
    db.add(review)
    try:
        await db.commit()
    except IntegrityError:
        #duplicate review.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this business. Edit your existing review instead.",
        )

    # Reload with author eagerly loaded so the API response includes it
    # without a lazy-load surprise.
    result = await db.execute(
        select(Review)
        .where(Review.id == review.id)
        .options(selectinload(Review.author))
    )
    return result.scalar_one()


async def list_business_reviews(
    db: AsyncSession,
    *,
    business_id: int,
    limit: int,
    offset: int,
) -> tuple[list[Review], int]:
    """Return (reviews, total_count) for a business's public reviews."""
    business_result = await db.execute(
        select(Business).where(Business.id == business_id)
    )
    business = business_result.scalar_one_or_none()

    if business is None or business.status != BusinessStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    base_filters = (
        Review.business_id == business_id,
        Review.is_hidden.is_(False),
    )

    count_stmt = select(func.count()).select_from(Review).where(*base_filters)
    total = (await db.execute(count_stmt)).scalar_one()

    items_stmt = (
        select(Review)
        .where(*base_filters)
        .options(selectinload(Review.author))
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    return items, total

async def update_review(
    db: AsyncSession,
    *,
    review_id: int,
    current_user_id: int,
    rating: int | None,
    text: str | None,
) -> Review:
    """Update an existing review. Only the author can edit their own review.

    Anti-enumeration: same 404 for "doesn't exist" and "not yours" — so the
    caller can't probe which review IDs belong to other users.

    Only fields that were explicitly sent (non-None) are applied. This makes
    PATCH partial — a client sending only `{"rating": 4}` won't wipe the text.
    """
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.author))
    )
    review = result.scalar_one_or_none()

    if review is None or review.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    if rating is not None:
        review.rating = rating
    if text is not None:
        review.text = text

    await db.commit()
    await db.refresh(review)
    return review


async def delete_review(
    db: AsyncSession,
    *,
    review_id: int,
    current_user_id: int,
) -> None:
    """Delete a review. Only the author can delete their own review."""
    result = await db.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()

    if review is None or review.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    await db.delete(review)
    await db.commit()
