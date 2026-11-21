"""Monthly portfolio valuation snapshots.

Revision ID: 0004
Revises: 0003
Create Date: 2025-11-21 13:50:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    # A recomputed snapshot may no longer contain an asset class, so the
    # background role needs to delete stale per-class rows.
    op.execute(
        f"GRANT DELETE ON TABLE {SCHEMA}.valuation_items TO eign_backend"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE DELETE ON TABLE {SCHEMA}.valuation_items FROM eign_backend"
    )
