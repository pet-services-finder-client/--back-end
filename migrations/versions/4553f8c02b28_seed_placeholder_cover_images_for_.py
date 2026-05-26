"""seed placeholder cover images for businesses

Revision ID: 4553f8c02b28
Revises: 4d46e83c1195
Create Date: 2026-05-26 12:09:03.933516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4553f8c02b28'
down_revision: Union[str, Sequence[str], None] = '4d46e83c1195'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set Picsum placeholder cover_image_url for businesses without one.
    use Picsum (https://picsum.photos) because:
    - Stable: no 404s, always serves an image
    - Deterministic: seed=<business_id> gives the same photo per business
    - Fast: lightweight CDN
    """
    bind = op.get_bind()

    # Find businesses that don't have a cover image yet — don't overwrite
    # any URL the user (or admin) may have already provided
    rows = bind.execute(
        sa.text("SELECT id FROM businesses WHERE cover_image_url IS NULL")
    ).all()

    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE businesses SET cover_image_url = :url WHERE id = :id"
            ),
            {
                "url": f"https://picsum.photos/seed/{row.id}/600/400",
                "id": row.id,
            },
        )


def downgrade() -> None:
    """Revert only our Picsum placeholders, leaving any real URLs untouched."""
    op.execute(
        "UPDATE businesses SET cover_image_url = NULL "
        "WHERE cover_image_url LIKE 'https://picsum.photos/seed/%'"
    )
