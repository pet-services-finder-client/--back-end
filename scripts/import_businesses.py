"""Import businesses from the analyst's XLSX file.

Reads `data/pawly_csv_fixed.xlsx` and creates Business + BusinessHours
records in the DB, linking them to existing AnimalType / Service /
BusinessCategory rows via their slugs.

Usage:
    python -m scripts.import_businesses
    # or with custom path:
    python -m scripts.import_businesses path/to/file.xlsx

The script is idempotent on slug: if a business with the same generated
slug already exists, the row is skipped (logged).
"""
from __future__ import annotations

import asyncio
import math
import sys
from datetime import time
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.slug import generate_unique_business_slug
from src.models.animal_type import AnimalType
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.business_hours import BusinessHours
from src.models.enums import BusinessStatus
from src.models.service import Service


# All imported businesses belong to user id=1 (the dev account).
# When admin panel is ready we can re-assign via UPDATE.
OWNER_ID = 1

# Default file location relative to repo root.
DEFAULT_XLSX = Path("data/pawly_csv_fixed.xlsx")


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _clean(value):
    """Return None for pandas NaN / NaT / empty string, otherwise the value.

    pandas reads empty cells as NaN (float). Passing NaN into SQLAlchemy
    columns that expect str | None would store the literal string "nan",
    which is wrong. This normalizes to None.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _parse_slug_list(value) -> list[str]:
    """Split 'dog,cat,rabbit' into ['dog', 'cat', 'rabbit'].

    Empty / NaN → []. Whitespace around items is trimmed.
    """
    cleaned = _clean(value)
    if cleaned is None:
        return []
    return [s.strip() for s in str(cleaned).split(",") if s.strip()]


def _to_time(value) -> time | None:
    """Convert a pandas time cell to a Python time, or None.

    The hours sheet may contain values as either:
    - datetime.time objects (when Excel cell is formatted as Time)
    - strings like '08:00:00' or '08:00'
    - NaN for 24h or closed rows
    """
    cleaned = _clean(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, time):
        return cleaned
    if isinstance(cleaned, str):
        # Try common formats; XLSX usually gives HH:MM:SS but be lenient
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                from datetime import datetime
                return datetime.strptime(cleaned, fmt).time()
            except ValueError:
                continue
        raise ValueError(f"Unrecognized time format: {cleaned!r}")
    raise TypeError(f"Cannot convert {type(cleaned).__name__} to time: {cleaned!r}")


def _to_bool(value, default: bool = False) -> bool:
    """Convert pandas cell to bool. NaN/None → default."""
    cleaned = _clean(value)
    if cleaned is None:
        return default
    if isinstance(cleaned, bool):
        return cleaned
    # Excel may give us 'True'/'False' strings
    if isinstance(cleaned, str):
        return cleaned.strip().lower() in ("true", "yes", "1", "так")
    return bool(cleaned)

# ──────────────────────────────────────────────────────────────────
# Lookups — load reference data once
# ──────────────────────────────────────────────────────────────────

async def load_lookups(db: AsyncSession) -> tuple[dict, dict, dict]:
    """Pre-load reference tables into dicts keyed by slug.

    Returns (categories_by_slug, animal_types_by_slug, services_by_slug).
    We do this once before the import loop so each row doesn't trigger
    its own SELECT to resolve slugs.
    """
    categories_result = await db.execute(select(BusinessCategory))
    categories = {c.slug: c for c in categories_result.scalars().all()}

    animals_result = await db.execute(
        select(AnimalType).where(AnimalType.is_active.is_(True))
    )
    animal_types = {a.slug: a for a in animals_result.scalars().all()}

    services_result = await db.execute(
        select(Service).where(Service.is_active.is_(True))
    )
    services = {s.slug: s for s in services_result.scalars().all()}

    return categories, animal_types, services

# ──────────────────────────────────────────────────────────────────
# Create one business from a DataFrame row
# ──────────────────────────────────────────────────────────────────

async def create_business(
    db: AsyncSession,
    row: pd.Series,
    categories: dict,
    animal_types: dict,
    services: dict,
) -> Business | None:
    """Create one Business with animal_types and services linked.

    Returns the created Business, or None if the row was skipped
    (slug collision or invalid data).
    """
    name = _clean(row["name"])
    if name is None:
        raise ValueError("Missing required field: name")

    # 1. Resolve category by slug
    category_slug = _clean(row["category"])
    if category_slug not in categories:
        raise ValueError(f"Unknown category slug: {category_slug!r}")
    category = categories[category_slug]

    # 2. Resolve animal_types (m:n) — must all exist
    at_slugs = _parse_slug_list(row["animal_types"])
    unknown_animals = [s for s in at_slugs if s not in animal_types]
    if unknown_animals:
        raise ValueError(f"Unknown animal_type slugs: {unknown_animals}")
    business_animal_types = [animal_types[s] for s in at_slugs]

    # 3. Resolve services (m:n) — must all exist AND belong to the category
    svc_slugs = _parse_slug_list(row["services"])
    unknown_services = [s for s in svc_slugs if s not in services]
    if unknown_services:
        raise ValueError(f"Unknown service slugs: {unknown_services}")
    business_services_list = [services[s] for s in svc_slugs]

    wrong_category = [
        s.slug for s in business_services_list if s.category_id != category.id
    ]
    if wrong_category:
        raise ValueError(
            f"Services don't belong to category {category_slug!r}: {wrong_category}"
        )

    # 4. Generate a unique slug (handles collisions: alevet, alevet-2, alevet-3)
    slug = await generate_unique_business_slug(db, name)

    # 5. Build the Business
    business = Business(
        name=name,
        slug=slug,
        description=_clean(row["description"]),
        category_id=category.id,
        owner_id=OWNER_ID,
        status=BusinessStatus.APPROVED,
        address=_clean(row["address"]) or "",
        city=_clean(row["city"]) or "Київ",
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        phone=_clean(row["phone"]),
        website=_clean(row["website"]),
        email=_clean(row["email"]),
        accepts_emergencies=_to_bool(row.get("accepts_emergencies"), default=False),
        emergency_24_7=_to_bool(row.get("emergency_24_7"), default=False),
        cover_image_url=_clean(row["cover_image_url"]),
    )
    business.animal_types = business_animal_types
    business.services = business_services_list

    db.add(business)
    await db.flush()  # populate business.id without committing
    return business

# ──────────────────────────────────────────────────────────────────
# Import hours sheet — link by business name
# ──────────────────────────────────────────────────────────────────

async def import_hours(
    db: AsyncSession,
    df_hours: pd.DataFrame,
    name_to_business_id: dict[str, int],
) -> tuple[int, list[str]]:
    """Create BusinessHours rows from the 'hours' sheet.

    Each business has 7 rows in the sheet (one per day of week).
    We look up the business_id by name from the map built during
    business import.

    Returns (rows_created, errors).
    """
    created = 0
    errors: list[str] = []

    for idx, row in df_hours.iterrows():
        bname = _clean(row["business_name"])
        if bname is None:
            errors.append(f"row {idx}: missing business_name")
            continue

        business_id = name_to_business_id.get(bname)
        if business_id is None:
            errors.append(f"row {idx}: business not found: {bname!r}")
            continue

        try:
            is_24h = _to_bool(row["is_24h"], default=False)
            is_closed = _to_bool(row["is_closed"], default=False)

            # 24h or closed days have no times
            open_time = None if (is_24h or is_closed) else _to_time(row["open_time"])
            close_time = None if (is_24h or is_closed) else _to_time(row["close_time"])

            hours = BusinessHours(
                business_id=business_id,
                day_of_week=int(row["day_of_week"]),
                is_closed=is_closed,
                is_24h=is_24h,
                open_time=open_time,
                close_time=close_time,
            )
            db.add(hours)
            created += 1
        except Exception as e:
            errors.append(f"row {idx} ({bname}, day {row.get('day_of_week')}): {e}")

    return created, errors

# ──────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────

async def main(xlsx_path: Path) -> int:
    """Run the import. Returns process exit code (0 = success)."""
    if not xlsx_path.exists():
        print(f"File not found: {xlsx_path}")
        return 1

    print(f"Reading {xlsx_path}")
    df_businesses = pd.read_excel(xlsx_path, sheet_name="businesses")
    df_hours = pd.read_excel(xlsx_path, sheet_name="hours")
    print(f"   {len(df_businesses)} businesses, {len(df_hours)} hours rows\n")

    async with AsyncSessionLocal() as db:
        # 1. Load lookup data once
        print("Loading lookups (categories, animal_types, services)")
        categories, animal_types, services = await load_lookups(db)
        print(
            f"   {len(categories)} categories, "
            f"{len(animal_types)} animal types, "
            f"{len(services)} services\n"
        )

        # 2. Import businesses, build name → id map for hours linking
        print("Creating businesses")
        name_to_business_id: dict[str, int] = {}
        skipped: list[tuple[str, str]] = []

        for idx, row in df_businesses.iterrows():
            try:
                business = await create_business(
                    db, row, categories, animal_types, services
                )
                if business is not None:
                    name_to_business_id[row["name"]] = business.id
            except Exception as e:
                skipped.append((str(row.get("name", f"row {idx}")), str(e)))

        print(f"   ✓ created {len(name_to_business_id)}")
        print(f"   ✗ skipped {len(skipped)}\n")

        # 3. Import hours
        print("Creating hours")
        hours_created, hours_errors = await import_hours(
            db, df_hours, name_to_business_id
        )
        print(f"   ✓ created {hours_created}")
        print(f"   ✗ errors  {len(hours_errors)}\n")

        # 4. Commit everything atomically — if anything failed badly
        #    above (uncaught), nothing is saved
        await db.commit()
        print("Committed to DB\n")

    # 5. Report problems for the operator to review
    if skipped:
        print("Skipped businesses:")
        for name, err in skipped:
            print(f"   - {name}: {err}")
        print()

    if hours_errors:
        print("Hours errors:")
        for err in hours_errors[:20]:  # cap to avoid wall of text
            print(f"   - {err}")
        if len(hours_errors) > 20:
            print(f"   ... and {len(hours_errors) - 20} more")
        print()

    return 0


if __name__ == "__main__":
    xlsx_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    exit_code = asyncio.run(main(xlsx_arg))
    sys.exit(exit_code)
