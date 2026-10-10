import argparse
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import numpy as np
import pandas as pd

from mimir_client import MIMIR_URL_DEFAULT, request as mimir_request, uses_https

def get_company_id(
    logger: logging.Logger,
    mimir_url: str,
    company_name: str,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> Optional[int]:
    """
    Retrieve the company ID for the given company name via the mímir service.
    Returns None if the company is not found.
    """
    companies = mimir_request(
        mimir_url,
        "GET",
        f"/companies?name={quote(company_name)}",
        logger=logger,
        cert_file=cert_file,
        key_file=key_file,
    )
    return companies[0]["id"] if companies else None

# ------------------------------------------------------------
# Load historical data from the database and prepare it for modeling.
# ------------------------------------------------------------
def load_historical_data(
    logger: logging.Logger,
    mimir_url: str,
    company_name: str,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> Tuple[pd.DataFrame, List[int]]:
    """
    Load data for the specified company via the mímir service.
    Returns a pivot table (years × metric codes) and an ordered list of years.
    """
    company_id = get_company_id(logger, mimir_url, company_name, cert_file, key_file)
    if not company_id:
        raise ValueError(f"Company '{company_name}' not found.")

    financials = mimir_request(
        mimir_url,
        "GET",
        f"/companies/{company_id}/financials",
        logger=logger,
        cert_file=cert_file,
        key_file=key_file,
    )
    metrics: dict[str, dict[str, float | None]] = financials.get("metrics") or {}
    if not metrics:
        raise ValueError("No data found for the company.")

    rows: list[tuple[int, str, float | None]] = [
        (int(year), code, value)
        for code, year_values in metrics.items()
        for year, value in year_values.items()
    ]
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

    poly = np.polynomial.Polynomial.fit(series.index.to_numpy(), series.to_numpy(), 1, window=None, full=False)
    return poly(target_year)

def extrapolate_series(
    df: pd.DataFrame,
    target_year: int
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
            result[col] = extrapolate(series, target_year)
    return pd.Series(result)

def recalculate_indicators(projection: pd.Series) -> pd.Series:
    """
    Recalculate derived indicators based on the forecasted metrics.
    Includes profit, cash flow and margin indicators that respond to changes
    in revenue, costs, depreciation and interest.
    """
    rev = projection.get("revenue", 0)
    cogs = projection.get("cogs", 0)
    sga = projection.get("sga", 0)
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

    fixed_costs = sga + depr
    variable_ratio = cogs / rev
    if variable_ratio >= 1:
        return np.inf  # company has structurally negative contribution margin

    be_revenue = fixed_costs / (1 - variable_ratio)
    return be_revenue

def play_scenario(
    logger: logging.Logger,
    mimir_url: str,
    scenarioId: int,
    base: pd.Series,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> pd.Series:
    """
    Apply the specified scenario from the mímir service to the baseline forecast.
    """
    variables = mimir_request(
        mimir_url,
        "GET",
        f"/scenarios/{scenarioId}/variables",
        logger=logger,
        cert_file=cert_file,
        key_file=key_file,
    )

    forecast = base.copy()
    # Revenue first, because scale_to_revenue depends on it
    revenue = next((v for v in variables if v["metricCode"] == "revenue"), None)
    if revenue and revenue["operator"] == "multiply":
        forecast["revenue"] = forecast["revenue"] * float(revenue["value"])

    # Other variables of scenario
    for var in variables:
        metric_code = var["metricCode"]
        operator = var["operator"]
        value = float(var["value"])

        if metric_code == "revenue":
            continue  # already done
        if metric_code not in forecast.index:
            continue

        if operator == "multiply":
            forecast[metric_code] = forecast[metric_code] * value
        elif operator == "add":
            forecast[metric_code] = forecast[metric_code] + value
        elif operator == "set":
            forecast[metric_code] = value
        elif operator == "scale_to_revenue":
            if "revenue" in forecast.index and forecast["revenue"] != 0:
                ratio = abs(base[metric_code]) / base["revenue"]
                forecast[metric_code] = -abs(forecast["revenue"] * ratio)
        else:
            logger.warning(f"unknown operator {operator} for variable {metric_code}")

    # Recalculate derived indicators and return the result
    return recalculate_indicators(forecast)

def play_scenarios(
    logger: logging.Logger,
    mimir_url: str,
    df: pd.DataFrame,
    last_year: int,
    forecast_year: int,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> Dict[str, pd.Series]:
    """
    Returns a dictionary of scenarios, where keys are scenario names and values are forecasted metrics.
    """

    logger.info(f"Generate forecasts for {forecast_year} based on data up to {last_year}")
    # ---------- Base forecast ----------
    base = extrapolate_series(df, forecast_year)

    # Results dictionary to hold all scenarios
    forecasts: Dict[str, pd.Series] = {}
    forecasts["base"] = recalculate_indicators(base)

    scenarios = mimir_request(
        mimir_url,
        "GET",
        "/scenarios?isActive=true",
        logger=logger,
        cert_file=cert_file,
        key_file=key_file,
    )
    logger.info(f"{len(scenarios)} active scenarios loaded from the mímir service")
    for scenario in scenarios:
        forecasts[scenario["code"]] = play_scenario(
            logger, mimir_url, scenario["id"], base, cert_file, key_file
        )

    return forecasts

# ------------------------------------------------------------
# Main function to run the modeling and output results.
# ------------------------------------------------------------
def forecast_scenarios(
    logger: logging.Logger,
    mimir_url: str,
    company_name: str,
    year: Optional[int],
    cert_file: str | None = None,
    key_file: str | None = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Main entry point for the forecasting model.
    Returns a dataframe with scenarios, breakeven points, safety margins, critical drops, and required price increases.
    """
    logger.info(f"Loading historical data for {company_name}")

    # Load historical data and generate scenarios
    df, years = load_historical_data(logger, mimir_url, company_name, cert_file, key_file)
    first_year = years[0]
    last_year = years[-1]
    if year is not None:
        forecast_year = year
    else:
        forecast_year = last_year + 1

    if forecast_year <= first_year or forecast_year > last_year + 1:
        raise ValueError(f"Forecast year {forecast_year} is out of valid range ({first_year + 1} to {last_year + 1})")

    scenarios = play_scenarios(logger, mimir_url, df, last_year, forecast_year, cert_file, key_file)

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
        operating_profit = forecast.get("operating_profit")
        pretax_profit = forecast.get("pretax_profit")
        net_profit = forecast.get("net_profit")
        cfo = forecast.get("cfo")
        fcf = forecast.get("free_cash_flow")
        ebitda = forecast.get("ebitda")
        ebitda_margin = forecast.get("ebitda_margin")
        operating_margin = forecast.get("operating_margin")
        net_margin = forecast.get("net_margin")
        cash_flow_margin = forecast.get("cash_flow_margin")

        rows.append({
            "scenario": name.capitalize(),
            "revenue": f"{rev:,.0f}" if rev else "—",
            "operating_profit": f"{operating_profit:,.0f}" if operating_profit is not None and not pd.isna(operating_profit) else "—",
            "pretax_profit": f"{pretax_profit:,.0f}" if pretax_profit is not None and not pd.isna(pretax_profit) else "—",
            "net_profit": f"{net_profit:,.0f}" if net_profit is not None and not pd.isna(net_profit) else "—",
            "ebitda": f"{ebitda:,.0f}" if ebitda is not None and not pd.isna(ebitda) else "—",
            "ebitda_margin": f"{ebitda_margin * 100:.1f}" if ebitda_margin is not None and not pd.isna(ebitda_margin) else "—",
            "cfo": f"{cfo:,.0f}" if cfo is not None and not pd.isna(cfo) else "—",
            "fcf": f"{fcf:,.0f}" if fcf is not None and not pd.isna(fcf) else "—",
            "operating_margin": f"{operating_margin * 100:.1f}" if operating_margin is not None and not pd.isna(operating_margin) else "—",
            "net_margin": f"{net_margin * 100:.1f}" if net_margin is not None and not pd.isna(net_margin) else "—",
            "cash_flow_margin": f"{cash_flow_margin * 100:.1f}" if cash_flow_margin is not None and not pd.isna(cash_flow_margin) else "—",
            "breakeven": f"{be[name]:,.0f}" if not np.isinf(be.get(name, np.nan)) else "∞",
            "safety_margin": f"{(rev / be[name] - 1) * 100:.1f}" if rev and be.get(name) and be[name] > 0 else "—",
            "critical_drop": f"{critical_drop.get(name, 0):.1f}" if critical_drop.get(name) is not None else "—",
            "required_price_increase": f"{required_price_increase.get(name, 0):.1f}" if required_price_increase.get(name) is not None else "—",
        })
    return pd.DataFrame(rows).set_index("scenario").sort_index(), forecast_year

def save_simulation_results(
    logger: logging.Logger,
    mimir_url: str,
    company: str,
    forecast_year: int,
    forecast: pd.DataFrame,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> None:
    """Save the scenario forecast results through the mímir service."""
    logger.debug(f"Saving {forecast_year} forecasts for {company} via mímir")
    company_id = get_company_id(logger, mimir_url, company, cert_file, key_file)
    if company_id is None:
        raise ValueError(f"Company '{company}' not found.")

    scenarios: List[dict[str, Any]] = []
    for row in forecast.itertuples():
        scenario_code = str(row.Index).lower()
        metrics: Dict[str, float] = {}
        for indicator in forecast.columns:
            metric_code = indicator.replace(" ", "_").replace(",", "").replace("%", "").lower()
            value = getattr(row, indicator, None)
            if value is None or value == "—":
                continue
            numeric_value = value.replace(',', '') if isinstance(value, str) else value
            try:
                numeric_value = float(numeric_value)
            except (TypeError, ValueError):
                logger.warning(
                    f"Value '{value}' for metric '{metric_code}' in scenario '{scenario_code}' is not numeric. Skipping."
                )
                continue
            metrics[metric_code] = numeric_value
        if metrics:
            scenarios.append({"scenarioCode": scenario_code, "metrics": metrics})

    if not scenarios:
        return

    result = mimir_request(
        mimir_url,
        "PUT",
        f"/companies/{company_id}/forecasts",
        {"forecastYear": forecast_year, "scenarios": scenarios},
        logger=logger,
        cert_file=cert_file,
        key_file=key_file,
    )
    logger.info(
        f"Saved forecasts via mímir: scenarios={result.get('scenarioCount')}, metrics={result.get('metricCount')}"
    )

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
    parser.add_argument('--dry-run', '-d', action='store_true', help='Run the model without saving results')
    parser.add_argument('--year', '-y', type=int, help='Forecast year (default: next year after last historical data)')
    parser.add_argument('--mimir-url', type=str, default=os.getenv('MIMIR_URL', MIMIR_URL_DEFAULT), help='Mímir service base URL')
    parser.add_argument('--client-cert-file', type=str, default=None, help='Path to the client TLS certificate (PEM). Required when --mimir-url uses https.')
    parser.add_argument('--client-key-file', type=str, default=None, help='Path to the client TLS private key (PEM). Required when --mimir-url uses https.')
    parser.add_argument('company_name', type=str, help='Name of the company to model')
    args = parser.parse_args()

    if uses_https(args.mimir_url):
        missing: list[str] = []
        if not args.client_cert_file:
            missing.append('--client-cert-file')
        if not args.client_key_file:
            missing.append('--client-key-file')
        if missing:
            parser.error(
                'the following arguments are required when --mimir-url uses https: '
                + ', '.join(missing)
            )

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

    try:
        result, forecast_year = forecast_scenarios(
            logger,
            args.mimir_url,
            args.company_name,
            year=args.year,
            cert_file=args.client_cert_file,
            key_file=args.client_key_file,
        )
        print(result)
        if not args.dry_run:
            logger.info("Saving simulation results via the mímir service...")
            save_simulation_results(
                logger,
                args.mimir_url,
                args.company_name,
                forecast_year=forecast_year,
                forecast=result,
                cert_file=args.client_cert_file,
                key_file=args.client_key_file,
            )
            logger.info("Results saved successfully.")
    except Exception as e:
        import traceback
        logger.error(f"An error occurred: {e}")
        logger.error(traceback.print_exception(e))