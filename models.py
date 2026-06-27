from sqlalchemy import (
    ForeignKey, PrimaryKeyConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.sql import func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Industry(Base):
    __tablename__ = 'industries'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    parent_id: Mapped[int] = mapped_column(ForeignKey('industries.id'), nullable=True)
    children = relationship('Industry', backref='parent', remote_side=[id])

class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(nullable=False)
    inn: Mapped[str] = mapped_column(nullable=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey('industries.id'), nullable=False)
    industry = relationship('Industry')

class FiscalPeriod(Base):
    __tablename__ = 'fiscal_periods'
    id: Mapped[int] = mapped_column(primary_key=True)
    end_date: Mapped[datetime] = mapped_column(unique=True, nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    quarter: Mapped[int] = mapped_column(nullable=True)
    period_type: Mapped[str] = mapped_column(nullable=False)  # 'Annual', 'Q1', 'H1' ...

class Metric(Base):
    __tablename__ = 'metrics'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)     # 'P&L', 'BS', 'CF'

class RawFinancial(Base):
    __tablename__ = 'raw_financials'
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey('fiscal_periods.id'), primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey('metrics.id'), primary_key=True)
    value: Mapped[float] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(default='RUB')
    __table_args__ = (
        PrimaryKeyConstraint('company_id', 'period_id', 'metric_id'),
        Index('idx_raw_fin_period_metric', 'period_id', 'metric_id'),
        Index('idx_raw_fin_company_period', 'company_id', 'period_id'),
    )

    company = relationship('Company')
    period = relationship('FiscalPeriod')
    metric = relationship('Metric')

class Ratio(Base):
    __tablename__ = 'ratios'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    formula: Mapped[str] = mapped_column(nullable=True)

class RatioFinancial(Base):
    __tablename__ = 'ratio_financials'
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey('fiscal_periods.id'), primary_key=True)
    ratio_id: Mapped[int] = mapped_column(ForeignKey('ratios.id'), primary_key=True)
    value: Mapped[float] = mapped_column(nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('company_id', 'period_id', 'ratio_id'),
        Index('idx_ratio_ratio_company_period', 'ratio_id', 'company_id', 'period_id'),
    )

    company = relationship('Company')
    period = relationship('FiscalPeriod')
    ratio = relationship('Ratio')

class Scenario(Base):
    __tablename__ = 'scenarios'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    variables = relationship('ScenarioVariable', backref='scenario', cascade='all, delete-orphan')

class ScenarioVariable(Base):
    __tablename__ = 'scenario_variables'
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey('scenarios.id'), nullable=False)
    metric_id: Mapped[int] = mapped_column(ForeignKey('metrics.id'), nullable=False)
    operator: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    __table_args__ = (UniqueConstraint('scenario_id', 'metric_id'),)

    metric = relationship('Metric')

class Forecasts(Base):
    __tablename__ = 'forecasts'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), nullable=False)
    scenario_id: Mapped[int] = mapped_column(ForeignKey('scenarios.id'), nullable=False)
    forecast_year: Mapped[int] = mapped_column(nullable=False)
    metric_id: Mapped[int] = mapped_column(ForeignKey('metrics.id'), nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint('company_id', 'scenario_id', 'forecast_year', 'metric_id'),
        Index('idx_forecast_company_scenario', 'company_id', 'scenario_id', 'forecast_year'),
    )