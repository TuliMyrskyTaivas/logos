"""Income currency

Income rows get an explicit currency: it defaults to the position currency but
may differ (e.g. a distribution paid in another currency).

Revision ID: 0006
Revises: 0005
Create Date: 2025-11-21 14:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    op.add_column(
        "income_plan_fact",
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("income_plan_fact", "currency", schema=SCHEMA)
