"""seed initial services

Revision ID: 568b98589285
Revises: f5bc17ad478e
Create Date: 2026-04-30 13:22:16.824759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '568b98589285'
down_revision: Union[str, Sequence[str], None] = 'f5bc17ad478e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert initial services for each business category."""
    bind = op.get_bind()

    # Look up category IDs by slug
    result = bind.execute(
        sa.text("SELECT id, slug FROM business_categories")
    ).mappings().all()
    category_id_by_slug = {row["slug"]: row["id"] for row in result}

    # Services grouped by category — easier to read and extend
    services_by_category = {
    "vet_clinic": [    
        ("vaccination", "Vaccination"),
        ("surgery", "Surgery"),
        ("diagnostics", "Diagnostics"),
        ("emergency_care", "Emergency Care"),
        ("dental", "Dental Care"),
        ("ultrasound", "Ultrasound"),
        ("xray", "X-Ray"),
        ("lab_tests", "Laboratory Tests"),
    ],
    "grooming": [
        ("haircut", "Haircut"),
        ("bath", "Bath & Wash"),
        ("nail_trim", "Nail Trimming"),
        ("ear_cleaning", "Ear Cleaning"),
    ],
    "pet_shop": [
        ("food", "Food"),
        ("accessories", "Accessories"),
        ("toys", "Toys"),
    ],
}

    # Build the rows with proper category_id and sort_order
    rows = []
    for category_slug, services in services_by_category.items():
        for index, (slug, name) in enumerate(services):
            rows.append({
                "slug": slug,
                "name": name,
                "category_id": category_id_by_slug[category_slug],
                "sort_order": (index + 1) * 10,
                "is_active": True,
            })

    services_table = sa.table(
        "services",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("category_id", sa.Integer),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(services_table, rows)



def downgrade() -> None:
    """Remove initial services."""
    op.execute(
        "DELETE FROM services WHERE slug IN ("
        "'vaccination', 'surgery', 'diagnostics', 'emergency_care', 'dental', "
        "'ultrasound', 'xray', 'lab_tests', "
        "'haircut', 'bath', 'nail_trim', 'ear_cleaning', "
        "'food', 'accessories', 'toys'"
        ")"
    )
