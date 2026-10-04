"""Unit tests for the pydantic request/response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    CompanyCreate,
    CompanyFinancialData,
    CompanyUpdate,
    FinancialDataUpload,
    ForecastEntry,
    ForecastUpload,
    IndustryCreate,
    Scenario,
)


def test_financial_data_upload_roundtrip() -> None:
    payload = FinancialDataUpload(
        companyName="Sber",
        ticker="SBER",
        industryName="Banks",
        metrics={"revenue": {"2023": 1000.0, "2024": None}},
        ratios={"2023": {"Current ratio": 1.5}},
    )
    assert payload.companyName == "Sber"
    assert payload.metrics["revenue"]["2024"] is None


def test_financial_data_upload_requires_company_name() -> None:
    with pytest.raises(ValidationError):
        FinancialDataUpload.model_validate(
            {"ticker": "SBER", "industryName": "Banks", "metrics": {}, "ratios": {}}
        )


def test_company_create_requires_industry_id() -> None:
    with pytest.raises(ValidationError):
        CompanyCreate.model_validate({"name": "Yandex"})


def test_company_create_optional_fields() -> None:
    company = CompanyCreate(name="Yandex", industryId=1)
    assert company.ticker is None
    assert company.inn is None


def test_company_update_exclude_unset() -> None:
    update = CompanyUpdate(inn="7700000000")
    assert update.model_dump(exclude_unset=True) == {"inn": "7700000000"}


def test_company_update_empty() -> None:
    update = CompanyUpdate()
    assert update.model_dump(exclude_unset=True) == {}


def test_industry_create_optional_parent() -> None:
    industry = IndustryCreate(name="Banks", code="BANKS")
    assert industry.parentId is None


def test_scenario_category_nullable() -> None:
    scenario = Scenario(id=1, code="base", name="Base", isActive=True)
    assert scenario.category is None
    assert scenario.description is None


def test_forecast_upload_structure() -> None:
    upload = ForecastUpload(
        forecastYear=2026,
        scenarios=[ForecastEntry(scenarioCode="base", metrics={"revenue": 150.0})],
    )
    assert upload.forecastYear == 2026
    assert upload.scenarios[0].metrics["revenue"] == 150.0


def test_company_financial_data_structure() -> None:
    data = CompanyFinancialData(
        companyId=1,
        companyName="Sber",
        ticker=None,
        metrics={"revenue": {"2023": 1000.0}},
        ratios={},
    )
    assert data.metrics["revenue"]["2023"] == 1000.0
    assert data.ticker is None
