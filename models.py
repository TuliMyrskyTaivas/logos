from sqlalchemy import (
    Column, Integer, String, Date, Numeric, ForeignKey, PrimaryKeyConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship

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