"""translate animal types to ukrainian

Revision ID: 492ac0fc4f1b
Revises: 4370437d6e1e
Create Date: 2026-06-24 21:16:45.459337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '492ac0fc4f1b'
down_revision: Union[str, Sequence[str], None] = '4370437d6e1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    translations = {
        "dog": "Собака",
        "cat": "Кіт",
        "bird": "Птах",
        "rabbit": "Кролик",
        "rodent": "Гризун",
        "reptile": "Рептилія",
        "fish": "Риба",
        "other": "Інше",
    }
    for slug, name_uk in translations.items():
        op.execute(
            sa.text("UPDATE animal_types SET name = :name WHERE slug = :slug").bindparams(
                name=name_uk, slug=slug
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    originals = {
        "dog": "Dog",
        "cat": "Cat",
        "bird": "Bird",
        "rabbit": "Rabbit",
        "rodent": "Rodent",
        "reptile": "Reptile",
        "fish": "Fish",
        "other": "Other",
    }
    for slug, name_en in originals.items():
        op.execute(
            sa.text("UPDATE animal_types SET name = :name WHERE slug = :slug").bindparams(
                name=name_en, slug=slug
            )
        )
