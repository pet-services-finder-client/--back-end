"""Tests for review endpoints — POST and GET on /businesses/{id}/reviews."""
import pytest_asyncio

from src.core.deps import get_current_active_user
from src.main import app
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.enums import BusinessStatus
from src.models.review import Review
from src.models.user import User

API = "/api/v1"

# helpers / fixtures

async def _add_business(
    db_session,
    *,
    name,
    slug,
    address,
    owner,
    category,
    status=BusinessStatus.APPROVED,
):
    business = Business(
        name=name,
        slug=slug,
        address=address,
        city="Київ",
        latitude=50.45,
        longitude=30.52,
        category_id=category.id,
        owner_id=owner.id,
        status=status,
    )
    db_session.add(business)
    await db_session.commit()
    return business


@pytest_asyncio.fixture
async def seed(db_session):
    """Two users (owner of test business + reviewer) plus a category and
    one approved business owned by `owner`."""
    owner = User(
        email="owner@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
        full_name="Власник Тест",
    )
    reviewer = User(
        email="reviewer@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
        full_name="Рецензент",
    )
    category = BusinessCategory(slug="vet", name="Ветеринари")
    db_session.add_all([owner, reviewer, category])
    await db_session.commit()

    business = await _add_business(
        db_session,
        name="Тест клініка", slug="test-klinika",
        address="вул. Перша, 1", owner=owner, category=category,
    )
    return {
        "owner": owner,
        "reviewer": reviewer,
        "category": category,
        "business": business,
    }


@pytest_asyncio.fixture
async def auth_as_reviewer(client, seed):
    """Client where /me requests resolve to seed['reviewer']."""
    app.dependency_overrides[get_current_active_user] = lambda: seed["reviewer"]
    yield client
    app.dependency_overrides.pop(get_current_active_user, None)


@pytest_asyncio.fixture
async def auth_as_owner(client, seed):
    """Client where /me requests resolve to seed['owner'] — useful for
    testing 'cannot review your own business'."""
    app.dependency_overrides[get_current_active_user] = lambda: seed["owner"]
    yield client
    app.dependency_overrides.pop(get_current_active_user, None)


# POST /businesses/{id}/reviews — happy path and validation

async def test_post_review_success(auth_as_reviewer, seed):
    """Logged-in user can post a valid review on someone else's business."""
    resp = await auth_as_reviewer.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 5, "text": "Чудові лікарі!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == 5
    assert data["text"] == "Чудові лікарі!"
    assert data["author"]["id"] == seed["reviewer"].id
    assert "is_hidden" not in data  # public schema should not expose this


async def test_post_review_requires_auth(client, seed):
    """Anonymous request is rejected."""
    resp = await client.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 5, "text": "X"},
    )
    assert resp.status_code in (401, 403)


async def test_post_review_rejects_rating_above_5(auth_as_reviewer, seed):
    """Pydantic enforces rating <= 5."""
    resp = await auth_as_reviewer.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 6, "text": "X"},
    )
    assert resp.status_code == 422


async def test_post_review_rejects_rating_below_1(auth_as_reviewer, seed):
    """Pydantic enforces rating >= 1."""
    resp = await auth_as_reviewer.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 0, "text": "X"},
    )
    assert resp.status_code == 422


async def test_post_review_on_own_business_rejected(auth_as_owner, seed):
    """Business owners cannot review their own businesses."""
    resp = await auth_as_owner.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 5, "text": "Сам себе хвалю"},
    )
    assert resp.status_code == 400


async def test_post_review_on_pending_business_returns_404(
    auth_as_reviewer, db_session, seed
):
    """Pending businesses are not visible — same 404 as non-existent
    (anti-enumeration: don't reveal which IDs exist in moderation)."""
    pending = await _add_business(
        db_session,
        name="На модерації", slug="pending-one",
        address="вул. Друга, 2",
        owner=seed["owner"], category=seed["category"],
        status=BusinessStatus.PENDING,
    )
    resp = await auth_as_reviewer.post(
        f"{API}/businesses/{pending.id}/reviews",
        json={"rating": 5, "text": "X"},
    )
    assert resp.status_code == 404


async def test_post_review_on_nonexistent_business_returns_404(
    auth_as_reviewer, seed
):
    resp = await auth_as_reviewer.post(
        f"{API}/businesses/999999/reviews",
        json={"rating": 5, "text": "X"},
    )
    assert resp.status_code == 404


async def test_post_duplicate_review_returns_409(auth_as_reviewer, seed):
    """UniqueConstraint(business_id, author_id) prevents a second review;
    the API translates that into a friendly 409."""
    payload = {"rating": 5, "text": "Перший"}
    first = await auth_as_reviewer.post(
        f"{API}/businesses/{seed['business'].id}/reviews", json=payload
    )
    assert first.status_code == 201

    second = await auth_as_reviewer.post(
        f"{API}/businesses/{seed['business'].id}/reviews",
        json={"rating": 4, "text": "Передумала"},
    )
    assert second.status_code == 409


# GET /businesses/{id}/reviews — listing

async def test_list_reviews_hides_is_hidden_ones(
    auth_as_reviewer, db_session, seed
):
    visible = Review(
        business_id=seed["business"].id,
        author_id=seed["reviewer"].id,
        rating=5, text="Видимий",
    )
    hidden = Review(
        business_id=seed["business"].id,
        author_id=seed["owner"].id,  # different author to bypass unique
        rating=1, text="Прихований",
        is_hidden=True,
    )
    db_session.add_all([visible, hidden])
    await db_session.commit()

    resp = await auth_as_reviewer.get(
        f"{API}/businesses/{seed['business'].id}/reviews"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["text"] == "Видимий"


async def test_list_reviews_newest_first(client, db_session, seed):
    older = Review(
        business_id=seed["business"].id,
        author_id=seed["reviewer"].id,
        rating=3, text="Старіший",
    )
    db_session.add(older)
    await db_session.commit()

    newer = Review(
        business_id=seed["business"].id,
        author_id=seed["owner"].id,
        rating=5, text="Новіший",
    )
    db_session.add(newer)
    await db_session.commit()

    resp = await client.get(
        f"{API}/businesses/{seed['business'].id}/reviews"
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["text"] == "Новіший"
    assert items[1]["text"] == "Старіший"


async def test_list_reviews_pagination(client, db_session, seed):
    extra_users = [
        User(
            email=f"u{i}@test.com",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        for i in range(3)
    ]
    db_session.add_all(extra_users)
    await db_session.commit()
    for u in extra_users:
        db_session.add(Review(
            business_id=seed["business"].id,
            author_id=u.id,
            rating=5,
        ))
    await db_session.commit()

    page1 = await client.get(
        f"{API}/businesses/{seed['business'].id}/reviews",
        params={"limit": 2, "offset": 0},
    )
    assert page1.status_code == 200
    d1 = page1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2

    page2 = await client.get(
        f"{API}/businesses/{seed['business'].id}/reviews",
        params={"limit": 2, "offset": 2},
    )
    assert len(page2.json()["items"]) == 1


async def test_list_reviews_on_pending_business_returns_404(
    client, db_session, seed
):
    pending = await _add_business(
        db_session,
        name="Pending", slug="pending-x",
        address="вул. Третя, 3",
        owner=seed["owner"], category=seed["category"],
        status=BusinessStatus.PENDING,
    )
    resp = await client.get(f"{API}/businesses/{pending.id}/reviews")
    assert resp.status_code == 404


async def test_list_reviews_on_nonexistent_business_returns_404(client, seed):
    resp = await client.get(f"{API}/businesses/999999/reviews")
    assert resp.status_code == 404
