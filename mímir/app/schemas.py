from __future__ import annotations

from pydantic import BaseModel, Field

# JSON-friendly representations of the `add_financial_data` arguments.
# `metrics` is metric code -> {year: value};
# `ratios` is year -> {ratio name: value}.


class FinancialDataUpload(BaseModel):
    """IFRS financial data for a single company."""

    companyName: str = Field(description="Full name of the company.")
    ticker: str = Field(description="Exchange ticker symbol.")
    industryName: str = Field(description="Industry name; must already exist.")
    metrics: dict[str, dict[str, float | None]] = Field(
        description="Metric code -> (fiscal year -> value)."
    )
    ratios: dict[str, dict[str, float | None]] = Field(
        description="Fiscal year -> (ratio name -> value)."
    )


class FinancialDataUploadResult(BaseModel):
    """Summary of a successful financial data upload."""

    companyId: int
    companyName: str
    ticker: str
    metricCount: int
    ratioCount: int


class Error(BaseModel):
    """Standard error response."""

    message: str
