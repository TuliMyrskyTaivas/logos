from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import Asset as AssetModel
from ..models import IncomePlanFact as IncomeModel
from ..models import User as UserModel
from ..reporting import income_monthly_totals
from ..schemas import (
    IncomeCreate,
    IncomePlanFact,
    IncomeSummary,
    IncomeType,
    IncomeUpdate,
    MonthlyIncome,
)

router = APIRouter(prefix="/income", tags=["income"])

MONEY = Decimal("0.01")


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _to_api(row: IncomeModel) -> IncomePlanFact:
    return IncomePlanFact(
        id=row.id,
        assetId=row.asset_id,
        month=row.month,
        incomeType=cast(IncomeType, row.income_type),
        currency=row.currency,
        plannedAmount=(
            float(row.planned_amount) if row.planned_amount is not None else None
        ),
        actualAmount=float(row.actual_amount) if row.actual_amount is not None else None,
        note=row.note,
    )


def _get_owned(session: Session, owner_id: int, income_id: int) -> IncomeModel:
    row = session.execute(
        select(IncomeModel).where(
            IncomeModel.id == income_id, IncomeModel.owner_id == owner_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Income entry not found"
        )
    return row


def _get_asset(session: Session, owner_id: int, asset_id: int) -> AssetModel:
    asset = session.execute(
        select(AssetModel).where(
            AssetModel.id == asset_id, AssetModel.owner_id == owner_id
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    return asset


def _ensure_amounts(planned: Decimal | None, actual: Decimal | None) -> None:
    if planned is None and actual is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one of plannedAmount or actualAmount is required",
        )


def _ensure_unique(
    session: Session,
    owner_id: int,
    asset_id: int | None,
    month: date,
    income_type: str,
    exclude_id: int | None = None,
) -> None:
    stmt = select(IncomeModel.id).where(
        IncomeModel.owner_id == owner_id,
        IncomeModel.month == month,
        IncomeModel.income_type == income_type,
    )
    stmt = stmt.where(
        IncomeModel.asset_id.is_(None) if asset_id is None else IncomeModel.asset_id == asset_id
    )
    if exclude_id is not None:
        stmt = stmt.where(IncomeModel.id != exclude_id)
    if session.execute(stmt.limit(1)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Income for this position, month and type already exists; "
                "update the existing entry instead"
            ),
        )


@router.get("", response_model=list[IncomePlanFact], summary="List income plan/fact rows")
def list_income(
    assetId: int | None = None,
    year: int | None = None,
    incomeType: IncomeType | None = None,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[IncomePlanFact]:
    """Return income rows, newest month first."""
    stmt = (
        select(IncomeModel)
        .where(IncomeModel.owner_id == user.id)
        .order_by(IncomeModel.month.desc(), IncomeModel.id.desc())
    )
    if assetId is not None:
        stmt = stmt.where(IncomeModel.asset_id == assetId)
    if year is not None:
        stmt = stmt.where(
            IncomeModel.month >= date(year, 1, 1), IncomeModel.month <= date(year, 12, 31)
        )
    if incomeType is not None:
        stmt = stmt.where(IncomeModel.income_type == incomeType)
    rows = session.execute(stmt).scalars().all()
    return [_to_api(row) for row in rows]


@router.get("/summary", response_model=IncomeSummary, summary="Plan/fact summary by month")
def get_income_summary(
    year: int | None = Query(default=None, ge=2000, le=2200),
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> IncomeSummary:
    """Return plan/fact totals per month of a year in the base currency."""
    base_currency = (user.base_currency or "RUB").strip().upper()
    report_year = year or date.today().year
    totals, unconverted = income_monthly_totals(
        session, user.id, base_currency, year=report_year, as_of=date.today()
    )

    return IncomeSummary(
        baseCurrency=base_currency,
        year=report_year,
        months=[
            MonthlyIncome(
                month=item.month,
                plannedBase=_money(item.planned),
                actualBase=_money(item.actual),
                planCount=item.plan_count,
                factCount=item.fact_count,
            )
            for item in totals
        ],
        plannedYearToDate=_money(sum((item.planned for item in totals), Decimal(0))),
        actualYearToDate=_money(sum((item.actual for item in totals), Decimal(0))),
        unconvertedCount=unconverted,
    )


@router.post(
    "",
    response_model=IncomePlanFact,
    status_code=status.HTTP_201_CREATED,
    summary="Add an income row",
)
def create_income(
    payload: IncomeCreate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> IncomePlanFact:
    """Record planned and/or actual income of a position for a month."""
    asset = (
        _get_asset(session, user.id, payload.assetId)
        if payload.assetId is not None
        else None
    )
    month = payload.month.replace(day=1)
    planned = (
        Decimal(str(payload.plannedAmount))
        if payload.plannedAmount is not None
        else None
    )
    actual = (
        Decimal(str(payload.actualAmount))
        if payload.actualAmount is not None
        else None
    )
    _ensure_amounts(planned, actual)
    _ensure_unique(session, user.id, asset.id if asset else None, month, payload.incomeType)

    currency = (
        payload.currency
        or (asset.currency if asset is not None else user.base_currency)
    ).strip().upper()

    row = IncomeModel(
        owner_id=user.id,
        asset_id=asset.id if asset is not None else None,
        month=month,
        income_type=payload.incomeType,
        currency=currency,
        planned_amount=planned,
        actual_amount=actual,
        note=payload.note,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_api(row)


@router.patch("/{incomeId}", response_model=IncomePlanFact, summary="Correct an income row")
def update_income(
    incomeId: int,
    payload: IncomeUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> IncomePlanFact:
    """Change amounts or details of an income row."""
    row = _get_owned(session, user.id, incomeId)
    data = payload.model_dump(exclude_unset=True)

    if "assetId" in data:
        if data["assetId"] is None:
            row.asset_id = None
        else:
            row.asset_id = _get_asset(session, user.id, data["assetId"]).id
    if data.get("month") is not None:
        row.month = data["month"].replace(day=1)
    if data.get("incomeType") is not None:
        row.income_type = data["incomeType"]
    if data.get("currency") is not None:
        row.currency = data["currency"].strip().upper()
    if "plannedAmount" in data:
        row.planned_amount = (
            Decimal(str(data["plannedAmount"]))
            if data["plannedAmount"] is not None
            else None
        )
    if "actualAmount" in data:
        row.actual_amount = (
            Decimal(str(data["actualAmount"]))
            if data["actualAmount"] is not None
            else None
        )
    if "note" in data:
        row.note = data["note"]

    _ensure_amounts(row.planned_amount, row.actual_amount)
    _ensure_unique(
        session,
        user.id,
        row.asset_id,
        row.month,
        row.income_type,
        exclude_id=row.id,
    )

    session.commit()
    session.refresh(row)
    return _to_api(row)


@router.delete(
    "/{incomeId}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an income row"
)
def delete_income(
    incomeId: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> None:
    """Delete an income row."""
    row = _get_owned(session, user.id, incomeId)
    session.delete(row)
    session.commit()
