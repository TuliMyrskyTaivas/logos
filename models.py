from sqlalchemy import (
    Column, Integer, BigInteger, String, Numeric, Date,
    TIMESTAMP, Boolean, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), unique=True, nullable=False)
    legal_name = Column(String(255), nullable=False)
    country = Column(String(100))
    industry = Column(String(100))
    created_at = Column(TIMESTAMP, default=datetime.now(timezone.utc))

    # relationships
    reporting_periods = relationship("ReportingPeriod", back_populates="company")


class ReportType(Base):
    __tablename__ = "report_type"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)

    reporting_periods = relationship("ReportingPeriod", back_populates="report_type")


class ReportingPeriod(Base):
    __tablename__ = "reporting_period"

    id = Column(Integer, primary_key=True)
    period_year = Column(Integer, nullable=False)
    period_end_date = Column(Date, nullable=False)
    report_type_id = Column(Integer, ForeignKey("report_type.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    is_audited = Column(Boolean, default=True)
    published_date = Column(Date)

    __table_args__ = (
        UniqueConstraint("company_id", "period_year", "report_type_id",
                        name="uq_company_period_report"),
    )

    # relationships
    company = relationship("Company", back_populates="reporting_periods")
    report_type = relationship("ReportType", back_populates="reporting_periods")
    statement_values = relationship("FinancialStatementValue", back_populates="reporting_period")
    ratio_values = relationship("CalculatedRatioValue", back_populates="reporting_period")


class FinancialStatementLine(Base):
    __tablename__ = "financial_statement_line"

    id = Column(Integer, primary_key=True)
    line_code = Column(String(50), unique=True, nullable=False)
    line_name = Column(String(255), nullable=False)
    statement_type = Column(String(20), nullable=False)  # 'balance', 'pl', 'cf'
    parent_id = Column(Integer, ForeignKey("financial_statement_line.id"))
    calculation_formula = Column(Text)

    # relationships
    parent = relationship("FinancialStatementLine", remote_side=[id])
    values = relationship("FinancialStatementValue", back_populates="line")


class FinancialStatementValue(Base):
    __tablename__ = "financial_statement_value"

    id = Column(BigInteger, primary_key=True)
    reporting_period_id = Column(Integer, ForeignKey("reporting_period.id"), nullable=False)
    line_id = Column(Integer, ForeignKey("financial_statement_line.id"), nullable=False)
    value = Column(Numeric(28, 2), nullable=False)
    currency = Column(String(3), default="RUB")

    __table_args__ = (
        UniqueConstraint("reporting_period_id", "line_id",
                        name="uq_period_line"),
    )

    # relationships
    reporting_period = relationship("ReportingPeriod", back_populates="statement_values")
    line = relationship("FinancialStatementLine", back_populates="values")


class FinancialRatio(Base):
    __tablename__ = "financial_ratio"

    id = Column(Integer, primary_key=True)
    ratio_code = Column(String(50), unique=True, nullable=False)
    ratio_name = Column(String(255), nullable=False)
    formula = Column(Text)
    normalization_min = Column(Numeric(5, 2))
    normalization_max = Column(Numeric(5, 2))
    interpretation = Column(Text)

    ratio_values = relationship("CalculatedRatioValue", back_populates="ratio")


class CalculatedRatioValue(Base):
    __tablename__ = "calculated_ratio_value"

    id = Column(BigInteger, primary_key=True)
    reporting_period_id = Column(Integer, ForeignKey("reporting_period.id"), nullable=False)
    ratio_id = Column(Integer, ForeignKey("financial_ratio.id"), nullable=False)
    value = Column(Numeric(20, 6), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("reporting_period_id", "ratio_id",
                        name="uq_period_ratio"),
    )

    # relationships
    reporting_period = relationship("ReportingPeriod", back_populates="ratio_values")
    ratio = relationship("FinancialRatio", back_populates="ratio_values")


class DataSource(Base):
    __tablename__ = "data_source"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text)
    reliability = Column(Integer, default=5)
