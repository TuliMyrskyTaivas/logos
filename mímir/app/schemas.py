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


class Industry(BaseModel):
    """An industry classification node."""

    id: int = Field(description="Database identifier.")
    name: str = Field(description="Industry name.")
    code: str = Field(description="Unique industry code.")
    parentId: int | None = Field(default=None, description="Parent industry id, or null for a top-level industry.")


class IndustryCreate(BaseModel):
    """Payload for creating an industry."""

    name: str = Field(description="Industry name.")
    code: str = Field(description="Unique industry code.")
    parentId: int | None = Field(default=None, description="Parent industry id, or null for a top-level industry.")


class IndustryUpdate(BaseModel):
    """Payload for partially updating an industry."""

    name: str | None = Field(default=None, description="Industry name.")
    code: str | None = Field(default=None, description="Unique industry code.")
    parentId: int | None = Field(default=None, description="Parent industry id, or null for a top-level industry.")


class Company(BaseModel):
    """A company linked to an industry."""

    id: int = Field(description="Database identifier.")
    ticker: str | None = Field(default=None, description="Exchange ticker symbol.")
    name: str = Field(description="Company name.")
    inn: str | None = Field(default=None, description="Russian tax identification number (INN).")
    industryId: int = Field(description="Id of the industry the company belongs to.")


class CompanyCreate(BaseModel):
    """Payload for creating a company."""

    ticker: str | None = Field(default=None, description="Exchange ticker symbol.")
    name: str = Field(description="Company name.")
    inn: str | None = Field(default=None, description="Russian tax identification number (INN).")
    industryId: int = Field(description="Id of the industry the company belongs to.")


class CompanyUpdate(BaseModel):
    """Payload for partially updating a company."""

    ticker: str | None = Field(default=None, description="Exchange ticker symbol.")
    name: str | None = Field(default=None, description="Company name.")
    inn: str | None = Field(default=None, description="Russian tax identification number (INN).")
    industryId: int | None = Field(default=None, description="Id of the industry the company belongs to.")
