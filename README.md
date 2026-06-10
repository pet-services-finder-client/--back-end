# Pawly — Pet Services Platform

Backend API for Pawly — a marketplace connecting pet owners with veterinary clinics, grooming salons, and pet shops in Kyiv and Kyiv Oblast.

## Tech Stack

Layer - Technology

Language - Python 3.13 
Web framework - FastAPI
ORM - SQLAlchemy 2.0 (async)
Database - PostgreSQL 16
Migrations - Alembic
Validation - Pydantic 2
Auth - JWT via python-jose, bcrypt
Admin panel - sqladmin
Containerization - Docker + Docker Compose
Testing - pytest, pytest-asyncio, httpx 

## Quick Start

Requires: Docker Desktop, Python 3.13, Git.

```bash
git clone https://github.com/pet-services-finder-client/--back-end.git
cd --back-end
cp .env.example .env
docker compose up -d --build
docker compose exec app alembic upgrade head
```

That's it. Open `http://localhost:8000/docs` for the Swagger UI.

The admin panel is at `http://localhost:8000/admin`.

## Project Structure

.
├── migrations/                       # Alembic migrations
│   ├── versions/                     # Migration files (one per schema change)
│   └── env.py                        # Alembic environment config
├── src/
│   ├── api/v1/                       # API endpoints (route handlers)
│   │   ├── auth.py                   # Registration, login, refresh, /me
│   │   ├── animal_types.py           # GET list of animal types
│   │   ├── pets.py                   # CRUD for user's pets
│   │   ├── businesses.py             # Business search, detail, autocomplete, submission
│   │   ├── business_categories.py    # GET list of business categories
│   │   ├── services.py               # GET list of services (filter by category)
│   │   ├── reviews.py                # Reviews CRUD (POST/GET/PATCH/DELETE)
│   │   ├── admin.py                  # Admin endpoints (incl. review moderation)
│   │   └── router.py                 # Aggregates all routers under /api/v1
│   ├── admin/                        # sqladmin setup (admin panel at /admin)
│   │   ├── auth.py                   # AdminAuth backend
│   │   └── views.py                  # ModelView definitions
│   ├── core/
│   │   ├── config.py                 # Settings (loaded from env vars)
│   │   ├── database.py               # Async engine, session factory, Base
│   │   ├── security.py               # JWT encode/decode, bcrypt helpers
│   │   └── deps.py                   # FastAPI deps (get_current_user, get_current_admin_user, get_db)
│   ├── crud/                         # Query builders and business logic
│   │   ├── business.py               # Search, validators, autocomplete, rating aggregation
│   │   └── review.py                 # Review create/update/delete/list/hide/unhide
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── pet.py
│   │   ├── animal_type.py
│   │   ├── business.py
│   │   ├── business_category.py
│   │   ├── business_hours.py
│   │   ├── service.py
│   │   ├── review.py                 # Review with rating, text, is_hidden flag
│   │   ├── password_reset_token.py
│   │   ├── associations.py           # Junction tables (business_animal_types, business_services)
│   │   ├── enums.py                  # PetGender, BusinessStatus
│   │   └── __init__.py               # Imports all models for SQLAlchemy registry
│   ├── schemas/                      # Pydantic schemas (request/response shapes)
│   │   ├── user.py                   # UserRead, UserPublic, UserCreate
│   │   ├── pet.py
│   │   ├── animal_type.py
│   │   ├── business.py               # BusinessRead with avg_rating, reviews_count
│   │   ├── business_create.py        # User submission payload
│   │   ├── business_update.py        # Partial update payload
│   │   ├── business_list.py          # BusinessListItem, BusinessListResponse
│   │   ├── business_autocomplete.py  # Lightweight schema for typeahead
│   │   ├── business_category.py
│   │   ├── business_hours.py
│   │   ├── service.py
│   │   └── review.py                 # ReviewCreate, ReviewRead, ReviewUpdate, ReviewAdminRead
│   └── main.py                       # FastAPI app entrypoint, CORS, admin mount
├── tests/                            # 90 tests using pytest + httpx
│   ├── conftest.py                   # Shared fixtures (db_session, client)
│   ├── test_businesses.py            # Search, CRUD, ratings (51 tests)
│   ├── test_reviews.py               # Review POST/GET/PATCH/DELETE (23 tests)
│   ├── test_admin_reviews.py         # Admin hide/unhide + permissions (11 tests)
│   └── test_review_model.py          # DB-level constraints (5 tests)
├── data/                             # Reference data (xlsx files excluded from Git)
├── scripts/
│   └── import_businesses.py          # CSV → DB import (123 Kyiv businesses)
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── pytest.ini                        # pytest config (asyncio_mode=auto)
├── requirements.txt                  # Runtime deps
├── requirements-import.txt           # Optional deps for data import (pandas, openpyxl)
└── README.md

## Architecture Overview

### Database schema

```
┌──────────┐       ┌──────────────┐
│  users   │──────<│  businesses  │  ──────────┐
└──────────┘       └──────────────┘            │
     │                    │                    │
     │                    │                    │
     │                    ├─< business_hours   │
     │                    │                    │
     │                    ├─< business_animal_types  >─┐
     │                    │                            │
     │                    ├─< business_services        │
     │                    │                            │
     │                    └─→ business_categories      │
     │                            │                    │
     │                            └─< services         │
     │                                                 │
     └─< pets ─→ animal_types <───────────────────────┘
```

**Cardinality:**
- `User` 1:m `Pet` (a user owns multiple pets)
- `User` 1:m `Business` (a user can propose multiple businesses, becomes the owner)
- `Business` n:1 `BusinessCategory` (each business belongs to one category)
- `Business` 1:m `BusinessHours` (one row per day of the week per business)
- `Business` n:m `AnimalType` (via `business_animal_types` junction)
- `Business` n:m `Service` (via `business_services` junction)
- `Service` n:1 `BusinessCategory` (each service belongs to one category)
- `Pet` n:1 `AnimalType`

**Cascade rules:**
- `User` deleted → their `Pet` and `Business` records deleted (CASCADE)
- `BusinessCategory` cannot be deleted while businesses reference it (RESTRICT)
- `AnimalType` cannot be deleted while pets/businesses reference it (RESTRICT)

### Business moderation flow

Businesses are user-submitted, but moderated:

```
User submits business
        ↓
   status: pending     ← not visible publicly
        ↓
Admin reviews in /admin
        ↓
   ┌────┴────┐
   ↓         ↓
approved  rejected
   ↓         ↓
public    hidden
```

Public endpoints (`GET /businesses`, `GET /businesses/{id}`) only return `status='approved'` businesses. Pending/rejected return 404 to avoid leaking the existence of unmoderated content.

## API Documentation

Live API docs: `http://localhost:8000/docs`

### Public endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login (returns JWT) |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/animal-types` | List all active animal types |
| GET | `/api/v1/business-categories` | List active business categories |
| GET | `/api/v1/services` | List active services (filter by category) |
| GET | `/api/v1/businesses` | Search businesses with full filters |
| GET | `/api/v1/businesses/{id}` | Business detail with all related data |

### Authenticated endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/auth/me` | Current user info |
| GET | `/api/v1/pets` | List current user's pets |
| POST | `/api/v1/pets` | Add a new pet |
| GET | `/api/v1/pets/{id}` | Get one pet (must be owner) |
| PATCH | `/api/v1/pets/{id}` | Update pet |
| DELETE | `/api/v1/pets/{id}` | Delete pet |

### Reviews endpoints

Public:

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/businesses/{id}/reviews` | List visible reviews for a business (paginated, newest first) |

Authenticated:

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/businesses/{id}/reviews` | Create a review (rating 1-5, optional text) |
| PATCH | `/api/v1/reviews/{id}` | Edit your own review |
| DELETE | `/api/v1/reviews/{id}` | Delete your own review |

Admin-only:

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/admin/reviews` | List all reviews including hidden ones |
| PATCH | `/api/v1/admin/reviews/{id}/hide` | Hide a review from public listings (idempotent) |
| PATCH | `/api/v1/admin/reviews/{id}/unhide` | Restore a hidden review (idempotent) |

**Business rules:**
- One review per user per business (DB-level `UniqueConstraint`)
- Users cannot review their own businesses (400)
- Anti-enumeration: editing or deleting someone else's review returns 404, not 403
- Hidden reviews are excluded from public listings AND from `avg_rating` / `reviews_count` aggregates
- `GET /businesses/{id}` and `GET /businesses` include `avg_rating` (float|null) and `reviews_count` (int) on every business


### `GET /businesses` filters

The search endpoint supports many optional filters that combine with AND:

| Param | Description |
|---|---|
| `category_id` | Filter by business category |
| `accepts_emergencies` | Only emergency-accepting businesses |
| `emergency_24_7` | Only 24/7 emergency services |
| `animal_type_id` | Businesses serving a specific species |
| `service_id` | Businesses offering a specific service |
| `lat`, `lon`, `radius_km` | Geo search via Haversine (all three required together) |
| `q` | Text search in name and description (ILIKE) |
| `open_now` | Only currently open (Kyiv timezone, with night-shift carryover) |
| `limit`, `offset` | Pagination (limit 1-100, default 20) |

Example: emergency vet care nearby right now:

```
GET /api/v1/businesses?open_now=true&accepts_emergencies=true&category_id=1&lat=50.45&lon=30.52&radius_km=20
```

## Admin Panel

The admin panel uses [sqladmin](https://github.com/aminalaee/sqladmin) and is mounted at `/admin`.

### Becoming an admin

There is no UI to grant admin rights — admins are managed via SQL:

```bash
docker compose exec db psql -U postgres -d pawly -c "UPDATE users SET is_admin=true WHERE email='you@example.com';"
```

After this, login with that user's credentials at `/admin`.

### Permissions

- Admins **cannot** create users (users must self-register)
- Admins **cannot** delete users (use `is_active=false` instead — soft delete)
- Admin status is re-checked on every request, so revocation is immediate

## Common Workflows

### Add a new model

1. Create `src/models/your_model.py` with SQLAlchemy class
2. Add import in `src/models/__init__.py` (so SQLAlchemy registers the mapper)
3. Add import in `migrations/env.py` (for autogenerate to detect the table)
4. Run `alembic revision --autogenerate -m "create your_model table"`
5. Review the generated migration file
6. Run `alembic upgrade head`

### Add a new endpoint

1. Create Pydantic schema in `src/schemas/your_thing.py`
2. Create router in `src/api/v1/your_thing.py` with `APIRouter(prefix="/your-things", tags=[...])`
3. Register the router in `src/api/v1/router.py`
4. Test in `/docs`

### Reset the database

```bash
docker compose down -v          # Remove volumes (deletes all data!)
docker compose up -d --build
docker compose exec app alembic upgrade head
```

### Run tests

```bash
# All tests
pytest -v

# One file
pytest tests/test_reviews.py -v

# Filter by name pattern
pytest -v -k "hidden"
```

Tests use a separate Postgres database (`pawly_test`) — create/drop tables run automatically per test for isolation. Override the URL via `TEST_DATABASE_URL` env var if needed.

### Reset the database

### Generate a migration after model changes

```bash
docker compose exec app alembic revision --autogenerate -m "what changed"
```

Always review the generated file before running `upgrade` — autogenerate is not perfect (it sometimes misses enum changes, custom constraints, etc).

## Environment Variables

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/pawly` | DB connection string for **host** (used by alembic, local uvicorn) |
| `SECRET_KEY` | (required) | JWT signing key — generate with `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `BACKEND_CORS_ORIGINS_RAW` | `http://localhost:3000` | Comma-separated CORS origins |
| `DEBUG` | `false` | Verbose SQL logging when true |

> **Note:** Inside Docker, `DATABASE_URL` is overridden in `docker-compose.yml` to use `@db` instead of `@localhost` (the Postgres service is reachable as `db` from the app container).

## Roadmap


### Completed

- **Auth** — registration, login, JWT tokens, current user endpoint
- **Pets** — CRUD for user's pets with animal type validation
- **Animal Types** — reference data with admin management
- **Admin Panel** — `is_admin` dependency + sqladmin integration for User, AnimalType, Business
- **Business models & data** — Business, BusinessCategory, Service, BusinessHours, junction tables with seed data and CSV import (123 real Kyiv businesses)
- **Business read API** — categories, services, detail, search with filters (geo, text, services, open-now, etc.)
- **Business write API** — user-submitted proposals with pending → approved/rejected admin moderation
- **Autocomplete** — `GET /businesses/autocomplete` for typeahead UI
- **Reviews epic** — full CRUD on reviews (POST/GET/PATCH/DELETE), admin hide/unhide moderation, `avg_rating` and `reviews_count` integrated into Business responses

- **Email verification** — verify user email after registration
- **Search ranking** — sort businesses by distance when geo params are provided
- **Postgres FTS** — full-text search with relevance instead of ILIKE
- **Region/city filtering** — pending product decision (Kyiv + Kyiv Oblast handling)
- **Google ratings integration** — hybrid display of Pawly + Google ratings on business detail (~10 SP, requires Google Places API + caching strategy)
- **Render deployment** — production deploy with custom domain, SSL, automatic deploy from Git

## Architectural Decisions

Key decisions made during development, with the reasoning behind them.

### Geo search: Haversine over PostGIS

For MVP-scale geo search (point + radius up to 200 km), the Haversine formula in raw SQL is sufficient. Postgres provides `acos`, `cos`, `sin`, `radians` out of the box, so no extension is required. PostGIS is reserved for the future when product needs polygon-based features (region boundaries, route calculations, complex geometries).

### `UserPublic` schema separate from `UserRead`

`UserRead` exposes email, admin flag, verification status — these should never leak through public endpoints. `UserPublic` is the safe shape for showing "who proposed this business" to anonymous visitors. Future changes to `UserRead` won't accidentally leak through public APIs because the schemas are decoupled.

### Soft delete via `is_active=false`

Instead of `DELETE FROM users`, we mark users inactive. This preserves audit trails, doesn't break foreign keys, and lets us reactivate accounts. Same approach is used for admin permissions: revoking is `is_admin=false`, not deletion.

### 404 instead of 403 for non-approved businesses

Public endpoints return 404 for pending or rejected businesses, even though they exist in the database. Returning 403 would leak the existence of unmoderated content. This is the same anti-enumeration pattern we use for accessing other users' pets.

### Eager loading strategy per relationship

- `Business.category` — `lazy="joined"` (almost always needed alongside the business)
- `Business.owner` — default lazy + explicit `selectinload()` in routes that need it
- `Business.animal_types`, `Business.services`, `Business.hours` — `selectinload()` (m:n and 1:m, avoiding cartesian product)

### City as a simple string field

For MVP we store `city: str = "Київ"` directly on `Business`, not a `City` reference table. The product is Kyiv-only at launch. If we need region filters, dropdowns, or polygons later, we'll migrate to a proper city/region table — that's a separate epic.

## Git Workflow

We use a simplified Git Flow:

```
main      ← stable, ready for production deploys
  ↑
develop   ← integration branch (all features merge here first)
  ↑
feature/* ← short-lived branches per task
hotfix/*  ← urgent fixes
docs/*    ← documentation
```

### Standard flow

```bash
git checkout develop
git pull
git checkout -b feature/your-task
# ... work, commit ...
git push -u origin feature/your-task
# Open PR on GitHub: feature/your-task → develop
# After review and merge:
git checkout develop
git pull
git branch -d feature/your-task
```

### Rules

- Never commit directly to `main`
- Try to avoid direct commits to `develop` — use PRs (exception: trivial hotfixes)
- One PR = one logical change
- Keep PRs small (target ~100-300 lines, max ~500)
- Each commit message should be a complete sentence describing what changed

### Commit message conventions

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `refactor:` — code change that doesn't add features or fix bugs
- `test:` — adding tests
- `chore:` — tooling, dependencies, etc

Prefix is optional but helps generate changelogs later.

## Troubleshooting

### `relation "users" does not exist`

The database is missing tables. Run migrations:

```bash
docker compose exec app alembic upgrade head
```

If that doesn't help, the volume might have stale data:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec app alembic upgrade head
```

### `MissingGreenlet: greenlet_spawn has not been called`

A SQLAlchemy relationship is being accessed lazily inside a Pydantic serialization, which doesn't work in async mode. Fix: load the relationship explicitly with `selectinload()` or `joinedload()` in the route handler.

### `expression 'X' failed to locate a name ('X')`

A SQLAlchemy model is referenced via string but not imported anywhere at app startup. Make sure the model is imported in `src/models/__init__.py`.

### `pydantic_core._pydantic_core.ValidationError: Field required`

The model returned from a route is missing a field that the response schema expects. Either add the field, or include the relationship via eager loading.

### Frontend can't reach the backend (CORS error)

Check `BACKEND_CORS_ORIGINS_RAW` in `.env` — make sure the frontend's URL is listed (comma-separated).

### Docker container can't connect to database

Inside the container, the database is at `db:5432`, not `localhost:5432`. The `DATABASE_URL` is overridden in `docker-compose.yml` to use `@db` for this reason. Don't change it back to `localhost` in the container.

## Author

Anastasiia Tarasenko — backend developer

For questions, ping me on Slack or open an issue.
