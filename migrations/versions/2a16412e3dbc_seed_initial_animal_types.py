"""seed initial animal types

Revision ID: 2a16412e3dbc
Revises: 3c0e6db85dfb
Create Date: 2026-04-25 20:37:23.130733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a16412e3dbc'
down_revision: Union[str, Sequence[str], None] = '3c0e6db85dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert initial animal types"""
    animal_types_table = sa.table(
        "animal_types",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        animal_types_table,
        [
          {"slug": "dog", "name": "Dog", "sort_order": 10, "is_active": True},
            {"slug": "cat", "name": "Cat", "sort_order": 20, "is_active": True},
            {"slug": "bird", "name": "Bird", "sort_order": 30, "is_active": True},
            {"slug": "rabbit", "name": "Rabbit", "sort_order": 40, "is_active": True},
            {"slug": "rodent", "name": "Rodent", "sort_order": 50, "is_active": True},
            {"slug": "reptile", "name": "Reptile", "sort_order": 60, "is_active": True},
            {"slug": "fish", "name": "Fish", "sort_order": 70, "is_active": True},
            {"slug": "other", "name": "Other", "sort_order": 999, "is_active": True},
        ],
    )


def downgrade() -> None:
    """Remove initial animal types"""
    op.execute(
        "DELETE FROM animal_types WHERE slug IN "
        "('dog', 'cat', 'bird', 'rabbit', 'rodent', 'reptile', 'fish', 'other')"
    )
