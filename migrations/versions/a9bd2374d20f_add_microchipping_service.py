"""add microchipping service

Revision ID: a9bd2374d20f
Revises: d081c07cf258
Create Date: 2026-05-22 ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9bd2374d20f'
down_revision: Union[str, Sequence[str], None] = 'd081c07cf258'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'microchipping' service to the vet_clinic category."""
    bind = op.get_bind()

    # Find vet_clinic category id
    vet_category = bind.execute(
        sa.text("SELECT id FROM business_categories WHERE slug = 'vet_clinic'")
    ).scalar_one()

    # Find the highest current sort_order for vet_clinic services
    # to append the new service after existing ones
    max_sort = bind.execute(
        sa.text(
            "SELECT COALESCE(MAX(sort_order), 0) FROM services "
            "WHERE category_id = :cid"
        ),
        {"cid": vet_category},
    ).scalar_one()

    services_table = sa.table(
        "services",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("category_id", sa.Integer),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        services_table,
        [
            {
                "slug": "microchipping",
                "name": "Microchipping",
                "category_id": vet_category,
                "sort_order": max_sort + 10,
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    """Remove 'microchipping' service."""
    op.execute("DELETE FROM services WHERE slug = 'microchipping'")
