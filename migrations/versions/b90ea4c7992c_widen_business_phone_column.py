"""widen business phone column

Revision ID: b90ea4c7992c
Revises: 0cd5b45c42b6
Create Date: 2026-05-29 18:37:55.390620

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b90ea4c7992c'
down_revision: Union[str, Sequence[str], None] = '0cd5b45c42b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen businesses.phone from VARCHAR(50) to VARCHAR(255).
    
    Analyst's data has multiple comma-separated phone numbers
    (e.g. "(073) 226 06 66,(068) 316 00 16,..."). Max observed
    is 63 chars, but 255 gives comfortable headroom without
    losing the type's safety guarantees.
    """
    op.alter_column(
        "businesses",
        "phone",
        existing_type=sa.String(50),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert businesses.phone to VARCHAR(50).
    
    WARNING: Will fail if any row has phone > 50 chars.
    Run after deleting such rows.
    """
    op.alter_column(
        "businesses",
        "phone",
        existing_type=sa.String(255),
        type_=sa.String(50),
        existing_nullable=True,
    )
