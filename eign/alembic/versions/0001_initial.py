"""Initial eign schema, database roles and seed data

Creates the `eign` schema of the shared Logos database, the two technical
database roles (`eign_frontend` for API requests, `eign_backend` for
background jobs) with strictly separated privileges, all service tables and
the `asset_classes` dictionary.

Revision ID: 0001
Revises:
Create Date: 2025-11-21 10:00:00.000000
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "eign"
FRONTEND_ROLE = "eign_frontend"
BACKEND_ROLE = "eign_backend"


def _get_password(env_name: str) -> str:
    """Read a role password from the environment (never hardcode secrets)."""
    password = os.environ.get(env_name)
    if not password:
        raise ValueError(f"Environment variable {env_name} is not set")
    return password


def _quote_ident(value: str) -> str:
    """Quote a PostgreSQL identifier."""
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    """Quote a PostgreSQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _create_role(bind: Connection, role: str, password: str) -> None:
    """Create a login role unless it already exists (idempotent)."""
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
    ).scalar()
    if exists:
        return
    bind.execute(
        sa.text(f"CREATE ROLE {_quote_ident(role)} LOGIN PASSWORD {_quote_literal(password)}")
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- Schema and technical roles -------------------------------------
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    _create_role(bind, FRONTEND_ROLE, _get_password("EIGN_FRONTEND_PASSWORD"))
    _create_role(bind, BACKEND_ROLE, _get_password("EIGN_BACKEND_PASSWORD"))

    database = bind.engine.url.database
    if database:
        op.execute(
            f"GRANT CONNECT ON DATABASE {_quote_ident(database)} "
            f"TO {FRONTEND_ROLE}, {BACKEND_ROLE}"
        )

    # --- Dictionary tables ----------------------------------------------
    op.create_table(
        "asset_classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id", name="pk_asset_classes"),
        sa.UniqueConstraint("code", name="uq_asset_classes_code"),
        schema=SCHEMA,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default=sa.text("'user'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "base_currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("login", name="uq_users_login"),
        schema=SCHEMA,
    )

    # --- Portfolio tables -----------------------------------------------
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("asset_class_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("metal_code", sa.String(length=8), nullable=True),
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        sa.Column(
            "quantity", sa.Numeric(precision=20, scale=8), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("avg_purchase_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("custodian", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_assets_quantity"),
        sa.ForeignKeyConstraint(
            ["asset_class_id"], [f"{SCHEMA}.asset_classes.id"], name="fk_assets_asset_class"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_assets_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.UniqueConstraint("owner_id", "name", name="uq_assets_owner_name"),
        schema=SCHEMA,
    )
    op.create_index("ix_assets_owner", "assets", ["owner_id"], schema=SCHEMA)

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("trade_type", sa.String(length=8), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "fee", sa.Numeric(precision=20, scale=8), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("trade_type IN ('BUY', 'SELL')", name="ck_trades_type"),
        sa.CheckConstraint("quantity > 0", name="ck_trades_quantity"),
        sa.CheckConstraint("price >= 0", name="ck_trades_price"),
        sa.CheckConstraint("fee >= 0", name="ck_trades_fee"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.assets.id"],
            name="fk_trades_asset",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_trades_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trades"),
        schema=SCHEMA,
    )
    op.create_index("ix_trades_owner_date", "trades", ["owner_id", "trade_date"], schema=SCHEMA)
    op.create_index("ix_trades_asset", "trades", ["asset_id"], schema=SCHEMA)

    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("target_total_value", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("target_annual_return", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_goals_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_goals"),
        sa.UniqueConstraint("owner_id", name="uq_goals_owner"),
        schema=SCHEMA,
    )

    op.create_table(
        "goal_allocations",
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("asset_class_id", sa.Integer(), nullable=False),
        sa.Column("target_weight", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.CheckConstraint(
            "target_weight >= 0 AND target_weight <= 1",
            name="ck_goal_allocations_weight",
        ),
        sa.ForeignKeyConstraint(
            ["asset_class_id"],
            [f"{SCHEMA}.asset_classes.id"],
            name="fk_goal_allocations_asset_class",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            [f"{SCHEMA}.goals.id"],
            name="fk_goal_allocations_goal",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("goal_id", "asset_class_id", name="pk_goal_allocations"),
        schema=SCHEMA,
    )

    op.create_table(
        "valuations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        sa.Column(
            "created_by",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'backend'"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_valuations_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_valuations"),
        sa.UniqueConstraint("owner_id", "valuation_date", name="uq_valuations_owner_date"),
        schema=SCHEMA,
    )

    op.create_table(
        "valuation_items",
        sa.Column("valuation_id", sa.Integer(), nullable=False),
        sa.Column("asset_class_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_class_id"],
            [f"{SCHEMA}.asset_classes.id"],
            name="fk_valuation_items_asset_class",
        ),
        sa.ForeignKeyConstraint(
            ["valuation_id"],
            [f"{SCHEMA}.valuations.id"],
            name="fk_valuation_items_valuation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("valuation_id", "asset_class_id", name="pk_valuation_items"),
        schema=SCHEMA,
    )

    op.create_table(
        "trade_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("asset_class_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'planned'"),
        ),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("direction IN ('BUY', 'SELL')", name="ck_trade_plan_direction"),
        sa.CheckConstraint(
            "status IN ('planned', 'executed', 'cancelled')", name="ck_trade_plan_status"
        ),
        sa.CheckConstraint(
            "asset_class_id IS NOT NULL OR asset_id IS NOT NULL",
            name="ck_trade_plan_target",
        ),
        sa.ForeignKeyConstraint(
            ["asset_class_id"],
            [f"{SCHEMA}.asset_classes.id"],
            name="fk_trade_plan_asset_class",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.assets.id"],
            name="fk_trade_plan_asset",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_trade_plan_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            [f"{SCHEMA}.trades.id"],
            name="fk_trade_plan_trade",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trade_plan"),
        schema=SCHEMA,
    )
    op.create_index("ix_trade_plan_owner_month", "trade_plan", ["owner_id", "month"], schema=SCHEMA)

    op.create_table(
        "income_plan_fact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("income_type", sa.String(length=16), nullable=False),
        sa.Column("planned_amount", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("actual_amount", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.CheckConstraint(
            "income_type IN ('dividend', 'coupon', 'interest', 'other')",
            name="ck_income_plan_fact_type",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.assets.id"],
            name="fk_income_plan_fact_asset",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_income_plan_fact_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_income_plan_fact"),
        sa.UniqueConstraint(
            "owner_id",
            "asset_id",
            "month",
            "income_type",
            name="uq_income_plan_fact_owner_asset_month_type",
            postgresql_nulls_not_distinct=True,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_income_plan_fact_owner_month",
        "income_plan_fact",
        ["owner_id", "month"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_income_plan_fact_asset_month",
        "income_plan_fact",
        ["asset_id", "month"],
        schema=SCHEMA,
    )

    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "currency", sa.CHAR(length=3), nullable=False, server_default=sa.text("'RUB'")
        ),
        sa.CheckConstraint(
            "instrument_type IN ('ticker', 'isin', 'metal')",
            name="ck_prices_instrument_type",
        ),
        sa.CheckConstraint(
            "source IN ('moex', 'cbr', 'guldvegt', 'manual')", name="ck_prices_source"
        ),
        sa.CheckConstraint("price >= 0", name="ck_prices_price"),
        sa.PrimaryKeyConstraint("id", name="pk_prices"),
        sa.UniqueConstraint(
            "instrument", "source", "price_date", name="uq_prices_instrument_source_date"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_prices_instrument_date", "prices", ["instrument", "price_date"], schema=SCHEMA
    )

    # --- Seed data -------------------------------------------------------
    asset_classes = sa.table(
        "asset_classes",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        schema=SCHEMA,
    )
    op.bulk_insert(
        asset_classes,
        [
            {"id": 1, "code": "EQUITY", "name": "Акции", "sort_order": 10},
            {"id": 2, "code": "BOND", "name": "Облигации", "sort_order": 20},
            {"id": 3, "code": "REIT", "name": "Паевые фонды (REIT)", "sort_order": 30},
            {"id": 4, "code": "CASH", "name": "Наличные на счетах", "sort_order": 40},
            {"id": 5, "code": "METAL", "name": "Драгоценные металлы", "sort_order": 50},
        ],
    )
    # Rows were inserted with explicit ids, so advance the identity sequence.
    op.execute(
        f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.asset_classes', 'id'), "
        f"(SELECT COALESCE(MAX(id), 1) FROM {SCHEMA}.asset_classes))"
    )

    # --- Privileges ------------------------------------------------------
    # Pseudo-role split required by the specification: the API layer
    # (eign_frontend) writes trades and positions but never valuations;
    # background jobs (eign_backend) write valuations and prices only.
    op.execute(
        f"GRANT USAGE ON SCHEMA {SCHEMA} TO {FRONTEND_ROLE}, {BACKEND_ROLE}"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {SCHEMA} "
        f"TO {FRONTEND_ROLE}, {BACKEND_ROLE}"
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "
        f"{SCHEMA}.users, {SCHEMA}.assets, {SCHEMA}.trades, {SCHEMA}.goals, "
        f"{SCHEMA}.goal_allocations, {SCHEMA}.trade_plan, "
        f"{SCHEMA}.income_plan_fact, {SCHEMA}.asset_classes TO {FRONTEND_ROLE}"
    )
    op.execute(
        f"GRANT SELECT ON TABLE {SCHEMA}.valuations, {SCHEMA}.valuation_items TO {FRONTEND_ROLE}"
    )
    op.execute(f"GRANT SELECT, INSERT ON TABLE {SCHEMA}.prices TO {FRONTEND_ROLE}")

    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO {BACKEND_ROLE}")
    op.execute(
        "GRANT INSERT, UPDATE ON TABLE "
        f"{SCHEMA}.valuations, {SCHEMA}.valuation_items, {SCHEMA}.prices TO {BACKEND_ROLE}"
    )

    op.execute(f"ALTER ROLE {FRONTEND_ROLE} SET search_path TO {SCHEMA}, public")
    op.execute(f"ALTER ROLE {BACKEND_ROLE} SET search_path TO {SCHEMA}, public")


def downgrade() -> None:
    bind = op.get_bind()
    database = bind.engine.url.database
    if database:
        op.execute(
            f"REVOKE ALL ON DATABASE {_quote_ident(database)} "
            f"FROM {FRONTEND_ROLE}, {BACKEND_ROLE}"
        )
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    op.execute(f"DROP ROLE IF EXISTS {FRONTEND_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {BACKEND_ROLE}")
