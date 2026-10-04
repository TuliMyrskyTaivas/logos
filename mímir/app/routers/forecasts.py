from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ForecastUpload, ForecastUploadResult

from models import (
    Company as CompanyModel,
    Forecasts,
    Metric as MetricModel,
    Scenario as ScenarioModel,
)

router = APIRouter(prefix="/companies", tags=["forecasts"])

logger = logging.getLogger(__name__)


@router.put(
    "/{companyId}/forecasts",
    response_model=ForecastUploadResult,
    status_code=status.HTTP_201_CREATED,
)
def upload_forecasts(
    companyId: int,
    payload: ForecastUpload,
    session: Session = Depends(get_db),
) -> ForecastUploadResult:
    """Upsert forecasted metric values for a company and forecast year."""
    company = session.get(CompanyModel, companyId)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    scenario_count = 0
    metric_count = 0
    for entry in payload.scenarios:
        scenario = session.execute(
            select(ScenarioModel).where(ScenarioModel.code == entry.scenarioCode)
        ).scalar_one_or_none()
        if scenario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario '{entry.scenarioCode}' not found",
            )
        scenario_count += 1

        for code, value in entry.metrics.items():
            metric = session.execute(
                select(MetricModel).where(MetricModel.code == code)
            ).scalar_one_or_none()
            if metric is None:
                logger.warning("metric '%s' not found, skipping", code)
                continue

            existing = session.execute(
                select(Forecasts).where(
                    Forecasts.company_id == companyId,
                    Forecasts.scenario_id == scenario.id,
                    Forecasts.forecast_year == payload.forecastYear,
                    Forecasts.metric_id == metric.id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.value = value
            else:
                session.add(
                    Forecasts(
                        company_id=companyId,
                        scenario_id=scenario.id,
                        forecast_year=payload.forecastYear,
                        metric_id=metric.id,
                        value=value,
                    )
                )
            metric_count += 1

    session.commit()
    return ForecastUploadResult(
        companyId=companyId,
        forecastYear=payload.forecastYear,
        scenarioCount=scenario_count,
        metricCount=metric_count,
    )
