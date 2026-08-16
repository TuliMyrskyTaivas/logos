#!/usr/bin/env python3
"""
Import IFRS financial data from an Excel file, extract key financial indicators, calculate financial ratios
and save the results to a database.
"""

import sys
import argparse
import logging
import pandas as pd
import re
from pathlib import Path
from typing import Any

from ratios import Ratios
from crud import add_financial_data
from database import get_session

def is_year(value : Any) -> bool:
    """
    Check if value is a year in YYYY format (4 digits). Returns True if the value can be interpreted as a year.
    """
    if pd.isna(value):
        return False

    # Try to convert to string and check if it matches a 4-digit year pattern
    try:
        # If it's an integer
        if isinstance(value, int):
            year_str = str(value)
        # If it's a float, try to convert it to an integer
        elif isinstance(value, float):
            year_str = str(int(value))
        else:
            year_str = str(value).strip()

        # Check if it's a 4-digit year

        if re.match(r'^\d{4}$', year_str):
            year = int(year_str)
            # Check if the year is in a reasonable range
            if 1900 <= year <= 2100:
                return True
    except (ValueError, TypeError):
        pass

    return False


def extract_year_columns(df : pd.DataFrame) -> tuple[dict[int, int], int]:
    """
    Analyzes the first row of the DataFrame and returns:
    - A dictionary {column_index: year} for columns containing years
    - The index of the column with indicator names (the first column)
    Assumes that the first row contains headers and that the first column contains indicator names.
    """
    if df.empty:
        return {}, 0

    # First row contains headers
    header_row = df.iloc[0]
    year_columns : dict[int, int] = {}

    # Start from the second column (index 1), since the first contains indicator names
    for col_idx in range(1, len(header_row)):
        value = header_row.iloc[col_idx]
        if is_year(value):
            year_str = str(int(value)) if isinstance(value, float) else str(value).strip()
            year_columns[col_idx] = int(year_str)

    return year_columns, 0  # 0 - index of the column with indicator names


def normalize_indicator_name(name : Any) -> str:
    """Normalizes the indicator name for searching (lowercase, remove punctuation, normalize spaces)"""
    if pd.isna(name):
        return ""
    # Convert to lowercase, remove extra spaces and special characters
    name = str(name).strip().lower()
    name = re.sub(r'[^\w\s]', '', name)  # remove punctuation
    name = re.sub(r'\s+', ' ', name)  # normalize spaces
    return name


def find_indicator(df : pd.DataFrame, patterns : list[str], year_columns : dict[int, int]) -> pd.Series | None:
    """
    Finds an indicator in the DataFrame by a list of possible names.
    Returns a Series with years as the index or None.
    """
    if df.empty:
        return None

    first_col = df.iloc[:, 0]  # first column with indicator names

    for idx, value in first_col.items():
        if idx == 0:  # skip header row
            continue

        normalized = normalize_indicator_name(value)
        for pattern in patterns:
            pattern_normalized = normalize_indicator_name(pattern)
            if pattern_normalized == normalized:
                # Extract values for the years from the corresponding columns
                data_dict : dict[int, float] = {}
                for col_idx, year in year_columns.items():
                    if col_idx < len(df.columns):
                        cell_value = df.iloc[idx, col_idx]
                        # Convert to numeric
                        try:
                            numeric_value = pd.to_numeric(cell_value, errors='coerce')
                            if not pd.isna(numeric_value):
                                # Import all values as positives
                                data_dict[year] = abs(numeric_value)
                        except:
                            pass

                if data_dict:
                    return pd.Series(data_dict)

    return None

def load_excel_sheets(file_path : str) -> dict[str, pd.DataFrame]:
    """Loads all sheets from an Excel file into a dictionary {sheet_name: DataFrame}"""
    try:
        excel_file = pd.ExcelFile(file_path)
        print(f"Found sheets: {excel_file.sheet_names}")

        sheets : dict[str, pd.DataFrame] = {}
        for sheet_name in excel_file.sheet_names:
            # Read the sheet without headers, as we will process them manually
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            sheets[str(sheet_name)] = df

        return sheets
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def find_sheet_by_keywords(sheets : dict[str, pd.DataFrame], keywords : list[str]) -> tuple[pd.DataFrame | None, str | None]:
    """Finds a sheet by keywords in its name. Returns the DataFrame and the sheet name, or (None, None) if not found."""
    for sheet_name, df in sheets.items():
        sheet_name_normalized = normalize_indicator_name(sheet_name)
        for keyword in keywords:
            if normalize_indicator_name(keyword) in sheet_name_normalized:
                print(f"  Found sheet: '{sheet_name}' (by keyword '{keyword}')")
                return df, sheet_name
    return None, None


def extract_financial_data(sheets : dict[str, pd.DataFrame]) -> dict[str, pd.Series | None]:
    """Extracts all necessary indicators from the financial statements sheets"""
    data : dict[str, pd.Series | None] = {}

    # 1. Income Statement
    pnl_sheet, _ = find_sheet_by_keywords(sheets, [
        'прибыли и убытки', 'прибыль и убыток',
        'доходы и расходы', 'income statement', 'profit and loss'
    ])

    if pnl_sheet is not None:
        print("✓ Found income statement sheet")
        year_columns, _ = extract_year_columns(pnl_sheet)
        print(f"  Found years: {sorted(year_columns.values())}")

        data['revenue'] = find_indicator(pnl_sheet, [
            'выручка', 'выручка от реализации', 'выручка от продаж',
            'итого выручка',
            'итого выручка от продаж',
            'revenue', 'sales', 'turnover'
        ], year_columns)

        data['cogs'] = find_indicator(pnl_sheet, [
            'себестоимость', 'себестоимость продаж', 'себестоимость реализации',
            'итого себестоимость',
            'cost of sales', 'cost of goods sold', 'cogs'
        ], year_columns)

        data['gross_profit'] = find_indicator(pnl_sheet, [
            'валовая прибыль', 'валовый доход', 'валовая маржа',
            'gross profit', 'gross margin', 'gross income'
        ], year_columns)

        data['operating_profit'] = find_indicator(pnl_sheet, [
            'прибыль от операционной деятельности', 'операционная прибыль',
            'операционная прибыль по небанковским операциям',
            'операционный (убыток)/прибыль',
            'прибыль от продаж', 'операционный доход',
            'operating profit', 'operating income', 'ebit',
            'прибыль убыток от операционной деятельности'
        ], year_columns)

        data['pretax_profit'] = find_indicator(pnl_sheet, [
            '(убыток)/прибыль до налогообложения',
            'прибыль до налога на прибыль',
            'прибыль до налогообложения', 'прибыль до уплаты налогов',
            'profit before tax', 'pbt', 'income before tax'
        ], year_columns)

        data['net_profit'] = find_indicator(pnl_sheet, [
            'прибыль за год',
            'прибыль за период',
            'прибыль за отчётный период',
            '(убыток)/прибыль за отчётный период',
            'прибыль за отчётный год', 'чистая прибыль',
            'чистая прибыль и совокупный доход', 'чистая прибыль за период',
            'чистая прибыль и совокупный доход за период',
            'net income', 'net profit', 'profit for the year',
            'comprehensive income', 'прибыль за год'
        ], year_columns)

        data['depreciation'] = find_indicator(pnl_sheet, [
            'амортизация', 'амортизационные расходы', 'износ',
            'износ и амортизация', 'износ, истощение и амортизация',
            'depreciation', 'amortization', 'depreciation and amortization',
            'depreciation expense', 'amortization expense',
            'depreciation and amortisation'
        ], year_columns)

        data['sga'] = find_indicator(pnl_sheet, [
            'административные расходы', 'управленческие расходы',
            'общехозяйственные и административные расходы',
            'коммерческие и административные расходы',
            'общие и административные расходы',
            'расходы на продажу', 'продажные и административные расходы',
            'коммерческие, общехозяйственные и административные расходы',
            'распределительные и административные расходы',
            'selling general and administrative expenses',
            'selling and administrative expenses', 'selling expenses',
            'general and administrative expenses', 'sg&a', 'sga'
        ], year_columns)

        data['interest_expense'] = find_indicator(pnl_sheet, [
            'проценты к уплате', 'процентные расходы', 'расходы по процентам',
            'процентные и комиссионные доходы',
            'проценты уплаченные', 'финансовые расходы',
            'interest expense', 'finance costs', 'interest paid',
            'процентные платежи'
        ], year_columns)
    else:
        print("Income Statement sheet not found")
        print("  Available sheets:", list(sheets.keys()))

    # 2. Balance Statement
    balance_sheet, _ = find_sheet_by_keywords(sheets, [
        'финансовое положение', 'активы и обязательства', 'баланс',
        'бухгалтерский баланс', 'balance sheet',
        'statement of financial position'
    ])

    if balance_sheet is not None:
        print("✓ Found balance sheet")
        year_columns, _ = extract_year_columns(balance_sheet)
        print(f"  Found years: {sorted(year_columns.values())}")

        data['non_current_assets'] = find_indicator(balance_sheet, [
            'итого внеоборотных активов', 'всего внеоборотных активов',
            'итого внеоборотные активы', 'всего внеоборотные активы',
            'внеоборотные активы',
            'non-current assets', 'long-term assets', 'fixed assets'
        ], year_columns)

        data['accounts_receivable'] = find_indicator(balance_sheet, [
            'дебиторская задолженность', 'итого дебиторская задолженность',
            'краткосрочная дебиторская задолженность',
            'торговая и прочая дебиторская задолженность',
            'торговая дебиторская задолженность',
            'дебиторская задолженность за минусом резерва под ожидаемые кредитные убытки',
            'торговая и прочая дебиторская задолженность и расходы будущих периодов',
            'всего дебиторская задолженность', 'accounts receivable',
            'trade receivables'
        ], year_columns)

        data['current_assets'] = find_indicator(balance_sheet, [
            'итого оборотных активов', 'оборотные активы',
            'итого оборотные активы', 'всего оборотные активы',
            'всего оборотных активов', 'current assets'
        ], year_columns)

        data['total_equity'] = find_indicator(balance_sheet, [
            'всего капитал и резервы', 'итого капитал и резервы', 'итого капитала',
            'итого акционерный капитал',
            'итого капитал', 'итого собственный капитал'
        ], year_columns)

        data['long_term_liabilities'] = find_indicator(balance_sheet, [
            'итого долгосрочные обязательства', 'долгосрочные обязательства',
            'всего долгосрочные обязательства',
            'итого долгосрочных обязательств'
        ], year_columns)

        data['current_liabilities'] = find_indicator(balance_sheet, [
            'итого краткосрочные обязательства', 'краткосрочные обязательства',
            'всего краткосрочные обязательства', 'итого краткосрочных обязательств'
        ], year_columns)

        data['fixed_assets'] = find_indicator(balance_sheet, [
            'основные средства', 'основные средства и нематериальные активы',
            'основные средства за вычетом накопленного износа и обесценения',
            'основные производственные фонды',
            'property plant and equipment', 'fixed assets', 'ppe',
            'земля здания и оборудование'
        ], year_columns)
    else:
        print("Balance Sheet sheet not found")
        print("  Available sheets:", list(sheets.keys()))

    # 3. Cash Flow Statement
    cash_flow, _ = find_sheet_by_keywords(sheets, [
        'оддс', 'движение денежных средств', 'денежные потоки',
        'отчет о движении денежных средств',
        'cash flow', 'statement of cash flows'
    ])

    if cash_flow is not None:
        print("✓ Cash flow statement sheet found")
        year_columns, _ = extract_year_columns(cash_flow)
        print(f"  Available years: {sorted(year_columns.values())}")

        data['cfo'] = find_indicator(cash_flow, [
            'чистый поток денежных средств от операционной деятельности',
            'чистые денежные средства - операционная деятельность',
            'чистый поток денежных средств, использованный в операционной деятельности',
            'чистая сумма средств, поступивших от операционной деятельности',
            'чистые денежные средства, полученные от операционной деятельности',
            'денежные средства от операционной деятельности',
            'чистые денежные средства от операционной деятельности',
            'результат движения денежных средств от операционной деятельности',
            'чистый денежный поток от операционной деятельности',
            'net cash from operating activities', 'operating cash flow',
            'cash flows from operating activities'
        ], year_columns)

        data['cff'] = find_indicator(cash_flow, [
            'денежные средства, использованные в финансовой деятельности',
            'чистый поток денежных средств от финансовой деятельности',
            'чистые денежные средства от финансовой деятельности',
            'чистые денежные средства, использованные в финансовой деятельности',
            'чистые средства, использованные в финансовой деятельности',
            'чистый поток денежных средств, использованный в финансовой деятельности',
            'результат движения денежных средств от финансовой деятельности',
            'чистый денежный поток от финансовой деятельности',
            'net cash from financing activities', 'financing cash flow',
            'cash flows from financing activities'
        ], year_columns)

        data['cfi'] = find_indicator(cash_flow, [
            'денежные средства, использованные в инвестиционной деятельности',
            'чистый поток денежных средств от инвестиционной деятельности',
            'чистые денежные средства от инвестиционной деятельности',
            'чистые денежные средства, использованные в инвестиционной деятельности',
            'чистый поток денежных средств, использованный в инвестиционной деятельности',
            'результат движения денежных средств от инвестиционной деятельности',
            'чистый денежный поток от инвестиционной деятельности',
            'net cash from investing activities', 'investing cash flow',
            'cash flows from investing activities'
        ], year_columns)

        data['capex'] = find_indicator(cash_flow, [
            'приобретение основных средств и нематериальных активов, без НДС',
            'приобретение объектов основных средств и нематериальных активов',
            'приобретение основных средств и нематериальных активов',
            'приобретение основных средств и прочих внеоборотных активов',
            'приобретение основных средств',
            'капитальные затраты'
        ], year_columns)

        if data.get('depreciation') is None:
            data['depreciation'] = find_indicator(cash_flow, [
                'износ, истощение и амортизация',
                'амортизация основных средств, нематериальных активов и активов в форме права пользования',
                'амортизация основных средств и материальных активов',
                'амортизация внеоборотных активов',
                'амортизация', 'износ', 'амортизация и износ',
                'амортизация основных средств и нематериальных активов',
                'амортизация основных средств',
                'depreciation', 'amortization', 'depreciation and amortization',
                'depreciation expense', 'amortization expense'
            ], year_columns)

        if data.get('interest_expense') is None:
            data['interest_expense'] = find_indicator(cash_flow, [
                'уплаченные проценты и оплата расходов на привлечение финансирования',
            ], year_columns)
    else:
        print("Cash flow statement sheet not found")
        print("  Available sheets:", list(sheets.keys()))

    return data


def calculate_ratios(logger: logging.Logger, data : dict[str, pd.Series | None]) -> pd.DataFrame:
    """Calculates financial ratios based on the extracted indicators. Returns a DataFrame with ratios."""
    # Collect all years from the available indicators to create a unified index for the ratios DataFrame
    all_years : set[int] = set()
    for _, value in data.items():
        if value is not None:
            all_years.update(value.index)

    years = sorted(all_years)
    print(f"\nCombined analysis periods: {years}")

    if not years:
        print("No periods found for analysis!")
        return pd.DataFrame()

    # Create an empty DataFrame with years as the index to store the calculated ratios
    results = pd.DataFrame(index=years)
    ratios = Ratios(logger)

    results['icr'] = ratios.icr(data)
    results['tata'] = ratios.tata(data)
    results['current_ratio'] = ratios.current_ratio(data)
    results['aqi'] = ratios.aqi(data)
    results['gmi'] = ratios.gmi(data)
    results['sgai'] = ratios.sgai(data)
    results['depi'] = ratios.depi(data)
    results['dsri'] = ratios.dsri(data)
    results['sgi'] = ratios.sgi(data)
    results['rofa'] = ratios.rofa(data)
    results['fat'] = ratios.fat(data)

    leverage = ratios.leverage(data)
    if leverage is not None:
        results['leverage'] = leverage
        results['lvgi'] = ratios.lvgi(leverage)


    results["m_score"] = ratios.m_score(results['dsri'], results['gmi'], results['aqi'], results['sgi'],
                                        results['depi'], results['sgai'], results['lvgi'], results['tata'])

    return results


def print_detailed_data(data : dict[str, pd.Series | None]):
    """Prints detailed data for each indicator with year-over-year changes and percentage changes."""
    for indicator_name, series in data.items():
        if series is not None and not series.empty:
            print(f"\n{indicator_name}:")
            years = sorted(series.index)
            prev_value = None

            for year in years:
                value = series[year]
                if pd.isna(value):
                    print(f"  {year}: N/A")
                    prev_value = None
                else:
                    # Format the value with thousand separators and 2 decimal places
                    value_str = f"{value:,.2f}"

                    # Calculate year-over-year ratio and percentage change if previous value is available
                    if prev_value is not None and not pd.isna(prev_value) and prev_value != 0:
                        yoy_ratio = value / prev_value
                        yoy_percent = (yoy_ratio - 1) * 100
                        print(f"  {year}: {value_str:>15} (YoY: {yoy_ratio:>6.2f}x, {yoy_percent:+6.1f}%)")
                    else:
                        print(f"  {year}: {value_str:>15}")

                    prev_value = value
        else:
            print(f"\n{indicator_name}: NOT FOUND")


def print_results(extracted_data : dict[str, pd.Series | None], ratios : pd.DataFrame):
    """Prints the results of the analysis, including detailed data and calculated ratios with interpretations."""
    print("\n" + "="*80)
    print("IMPORTED IFRS DATA")
    print("="*80)

    # Выводим детальные данные
    print_detailed_data(extracted_data)

    print("\n" + "="*80)
    print("CALCULATED RATIOS")
    print("="*80)

    if not ratios.empty:
        # Форматируем вывод
        pd.set_option('display.float_format', '{:.2f}'.format)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_rows', None)

        print(ratios.to_string())

        # Дополнительные комментарии
        print("\n" + "-"*80)
        print("INTERPRETATION OF RESULTS (latest available period):")
        print("-"*80)

        if 'icr' in ratios.columns:
            last_icr = ratios['icr'].dropna()
            if not last_icr.empty:
                last_icr = last_icr.iloc[-1]
                if last_icr > 3:
                    print(f"✓ ICR = {last_icr:.2f}: Excellent indicator (>3), company confidently covers interest expenses")
                elif last_icr > 1.5:
                    print(f"⚠ ICR = {last_icr:.2f}: Acceptable indicator, but requires monitoring (1.5-3)")
                elif last_icr > 1:
                    print(f"⚠ ICR = {last_icr:.2f}: Low indicator, minimal interest coverage (1-1.5), potential risk if earnings decline")
                else:
                    print(f"❌ ICR = {last_icr:.2f}: CRITICAL! Company cannot cover interest expenses with operating profit (<1)")

        if 'current_ratio' in ratios.columns:
            last_cr = ratios['current_ratio'].dropna()
            if not last_cr.empty:
                last_cr = last_cr.iloc[-1]
                if last_cr > 2:
                    print(f"✓ Current Ratio = {last_cr:.2f}: Excellent liquidity (>2)")
                elif last_cr > 1.5:
                    print(f"✓ Current Ratio = {last_cr:.2f}: Good liquidity (>1.5)")
                elif last_cr > 1.0:
                    print(f"⚠ Current Ratio = {last_cr:.2f}: Sufficient liquidity, but below optimal level (1-1.5), monitor closely")
                else:
                    print(f"❌ Current Ratio = {last_cr:.2f}: CRITICAL LIQUIDITY PROBLEMS! (<1.0)")

        if 'leverage' in ratios.columns:
            last_lev = ratios['leverage'].dropna()
            if not last_lev.empty:
                last_lev = last_lev.iloc[-1]
                if last_lev < 0.5:
                    print(f"✓ Leverage = {last_lev:.2f}: Very low debt burden (<0.5)")
                elif last_lev < 1:
                    print(f"✓ Leverage = {last_lev:.2f}: Conservative debt burden (<1)")
                elif last_lev < 2:
                    print(f"⚠ Leverage = {last_lev:.2f}: Moderate debt burden (1-2), requires attention to debt management")
                elif last_lev < 3:
                    print(f"⚠ Leverage = {last_lev:.2f}: High debt burden (2-3), increased financial risk, monitor debt levels closely")
                else:
                    print(f"❌ Leverage = {last_lev:.2f}: CRITICAL! Excessive debt burden (>3)")

        if 'rofa' in ratios.columns:
            last_rofa = ratios['rofa'].dropna()
            if not last_rofa.empty:
                last_rofa = last_rofa.iloc[-1]
                print(f"📊 ROFA = {last_rofa:.2f} ({last_rofa*100:.1f}%) - Profitability of Fixed Assets")
                if last_rofa < 0:
                    print(f"   ❌ Negative profitability of fixed assets!")

        if 'fat' in ratios.columns:
            last_fat = ratios['fat'].dropna()
            if not last_fat.empty:
                last_fat = last_fat.iloc[-1]
                print(f"📊 FAT = {last_fat:.2f} - Turnover of Fixed Assets")
                if last_fat < 1:
                    print(f"   ⚠ Low turnover of fixed assets (<1), possible inefficient investments or overvaluation of fixed assets")

        if 'dsri' in ratios.columns:
            last_dsri = ratios['dsri'].dropna()
            if not last_dsri.empty:
                last_dsri = last_dsri.iloc[-1]
                if last_dsri > 1:
                    print(f"⚠ DSRI = {last_dsri:.2f}: Growth of accounts receivable exceeds revenue growth, increased risk of deferred sales")
                else:
                    print(f"✓ DSRI = {last_dsri:.2f}: Accounts receivable grows slower than revenue, normal trend")

        if 'gmi' in ratios.columns:
            last_gmi = ratios['gmi'].dropna()
            if not last_gmi.empty:
                last_gmi = last_gmi.iloc[-1]
                if last_gmi > 1:
                    print(f"⚠ GMI = {last_gmi:.2f}: Gross margin is deteriorating, this may indicate pressure on profitability")
                else:
                    print(f"✓ GMI = {last_gmi:.2f}: Gross margin is improving or stable, positive sign for profitability")

        if 'aqi' in ratios.columns:
            last_aqi = ratios['aqi'].dropna()
            if not last_aqi.empty:
                last_aqi = last_aqi.iloc[-1]
                if last_aqi > 1:
                    print(f"⚠ AQI = {last_aqi:.2f}: Quality of assets is deteriorating, increasing proportion of less liquid assets")
                else:
                    print(f"✓ AQI = {last_aqi:.2f}: Quality of assets is improving or remaining stable")

        if 'sgai' in ratios.columns:
            last_sgai = ratios['sgai'].dropna()
            if not last_sgai.empty:
                last_sgai = last_sgai.iloc[-1]
                if last_sgai > 1:
                    print(f"⚠ SGAI = {last_sgai:.2f}: SG&A is growing faster than revenue, indicating potentially high selling and administrative expenses")
                else:
                    print(f"✓ SGAI = {last_sgai:.2f}: SG&A is growing slower than revenue, suggesting controlled operating expenses")

        if 'depi' in ratios.columns:
            last_depi = ratios['depi'].dropna()
            if not last_depi.empty:
                last_depi = last_depi.iloc[-1]
                if last_depi > 1:
                    print(f"⚠ DEPI = {last_depi:.2f}: Depreciation is slowing down or asset useful life is increasing, possibly indicating aggressive accounting policies")
                else:
                    print(f"✓ DEPI = {last_depi:.2f}: Depreciation is developing appropriately in relation to fixed assets")

        if 'lvgi' in ratios.columns:
            last_lvgi = ratios['lvgi'].dropna()
            if not last_lvgi.empty:
                last_lvgi = last_lvgi.iloc[-1]
                if last_lvgi > 1:
                    print(f"⚠ LVGI = {last_lvgi:.2f}: Credit burden is increasing, raising the risk of financial stability")
                else:
                    print(f"✓ LVGI = {last_lvgi:.2f}: Credit burden is decreasing or stable")
        if 'tata' in ratios.columns:
            last_tata = ratios['tata'].dropna()
            if not last_tata.empty:
                last_tata = last_tata.iloc[-1]
                if last_tata > 0:
                    print(f"⚠ TATA = {last_tata:.2f}: Assets are growing due to accruals, possible elements of profit manipulation")
                else:
                    print(f"✓ TATA = {last_tata:.2f}: Cash component of profit dominates, lower risk of accruals")

        if 'sgi' in ratios.columns:
            last_sgi = ratios['sgi'].dropna()
            if not last_sgi.empty:
                last_sgi = last_sgi.iloc[-1]
                if last_sgi > 1:
                    print(f"✓ SGI = {last_sgi:.2f}: Revenue is growing, the company is developing")
                else:
                    print(f"⚠ SGI = {last_sgi:.2f}: Revenue is declining or stabilizing, requiring analysis of causes")

        if 'm_score' in ratios.columns:
            last_mscore = ratios['m_score'].dropna()
            if not last_mscore.empty:
                last_mscore = last_mscore.iloc[-1]
                if last_mscore > -1.78:
                    print(f"❌ M-Score = {last_mscore:.2f}: Probable profit manipulation (value above -1.78)")
                else:
                    print(f"✓ M-Score = {last_mscore:.2f}: No clear signs of profit manipulation (value below -1.78)")
    else:
        print("Failed to calculate any ratio")
        print("   Please check the presence of all necessary indicators in the financial statements")


def main():
    parser = argparse.ArgumentParser(
        description='Import and analyze IFRS statements from Excel file.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python import_ifrs_from_excel.py reports.xlsx --company "Роснефть" --industry "Нефтяная промышленность"
        """
    )
    parser.add_argument('file_path', type=str, help='Path to the Excel file containing IFRS statements')
    parser.add_argument('--company', '-o', type=str, help='Company name', default=None)
    parser.add_argument('--ticker', '-t', type=str, help='Company ticker symbol', default=None)
    parser.add_argument('--industry', '-i', type=str, help='Industry name', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output with detailed information about the analysis process')

    args = parser.parse_args()

    # Setup logging
    logger = logging.getLogger('import_ifrs')
    handler = logging.StreamHandler()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
    else:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)

    logger.addHandler(handler)

    if not Path(args.file_path).exists():
        print(f"Error: File '{args.file_path}' not found, please check the file path.")
        sys.exit(1)

    logger.info(f"Import IFRS Statements from Excel {args.file_path}")

    # Load all sheets from the Excel file
    sheets = load_excel_sheets(args.file_path)

    # Extract financial data from the sheets
    extracted_data = extract_financial_data(sheets)

    # Calculate financial ratios based on the extracted data
    ratios = calculate_ratios(logger, extracted_data)

    # Print the extracted data and calculated ratios with detailed information
    print_results(extracted_data, ratios)

    # Save the data to the database
    if args.company and args.industry:
        metrics_data = {
            metric_name: series
            for metric_name, series in extracted_data.items()
            if series is not None
        }

        ImporterSession = get_session('importer', 'IMPORTER_PASSWORD')
        with ImporterSession() as session:
            try:
                add_financial_data(session, args.company, args.ticker, args.industry, metrics_data, ratios)
                session.commit()
                print("Data saved to the database")
            except Exception:
                session.rollback()
                raise
    else:
        print("Skipping database save: --company and --industry are required")


if __name__ == "__main__":
    main()