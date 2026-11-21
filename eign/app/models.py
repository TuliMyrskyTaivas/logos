from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# All Eign tables live in a dedicated schema of the shared Logos database.
SCHEMA = "eign"

# Monetary amounts and quantities: 20 significant digits with 8 decimals is
# enough for both rouble values and fractional units (grams, fund units).
MONEY = Numeric(20, 8)


class Base(DeclarativeBase):
    """Declarative base of the Eign schema."""


class AssetClass(Base):
    """Dictionary of asset classes (EQUITY, BOND, REIT, CASH, METAL)."""

    __tablename__ = "asset_classes"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class User(Base):
    """Portfolio owner. The login is the CN of the client X.509 certificate."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'user'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    base_currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    assets: Mapped[list[Asset]] = relationship(back_populates="owner", passive_deletes=True)


class Asset(Base):
    """A portfolio position: units held, purchase and current price."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_assets_owner_name"),
        CheckConstraint("quantity >= 0", name="ck_assets_quantity"),
        Index("ix_assets_owner", "owner_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False
    )
    asset_class_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.asset_classes.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    metal_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default=text("0"))
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    avg_purchase_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    custodian: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship(back_populates="assets")
    asset_class: Mapped[AssetClass] = relationship()
    trades: Mapped[list[Trade]] = relationship(back_populates="asset", passive_deletes=True)


class Trade(Base):
    """A registered buy or sell transaction."""

    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("trade_type IN ('BUY', 'SELL')", name="ck_trades_type"),
        CheckConstraint("quantity > 0", name="ck_trades_quantity"),
        CheckConstraint("price >= 0", name="ck_trades_price"),
        CheckConstraint("fee >= 0", name="ck_trades_fee"),
        Index("ix_trades_owner_date", "owner_id", "trade_date"),
        Index("ix_trades_asset", "asset_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.assets.id", ondelete="CASCADE"), nullable=False
    )
    trade_type: Mapped[str] = mapped_column(String(8), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped[Asset] = relationship(back_populates="trades")


class Goal(Base):
    """Portfolio targets: total value and target annual return."""

    __tablename__ = "goals"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Fiat code or metal code (XAU/XAG): the target value may be expressed in gold.
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    target_total_value: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    target_annual_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    allocations: Mapped[list[GoalAllocation]] = relationship(
        back_populates="goal", passive_deletes=True
    )


class GoalAllocation(Base):
    """Target weight of an asset class inside a goal."""

    __tablename__ = "goal_allocations"
    __table_args__ = (
        CheckConstraint(
            "target_weight >= 0 AND target_weight <= 1", name="ck_goal_allocations_weight"
        ),
        {"schema": SCHEMA},
    )

    goal_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.goals.id", ondelete="CASCADE"), primary_key=True
    )
    asset_class_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.asset_classes.id"), primary_key=True
    )
    target_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)

    goal: Mapped[Goal] = relationship(back_populates="allocations")
    asset_class: Mapped[AssetClass] = relationship()


class Valuation(Base):
    """Monthly portfolio valuation snapshot written by background tasks."""

    __tablename__ = "valuations"
    __table_args__ = (
        UniqueConstraint("owner_id", "valuation_date", name="uq_valuations_owner_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    created_by: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'backend'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list[ValuationItem]] = relationship(
        back_populates="valuation", passive_deletes=True
    )


class ValuationItem(Base):
    """Value of one asset class inside a valuation snapshot."""

    __tablename__ = "valuation_items"
    __table_args__ = ({"schema": SCHEMA},)

    valuation_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.valuations.id", ondelete="CASCADE"), primary_key=True
    )
    asset_class_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.asset_classes.id"), primary_key=True
    )
    value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    valuation: Mapped[Valuation] = relationship(back_populates="items")
    asset_class: Mapped[AssetClass] = relationship()


class TradePlan(Base):
    """Planned purchase or sale of an asset class or a specific asset."""

    __tablename__ = "trade_plan"
    __table_args__ = (
        CheckConstraint("direction IN ('BUY', 'SELL')", name="ck_trade_plan_direction"),
        CheckConstraint(
            "status IN ('planned', 'cancelled')", name="ck_trade_plan_status"
        ),
        CheckConstraint(
            "asset_class_id IS NOT NULL OR asset_id IS NOT NULL",
            name="ck_trade_plan_target",
        ),
        CheckConstraint(
            "(amount IS NULL) <> (quantity IS NULL)",
            name="ck_trade_plan_target_amount",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0", name="ck_trade_plan_quantity_positive"
        ),
        CheckConstraint(
            "quantity IS NULL OR asset_id IS NOT NULL",
            name="ck_trade_plan_quantity_target",
        ),
        Index("ix_trade_plan_owner_month", "owner_id", "month"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False
    )
    asset_class_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.asset_classes.id"), nullable=True
    )
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.assets.id", ondelete="CASCADE"), nullable=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    # Stored status is only `planned` or `cancelled`; `executed` is derived
    # from the trades of the month when the plan is read.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'planned'")
    )
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IncomePlanFact(Base):
    """Planned and actual income of a position for a month."""

    __tablename__ = "income_plan_fact"
    __table_args__ = (
        CheckConstraint(
            "income_type IN ('dividend', 'coupon', 'interest', 'other')",
            name="ck_income_plan_fact_type",
        ),
        UniqueConstraint(
            "owner_id",
            "asset_id",
            "month",
            "income_type",
            name="uq_income_plan_fact_owner_asset_month_type",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_income_plan_fact_owner_month", "owner_id", "month"),
        Index("ix_income_plan_fact_asset_month", "asset_id", "month"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.assets.id", ondelete="SET NULL"), nullable=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    income_type: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
    planned_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    actual_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Price(Base):
    """Market price cache: tickers/ISINs/metals from external sources."""

    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint(
            "instrument_type IN ('ticker', 'isin', 'metal', 'currency')",
            name="ck_prices_instrument_type",
        ),
        CheckConstraint(
            "source IN ('moex', 'cbr', 'guldvegt', 'manual')", name="ck_prices_source"
        ),
        CheckConstraint("price >= 0", name="ck_prices_price"),
        UniqueConstraint(
            "instrument", "source", "price_date", name="uq_prices_instrument_source_date"
        ),
        Index("ix_prices_instrument_date", "instrument", "price_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'RUB'")
    )
