import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from models import (
    Industry, Company, Metric, FiscalPeriod,
    RawFinancial, Ratio, RatioFinancial
)

def add_financial_data(
    session: Session,
    company_name: str,
    industry_name: str,
    metrics_data: dict[str, pd.Series],
    ratios_data: pd.DataFrame
) -> None:
    """
    Saves / updates financial metrics (IFRS) and ratios for a single company.
    Parameters
    ----------
    session : Session
        Active SQLAlchemy session.
    company_name : str
        Name of the company.
    industry_name : str
        Name of the industry. If the industry does not exist in the DB, a new one is created (code is generated automatically from the name).
    metrics_data : dict[str, pd.Series]
        Dictionary mapping metric names to pandas Series with years as the index and metric values as the data.
    ratios_data : pd.DataFrame
        DataFrame with years as the index and ratio names as the columns.
    """
    # 1. Industry: search or create
    industry = session.query(Industry).filter_by(name=industry_name).first()
    if not industry:
        code = industry_name.upper().replace(' ', '_')
        industry = Industry(name=industry_name, code=code)
        session.add(industry)
        session.flush()  # получить id до вставки компании

    # 2. Company: search or create
    company = session.query(Company).filter_by(
        name=company_name, industry_id=industry.id
    ).first()
    if not company:
        company = Company(name=company_name, industry_id=industry.id)
        session.add(company)
        session.flush()

    # Auxiliary function to get or create a fiscal period
    def get_or_create_period(year: int) -> FiscalPeriod:
        end_date = date(year, 12, 31)
        period = session.query(FiscalPeriod).filter_by(end_date=end_date).first()
        if not period:
            period = FiscalPeriod(
                end_date=end_date,
                year=year,
                quarter=None,
                period_type='Annual'
            )
            session.add(period)
            session.flush()
        return period

    # 3. Processing absolute metrics
    for metric_name, series in metrics_data.items():
        # Search or create the metric
        metric = session.query(Metric).filter_by(code=metric_name).first()
        if not metric:
            # Assume the name is unique; generate the code automatically
            print (f"Metric {metric_name} not found in DB. Creating new metric.")
            metric = Metric(
                code=metric_name,
                name=metric_name,
                category='P&L'  # TODO: Determine category based on metric name or other logic
            )
            session.add(metric)
            session.flush()

        for idx, value in series.items():
            if pd.isna(value):
                continue
            year = int(idx)
            period = get_or_create_period(year)

            # Upsert в raw_financials
            raw = session.query(RawFinancial).filter_by(
                company_id=company.id,
                period_id=period.id,
                metric_id=metric.id
            ).first()
            if raw:
                raw.value = value
            else:
                session.add(RawFinancial(
                    company_id=company.id,
                    period_id=period.id,
                    metric_id=metric.id,
                    value=value,
                    currency='RUB'
                ))

    # 4. Processing ratios
    for ratio_name in ratios_data.columns:
        ratio_code = str(ratio_name).strip().lower().replace(' ', '_').replace('-', '_')
        ratio = session.query(Ratio).filter(
            (Ratio.code == ratio_code) | (Ratio.name == ratio_name)
        ).first()
        if not ratio:
            print (f"Ratio {ratio_name} not found in DB. Creating new ratio.")
            next_ratio_id = (session.query(func.max(Ratio.id)).scalar() or 0) + 1
            ratio = Ratio(
                id=next_ratio_id,
                code=ratio_code,
                name=ratio_name
            )
            session.add(ratio)
            session.flush()

        for year, value in ratios_data[ratio_name].items():
            if pd.isna(value):
                continue
            year = int(year)
            period = get_or_create_period(year)

            # Upsert в ratio_financials
            rat = session.query(RatioFinancial).filter_by(
                company_id=company.id,
                period_id=period.id,
                ratio_id=ratio.id
            ).first()
            if rat:
                rat.value = value
            else:
                session.add(RatioFinancial(
                    company_id=company.id,
                    period_id=period.id,
                    ratio_id=ratio.id,
                    value=value
                ))

    session.flush()