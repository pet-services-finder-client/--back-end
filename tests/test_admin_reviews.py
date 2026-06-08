"""Tests for admin moderation endpoints — hide/unhide/list all reviews."""
import pytest_asyncio

from src.core.deps import get_current_admin_user, get_current_active_user
from src.main import app
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.enums import BusinessStatus
from src.models.review import Review
from src.models.user import User

API = "/api/v1"


# Fixtures


@pytest_asyncio.fixture
async def seed_admin(db_session):
    """Set up: admin user, regular user, business owned by admin, and a
    third user to author reviews from."""
    admin = User(
        email="admin@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_admin=True,
        full_name="Адмін",
    )
    regular = User(
        email="regular@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_admin=False,
        full_name="Звичайний",
    )
    reviewer = User(
        email="reviewer@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        full_name="Рецензент",
    )
    category = BusinessCategory(slug="vet", name="Ветеринари")
    db_session.add_all([admin, regular, reviewer, category])
    await db_session.commit()

    business = Business(
        name="Клініка", slug="klinika",
        address="вул. Перша, 1", city="Київ",
        latitude=50.45, longitude=30.52,
        category_id=category.id, owner_id=admin.id,
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()

    return {
        "admin": admin,
        "regular": regular,
        "reviewer": reviewer,
        "business": business,
    }


@pytest_asyncio.fixture
async def auth_as_admin(client, seed_admin):
    app.dependency_overrides[get_current_active_user] = lambda: seed_admin["admin"]
    app.dependency_overrides[get_current_admin_user] = lambda: seed_admin["admin"]
    yield client
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_current_admin_user, None)


@pytest_asyncio.fixture
async def auth_as_regular(client, seed_admin):
    app.dependency_overrides[get_current_active_user] = lambda: seed_admin["regular"]
    yield client
    app.dependency_overrides.pop(get_current_active_user, None)


# GET /admin/reviews — listing all reviews


async def test_admin_can_list_all_reviews(auth_as_admin, db_session, seed_admin):
    """Admin sees every review, including hidden ones, with is_hidden flag."""
    visible = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5, text="Видимий",
    )
    hidden = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["regular"].id,
        rating=1, text="Прихований",
        is_hidden=True,
    )
    db_session.add_all([visible, hidden])
    await db_session.commit()

    resp = await auth_as_admin.get(f"{API}/admin/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # is_hidden must appear in admin schema (unlike public ReviewRead)
    flags = {item["text"]: item["is_hidden"] for item in data["items"]}
    assert flags == {"Видимий": False, "Прихований": True}


async def test_non_admin_cannot_list_reviews(auth_as_regular, seed_admin):
    resp = await auth_as_regular.get(f"{API}/admin/reviews")
    assert resp.status_code == 403


async def test_anonymous_cannot_list_admin_reviews(client, seed_admin):
    resp = await client.get(f"{API}/admin/reviews")
    assert resp.status_code in (401, 403)


# PATCH /admin/reviews/{id}/hide


async def test_admin_can_hide_review(auth_as_admin, db_session, seed_admin):
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5, text="Спам",
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_admin.patch(f"{API}/admin/reviews/{review.id}/hide")
    assert resp.status_code == 200
    assert resp.json()["is_hidden"] is True

    # Confirm the public listing no longer shows it
    public = await auth_as_admin.get(
        f"{API}/businesses/{seed_admin['business'].id}/reviews"
    )
    assert public.json()["total"] == 0


async def test_hide_is_idempotent(auth_as_admin, db_session, seed_admin):
    """Hiding an already-hidden review is not an error."""
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5,
        is_hidden=True,
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_admin.patch(f"{API}/admin/reviews/{review.id}/hide")
    assert resp.status_code == 200
    assert resp.json()["is_hidden"] is True


async def test_hide_nonexistent_review_returns_404(auth_as_admin, seed_admin):
    resp = await auth_as_admin.patch(f"{API}/admin/reviews/999999/hide")
    assert resp.status_code == 404


async def test_non_admin_cannot_hide_review(
    auth_as_regular, db_session, seed_admin
):
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5,
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_regular.patch(f"{API}/admin/reviews/{review.id}/hide")
    assert resp.status_code == 403


# PATCH /admin/reviews/{id}/unhide


async def test_admin_can_unhide_review(auth_as_admin, db_session, seed_admin):
    """Unhide restores a review to public visibility."""
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5, text="Помилково приховано",
        is_hidden=True,
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_admin.patch(f"{API}/admin/reviews/{review.id}/unhide")
    assert resp.status_code == 200
    assert resp.json()["is_hidden"] is False

    # Confirm it's now visible publicly
    public = await auth_as_admin.get(
        f"{API}/businesses/{seed_admin['business'].id}/reviews"
    )
    assert public.json()["total"] == 1


async def test_unhide_is_idempotent(auth_as_admin, db_session, seed_admin):
    """Unhiding an already-visible review is not an error."""
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5,
        is_hidden=False,
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_admin.patch(f"{API}/admin/reviews/{review.id}/unhide")
    assert resp.status_code == 200
    assert resp.json()["is_hidden"] is False


async def test_unhide_nonexistent_review_returns_404(auth_as_admin, seed_admin):
    resp = await auth_as_admin.patch(f"{API}/admin/reviews/999999/unhide")
    assert resp.status_code == 404


async def test_non_admin_cannot_unhide_review(
    auth_as_regular, db_session, seed_admin
):
    review = Review(
        business_id=seed_admin["business"].id,
        author_id=seed_admin["reviewer"].id,
        rating=5,
        is_hidden=True,
    )
    db_session.add(review)
    await db_session.commit()

    resp = await auth_as_regular.patch(f"{API}/admin/reviews/{review.id}/unhide")
    assert resp.status_code == 403
