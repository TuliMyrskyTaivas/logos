"""Accumulate trade plan execution across trades

Replaces the single `trade_id` link with cumulative execution: a plan is
considered executed when the trades of its month reach its target. Adds an
optional `quantity` target for plans expressed in units ("buy 100 units") and
keeps only `planned` / `cancelled` as stored statuses; `executed` is derived
from the trade history when a plan is read.

A plan attached to a position is deleted together with that position instead
of being turned into a class-level plan, because a unit target has no meaning
without the position.

Revision ID: 0002
Revises: 0001
Create Date: 2025-11-21 10:34:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"


def upgrade() -> None:
    # Stored `executed` rows become derived; reset them so the narrowed
    # status constraint can be applied.
    op.execute(f"UPDATE {SCHEMA}.trade_plan SET status = 'planned' WHERE status = 'executed'")
    op.drop_constraint("ck_trade_plan_status", "trade_plan", schema=SCHEMA)
    op.create_check_constraint(
        "ck_trade_plan_status", "trade_plan", "status IN ('planned', 'cancelled')", schema=SCHEMA
    )

    op.drop_constraint("fk_trade_plan_trade", "trade_plan", schema=SCHEMA)
    op.drop_column("trade_plan", "trade_id", schema=SCHEMA)

    op.add_column(
        "trade_plan", sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=True), schema=SCHEMA
    )
    # A plan is expressed either in money or in units, never in both.
    op.alter_column(
        "trade_plan",
        "amount",
        existing_type=sa.Numeric(precision=20, scale=8),
        nullable=True,
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_trade_plan_target_amount",
        "trade_plan",
        "(amount IS NULL) <> (quantity IS NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_trade_plan_quantity_positive",
        "trade_plan",
        "quantity IS NULL OR quantity > 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_trade_plan_quantity_target",
        "trade_plan",
        "quantity IS NULL OR asset_id IS NOT NULL",
        schema=SCHEMA,
    )

    op.drop_constraint("fk_trade_plan_asset", "trade_plan", schema=SCHEMA)
    op.create_foreign_key(
        "fk_trade_plan_asset",
        "trade_plan",
        "assets",
        ["asset_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_trade_plan_asset", "trade_plan", schema=SCHEMA)
    op.create_foreign_key(
        "fk_trade_plan_asset",
        "trade_plan",
        "assets",
        ["asset_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )

    op.drop_constraint("ck_trade_plan_quantity_target", "trade_plan", schema=SCHEMA)
    op.drop_constraint("ck_trade_plan_quantity_positive", "trade_plan", schema=SCHEMA)
    op.drop_constraint("ck_trade_plan_target_amount", "trade_plan", schema=SCHEMA)
    # Unit-only plans have no amount; the previous schema required it.
    op.execute(f"UPDATE {SCHEMA}.trade_plan SET amount = 0 WHERE amount IS NULL")
    op.alter_column(
        "trade_plan",
        "amount",
        existing_type=sa.Numeric(precision=20, scale=8),
        nullable=False,
        schema=SCHEMA,
    )
    op.drop_column("trade_plan", "quantity", schema=SCHEMA)

    op.add_column(
        "trade_plan", sa.Column("trade_id", sa.Integer(), nullable=True), schema=SCHEMA
    )
    op.create_foreign_key(
        "fk_trade_plan_trade",
        "trade_plan",
        "trades",
        ["trade_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )

    op.drop_constraint("ck_trade_plan_status", "trade_plan", schema=SCHEMA)
    op.create_check_constraint(
        "ck_trade_plan_status",
        "trade_plan",
        "status IN ('planned', 'executed', 'cancelled')",
        schema=SCHEMA,
    )
