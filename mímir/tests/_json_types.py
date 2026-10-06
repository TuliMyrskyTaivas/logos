"""Shared TypedDict schemas for JSON payloads and responses used in tests."""

from __future__ import annotations

from typing import TypedDict


class IndustryJson(TypedDict):
    id: int
    name: str
    code: str
    parentId: int | None


class CompanyJson(TypedDict):
    id: int
    ticker: str | None
    name: str
    inn: str | None
    industryId: int


class FinancialUploadJson(TypedDict):
    companyName: str
    ticker: str
    industryName: str
    metrics: dict[str, dict[str, float | None]]
    ratios: dict[str, dict[str, float | None]]


class ScenarioJson(TypedDict):
    id: int
    code: str
    name: str
    category: str | None
    description: str | None
    isActive: bool


class ForecastEntryJson(TypedDict):
    scenarioCode: str
    metrics: dict[str, float]


class ForecastUploadJson(TypedDict):
    forecastYear: int
    scenarios: list[ForecastEntryJson]
