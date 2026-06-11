from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import select

from src.core.deps import get_current_active_user
from src.core.security import generate_verification_token
from src.main import app
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.email_verification_token import EmailVerificationToken
from src.models.enums import BusinessStatus
from src.models.user import User

API = "/api/v1"


# Mock email sending — tests must never hit Resend

@pytest_asyncio.fixture(autouse=True)
def _mock_email_sending(monkeypatch):
    """Replace real email-sending functions with no-ops.

    autouse=True means this is applied to every test in this file without
    needing to request it explicitly. We never want tests to hit Resend
    (it's slow, costs from the free tier, and would spam fake addresses).
    """
    monkeypatch.setattr(
        "src.api.v1.auth.send_welcome_with_verification_email",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "src.api.v1.auth.send_verification_email",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "src.api.v1.auth.send_password_reset_email",
        lambda **kwargs: None,
    )


# Fixtures: business + reviewer for verified/unverified flow tests


@pytest_asyncio.fixture
async def seed_for_reviews(db_session):
    """One approved business owned by an admin, ready for review tests."""
    owner = User(
        email="biz-owner@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        full_name="Власник",
    )
    category = BusinessCategory(slug="vet", name="Ветеринари")
    db_session.add_all([owner, category])
    await db_session.commit()

    business = Business(
        name="Клініка для тестів",
        slug="klinika-tests",
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
    return {"owner": owner, "category": category, "business": business}


# Section 1: Registration — creates unverified user + token


async def test_register_creates_unverified_user(client):
    """A newly registered user has is_verified=False."""
    resp = await client.post(
        f"{API}/auth/register",
        json={
            "email": "newuser@test.com",
            "password": "TestPass123",
            "full_name": "Тестова",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@test.com"
    assert data["is_verified"] is False


async def test_register_creates_verification_token(client, db_session):
    """Registration also persists an EmailVerificationToken for the user."""
    resp = await client.post(
        f"{API}/auth/register",
        json={
            "email": "tokencheck@test.com",
            "password": "TestPass123",
        },
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    result = await db_session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user_id)
    )
    tokens = result.scalars().all()
    assert len(tokens) == 1
    assert tokens[0].used_at is None
    assert tokens[0].expires_at > datetime.now(timezone.utc)


# Section 2: Verify email — token consumption and validation


async def test_verify_email_success_marks_user_verified(client, db_session):
    """Submitting a valid token marks the user as verified."""
    # Register first
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "verify-success@test.com", "password": "TestPass123"},
    )
    user_id = resp.json()["id"]

    # Inject a known token directly (we can't read the raw token from the
    # email, only from generation — so we create one in-test)
    raw, token_hash = generate_verification_token()
    db_session.add(EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db_session.commit()

    # Verify
    verify_resp = await client.post(
        f"{API}/auth/verify-email",
        json={"token": raw},
    )
    assert verify_resp.status_code == 204

    # User is now verified
    result = await db_session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    await db_session.refresh(user)
    assert user.is_verified is True


async def test_verify_email_marks_token_used(client, db_session):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "verify-used@test.com", "password": "TestPass123"},
    )
    user_id = resp.json()["id"]

    raw, token_hash = generate_verification_token()
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(token)
    await db_session.commit()

    await client.post(f"{API}/auth/verify-email", json={"token": raw})

    await db_session.refresh(token)
    assert token.used_at is not None


async def test_verify_with_invalid_token_returns_400(client):
    """A made-up token that doesn't exist in the DB → 400."""
    resp = await client.post(
        f"{API}/auth/verify-email",
        json={"token": "this-token-does-not-exist-in-the-db"},
    )
    assert resp.status_code == 400


async def test_verify_with_expired_token_returns_400(client, db_session):
    """An expired token → 400, user stays unverified."""
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "verify-expired@test.com", "password": "TestPass123"},
    )
    user_id = resp.json()["id"]

    # Create a token that expired an hour ago
    raw, token_hash = generate_verification_token()
    db_session.add(EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    ))
    await db_session.commit()

    resp = await client.post(
        f"{API}/auth/verify-email",
        json={"token": raw},
    )
    assert resp.status_code == 400


async def test_verify_with_used_token_returns_400(client, db_session):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "verify-used-twice@test.com", "password": "TestPass123"},
    )
    user_id = resp.json()["id"]

    raw, token_hash = generate_verification_token()
    db_session.add(EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db_session.commit()

    # First use — succeeds
    first = await client.post(f"{API}/auth/verify-email", json={"token": raw})
    assert first.status_code == 204

    # Second use — fails
    second = await client.post(f"{API}/auth/verify-email", json={"token": raw})
    assert second.status_code == 400


# Section 3: Resend verification — anti-enumeration and rate limit


async def test_resend_for_nonexistent_email_returns_neutral(client, db_session):
    resp = await client.post(
        f"{API}/auth/resend-verification",
        json={"email": "nobody@nowhere.com"},
    )
    assert resp.status_code == 200
    # No new token should have been created for a non-existent user
    result = await db_session.execute(select(EmailVerificationToken))
    tokens = result.scalars().all()
    assert len(tokens) == 0


async def test_resend_for_verified_user_skips_token_creation(client, db_session):
    # Register
    reg = await client.post(
        f"{API}/auth/register",
        json={"email": "already-verified@test.com", "password": "TestPass123"},
    )
    user_id = reg.json()["id"]

    # Mark verified manually
    user = (await db_session.execute(
        select(User).where(User.id == user_id)
    )).scalar_one()
    user.is_verified = True
    await db_session.commit()

    # Count tokens before resend (register itself creates one)
    before = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id
        )
    )
    count_before = len(before.scalars().all())

    # Request resend
    resp = await client.post(
        f"{API}/auth/resend-verification",
        json={"email": "already-verified@test.com"},
    )
    assert resp.status_code == 200

    # No new token created
    after = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id
        )
    )
    count_after = len(after.scalars().all())
    assert count_after == count_before


async def test_resend_rate_limit_skips_new_token_within_60s(client, db_session):
    # Register — this creates token #1
    reg = await client.post(
        f"{API}/auth/register",
        json={"email": "rate-limit@test.com", "password": "TestPass123"},
    )
    user_id = reg.json()["id"]

    # Immediate resend — should NOT create a new token
    resp = await client.post(
        f"{API}/auth/resend-verification",
        json={"email": "rate-limit@test.com"},
    )
    assert resp.status_code == 200

    tokens = (await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id
        )
    )).scalars().all()
    assert len(tokens) == 1  # still just the original token from register

# Section 4: Endpoint protection — verified-only actions


async def test_unverified_user_cannot_post_review(client, db_session, seed_for_reviews):
    """A logged-in but unverified user gets 403 when posting a review."""
    unverified = User(
        email="unverified@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=False,
        full_name="Невірифікований",
    )
    db_session.add(unverified)
    await db_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: unverified
    try:
        resp = await client.post(
            f"{API}/businesses/{seed_for_reviews['business'].id}/reviews",
            json={"rating": 5, "text": "Тест захисту"},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert resp.status_code == 403
    assert "пошту" in resp.json()["detail"].lower()  # Ukrainian message check


async def test_verified_user_can_post_review(client, db_session, seed_for_reviews):
    """A verified user can successfully post a review."""
    verified = User(
        email="verified-reviewer@test.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        full_name="Верифікований",
    )
    db_session.add(verified)
    await db_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: verified
    try:
        resp = await client.post(
            f"{API}/businesses/{seed_for_reviews['business'].id}/reviews",
            json={"rating": 5, "text": "Можу писати"},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert resp.status_code == 201
