import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from src.models.animal_type import AnimalType
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.enums import BusinessStatus
from src.models.review import Review
from src.models.service import Service
from src.models.user import User


@pytest_asyncio.fixture
async def two_users_and_business(db_session):
    owner = User(
        email="owner@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
    )
    reviewer = User(
        email="reviewer@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
    )
    category = BusinessCategory(slug="vet", name="Ветеринари")
    db_session.add_all([owner, reviewer, category])
    await db_session.commit()

    business = Business(
        name="Тест клініка",
        slug="test-klinika",
        address="вул. Перша, 1",
        city="Київ",
        latitude=50.45,
        longitude=30.52,
        category_id=category.id,
        owner_id=owner.id,
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()

    return {"owner": owner, "reviewer": reviewer, "business": business}


# Review model — basic creation

async def test_review_can_be_created(db_session, two_users_and_business):
    """Happy path: a valid review saves successfully."""
    s = two_users_and_business
    review = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=5,
        text="Чудові лікарі!",
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    assert review.id is not None
    assert review.is_hidden is False  # default
    assert review.created_at is not None


async def test_review_text_is_optional(db_session, two_users_and_business):
    s = two_users_and_business
    review = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=4,
    )
    db_session.add(review)
    await db_session.commit()

    assert review.id is not None
    assert review.text is None


# Constraints — DB-level safety

async def test_rating_above_5_is_rejected(db_session, two_users_and_business):
    s = two_users_and_business
    review = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=6,
    )
    db_session.add(review)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_rating_below_1_is_rejected(db_session, two_users_and_business):
    s = two_users_and_business
    review = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=0,
    )
    db_session.add(review)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_one_review_per_user_per_business(db_session, two_users_and_business):
    s = two_users_and_business
    first = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=5,
    )
    db_session.add(first)
    await db_session.commit()

    second = Review(
        business_id=s["business"].id,
        author_id=s["reviewer"].id,
        rating=3,
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        await db_session.commit()
