from sqlalchemy import (
    Column, Integer, String, Date, Numeric, Boolean, ForeignKey, PrimaryKeyConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Industry(Base):
    __tablename__ = 'industries'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey('industries.id'), nullable=True)
    children = relationship('Industry', backref='parent', remote_side=[id])

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    name = Column(String, nullable=False)
    inn = Column(String)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    industry = relationship('Industry')

class FiscalPeriod(Base):
    __tablename__ = 'fiscal_periods'
    id = Column(Integer, primary_key=True)
    end_date = Column(Date, unique=True, nullable=False)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=True)
    period_type = Column(String, nullable=False)  # 'Annual', 'Q1', 'H1' ...

class Metric(Base):
    __tablename__ = 'metrics'
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)     # 'P&L', 'BS', 'CF'

class RawFinancial(Base):
    __tablename__ = 'raw_financials'
    company_id = Column(Integer, ForeignKey('companies.id'), primary_key=True)
    period_id = Column(Integer, ForeignKey('fiscal_periods.id'), primary_key=True)
    metric_id = Column(Integer, ForeignKey('metrics.id'), primary_key=True)
    value = Column(Numeric)
    currency = Column(String, default='RUB')
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
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    formula = Column(String, nullable=True)

class RatioFinancial(Base):
    __tablename__ = 'ratio_financials'
    company_id = Column(Integer, ForeignKey('companies.id'), primary_key=True)
    period_id = Column(Integer, ForeignKey('fiscal_periods.id'), primary_key=True)
    ratio_id = Column(Integer, ForeignKey('ratios.id'), primary_key=True)
    value = Column(Numeric, nullable=False)
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
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    variables = relationship('ScenarioVariable', backref='scenario', cascade='all, delete-orphan')


class ScenarioVariable(Base):
    __tablename__ = 'scenario_variables'
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    metric_id = Column(Integer, ForeignKey('metrics.id'), nullable=False)
    operator = Column(String, nullable=False)
    value = Column(Numeric, nullable=True)
    __table_args__ = (UniqueConstraint('scenario_id', 'metric_id'),)

    metric = relationship('Metric')

class Forecasts(Base):
    __tablename__ = 'forecasts'
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    forecast_year = Column(Integer, nullable=False)
    metric_id = Column(String, ForeignKey('metrics.id'), nullable=False)
    value = Column(Numeric)
    __table_args__ = (
        UniqueConstraint('company_id', 'scenario_id', 'forecast_year', 'metric_id'),
        Index('idx_forecast_company_scenario', 'company_id', 'scenario_id', 'forecast_year'),
    )