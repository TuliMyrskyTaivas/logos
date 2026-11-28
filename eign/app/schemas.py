from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["admin", "user"]
TradeType = Literal["BUY", "SELL"]
PlanStatus = Literal["planned", "executed", "cancelled"]
PlanStatusInput = Literal["planned", "cancelled"]
AssetUnit = Literal["share", "bond", "unit", "RUB", "g", "oz"]
PriceInstrumentType = Literal["ticker", "isin", "metal", "currency"]
IncomeType = Literal["dividend", "coupon", "interest", "other"]

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class Error(BaseModel):
    """Standard error response."""

    message: str


class HealthStatus(BaseModel):
    """Service liveness response."""

    status: str


class User(BaseModel):
    """A portfolio owner as exposed by the API."""

    id: int = Field(description="Database identifier.")
    login: str = Field(description="Login taken from the client certificate CN.")
    role: UserRole = Field(description="Application role.")
    isActive: bool = Field(description="Whether the user may sign in.")
    baseCurrency: str = Field(description="Base currency of the user's portfolio.")
    riskFreeRate: float | None = Field(
        default=None,
        description=(
            "Annual risk-free rate used by Sharpe/Sortino, or null to use the "
            "service default."
        ),
    )
    lastLoginAt: datetime | None = Field(
        default=None, description="Last successful sign-in, or null."
    )


class UserSettingsUpdate(BaseModel):
    """Payload for changing the caller's own portfolio settings."""

    baseCurrency: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z]{3}$",
        description="New base currency of the portfolio (fiat or metal code).",
    )
    riskFreeRate: float | None = Field(
        default=None,
        ge=-1.0,
        le=10.0,
        description="Annual risk-free rate; null restores the service default.",
    )


class UserCreate(BaseModel):
    """Payload for creating a user (administrators only)."""

    login: str = Field(
        min_length=1,
        max_length=128,
        description="Login that must match the CN of the user's certificate.",
    )
    role: UserRole = Field(default="user", description="Initial application role.")


class UserUpdate(BaseModel):
    """Payload for partially updating a user (administrators only)."""

    role: UserRole | None = Field(default=None, description="New application role.")
    isActive: bool | None = Field(
        default=None, description="Set to false to deactivate the user."
    )


class Asset(BaseModel):
    """A portfolio position."""

    id: int = Field(description="Database identifier.")
    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code (EQUITY, BOND, ...).")
    name: str = Field(description="Position name.")
    ticker: str | None = Field(default=None, description="Exchange ticker.")
    isin: str | None = Field(default=None, description="ISIN code.")
    metalCode: str | None = Field(default=None, description="Metal code for METAL positions (XAU, XAG, ...).")
    currency: str = Field(description="Currency of the position.")
    quantity: float = Field(description="Units held; derived from trades.")
    unit: AssetUnit = Field(description="Unit of the quantity.")
    avgPurchasePrice: float | None = Field(
        default=None, description="Weighted average cost per unit, or null."
    )
    currentPrice: float | None = Field(
        default=None, description="Last known price per unit, or null."
    )
    custodian: str | None = Field(default=None, description="Broker or storage.")
    createdAt: datetime = Field(description="Creation timestamp.")
    updatedAt: datetime = Field(description="Last modification timestamp.")


class AssetCreate(BaseModel):
    """Payload for creating a position."""

    assetClassId: int = Field(description="Asset class identifier.")
    name: str = Field(min_length=1, max_length=255, description="Position name.")
    unit: AssetUnit = Field(description="Unit of the quantity.")
    quantity: float = Field(default=0, ge=0, description="Initial quantity.")
    ticker: str | None = Field(default=None, max_length=32, description="Exchange ticker.")
    isin: str | None = Field(default=None, max_length=12, description="ISIN code.")
    metalCode: str | None = Field(
        default=None, max_length=8, description="Metal code; required for METAL."
    )
    currency: str = Field(default="RUB", pattern=CURRENCY_PATTERN, description="Currency.")
    avgPurchasePrice: float | None = Field(
        default=None, ge=0, description="Average purchase price per unit."
    )
    currentPrice: float | None = Field(
        default=None, ge=0, description="Current price per unit."
    )
    custodian: str | None = Field(default=None, max_length=128, description="Broker or storage.")


class AssetUpdate(BaseModel):
    """Payload for partially updating a position."""

    assetClassId: int | None = Field(default=None, description="Asset class identifier.")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit: AssetUnit | None = None
    quantity: float | None = Field(
        default=None, ge=0, description="Only for positions without trades."
    )
    ticker: str | None = Field(default=None, max_length=32)
    isin: str | None = Field(default=None, max_length=12)
    metalCode: str | None = Field(default=None, max_length=8)
    currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    avgPurchasePrice: float | None = Field(
        default=None, ge=0, description="Only for positions without trades."
    )
    currentPrice: float | None = Field(default=None, ge=0)
    custodian: str | None = Field(default=None, max_length=128)


class Trade(BaseModel):
    """A registered buy or sell transaction."""

    id: int = Field(description="Database identifier.")
    assetId: int = Field(description="Position the trade belongs to.")
    tradeType: TradeType = Field(description="BUY or SELL.")
    tradeDate: date = Field(description="Trade date.")
    quantity: float = Field(description="Traded quantity.")
    price: float = Field(description="Price per unit.")
    fee: float = Field(description="Commission paid.")
    currency: str = Field(description="Trade currency.")
    note: str | None = Field(default=None, description="Free-form note.")
    createdAt: datetime = Field(description="Creation timestamp.")


class TradeCreate(BaseModel):
    """Payload for registering a trade."""

    assetId: int = Field(description="Position the trade belongs to.")
    tradeType: TradeType = Field(description="BUY or SELL.")
    tradeDate: date = Field(description="Trade date.")
    quantity: float = Field(gt=0, description="Traded quantity.")
    price: float = Field(ge=0, description="Price per unit.")
    fee: float = Field(default=0, ge=0, description="Commission paid.")
    currency: str | None = Field(
        default=None,
        pattern=CURRENCY_PATTERN,
        description="Defaults to the position currency; a different one is rejected.",
    )
    note: str | None = Field(default=None, max_length=512)


class TradeUpdate(BaseModel):
    """Payload for correcting a trade; the position is recalculated."""

    tradeType: TradeType | None = None
    tradeDate: date | None = None
    quantity: float | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, ge=0)
    fee: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    note: str | None = Field(default=None, max_length=512)


class AssetClassInfo(BaseModel):
    """An entry of the asset class dictionary."""

    id: int = Field(description="Database identifier.")
    code: str = Field(description="Stable code (EQUITY, BOND, REIT, CASH, METAL).")
    name: str = Field(description="Human-readable name.")
    sortOrder: int = Field(description="Display order.")


class TradePlan(BaseModel):
    """A planned purchase or sale for a month."""

    id: int = Field(description="Database identifier.")
    assetId: int | None = Field(default=None, description="Target position, if planned per asset.")
    assetClassId: int | None = Field(default=None, description="Target class, if planned per class.")
    month: date = Field(description="Target month (always the first day of the month).")
    direction: TradeType = Field(description="BUY or SELL.")
    amount: float | None = Field(
        default=None, description="Planned amount in the position currency."
    )
    quantity: float | None = Field(
        default=None,
        description="Planned quantity in units; only for plans attached to a position.",
    )
    filled: float = Field(
        description=(
            "Progress of the month in the same unit as the target: traded units "
            "when `quantity` is set, otherwise the traded amount of the month."
        )
    )
    status: PlanStatus = Field(
        description="planned, executed (reached by the trades of the month) or cancelled."
    )
    note: str | None = Field(default=None, description="Free-form note.")
    createdAt: datetime = Field(description="Creation timestamp.")


class TradePlanCreate(BaseModel):
    """Payload for planning a trade."""

    month: date = Field(description="Target month; normalised to the first day.")
    direction: TradeType = Field(description="BUY or SELL.")
    amount: float | None = Field(
        default=None, gt=0, description="Planned amount; exactly one of amount/quantity."
    )
    quantity: float | None = Field(
        default=None, gt=0, description="Planned quantity; requires assetId."
    )
    assetId: int | None = Field(default=None, description="Target position.")
    assetClassId: int | None = Field(default=None, description="Target class.")
    note: str | None = Field(default=None, max_length=512)


class TradePlanUpdate(BaseModel):
    """Payload for changing a planned trade."""

    month: date | None = Field(default=None, description="Target month; normalised to the first day.")
    direction: TradeType | None = None
    amount: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(
        default=None, gt=0, description="Planned quantity; null clears it."
    )
    assetId: int | None = Field(
        default=None, description="Target position; null clears it."
    )
    assetClassId: int | None = Field(
        default=None, description="Target class; null clears it."
    )
    status: PlanStatusInput | None = None
    note: str | None = Field(default=None, max_length=512)


class GoalAllocation(BaseModel):
    """Target weight of one asset class in the portfolio."""

    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code.")
    targetWeight: float = Field(description="Target share of the portfolio (0..1).")


class Goal(BaseModel):
    """Portfolio goals of the current user."""

    id: int | None = Field(default=None, description="Database identifier; null until saved.")
    currency: str = Field(
        description="Currency of the target value: fiat code or metal code (XAU/XAG, per gram)."
    )
    targetTotalValue: float | None = Field(default=None, description="Target portfolio value.")
    targetAnnualReturn: float | None = Field(
        default=None, description="Target annual return (0.1 = 10 %)."
    )
    allocations: list[GoalAllocation] = Field(
        default_factory=list, description="Target weights by asset class."
    )
    updatedAt: datetime | None = Field(default=None, description="Last update timestamp.")


class GoalAllocationInput(BaseModel):
    """Target weight of one asset class in a goal payload."""

    assetClassId: int = Field(description="Asset class identifier.")
    targetWeight: float = Field(ge=0, le=1, description="Target share of the portfolio.")


class GoalUpdate(BaseModel):
    """Payload for saving portfolio goals; allocations are replaced entirely."""

    currency: str = Field(
        default="RUB",
        pattern=r"^[A-Za-z]{3}$",
        description="Currency of the target value (RUB/USD/… or XAU/XAG per gram).",
    )
    targetTotalValue: float | None = Field(default=None, gt=0)
    targetAnnualReturn: float | None = Field(default=None, ge=-1.0, le=10.0)
    allocations: list[GoalAllocationInput] = Field(default_factory=list)


class GoalAllocationProgress(BaseModel):
    """Comparison of the target and actual weight of an asset class."""

    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code.")
    targetWeight: float = Field(description="Target share (0..1).")
    actualWeight: float = Field(description="Actual share (0..1).")
    delta: float = Field(description="actualWeight - targetWeight.")


class GoalProgress(BaseModel):
    """How far the portfolio is from its goals."""

    currency: str = Field(description="Currency the target value is expressed in.")
    baseCurrency: str = Field(description="Base currency of the portfolio.")
    asOf: date = Field(description="Valuation date.")
    targetTotalValue: float | None = Field(default=None, description="Target value as set.")
    targetTotalValueBase: float | None = Field(
        default=None, description="Target value converted to the base currency."
    )
    currentValueBase: float = Field(description="Current portfolio value in the base currency.")
    valueProgress: float | None = Field(
        default=None, description="currentValueBase / targetTotalValueBase, or null."
    )
    valueGapBase: float | None = Field(
        default=None, description="Remaining amount in the base currency (negative when exceeded)."
    )
    targetAnnualReturn: float | None = Field(default=None, description="Target annual return.")
    actualAnnualReturn: float | None = Field(
        default=None, description="Actual annualised TWR, or null without history."
    )
    returnGap: float | None = Field(
        default=None, description="actualAnnualReturn - targetAnnualReturn."
    )
    allocations: list[GoalAllocationProgress] = Field(
        default_factory=list, description="Target vs actual weights."
    )


class Price(BaseModel):
    """A cached market price or currency rate."""

    id: int = Field(description="Database identifier.")
    instrument: str = Field(description="Ticker, ISIN, metal or currency code.")
    instrumentType: PriceInstrumentType = Field(description="Kind of the instrument.")
    source: str = Field(description="Quote source (manual, moex, cbr, guldvegt).")
    priceDate: date = Field(description="Quote date.")
    price: float = Field(description="Price per unit in `currency`.")
    currency: str = Field(description="Quote currency.")


class PriceCreate(BaseModel):
    """Payload for entering a quote manually."""

    instrument: str = Field(min_length=1, max_length=32, description="Ticker, ISIN or metal code.")
    instrumentType: PriceInstrumentType = Field(description="Kind of the instrument.")
    price: float = Field(gt=0, description="Price per unit.")
    currency: str = Field(default="RUB", pattern=CURRENCY_PATTERN)
    priceDate: date | None = Field(
        default=None, description="Quote date; defaults to today."
    )


class PortfolioPosition(BaseModel):
    """A position valued at the latest known price."""

    assetId: int = Field(description="Database identifier of the position.")
    name: str = Field(description="Position name.")
    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code.")
    currency: str = Field(description="Position currency.")
    quantity: float = Field(description="Units held.")
    price: float | None = Field(default=None, description="Price per unit used for valuation.")
    priceCurrency: str | None = Field(default=None, description="Currency of that price.")
    priceDate: date | None = Field(default=None, description="Date of that price.")
    priceSource: str | None = Field(
        default=None, description="Where the price came from (moex, cbr, guldvegt, manual, cash)."
    )
    value: float | None = Field(default=None, description="Value in the position currency.")
    valueBase: float | None = Field(default=None, description="Value in the base currency.")
    priced: bool = Field(description="Whether the position could be valued.")
    unpricedReason: str | None = Field(
        default=None, description="no_instrument, no_price or no_rate when not priced."
    )


class PortfolioClassSummary(BaseModel):
    """Portfolio value of one asset class."""

    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code.")
    value: float = Field(description="Value in the base currency.")
    weight: float = Field(description="Share of the total value (0..1).")


class PortfolioSummary(BaseModel):
    """Current portfolio valuation."""

    baseCurrency: str = Field(description="Base currency of the portfolio.")
    asOf: date = Field(description="Valuation date.")
    totalValue: float = Field(description="Total value in the base currency.")
    byClass: list[PortfolioClassSummary] = Field(description="Value per asset class.")
    positions: list[PortfolioPosition] = Field(description="Valued positions.")
    unpricedCount: int = Field(description="Positions that could not be valued.")
    incomeYearToDate: float = Field(
        default=0.0, description="Actual income of the current year in the base currency."
    )
    incomePlanYearToDate: float = Field(
        default=0.0, description="Planned income of the current year in the base currency."
    )


class ValuationItem(BaseModel):
    """Value of one asset class inside a stored snapshot."""

    assetClassId: int = Field(description="Asset class identifier.")
    assetClassCode: str = Field(description="Asset class code.")
    value: float = Field(description="Value in the snapshot currency.")


class Valuation(BaseModel):
    """A stored portfolio valuation snapshot."""

    id: int = Field(description="Database identifier.")
    valuationDate: date = Field(description="Date of the snapshot.")
    totalValue: float = Field(description="Total value at that date.")
    currency: str = Field(description="Currency of the snapshot.")
    items: list[ValuationItem] = Field(description="Breakdown by asset class.")
    createdAt: datetime = Field(description="Creation timestamp.")


class MonthlyPerformance(BaseModel):
    """Performance of one sub-period between two snapshots."""

    periodDate: date = Field(description="Snapshot date closing the period.")
    value: float = Field(description="Portfolio value at that date.")
    flow: float = Field(
        description="Net invested money in the period (positive = bought, negative = sold)."
    )
    returnPct: float | None = Field(
        default=None, description="Time-weighted return of the period, or null."
    )


class Performance(BaseModel):
    """Portfolio performance and risk metrics."""

    baseCurrency: str = Field(description="Base currency of the portfolio.")
    asOf: date = Field(description="Date the metrics were requested.")
    periodStart: date | None = Field(default=None, description="First snapshot date.")
    periodEnd: date | None = Field(default=None, description="Last snapshot date.")
    initialValue: float | None = Field(default=None, description="Value at the first snapshot.")
    finalValue: float | None = Field(default=None, description="Value at the last snapshot.")
    contributions: float = Field(description="Money invested during the period.")
    withdrawals: float = Field(description="Money withdrawn during the period.")
    income: float = Field(
        default=0.0, description="Income received during the period (in the base currency)."
    )
    simpleReturn: float | None = Field(
        default=None, description="Simple return over the whole period."
    )
    twr: float | None = Field(default=None, description="Time-weighted return.")
    annualizedTwr: float | None = Field(default=None, description="Annualised TWR.")
    xirr: float | None = Field(default=None, description="Money-weighted return (XIRR).")
    volatility: float | None = Field(
        default=None, description="Annualised volatility of period returns."
    )
    maxDrawdown: float | None = Field(
        default=None, description="Maximum drawdown of the TWR index (negative or zero)."
    )
    sharpe: float | None = Field(default=None, description="Sharpe ratio.")
    sortino: float | None = Field(default=None, description="Sortino ratio.")
    periods: int = Field(description="Number of sub-periods with a computed return.")
    monthly: list[MonthlyPerformance] = Field(description="Per-period details.")


class IncomePlanFact(BaseModel):
    """Planned and actual income of a position (or of the portfolio) per month."""

    id: int = Field(description="Database identifier.")
    assetId: int | None = Field(default=None, description="Income source position, or null.")
    month: date = Field(description="Income month (always the first day).")
    incomeType: IncomeType = Field(description="dividend, coupon, interest or other.")
    currency: str = Field(description="Currency of the amounts.")
    plannedAmount: float | None = Field(default=None, description="Planned amount.")
    actualAmount: float | None = Field(default=None, description="Actual amount received.")
    note: str | None = Field(default=None, description="Free-form note.")


class IncomeCreate(BaseModel):
    """Payload for adding a planned/actual income row."""

    month: date = Field(description="Income month; normalised to the first day.")
    incomeType: IncomeType = Field(description="dividend, coupon, interest or other.")
    assetId: int | None = Field(default=None, description="Income source position.")
    currency: str | None = Field(
        default=None,
        pattern=CURRENCY_PATTERN,
        description="Defaults to the position currency, otherwise the base currency.",
    )
    plannedAmount: float | None = Field(default=None, ge=0)
    actualAmount: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=512)


class IncomeUpdate(BaseModel):
    """Payload for correcting an income row."""

    month: date | None = Field(default=None, description="Income month; normalised to the first day.")
    incomeType: IncomeType | None = None
    assetId: int | None = Field(default=None, description="Income source position; null clears it.")
    currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    plannedAmount: float | None = Field(default=None, ge=0)
    actualAmount: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=512)


class MonthlyIncome(BaseModel):
    """Plan and fact of one month in the base currency."""

    month: date = Field(description="Month (first day).")
    plannedBase: float = Field(description="Planned income converted to the base currency.")
    actualBase: float = Field(description="Actual income converted to the base currency.")
    planCount: int = Field(description="Rows that have a planned amount.")
    factCount: int = Field(description="Rows that have an actual amount.")


class IncomeSummary(BaseModel):
    """Income plan/fact for a year."""

    baseCurrency: str = Field(description="Base currency of the portfolio.")
    year: int = Field(description="Reporting year.")
    months: list[MonthlyIncome] = Field(description="Plan and fact per month.")
    plannedYearToDate: float = Field(description="Planned income for the year so far.")
    actualYearToDate: float = Field(description="Actual income for the year so far.")
    unconvertedCount: int = Field(
        description="Rows skipped because the currency rate is unknown."
    )
