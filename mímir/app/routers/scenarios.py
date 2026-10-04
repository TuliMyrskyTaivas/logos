from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Scenario, ScenarioVariable

from models import (
    Scenario as ScenarioModel,
    ScenarioVariable as ScenarioVariableModel,
    Metric as MetricModel,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _to_scenario(scenario: ScenarioModel) -> Scenario:
    return Scenario(
        id=scenario.id,
        code=scenario.code,
        name=scenario.name,
        category=scenario.category,
        description=scenario.description,
        isActive=scenario.is_active,
    )


@router.get("", response_model=list[Scenario])
def list_scenarios(
    isActive: bool | None = None,
    session: Session = Depends(get_db),
) -> list[Scenario]:
    """Return what-if scenarios, optionally filtered by active status."""
    stmt = select(ScenarioModel).order_by(ScenarioModel.id)
    if isActive is not None:
        stmt = stmt.where(ScenarioModel.is_active == isActive)
    scenarios = session.execute(stmt).scalars().all()
    return [_to_scenario(s) for s in scenarios]


@router.get("/{scenarioId}/variables", response_model=list[ScenarioVariable])
def list_scenario_variables(
    scenarioId: int,
    session: Session = Depends(get_db),
) -> list[ScenarioVariable]:
    """Return the metric adjustments that define a scenario."""
    scenario = session.get(ScenarioModel, scenarioId)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    rows = session.execute(
        select(ScenarioVariableModel, MetricModel.code)
        .join(MetricModel, ScenarioVariableModel.metric_id == MetricModel.id)
        .where(ScenarioVariableModel.scenario_id == scenarioId)
    ).all()
    return [
        ScenarioVariable(metricCode=code, operator=var.operator, value=float(var.value))
        for var, code in rows
    ]
