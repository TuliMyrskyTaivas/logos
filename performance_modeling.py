import argparse
import logging
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple
from database import get_db
from models import Company, Metric, FiscalPeriod, RawFinancial

# ------------------------------------------------------------
# Load historical data from the database and prepare it for modeling.
# ------------------------------------------------------------
def load_historical_data(logger: logging.Logger, session: Session, company_name: str) -> Tuple[pd.DataFrame, List[int]]:
    """
    Load data from the database for the specified company.
    Returns a pivot table (years × metric codes) and an ordered list of years.
    """
    company = session.query(Company).filter(Company.name == company_name).first()
    if not company:
        raise ValueError(f"Company '{company_name}' not found.")

    rows = (
        session.query(
            FiscalPeriod.year,
            Metric.code,
            RawFinancial.value,
        )
        .join(RawFinancial.period)
        .join(RawFinancial.metric)
        .filter(RawFinancial.company_id == company.id)
        .all()
    )
    if not rows:
        raise ValueError("No data found for the company.")

    df = pd.DataFrame(rows, columns=["year", "code", "value"])
    df["value"] = df["value"].astype(float)
    pivot = df.pivot_table(
        index="year", columns="code", values="value", aggfunc="first"
    )
    pivot.sort_index(inplace=True)
    years = sorted(pivot.index.tolist())
    logger.info(f"Loaded historical data for {company_name} with years: {years}")
    return pivot, years


# ------------------------------------------------------------
# Forecasting functions: extrapolation and scenario generation.
# ------------------------------------------------------------

def extrapolate(
    series: pd.Series, target_year: int, method: str = "linear"
) -> float:
    """
    Extrapolate a metric to the target year using a linear trend.
    series: index = year, value = metric value.
    """
    valid = series.dropna()
    if len(valid) < 2:
        return valid.iloc[-1]  # no base for trend – return the last value

    x = valid.index.values.astype(float)
    y = valid.values
    slope, intercept = np.polyfit(x, y, 1)
    return slope * target_year + intercept


def extrapolate_series(
    df: pd.DataFrame,
    target_year: int,
    min_hist: int = 3,
) -> pd.Series:
    """
    For each column (metric) in df, build a forecast for target_year.
    Uses the last min_hist years to ensure the trend is current.
    """
    result = {}
    for col in df.columns:
        series = df[col].dropna()
        if len(series) < 2:
            result[col] = series.iloc[-1] if len(series) > 0 else np.nan
        else:
            # take the last min_hist points (or as many as available)
            recent = series.iloc[-min_hist:] if len(series) >= min_hist else series
            result[col] = extrapolate(recent, target_year)
    return pd.Series(result)

# ------------------------------------------------------------
# Scenario generation based on the base forecast and assumptions.
# ------------------------------------------------------------
def generate_scenarios(
    logger: logging.Logger,
    df: pd.DataFrame,
    last_year: int,
    forecast_year: int,
) -> Dict[str, pd.Series]:
    """
    Returns three scenarios: 'base', 'mild', 'severe'.
    Each is a pd.Series with forecast values for the metrics.
    """

    logger.info(f"Generating scenarios for {forecast_year} based on data up to {last_year}")
    # ---------- Base forecast ----------
    base = extrapolate_series(df, forecast_year)

    # ---------- Mild: revenue -10 % ----------
    mild = base.copy()
    rev_col = "revenue" if "revenue" in base.index else None
    cogs_col = "cogs" if "cogs" in base.index else None
    sga_col = "sga" if "sga" in base.index else None
    depr_col = "depreciation" if "depreciation" in base.index else None
    int_col = "interest_expense" if "interest_expense" in base.index else None
    pretax_col = "pretax_profit" if "pretax_profit" in base.index else None
    net_col = "net_profit" if "net_profit" in base.index else None

    if rev_col:
        mild[rev_col] *= 0.9  # revenue decrease by 10%

    # Variable costs are proportional to revenue (COGS - cost of goods sold), therefore we scale them by the same factor.
    # SGA, depreciation, interest – considered constant.
    if cogs_col and rev_col:
        ratio_cogs = base[cogs_col] / base[rev_col] if base[rev_col] != 0 else 0
        mild[cogs_col] = mild[rev_col] * ratio_cogs

    # SGA считаем постоянными (общехозяйственные не масштабируются автоматически)
    # Амортизация и проценты – постоянны
    # Операционная прибыль пересчитывается
    if rev_col and cogs_col and sga_col and depr_col:
        mild["operating_profit"] = (
            mild[rev_col] - mild[cogs_col] - mild[sga_col] - mild[depr_col]
        )
    # Прибыль до налогообложения (ставка налога 20% упрощённо)
    if int_col and "operating_profit" in mild.index:
        mild["pretax_profit"] = mild["operating_profit"] - mild[int_col]
    if pretax_col:
        mild["net_profit"] = mild["pretax_profit"] * 0.8

    # ---------- Severe: выручка -20 %, себестоимость +20 % ----------
    severe = base.copy()
    if rev_col:
        severe[rev_col] *= 0.8
    if cogs_col:
        severe[cogs_col] = base[cogs_col] * 1.2  # рост себестоимости на 20%

    # SGA, амортизация, проценты – неизменны
    if rev_col and cogs_col and sga_col and depr_col:
        severe["operating_profit"] = (
            severe[rev_col]
            - severe[cogs_col]
            - severe[sga_col]
            - severe[depr_col]
        )
    if int_col and "operating_profit" in severe.index:
        severe["pretax_profit"] = severe["operating_profit"] - severe[int_col]
    if pretax_col:
        severe["net_profit"] = severe["net_profit"] * 0.8

    return {"base": base, "mild": mild, "severe": severe}

# ------------------------------------------------------------
# Breakeven analysis to find the revenue level where operating profit = 0.
# ------------------------------------------------------------
def breakeven_analysis(base: pd.Series) -> float:
    """
    Calculate the breakeven revenue where operating profit = 0.
    Uses the cost structure of the base scenario:
        FC = SGA + Depreciation
        v  = COGS / Revenue  (variable costs per 1 rub. revenue)
    """
    rev = base.get("revenue", np.nan)
    cogs = base.get("cogs", np.nan)
    sga = base.get("sga", 0)
    depr = base.get("depreciation", 0)
    if pd.isna(rev) or pd.isna(cogs) or rev == 0:
        return np.nan

    fixed_costs = abs(sga) + abs(depr)
    variable_ratio = abs(cogs) / rev
    if variable_ratio >= 1:
        return np.inf  # company has structurally negative contribution margin

    be_revenue = fixed_costs / (1 - variable_ratio)
    return be_revenue


# ------------------------------------------------------------
# Main function to run the modeling and output results.
# ------------------------------------------------------------
def forecast_scenarios(
    logger: logging.Logger, session: Session, company_name: str
) -> Dict:
    """
    Main entry point for the forecasting model.
    Returns a dictionary containing:
        - 'scenarios': dict with three pd.Series
        - 'breakeven': dict with breakeven thresholds for each scenario
        - 'commentary': text outputs with insights on the results
    """
    logger.info(f"Loading historical data for {company_name}")
    df, years = load_historical_data(logger, session, company_name)
    last_year = years[-1]
    forecast_year = last_year + 1

    scenarios = generate_scenarios(logger, df, last_year, forecast_year)

    # Breakeven analysis for each scenario
    be = {}
    for name, proj in scenarios.items():
        be[name] = breakeven_analysis(proj)

    # Commentary generation based on the results
    commentary = []
    base_rev = scenarios["base"].get("revenue")
    if not pd.isna(base_rev):
        commentary.append(
            f"Base revenue for {forecast_year}: {base_rev:,.0f} rub."
        )
        for name, be_rev in be.items():
            if not np.isinf(be_rev) and not pd.isna(be_rev):
                safety = (
                    (scenarios[name].get("revenue", 0) / be_rev - 1) * 100
                )
                commentary.append(
                    f"{name.capitalize()}: breakeven threshold {be_rev:,.0f} rub., "
                    f"safety margin {safety:.1f}%."
                )
            elif np.isinf(be_rev):
                commentary.append(
                    f"{name.capitalize()}: company does not reach breakeven "
                    "under the current cost structure."
                )

    return {
        "company": company_name,
        "forecast_year": forecast_year,
        "scenarios": {k: v.to_dict() for k, v in scenarios.items()},
        "breakeven": be,
        "commentary": "\n".join(commentary),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Model company performance scenarios.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python performance_modeling.py --verbose "Acme Corp"
  python performance_modeling.py "Beta Inc"
        """
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output for debugging')
    parser.add_argument('company_name', type=str, help='Name of the company to model')
    args = parser.parse_args()

    # Setup logging
    logger = logging.getLogger('performance_modeling')
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

    logger.info("Starting financial modeling...")

    db_gen = get_db()
    session = next(db_gen)

    result = forecast_scenarios(logger, session, args.company_name)
    print(result["commentary"])