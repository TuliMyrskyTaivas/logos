"""Per-user portfolio settings

Adds the annual risk-free rate the user wants Sharpe/Sortino to use. NULL keeps
the service-wide `EIGN_RISK_FREE_RATE` default, so existing users are unaffected.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-28 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("risk_free_rate", sa.Numeric(precision=6, scale=4), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_users_risk_free_rate",
        "users",
        "risk_free_rate IS NULL OR (risk_free_rate >= -1 AND risk_free_rate <= 10)",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_risk_free_rate", "users", type_="check", schema=SCHEMA)
    op.drop_column("users", "risk_free_rate", schema=SCHEMA)
