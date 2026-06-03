from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest_asyncio

from src.core.deps import get_current_active_user
from src.main import app
from src.models.animal_type import AnimalType
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.business_hours import BusinessHours
from src.models.enums import BusinessStatus
from src.models.service import Service
from src.models.user import User

API = "/api/v1"


# ====================================================================
# helpers
# ====================================================================

def make_hours():
    return [
        {
            "day_of_week": d,
            "is_closed": False,
            "is_24h": False,
            "open_time": "09:00:00",
            "close_time": "18:00:00",
        }
        for d in range(7)
    ]


def make_payload(seed, **overrides):
    payload = {
        "name": "Хвостик",
        "address": "вул. Хрещатик, 1",
        "latitude": 50.45,
        "longitude": 30.52,
        "category_id": seed["category"].id,
        "animal_type_ids": [seed["animal_type"].id],
        "service_ids": [seed["service"].id],
        "hours": make_hours(),
    }
    payload.update(overrides)
    return payload


async def add_business(
    db_session,
    seed,
    *,
    name,
    slug,
    address,
    status=BusinessStatus.APPROVED,
    owner=None,
    lat=50.45,
    lon=30.52,
    animal_types=None,
    services=None,
    accepts_emergencies=False,
    emergency_24_7=False,
    hours=None,
):
    """Створити бізнес напряму в базі (повз API) і закомітити."""
    business = Business(
        name=name,
        slug=slug,
        address=address,
        city="Київ",
        category_id=seed["category"].id,
        owner_id=(owner or seed["user"]).id,
        status=status,
        latitude=lat,
        longitude=lon,
        accepts_emergencies=accepts_emergencies,
        emergency_24_7=emergency_24_7,
    )
    if animal_types is not None:
        business.animal_types = animal_types
    if services is not None:
        business.services = services
    if hours is not None:
        business.hours = hours
    db_session.add(business)
    await db_session.commit()
    return business


# ====================================================================
# fixtures
# ====================================================================

@pytest_asyncio.fixture
async def seed(db_session):
    """Передумови: юзер-власник, категорія, тип тварини, послуга."""
    user = User(
        email="owner@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
    )
    category = BusinessCategory(slug="vet", name="Ветеринари")
    animal_type = AnimalType(slug="dog", name="Собака")
    service = Service(slug="vaccination", name="Вакцинація", category=category)

    db_session.add_all([user, category, animal_type, service])
    await db_session.commit()

    return {
        "user": user,
        "category": category,
        "animal_type": animal_type,
        "service": service,
    }


@pytest_asyncio.fixture
async def other_user(db_session):
    """Другий користувач — для перевірок 'не твій бізнес'."""
    user = User(
        email="stranger@test.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def auth_client(client, seed):
    """client із підміненою авторизацією — запити йдуть від засіяного юзера."""
    app.dependency_overrides[get_current_active_user] = lambda: seed["user"]
    yield client
    app.dependency_overrides.pop(get_current_active_user, None)


# ====================================================================
# CREATE  (POST /businesses)
# ====================================================================

async def test_create_business_success(auth_client, seed):
    resp = await auth_client.post(f"{API}/businesses", json=make_payload(seed))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Хвостик"
    assert data["status"] == "pending"   # новий бізнес завжди на модерації
    assert "slug" in data


async def test_create_requires_auth(client, seed):
    # без підміни авторизації — запит має бути відхилений
    resp = await client.post(f"{API}/businesses", json=make_payload(seed))
    assert resp.status_code in (401, 403)


async def test_create_rejects_unknown_category(auth_client, seed):
    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, category_id=999999)
    )
    assert resp.status_code == 400


async def test_create_rejects_inactive_category(auth_client, db_session, seed):
    inactive = BusinessCategory(slug="closed-cat", name="Неактивна", is_active=False)
    db_session.add(inactive)
    await db_session.commit()

    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, category_id=inactive.id)
    )
    assert resp.status_code == 400


async def test_create_rejects_invalid_animal_type(auth_client, seed):
    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, animal_type_ids=[999999])
    )
    assert resp.status_code == 400


async def test_create_rejects_inactive_animal_type(auth_client, db_session, seed):
    inactive = AnimalType(slug="dino", name="Динозавр", is_active=False)
    db_session.add(inactive)
    await db_session.commit()

    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, animal_type_ids=[inactive.id])
    )
    assert resp.status_code == 400


async def test_create_rejects_invalid_service(auth_client, seed):
    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, service_ids=[999999])
    )
    assert resp.status_code == 400


async def test_create_rejects_service_from_other_category(auth_client, db_session, seed):
    other_cat = BusinessCategory(slug="grooming", name="Грумінг")
    other_service = Service(slug="haircut", name="Стрижка", category=other_cat)
    db_session.add_all([other_cat, other_service])
    await db_session.commit()

    # категорія лишається vet, а послуга — з grooming → 400
    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, service_ids=[other_service.id])
    )
    assert resp.status_code == 400


async def test_create_generates_unique_slugs(auth_client, seed):
    # дві назви однакові, адреси різні (через UniqueConstraint(name, address))
    first = await auth_client.post(
        f"{API}/businesses",
        json=make_payload(seed, name="Лапка", address="вул. Перша, 1"),
    )
    second = await auth_client.post(
        f"{API}/businesses",
        json=make_payload(seed, name="Лапка", address="вул. Друга, 2"),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["slug"] != second.json()["slug"]


async def test_create_rejects_hours_not_seven_days(auth_client, seed):
    # лише 5 днів замість 7 → помилка валідації схеми (422)
    bad_hours = make_hours()[:5]
    resp = await auth_client.post(
        f"{API}/businesses", json=make_payload(seed, hours=bad_hours)
    )
    assert resp.status_code == 422


async def test_create_rejects_closed_day_with_times(auth_client, seed):
    # закритий день не повинен мати часів → 422
    hours = make_hours()
    hours[0] = {
        "day_of_week": 0,
        "is_closed": True,
        "is_24h": False,
        "open_time": "09:00:00",
        "close_time": "18:00:00",
    }
    resp = await auth_client.post(f"{API}/businesses", json=make_payload(seed, hours=hours))
    assert resp.status_code == 422


# ====================================================================
# GET single  (GET /businesses/{id})
# ====================================================================

async def test_get_approved_business(client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Котячий рай", slug="kotyachiy-ray",
        address="вул. Перша, 1", status=BusinessStatus.APPROVED,
    )
    resp = await client.get(f"{API}/businesses/{b.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Котячий рай"


async def test_get_pending_returns_404(client, db_session, seed):
    b = await add_business(
        db_session, seed, name="На модерації", slug="pending-one",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await client.get(f"{API}/businesses/{b.id}")
    assert resp.status_code == 404


async def test_get_rejected_returns_404(client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Відхилений", slug="rejected-one",
        address="вул. Перша, 1", status=BusinessStatus.REJECTED,
    )
    resp = await client.get(f"{API}/businesses/{b.id}")
    assert resp.status_code == 404


async def test_get_nonexistent_returns_404(client, seed):
    resp = await client.get(f"{API}/businesses/999999")
    assert resp.status_code == 404


# ====================================================================
# UPDATE  (PATCH /businesses/{id})
# ====================================================================

async def test_update_name_success(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Стара назва", slug="old-name",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}", json={"name": "Нова назва"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Нова назва"


async def test_update_regenerates_slug_on_name_change(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Стара назва", slug="old-name",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}", json={"name": "Зовсім інша назва"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] != "old-name"


async def test_update_animal_types(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Бізнес", slug="biz",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}",
        json={"animal_type_ids": [seed["animal_type"].id]},
    )
    assert resp.status_code == 200


async def test_update_service_from_other_category_rejected(auth_client, db_session, seed):
    other_cat = BusinessCategory(slug="grooming", name="Грумінг")
    other_service = Service(slug="haircut", name="Стрижка", category=other_cat)
    db_session.add_all([other_cat, other_service])
    await db_session.commit()

    b = await add_business(
        db_session, seed, name="Бізнес", slug="biz",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}", json={"service_ids": [other_service.id]}
    )
    assert resp.status_code == 400


async def test_update_not_owner_returns_404(auth_client, db_session, seed, other_user):
    b = await add_business(
        db_session, seed, name="Чужий", slug="strangers",
        address="вул. Перша, 1", status=BusinessStatus.PENDING, owner=other_user,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}", json={"name": "Перехоплено"}
    )
    assert resp.status_code == 404


async def test_update_nonexistent_returns_404(auth_client, seed):
    resp = await auth_client.patch(f"{API}/businesses/999999", json={"name": "Тест"})
    assert resp.status_code == 404


async def test_update_approved_business_rejected(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Схвалений", slug="approved-one",
        address="вул. Перша, 1", status=BusinessStatus.APPROVED,
    )
    resp = await auth_client.patch(
        f"{API}/businesses/{b.id}", json={"name": "Не можна"}
    )
    assert resp.status_code == 400


async def test_update_requires_auth(client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Бізнес", slug="biz",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await client.patch(f"{API}/businesses/{b.id}", json={"name": "X"})
    assert resp.status_code in (401, 403)


# ====================================================================
# DELETE  (DELETE /businesses/{id})
# ====================================================================

async def test_delete_own_pending_success(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Бізнес", slug="biz",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await auth_client.delete(f"{API}/businesses/{b.id}")
    assert resp.status_code == 204


async def test_delete_not_owner_returns_404(auth_client, db_session, seed, other_user):
    b = await add_business(
        db_session, seed, name="Чужий", slug="strangers",
        address="вул. Перша, 1", status=BusinessStatus.PENDING, owner=other_user,
    )
    resp = await auth_client.delete(f"{API}/businesses/{b.id}")
    assert resp.status_code == 404


async def test_delete_nonexistent_returns_404(auth_client, seed):
    resp = await auth_client.delete(f"{API}/businesses/999999")
    assert resp.status_code == 404


async def test_delete_approved_rejected(auth_client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Схвалений", slug="approved-one",
        address="вул. Перша, 1", status=BusinessStatus.APPROVED,
    )
    resp = await auth_client.delete(f"{API}/businesses/{b.id}")
    assert resp.status_code == 400


async def test_delete_requires_auth(client, db_session, seed):
    b = await add_business(
        db_session, seed, name="Бізнес", slug="biz",
        address="вул. Перша, 1", status=BusinessStatus.PENDING,
    )
    resp = await client.delete(f"{API}/businesses/{b.id}")
    assert resp.status_code in (401, 403)


# ====================================================================
# LIST / SEARCH  (GET /businesses)
# ====================================================================

async def test_search_returns_only_approved(client, db_session, seed):
    await add_business(db_session, seed, name="Схвалений", slug="ok",
                       address="вул. Перша, 1", status=BusinessStatus.APPROVED)
    await add_business(db_session, seed, name="Прихований", slug="hidden",
                       address="вул. Друга, 2", status=BusinessStatus.PENDING)
    resp = await client.get(f"{API}/businesses")
    assert resp.status_code == 200
    data = resp.json()
    names = {i["name"] for i in data["items"]}
    assert "Схвалений" in names
    assert "Прихований" not in names
    assert data["total"] == 1


async def test_search_text_query(client, db_session, seed):
    await add_business(db_session, seed, name="Котячий рай", slug="cats",
                       address="вул. Перша, 1")
    await add_business(db_session, seed, name="Песик і друзі", slug="dogs",
                       address="вул. Друга, 2")
    resp = await client.get(f"{API}/businesses", params={"q": "Котячий"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Котячий рай"


async def test_search_geo_radius(client, db_session, seed):
    await add_business(db_session, seed, name="Поруч", slug="near",
                       address="вул. Перша, 1", lat=50.45, lon=30.52)
    await add_business(db_session, seed, name="Далеко", slug="far",
                       address="вул. Друга, 2", lat=49.0, lon=30.0)
    resp = await client.get(
        f"{API}/businesses", params={"lat": 50.45, "lon": 30.52, "radius_km": 5}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert "Поруч" in names
    assert "Далеко" not in names


async def test_search_geo_requires_all_params(client, seed):
    # лише lat без lon/radius → 400
    resp = await client.get(f"{API}/businesses", params={"lat": 50.45})
    assert resp.status_code == 400


async def test_search_geo_sorts_nearest_first(client, db_session, seed):
    await add_business(db_session, seed, name="Дальній", slug="b-far",
                       address="вул. Друга, 2", lat=50.50, lon=30.60)
    await add_business(db_session, seed, name="Ближній", slug="b-near",
                       address="вул. Перша, 1", lat=50.45, lon=30.52)
    resp = await client.get(
        f"{API}/businesses", params={"lat": 50.45, "lon": 30.52, "radius_km": 50}
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["name"] == "Ближній"          # найближчий першим
    assert "distance_km" in items[0]


async def test_search_filter_by_category(client, db_session, seed):
    other_cat = BusinessCategory(slug="grooming", name="Грумінг")
    db_session.add(other_cat)
    await db_session.commit()

    await add_business(db_session, seed, name="Ветклініка", slug="vet1",
                       address="вул. Перша, 1")  # категорія seed (vet)
    other = Business(
        name="Грумер", slug="groom1", address="вул. Друга, 2", city="Київ",
        category_id=other_cat.id, owner_id=seed["user"].id,
        status=BusinessStatus.APPROVED, latitude=50.45, longitude=30.52,
    )
    db_session.add(other)
    await db_session.commit()

    resp = await client.get(
        f"{API}/businesses", params={"category_id": seed["category"].id}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert names == {"Ветклініка"}


async def test_search_filter_by_animal_type(client, db_session, seed):
    await add_business(db_session, seed, name="Для собак", slug="dogs",
                       address="вул. Перша, 1",
                       animal_types=[seed["animal_type"]])
    await add_business(db_session, seed, name="Без тварин", slug="none",
                       address="вул. Друга, 2", animal_types=[])
    resp = await client.get(
        f"{API}/businesses", params={"animal_type_id": seed["animal_type"].id}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert names == {"Для собак"}


async def test_search_filter_by_service(client, db_session, seed):
    await add_business(db_session, seed, name="З послугою", slug="with-srv",
                       address="вул. Перша, 1", services=[seed["service"]])
    await add_business(db_session, seed, name="Без послуги", slug="no-srv",
                       address="вул. Друга, 2", services=[])
    resp = await client.get(
        f"{API}/businesses", params={"service_id": seed["service"].id}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert names == {"З послугою"}


async def test_search_filter_accepts_emergencies(client, db_session, seed):
    await add_business(db_session, seed, name="Екстрена", slug="emerg",
                       address="вул. Перша, 1", accepts_emergencies=True)
    await add_business(db_session, seed, name="Звичайна", slug="normal",
                       address="вул. Друга, 2", accepts_emergencies=False)
    resp = await client.get(
        f"{API}/businesses", params={"accepts_emergencies": "true"}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert names == {"Екстрена"}


async def test_search_filter_emergency_24_7(client, db_session, seed):
    await add_business(db_session, seed, name="Цілодобова", slug="247",
                       address="вул. Перша, 1", emergency_24_7=True)
    await add_business(db_session, seed, name="Денна", slug="day",
                       address="вул. Друга, 2", emergency_24_7=False)
    resp = await client.get(f"{API}/businesses", params={"emergency_24_7": "true"})
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert names == {"Цілодобова"}


async def test_search_pagination(client, db_session, seed):
    for n in range(3):
        await add_business(db_session, seed, name=f"Бізнес {n}", slug=f"biz-{n}",
                           address=f"вул. Тестова, {n}")
    page1 = await client.get(f"{API}/businesses", params={"limit": 2, "offset": 0})
    assert page1.status_code == 200
    d1 = page1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2

    page2 = await client.get(f"{API}/businesses", params={"limit": 2, "offset": 2})
    assert len(page2.json()["items"]) == 1


async def test_search_open_now_basic(client, db_session, seed):
    today = datetime.now(ZoneInfo("Europe/Kyiv")).weekday()
    # цілодобовий сьогодні → відкритий зараз
    await add_business(
        db_session, seed, name="Відкритий", slug="open-now",
        address="вул. Перша, 1",
        hours=[BusinessHours(day_of_week=today, is_24h=True, is_closed=False)],
    )
    # закритий сьогодні → не відкритий
    await add_business(
        db_session, seed, name="Закритий", slug="closed-now",
        address="вул. Друга, 2",
        hours=[BusinessHours(day_of_week=today, is_closed=True)],
    )
    resp = await client.get(f"{API}/businesses", params={"open_now": "true"})
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert "Відкритий" in names
    assert "Закритий" not in names


async def test_search_open_now_midnight_carryover(client, db_session, seed, monkeypatch):
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # вівторок, 02:00 за Києвом
            return datetime(2024, 1, 2, 2, 0, tzinfo=tz)

    monkeypatch.setattr("src.api.v1.businesses.datetime", _FrozenDatetime)

    # понеділок (0): 19:00–03:00 (open > close → нічна зміна)
    await add_business(
        db_session, seed, name="Нічний", slug="night",
        address="вул. Перша, 1",
        hours=[BusinessHours(
            day_of_week=0, is_closed=False, is_24h=False,
            open_time=time(19, 0), close_time=time(3, 0),
        )],
    )
    resp = await client.get(f"{API}/businesses", params={"open_now": "true"})
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()["items"]}
    assert "Нічний" in names
