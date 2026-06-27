import argparse
import logging
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple
from database import get_db
from models import Company, Metric, FiscalPeriod, RawFinancial, Scenario, ScenarioVariable

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

def recalculate_indicators(projection: pd.Series) -> pd.Series:
    """
    Recalculate derived indicators based on the forecasted metrics.
    Includes profit, cash flow and margin indicators that respond to changes
    in revenue, costs, depreciation and interest.
    """
    rev = projection.get("revenue", 0)
    cogs = abs(projection.get("cogs", 0))
    sga = abs(projection.get("sga", 0))
    depr = projection.get("depreciation", 0)
    int_exp = projection.get("interest_expense", 0)

    # EBITDA and operating profit
    ebitda = rev - cogs - sga
    projection["ebitda"] = ebitda
    projection["ebitda_margin"] = ebitda / rev if rev else np.nan

    op_profit = ebitda - depr
    projection["operating_profit"] = op_profit

    # Pretax and net profit
    pretax_profit = op_profit - int_exp
    projection["pretax_profit"] = pretax_profit

    net_profit = pretax_profit * 0.8
    projection["net_profit"] = net_profit

    # Cash flow indicators
    cfo = projection.get("cfo")
    if pd.isna(cfo):
        cfo = net_profit + depr
    projection["cfo"] = cfo

    capex = projection.get("capex", np.nan)
    projection["free_cash_flow"] = cfo - capex if pd.notna(capex) else np.nan

    # Margin indicators
    projection["operating_margin"] = op_profit / rev if rev else np.nan
    projection["net_margin"] = net_profit / rev if rev else np.nan
    projection["cash_flow_margin"] = cfo / rev if rev else np.nan

    return projection

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

def play_scenario(logger: logging.Logger, session: Session, scenarioId: int, base: pd.Series) -> pd.Series:
    """
    Apply specified scenario from the database to the baseline forecast
    """

    # Get variables for the scenario from the database
    variables = (
        session.query(ScenarioVariable)
        .join(Metric)
        .filter(ScenarioVariable.scenario_id == scenarioId)
        .all()
    )

    forecast = base.copy()
    # Revenue first, because scale_to_revenue depends on it
    revenue = next((v for v in variables if v.metric == 'revenue'), None)
    if revenue:
        operator = revenue.operator.value if hasattr(revenue.operator, 'value') else str(revenue.operator)
        if operator == 'multiply':
            forecast['revenue'] = forecast['revenue'] * float(revenue.value)

    # Other variables of scenario
    for var in variables:
        if var.metric == 'revenue':
            continue  # already done

        metric_code = getattr(var.metric, 'code', None)
        if not metric_code or metric_code not in forecast.index:
            continue

        operator = var.operator.value if hasattr(var.operator, 'value') else str(var.operator)

        if operator == 'multiply':
            forecast[metric_code] = forecast[metric_code] * float(var.value)
        elif operator == 'add':
            forecast[metric_code] = forecast[metric_code] + float(var.value)
        elif operator == 'set':
            forecast[metric_code] = float(var.value)
        elif operator == 'scale_to_revenue':
            if 'revenue' in forecast.index and forecast['revenue'] != 0:
                ratio = abs(base[metric_code]) / base['revenue']
                forecast[metric_code] = -abs(forecast['revenue'] * ratio)
        else:
            logger.warning(f"unknown operator {operator} for variable {var.metric}")

    # Recalculate derived indicators and return the result
    return recalculate_indicators(forecast)

def play_scenarios(
    logger: logging.Logger,
    session: Session,
    df: pd.DataFrame,
    last_year: int,
    forecast_year: int,
) -> Dict[str, pd.Series]:
    """
    Returns a dictionary of scenarios, where keys are scenario names and values are forecasted metrics.
    """

    logger.info(f"Generate forecasts for {forecast_year} based on data up to {last_year}")
    # ---------- Base forecast ----------
    base = extrapolate_series(df, forecast_year)

    # Results dictionary to hold all scenarios
    forecasts : Dict[str, pd.Series] = {}
    forecasts["base"] = recalculate_indicators(base)

    # Get variables for the scenario from the database
    scenarios = (
        session.query(Scenario)
        .filter(Scenario.is_active == True)
        .all()
    )

    logger.info(f"{len(scenarios)} active scenarios loaded from the database")
    for scenario in scenarios:
        forecasts[scenario.code] = play_scenario(logger, session, int(scenario.id), base)

    return forecasts

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
    #scenarios = generate_scenarios(logger, df, last_year, forecast_year)
    scenarios = play_scenarios(logger, session, df, last_year, forecast_year)

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

    for name, forecast in scenarios.items():
        rev = forecast.get("revenue")
        cfo = forecast.get("cfo")
        fcf = forecast.get("free_cash_flow")
        ebitda = forecast.get("ebitda")
        ebitda_margin = forecast.get("ebitda_margin")
        operating_margin = forecast.get("operating_margin")
        net_margin = forecast.get("net_margin")
        cash_flow_margin = forecast.get("cash_flow_margin")

        rows.append({
            "Scenario": name.capitalize(),
            "Revenue": f"{rev:,.0f}" if rev else "—",
            "EBITDA": f"{ebitda:,.0f}" if ebitda is not None and not pd.isna(ebitda) else "—",
            "EBITDA Margin, %": f"{ebitda_margin * 100:.1f}" if ebitda_margin is not None and not pd.isna(ebitda_margin) else "—",
            "CFO": f"{cfo:,.0f}" if cfo is not None and not pd.isna(cfo) else "—",
            "Free Cash Flow": f"{fcf:,.0f}" if fcf is not None and not pd.isna(fcf) else "—",
            "Operating Margin, %": f"{operating_margin * 100:.1f}" if operating_margin is not None and not pd.isna(operating_margin) else "—",
            "Net Margin, %": f"{net_margin * 100:.1f}" if net_margin is not None and not pd.isna(net_margin) else "—",
            "Cash Flow Margin, %": f"{cash_flow_margin * 100:.1f}" if cash_flow_margin is not None and not pd.isna(cash_flow_margin) else "—",
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