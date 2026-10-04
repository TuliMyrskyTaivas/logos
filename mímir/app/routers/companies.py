from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Company, CompanyCreate, CompanyUpdate

from models import (
    Company as CompanyModel,
    Industry as IndustryModel,
    Forecasts,
    RawFinancial,
    RatioFinancial,
)

router = APIRouter(prefix="/companies", tags=["companies"])


def _to_company(company: CompanyModel) -> Company:
    return Company(
        id=company.id,
        ticker=company.ticker,
        name=company.name,
        inn=company.inn,
        industryId=company.industry_id,
    )


@router.get("", response_model=list[Company])
def list_companies(
    industryId: int | None = None,
    session: Session = Depends(get_db),
) -> list[Company]:
    """Return companies, optionally filtered by industry."""
    stmt = select(CompanyModel).order_by(CompanyModel.id)
    if industryId is not None:
        stmt = stmt.where(CompanyModel.industry_id == industryId)
    companies = session.execute(stmt).scalars().all()
    return [_to_company(c) for c in companies]


@router.post("", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, session: Session = Depends(get_db)) -> Company:
    """Create a new company linked to an industry."""
    industry = session.get(IndustryModel, payload.industryId)
    if industry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Industry {payload.industryId} does not exist",
        )

    company = CompanyModel(
        name=payload.name,
        ticker=payload.ticker,
        inn=payload.inn,
        industry_id=payload.industryId,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return _to_company(company)


@router.patch("/{companyId}", response_model=Company)
def update_company(
    companyId: int,
    payload: CompanyUpdate,
    session: Session = Depends(get_db),
) -> Company:
    """Update fields of an existing company."""
    company = session.get(CompanyModel, companyId)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    data = payload.model_dump(exclude_unset=True)

    if "industryId" in data:
        industry = session.get(IndustryModel, data["industryId"])
        if industry is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Industry {data['industryId']} does not exist",
            )

    for field, value in data.items():
        if field == "industryId":
            company.industry_id = value
        else:
            setattr(company, field, value)

    session.commit()
    session.refresh(company)
    return _to_company(company)


@router.delete("/{companyId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(companyId: int, session: Session = Depends(get_db)) -> None:
    """Delete a company and its financial data."""
    company = session.get(CompanyModel, companyId)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    session.execute(delete(Forecasts).where(Forecasts.company_id == companyId))
    session.execute(delete(RawFinancial).where(RawFinancial.company_id == companyId))
    session.execute(delete(RatioFinancial).where(RatioFinancial.company_id == companyId))
    session.delete(company)
    session.commit()
