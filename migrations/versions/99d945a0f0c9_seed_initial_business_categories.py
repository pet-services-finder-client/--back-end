"""seed initial business categories

Revision ID: 99d945a0f0c9
Revises: 2a5e6f8b4876
Create Date: 2026-04-30 13:02:33.030561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99d945a0f0c9'
down_revision: Union[str, Sequence[str], None] = '2a5e6f8b4876'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert initial business categories."""
    business_categories_table = sa.table(
        "business_categories",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        business_categories_table,
        [
            {"slug": "vet_clinic", "name": "Veterinary Clinic", "sort_order": 10, "is_active": True},
            {"slug": "grooming", "name": "Grooming Salon", "sort_order": 20, "is_active": True},
            {"slug": "pet_shop", "name": "Pet Shop", "sort_order": 30, "is_active": True},
        ],
    )


def downgrade() -> None:
    """Remove initial business categories."""
    op.execute(
        "DELETE FROM business_categories WHERE slug IN "
        "('vet_clinic', 'grooming', 'pet_shop')"
    )
