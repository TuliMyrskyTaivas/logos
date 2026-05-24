from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, List
import pandas as pd
from decimal import Decimal

from models import (
    Company, ReportType, ReportingPeriod, FinancialStatementLine,
    FinancialStatementValue, FinancialRatio, CalculatedRatioValue
)


class FinancialDataAPI:
    """API для загрузки финансовых данных в нормализованную БД"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== РАБОТА С КОМПАНИЯМИ ====================

    def get_or_create_company(self, ticker: str, legal_name: str,
                               country: str = None, industry: str = None) -> Company:
        """Получить или создать компанию"""
        company = self.db.execute(
            select(Company).where(Company.ticker == ticker)
        ).scalar_one_or_none()

        if not company:
            company = Company(
                ticker=ticker,
                legal_name=legal_name,
                country=country,
                industry=industry
            )
            self.db.add(company)
            self.db.flush()

        return company

    def get_or_create_report_type(self, name: str, description: str = None) -> ReportType:
        """Получить или создать тип отчёта"""
        report_type = self.db.execute(
            select(ReportType).where(ReportType.name == name)
        ).scalar_one_or_none()

        if not report_type:
            report_type = ReportType(name=name, description=description)
            self.db.add(report_type)
            self.db.flush()

        return report_type

    def get_or_create_reporting_period(self, company_id: int, period_year: int,
                                        period_end_date: str, report_type_id: int,
                                        is_audited: bool = True) -> ReportingPeriod:
        """Получить или создать отчётный период"""
        period = self.db.execute(
            select(ReportingPeriod).where(
                ReportingPeriod.company_id == company_id,
                ReportingPeriod.period_year == period_year,
                ReportingPeriod.report_type_id == report_type_id
            )
        ).scalar_one_or_none()

        if not period:
            period = ReportingPeriod(
                company_id=company_id,
                period_year=period_year,
                period_end_date=period_end_date,
                report_type_id=report_type_id,
                is_audited=is_audited
            )
            self.db.add(period)
            self.db.flush()

        return period

    # ==================== РАБОТА СО СТРОКАМИ ОТЧЁТОВ ====================

    def get_or_create_line(self, line_code: str, line_name: str,
                           statement_type: str) -> FinancialStatementLine:
        """Получить или создать строку отчёта"""
        line = self.db.execute(
            select(FinancialStatementLine).where(
                FinancialStatementLine.line_code == line_code
            )
        ).scalar_one_or_none()

        if not line:
            line = FinancialStatementLine(
                line_code=line_code,
                line_name=line_name,
                statement_type=statement_type
            )
            self.db.add(line)
            self.db.flush()

        return line

    def add_statement_values(self, reporting_period_id: int,
                             values_dict: Dict[str, float]) -> List[FinancialStatementValue]:
        """
        Добавить значения статей отчёта
        values_dict: {'line_code': value, ...}
        """
        added = []
        for line_code, value in values_dict.items():
            # Находим строку по коду
            line = self.db.execute(
                select(FinancialStatementLine).where(
                    FinancialStatementLine.line_code == line_code
                )
            ).scalar_one_or_none()

            if not line:
                raise ValueError(f"Line with code '{line_code}' not found")

            # Проверяем, существует ли уже значение
            existing = self.db.execute(
                select(FinancialStatementValue).where(
                    FinancialStatementValue.reporting_period_id == reporting_period_id,
                    FinancialStatementValue.line_id == line.id
                )
            ).scalar_one_or_none()

            if existing:
                # Обновляем существующее
                existing.value = Decimal(str(value))
                added.append(existing)
            else:
                # Создаём новое
                stmt_value = FinancialStatementValue(
                    reporting_period_id=reporting_period_id,
                    line_id=line.id,
                    value=Decimal(str(value))
                )
                self.db.add(stmt_value)
                added.append(stmt_value)

        self.db.flush()
        return added

    # ==================== ЗАГРУЗКА ИЗ PANDAS SERIES ====================

    def load_from_pandas_series(self,
                                 company_ticker: str,
                                 company_name: str,
                                 period_year: int,
                                 period_end_date: str,
                                 series: pd.Series,
                                 line_mapping: Dict[str, str]) -> int:
        """
        Загрузить данные из pandas.Series с показателями по годам

        Args:
            company_ticker: Тикер компании
            company_name: Полное название
            period_year: Год отчёта
            period_end_date: Дата окончания периода
            series: pandas.Series с индексами = названия показателей
            line_mapping: mapping {'название_в_series': 'line_code'}

        Returns:
            reporting_period_id
        """
        # 1. Создаём компанию
        company = self.get_or_create_company(company_ticker, company_name)

        # 2. Создаём тип отчёта (МСФО)
        report_type = self.get_or_create_report_type("IFRS", "Международные стандарты")

        # 3. Создаём отчётный период
        period = self.get_or_create_reporting_period(
            company_id=company.id,
            period_year=period_year,
            period_end_date=period_end_date,
            report_type_id=report_type.id
        )

        # 4. Формируем словарь значений для загрузки
        values_dict = {}
        for series_name, line_code in line_mapping.items():
            if series_name in series.index and pd.notna(series[series_name]):
                values_dict[line_code] = float(series[series_name])

        # 5. Добавляем значения
        self.add_statement_values(period.id, values_dict)

        self.db.commit()
        return period.id

    def load_ratios_from_dataframe(self,
                                    company_ticker: str,
                                    ratios_df: pd.DataFrame,
                                    period_col: str = "period_year") -> List[int]:
        """
        Загрузить рассчитанные коэффициенты из pandas.DataFrame

        Args:
            company_ticker: Тикер компании
            ratios_df: DataFrame с колонками:
                - period_year: год
                - ratio_code: код коэффициента
                - value: значение
            period_col: название колонки с годом

        Returns:
            Список ID записей coefficients
        """
        # Находим компанию
        company = self.db.execute(
            select(Company).where(Company.ticker == company_ticker)
        ).scalar_one_or_none()

        if not company:
            raise ValueError(f"Company {company_ticker} not found")

        report_type = self.db.execute(
            select(ReportType).where(ReportType.name == "IFRS")
        ).scalar_one()

        added_ids = []

        for _, row in ratios_df.iterrows():
            period_year = int(row[period_col])
            ratio_code = row["ratio_code"]
            value = float(row["value"])

            # Находим отчётный период
            period = self.db.execute(
                select(ReportingPeriod).where(
                    ReportingPeriod.company_id == company.id,
                    ReportingPeriod.period_year == period_year,
                    ReportingPeriod.report_type_id == report_type.id
                )
            ).scalar_one_or_none()

            if not period:
                print(f"Warning: Period {period_year} not found for {company_ticker}, skipping ratio {ratio_code}")
                continue

            # Находим коэффициент
            ratio = self.db.execute(
                select(FinancialRatio).where(FinancialRatio.ratio_code == ratio_code)
            ).scalar_one_or_none()

            if not ratio:
                raise ValueError(f"Ratio {ratio_code} not found in financial_ratio table")

            # Сохраняем значение
            existing = self.db.execute(
                select(CalculatedRatioValue).where(
                    CalculatedRatioValue.reporting_period_id == period.id,
                    CalculatedRatioValue.ratio_id == ratio.id
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = Decimal(str(value))
                added_ids.append(existing.id)
            else:
                ratio_value = CalculatedRatioValue(
                    reporting_period_id=period.id,
                    ratio_id=ratio.id,
                    value=Decimal(str(value))
                )
                self.db.add(ratio_value)
                self.db.flush()
                added_ids.append(ratio_value.id)

        self.db.commit()
        return added_ids

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def ensure_ratio_exists(self, ratio_code: str, ratio_name: str,
                            formula: str = None) -> int:
        """Убедиться, что коэффициент существует в справочнике"""
        ratio = self.db.execute(
            select(FinancialRatio).where(FinancialRatio.ratio_code == ratio_code)
        ).scalar_one_or_none()

        if not ratio:
            ratio = FinancialRatio(
                ratio_code=ratio_code,
                ratio_name=ratio_name,
                formula=formula
            )
            self.db.add(ratio)
            self.db.flush()

        return ratio.id

    def ensure_line_exists(self, line_code: str, line_name: str,
                          statement_type: str) -> int:
        """Убедиться, что строка отчёта существует в справочнике"""
        line = self.db.execute(
            select(FinancialStatementLine).where(
                FinancialStatementLine.line_code == line_code
            )
        ).scalar_one_or_none()

        if not line:
            line = FinancialStatementLine(
                line_code=line_code,
                line_name=line_name,
                statement_type=statement_type
            )
            self.db.add(line)
            self.db.flush()

        return line.id