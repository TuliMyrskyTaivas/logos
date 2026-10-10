from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Industry, IndustryCreate, IndustryUpdate

from models import Industry as IndustryModel, Company as CompanyModel

router = APIRouter(prefix="/industries", tags=["industries"])


def _to_industry(industry: IndustryModel) -> Industry:
    return Industry(
        id=industry.id,
        name=industry.name,
        code=industry.code,
        parentId=industry.parent_id,
    )


@router.get("", response_model=list[Industry])
def list_industries(
    id: int | None = None,
    name: str | None = None,
    session: Session = Depends(get_db),
) -> list[Industry]:
    """Return industries, optionally filtered by id or name."""
    stmt = select(IndustryModel).order_by(IndustryModel.id)
    if id is not None:
        stmt = stmt.where(IndustryModel.id == id)
    if name is not None:
        stmt = stmt.where(IndustryModel.name == name)
    industries = session.execute(stmt).scalars().all()
    return [_to_industry(i) for i in industries]


@router.post("", response_model=Industry, status_code=status.HTTP_201_CREATED)
def create_industry(payload: IndustryCreate, session: Session = Depends(get_db)) -> Industry:
    """Create a new industry classification node."""
    existing = session.execute(
        select(IndustryModel).where(IndustryModel.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Industry code '{payload.code}' already exists",
        )

    if payload.parentId is not None:
        parent = session.get(IndustryModel, payload.parentId)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent industry {payload.parentId} not found",
            )

    industry = IndustryModel(
        name=payload.name,
        code=payload.code,
        parent_id=payload.parentId,
    )
    session.add(industry)
    session.commit()
    session.refresh(industry)
    return _to_industry(industry)


@router.patch("/{industryId}", response_model=Industry)
def update_industry(
    industryId: int,
    payload: IndustryUpdate,
    session: Session = Depends(get_db),
) -> Industry:
    """Update fields of an existing industry."""
    industry = session.get(IndustryModel, industryId)
    if industry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found")

    data = payload.model_dump(exclude_unset=True)

    if "code" in data:
        existing = session.execute(
            select(IndustryModel).where(
                IndustryModel.code == data["code"],
                IndustryModel.id != industryId,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Industry code '{data['code']}' already exists",
            )

    if data.get("parentId") is not None:
        parent_id = data["parentId"]
        if parent_id == industryId:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An industry cannot be its own parent",
            )
        parent = session.get(IndustryModel, parent_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent industry {parent_id} not found",
            )

    for field, value in data.items():
        if field == "parentId":
            industry.parent_id = value
        else:
            setattr(industry, field, value)

    session.commit()
    session.refresh(industry)
    return _to_industry(industry)


@router.delete("/{industryId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_industry(industryId: int, session: Session = Depends(get_db)) -> None:
    """Delete an industry. Fails if it still has children or companies."""
    industry = session.get(IndustryModel, industryId)
    if industry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found")

    child_count = session.execute(
        select(func.count()).select_from(IndustryModel).where(IndustryModel.parent_id == industryId)
    ).scalar_one()
    company_count = session.execute(
        select(func.count()).select_from(CompanyModel).where(CompanyModel.industry_id == industryId)
    ).scalar_one()
    if child_count or company_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Industry still has child industries or companies",
        )

    session.delete(industry)
    session.commit()
