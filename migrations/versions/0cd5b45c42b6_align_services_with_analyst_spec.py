"""align services with analyst spec

Revision ID: 0cd5b45c42b6
Revises: 4553f8c02b28
Create Date: 2026-05-29 16:34:28.035180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0cd5b45c42b6'
down_revision: Union[str, Sequence[str], None] = '4553f8c02b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Align services with what the analyst's CSV uses.

    Changes:
    - Add `checkup` and `castration` to vet_clinic
    - Add `pharmacy` to pet_shop
    - Rename `bath` -> `bathing`, `nail_trim` -> `nail_trimming` in grooming
    - Deactivate `diagnostics`, `emergency_care` (vet), `toys` (pet_shop)
      because the analyst's data doesn't use them
    """
    bind = op.get_bind()

    # 1. Find category ids by slug
    categories = bind.execute(
        sa.text("SELECT id, slug FROM business_categories")
    ).mappings().all()
    cat_id = {row["slug"]: row["id"] for row in categories}

    # 2. Add new services
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
            # vet_clinic — checkup goes between vaccination(10) and surgery(20)
            {
                "slug": "checkup",
                "name": "Огляд",
                "category_id": cat_id["vet_clinic"],
                "sort_order": 15,
                "is_active": True,
            },
            # vet_clinic — castration after microchipping(90)
            {
                "slug": "castration",
                "name": "Кастрація / стерилізація",
                "category_id": cat_id["vet_clinic"],
                "sort_order": 100,
                "is_active": True,
            },
            # pet_shop — pharmacy between food(?) and accessories(?)
            {
                "slug": "pharmacy",
                "name": "Ветаптека",
                "category_id": cat_id["pet_shop"],
                "sort_order": 15,
                "is_active": True,
            },
        ],
    )

    # 3. Rename slugs in grooming
    op.execute("UPDATE services SET slug = 'bathing' WHERE slug = 'bath'")
    op.execute("UPDATE services SET slug = 'nail_trimming' WHERE slug = 'nail_trim'")

    # 4. Deactivate unused services
    op.execute(
        "UPDATE services SET is_active = false "
        "WHERE slug IN ('diagnostics', 'emergency_care', 'toys')"
    )


def downgrade() -> None:
    """Revert services alignment."""
    # 1. Re-activate deactivated services
    op.execute(
        "UPDATE services SET is_active = true "
        "WHERE slug IN ('diagnostics', 'emergency_care', 'toys')"
    )

    # 2. Revert renamed slugs
    op.execute("UPDATE services SET slug = 'bath' WHERE slug = 'bathing'")
    op.execute("UPDATE services SET slug = 'nail_trim' WHERE slug = 'nail_trimming'")

    # 3. Remove added services
    op.execute(
        "DELETE FROM services WHERE slug IN ('checkup', 'castration', 'pharmacy')"
    )
