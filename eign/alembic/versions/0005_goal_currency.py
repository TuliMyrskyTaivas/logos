"""Goal currency

The target portfolio value may be expressed not only in a fiat currency but
also in a metal (XAU/XAG), so the goal needs its own currency code.

Revision ID: 0005
Revises: 0004
Create Date: 2025-11-21 14:05:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("goals", "currency", schema=SCHEMA)
