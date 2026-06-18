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
    y = valid.values.astype(float)
    slope, intercept = np.polynomial.Polynomial.fit(x, y, 1)
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
    result : Dict[str, float] = {}
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

    rev_col = "revenue" if "revenue" in base.index else None
    cogs_col = "cogs" if "cogs" in base.index else None
    sga_col = "sga" if "sga" in base.index else None
    depr_col = "depreciation" if "depreciation" in base.index else None
    int_col = "interest_expense" if "interest_expense" in base.index else None
    pretax_col = "pretax_profit" if "pretax_profit" in base.index else None

    # ----------------------------------------------------------
    # 1. DEMAND SHOCK SCENARIOS
    # ----------------------------------------------------------

    # 1.1 Mild: revenue -10 %
    mild = base.copy()
    if rev_col:
        mild[rev_col] *= 0.9  # revenue decrease by 10%

    # Variable costs are proportional to revenue (COGS - cost of goods sold), therefore we scale them by the same factor.
    # SGA, depreciation, interest – considered constant.
    if cogs_col and rev_col:
        ratio_cogs = base[cogs_col] / base[rev_col] if base[rev_col] != 0 else 0
        mild[cogs_col] = mild[rev_col] * ratio_cogs

    # Assume SGA, depreciation, and interest expenses remain constant in the mild scenario.
    # Operating profit is recalculated based on the new revenue and COGS.
    if rev_col and cogs_col and sga_col and depr_col:
        mild["operating_profit"] = (
            mild[rev_col] - mild[cogs_col] - mild[sga_col] - mild[depr_col]
        )
    # Profit before tax (simplified at 20% tax rate)
    if int_col and "operating_profit" in mild.index:
        mild["pretax_profit"] = mild["operating_profit"] - mild[int_col]
    if pretax_col:
        mild["net_profit"] = mild["pretax_profit"] * 0.8

    # 1.2 Severe scenario: revenue -20 %, cost of goods sold +20 %
    severe = base.copy()
    if rev_col:
        severe[rev_col] *= 0.8
    if cogs_col:
        severe[cogs_col] = base[cogs_col] * 1.2  # cost of goods sold increases by 20%

    # SGA, depreciation, interest are constant
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

    # 1.3 Deep recession scenario: revenue -30 %, COGS +30 %, SGA +10 %, depreciation +10 %
    deep_recession = base.copy()
    if rev_col:
        deep_recession[rev_col] *= 0.7
    if cogs_col:
        deep_recession[cogs_col] = base[cogs_col] * 1.3
    if sga_col:
        deep_recession[sga_col] = base[sga_col] * 1.1
    if depr_col:
        deep_recession[depr_col] = base[depr_col] * 1.1
    if rev_col and cogs_col and sga_col and depr_col:
        deep_recession["operating_profit"] = (
            deep_recession[rev_col]
            - deep_recession[cogs_col]
            - deep_recession[sga_col]
            - deep_recession[depr_col]
        )
    if int_col and "operating_profit" in deep_recession.index:
        deep_recession["pretax_profit"] = (
            deep_recession["operating_profit"] - deep_recession[int_col]
        )

    # ----------------------------------------------------------
    # 2. COST SHOCK SCENARIOS
    # ----------------------------------------------------------

    # 2.1 Cost-push inflation scenario: COGS +15 %, SGA +10 %, depreciation +5 %
    # Meaning:   cost inflation without the ability to fully pass it on to prices (relevant for 2021–2023).
    # Mechanics: cost price increases by 15%, SGA by 10% (salaries, logistics),
    #            revenue remains unchanged (the market does not accept price increases).
    cost_push = base.copy()
    if cogs_col:
        cost_push[cogs_col] = base[cogs_col] * 1.15
    if sga_col:
        cost_push[sga_col] = base[sga_col] * 1.10
    if depr_col:
        cost_push[depr_col] = base[depr_col] * 1.05
    if rev_col and cogs_col and sga_col and depr_col:
        cost_push["operating_profit"] = (
            cost_push[rev_col]
            - cost_push[cogs_col]
            - cost_push[sga_col]
            - cost_push[depr_col]
        )

    # 2.2. Commodity super-cycle scenario: COGS +30 %, SGA +20 %, depreciation +10 %
    commodity_super_cycle = base.copy()
    if cogs_col:
        commodity_super_cycle[cogs_col] = base[cogs_col] * 1.30
    if sga_col:
        commodity_super_cycle[sga_col] = base[sga_col] * 1.20
    if depr_col:
        commodity_super_cycle[depr_col] = base[depr_col] * 1.10
    if rev_col and cogs_col and sga_col and depr_col:
        commodity_super_cycle["operating_profit"] = (
            commodity_super_cycle[rev_col]
            - commodity_super_cycle[cogs_col]
            - commodity_super_cycle[sga_col]
            - commodity_super_cycle[depr_col]
        )

    # ----------------------------------------------------------
    # 3. INTEREST RATE AND CURRENCY SHOCKS
    # ----------------------------------------------------------

    # 3.1. Rate hike scenario: interest expense +30 %
    rate_hike = base.copy()
    if int_col:
        rate_hike[int_col] = base[int_col] * 1.30
    if rev_col and cogs_col and sga_col and depr_col and int_col:
        rate_hike["operating_profit"] = (
            rate_hike[rev_col]
            - rate_hike[cogs_col]
            - rate_hike[sga_col]
            - rate_hike[depr_col]
        )
        rate_hike["pretax_profit"] = rate_hike["operating_profit"] - rate_hike[int_col]
        if pretax_col:
            rate_hike["net_profit"] = rate_hike["pretax_profit"] * 0.8

    # ----------------------------------------------------------
    # 4. LIQUIDITY AND BALANCE SHOCKS
    # ----------------------------------------------------------

    # 4.1. Liquidity crunch scenario: interest expense +50 %, revenue -15 %
    liquidity_crunch = base.copy()
    if rev_col:
        liquidity_crunch[rev_col] *= 0.85
    if int_col:
        liquidity_crunch[int_col] *= 1.50

    return {"base": base,
            "mild": mild,
            "severe": severe,
            "deep_recession": deep_recession,
            "cost_push": cost_push,
            "commodity_super_cycle": commodity_super_cycle,
            "rate_hike": rate_hike,
            "liquidity_crunch": liquidity_crunch
        }

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
def forecast_scenarios(logger: logging.Logger, session: Session, company_name: str) -> pd.DataFrame:
    """
    Main entry point for the forecasting model.
    Returns a dataframe with scenarios, breakeven points, safety margins, critical drops, and required price increases.
    """
    logger.info(f"Loading historical data for {company_name}")

    # Load historical data and generate scenarios
    df, years = load_historical_data(logger, session, company_name)
    last_year = years[-1]
    forecast_year = last_year + 1
    scenarios = generate_scenarios(logger, df, last_year, forecast_year)

    # Calculate breakeven revenue for each scenario
    be : Dict[str, float] = {}
    for name, projection in scenarios.items():
        be[name] = breakeven_analysis(projection)

    # Calculate critical drop in revenue from the base forecast to reach breakeven
    critical_drop : Dict[str, float] = {}
    base_rev = scenarios["base"].get("revenue")

    if base_rev and not pd.isna(base_rev) and base_rev > 0:
        for name, be_rev in be.items():
            if np.isinf(be_rev) or pd.isna(be_rev):
                critical_drop[name] = np.nan  # unbreachable breakeven
            else:
                # Critical drop: how much % revenue must decrease from the base forecast to reach breakeven for this scenario
                drop = (base_rev - be_rev) / base_rev * 100
                critical_drop[name] = drop

    # Needed price increase to reach breakeven if revenue is below the threshold
    required_price_increase : Dict[str, float] = {}
    for name, projection in scenarios.items():
        rev = projection.get("revenue")
        be_rev = be.get(name)

        if rev and not pd.isna(rev) and rev > 0:
            if be_rev and not np.isinf(be_rev) and not pd.isna(be_rev) and be_rev > 0:
                if rev < be_rev:
                    # Find out how much % revenue needs to increase (through price or volume) to reach the breakeven threshold
                    increase = (be_rev / rev - 1) * 100
                    required_price_increase[name] = increase
                else:
                    required_price_increase[name] = 0.0  # already profitable, no increase needed
            else:
                required_price_increase[name] = np.nan
        else:
            required_price_increase[name] = np.nan

    rows : List[Dict[str, str]] = []
    for name in ["base", "mild", "severe", "deep_recession", "cost_push", "commodity_super_cycle", "rate_hike", "liquidity_crunch"]:
        rev = scenarios[name].get("revenue")
        rows.append({
            "Scenario": name.capitalize(),
            "Revenue": f"{rev:,.0f}" if rev else "—",
            "Breakeven": f"{be[name]:,.0f}" if not np.isinf(be.get(name, np.nan)) else "∞",
            "Safety Margin, %": f"{(rev / be[name] - 1) * 100:.1f}" if rev and be.get(name) and be[name] > 0 else "—",
            "Critical Drop, %": f"{critical_drop.get(name, 0):.1f}" if critical_drop.get(name) is not None else "—",
            "Required Price Increase, %": f"{required_price_increase.get(name, 0):.1f}" if required_price_increase.get(name) is not None else "—",
        })
    return pd.DataFrame(rows)

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
    print(result)