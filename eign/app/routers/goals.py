from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import AssetClass as AssetClassModel
from ..models import Goal as GoalModel
from ..models import GoalAllocation as GoalAllocationModel
from ..models import User as UserModel
from ..reporting import load_performance
from ..schemas import (
    Goal,
    GoalAllocation,
    GoalAllocationProgress,
    GoalProgress,
    GoalUpdate,
)
from ..valuation import convert_to_base, latest_rate_map, value_portfolio

router = APIRouter(prefix="/goals", tags=["goals"])

MONEY = Decimal("0.01")
WEIGHT_TOLERANCE = 1e-6


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _ratio(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _load_goal(session: Session, owner_id: int) -> GoalModel | None:
    return session.execute(
        select(GoalModel).where(GoalModel.owner_id == owner_id)
    ).scalar_one_or_none()


def _allocations(session: Session, goal_id: int) -> list[tuple[int, str, Decimal]]:
    rows = session.execute(
        select(
            GoalAllocationModel.asset_class_id,
            AssetClassModel.code,
            GoalAllocationModel.target_weight,
        )
        .join(AssetClassModel, AssetClassModel.id == GoalAllocationModel.asset_class_id)
        .where(GoalAllocationModel.goal_id == goal_id)
        .order_by(AssetClassModel.sort_order)
    ).all()
    return [(class_id, code, weight) for class_id, code, weight in rows]


def _to_api(session: Session, goal: GoalModel) -> Goal:
    return Goal(
        id=goal.id,
        currency=goal.currency,
        targetTotalValue=_money(goal.target_total_value),
        targetAnnualReturn=(
            float(goal.target_annual_return)
            if goal.target_annual_return is not None
            else None
        ),
        allocations=[
            GoalAllocation(
                assetClassId=class_id,
                assetClassCode=code,
                targetWeight=float(weight),
            )
            for class_id, code, weight in _allocations(session, goal.id)
        ],
        updatedAt=goal.updated_at,
    )


def _validate_allocations(session: Session, payload: GoalUpdate) -> None:
    if not payload.allocations:
        return

    total = sum(item.targetWeight for item in payload.allocations)
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Target weights must sum to 1.0, got {round(total, 6)}",
        )

    ids = [item.assetClassId for item in payload.allocations]
    if len(set(ids)) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Each asset class may appear only once",
        )

    existing = set(
        session.execute(
            select(AssetClassModel.id).where(AssetClassModel.id.in_(ids))
        ).scalars().all()
    )
    missing = sorted(set(ids) - existing)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset classes do not exist: {missing}",
        )


@router.get("", response_model=Goal, summary="Get portfolio goals")
def read_goals(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Goal:
    """Return the goals of the current user; an empty goal when none are set."""
    goal = _load_goal(session, user.id)
    if goal is None:
        return Goal(
            id=None,
            currency=(user.base_currency or "RUB").strip().upper(),
            updatedAt=None,
        )
    return _to_api(session, goal)


@router.put("", response_model=Goal, summary="Save portfolio goals")
def save_goals(
    payload: GoalUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Goal:
    """Create or replace the goals of the current user.

    Allocations are replaced entirely, so the payload is the full target
    distribution. Non-empty weights must sum to 100 %.
    """
    _validate_allocations(session, payload)

    goal = _load_goal(session, user.id)
    if goal is None:
        goal = GoalModel(owner_id=user.id)
        session.add(goal)

    goal.currency = payload.currency.strip().upper()
    goal.target_total_value = (
        Decimal(str(payload.targetTotalValue))
        if payload.targetTotalValue is not None
        else None
    )
    goal.target_annual_return = (
        Decimal(str(payload.targetAnnualReturn))
        if payload.targetAnnualReturn is not None
        else None
    )
    session.flush()

    session.execute(
        delete(GoalAllocationModel).where(GoalAllocationModel.goal_id == goal.id)
    )
    for item in payload.allocations:
        session.add(
            GoalAllocationModel(
                goal_id=goal.id,
                asset_class_id=item.assetClassId,
                target_weight=Decimal(str(item.targetWeight)),
            )
        )

    session.commit()
    session.refresh(goal)
    return _to_api(session, goal)


@router.get(
    "/progress", response_model=GoalProgress, summary="Progress towards the goals"
)
def get_goal_progress(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> GoalProgress:
    """Compare the current portfolio with the target value, weights and return."""
    as_of = date.today()
    base_currency = (user.base_currency or "RUB").strip().upper()
    goal = _load_goal(session, user.id)
    goal_currency = (
        goal.currency.strip().upper() if goal is not None else base_currency
    )

    valuation = value_portfolio(session, user.id, user.base_currency, as_of)
    rates = latest_rate_map(session, {goal_currency, base_currency}, as_of=as_of)

    target_base: Decimal | None = None
    if goal is not None and goal.target_total_value is not None:
        target_base = convert_to_base(
            goal.target_total_value, goal_currency, base_currency, rates
        )

    value_progress = (
        float(valuation.total / target_base)
        if target_base is not None and target_base > 0
        else None
    )
    value_gap: Decimal | None = (
        target_base - valuation.total if target_base is not None else None
    )

    performance = load_performance(
        session, user.id, (user.base_currency or "RUB").strip().upper()
    )
    actual_return = performance.annualized_twr
    target_return = (
        float(goal.target_annual_return)
        if goal is not None and goal.target_annual_return is not None
        else None
    )
    return_gap = (
        actual_return - target_return
        if actual_return is not None and target_return is not None
        else None
    )

    targets: dict[int, Decimal] = {}
    codes: dict[int, str] = {}
    if goal is not None:
        for class_id, code, weight in _allocations(session, goal.id):
            targets[class_id] = weight
            codes[class_id] = code
    for class_id, class_entry in valuation.by_class.items():
        codes.setdefault(class_id, class_entry[0])

    allocations: list[GoalAllocationProgress] = []
    for class_id in sorted(codes):
        target_weight = float(targets.get(class_id, Decimal(0)))
        actual_weight = 0.0
        class_entry = valuation.by_class.get(class_id)
        if class_entry is not None and valuation.total > 0:
            actual_weight = float(class_entry[1] / valuation.total)
        allocations.append(
            GoalAllocationProgress(
                assetClassId=class_id,
                assetClassCode=codes[class_id],
                targetWeight=round(target_weight, 6),
                actualWeight=round(actual_weight, 6),
                delta=round(actual_weight - target_weight, 6),
            )
        )

    return GoalProgress(
        currency=goal_currency,
        baseCurrency=base_currency,
        asOf=as_of,
        targetTotalValue=(
            _money(goal.target_total_value) if goal is not None else None
        ),
        targetTotalValueBase=_money(target_base),
        currentValueBase=_money(valuation.total) or 0.0,
        valueProgress=_ratio(value_progress),
        valueGapBase=_money(value_gap),
        targetAnnualReturn=target_return,
        actualAnnualReturn=_ratio(actual_return),
        returnGap=_ratio(return_gap),
        allocations=allocations,
    )
