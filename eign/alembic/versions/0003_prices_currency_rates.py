"""Currency rates in the price cache

Adds `currency` to the allowed instrument types so CBR rates can be cached in
the same table, and lets the API layer correct a manually entered quote.

Revision ID: 0003
Revises: 0002
Create Date: 2025-11-21 13:20:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    op.drop_constraint("ck_prices_instrument_type", "prices", schema=SCHEMA)
    op.create_check_constraint(
        "ck_prices_instrument_type",
        "prices",
        "instrument_type IN ('ticker', 'isin', 'metal', 'currency')",
        schema=SCHEMA,
    )
    # The API writes manual quotes and may correct them on the same day.
    op.execute(f"GRANT UPDATE ON TABLE {SCHEMA}.prices TO eign_frontend")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ON TABLE {SCHEMA}.prices FROM eign_frontend")
    op.execute(
        f"DELETE FROM {SCHEMA}.prices WHERE instrument_type = 'currency'"
    )
    op.drop_constraint("ck_prices_instrument_type", "prices", schema=SCHEMA)
    op.create_check_constraint(
        "ck_prices_instrument_type",
        "prices",
        "instrument_type IN ('ticker', 'isin', 'metal')",
        schema=SCHEMA,
    )
