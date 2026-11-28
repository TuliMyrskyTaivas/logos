import type { Performance } from "@/lib/types";
import { formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { toneClass, toneOf, type MetricTone } from "@/lib/metrics";

type Metric = {
  label: string;
  value: string;
  tone?: MetricTone;
};

export function PerformanceMetrics({ performance }: { performance: Performance }) {
  const currency = performance.baseCurrency;
  const metrics: Metric[] = [
    { label: "Simple return", value: formatPercent(performance.simpleReturn), tone: toneOf(performance.simpleReturn) },
    { label: "TWR", value: formatPercent(performance.twr), tone: toneOf(performance.twr) },
    { label: "Annualised TWR", value: formatPercent(performance.annualizedTwr), tone: toneOf(performance.annualizedTwr) },
    { label: "XIRR", value: formatPercent(performance.xirr), tone: toneOf(performance.xirr) },
    { label: "Volatility p.a.", value: formatPercent(performance.volatility) },
    { label: "Max drawdown", value: formatPercent(performance.maxDrawdown), tone: toneOf(performance.maxDrawdown) },
    { label: "Sharpe", value: formatNumber(performance.sharpe) },
    { label: "Sortino", value: formatNumber(performance.sortino) },
    { label: "Contributions", value: formatMoney(performance.contributions, currency) },
    { label: "Withdrawals", value: formatMoney(performance.withdrawals, currency) },
    { label: "Income", value: formatMoney(performance.income, currency) },
    { label: "Periods", value: formatNumber(performance.periods, 0) },
  ];

  return (
    <div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">{metric.label}</dt>
            <dd className={`mt-0.5 text-sm font-medium ${toneClass(metric.tone ?? "neutral")}`}>
              {metric.value}
            </dd>
          </div>
        ))}
      </dl>
      {performance.periods === 0 ? (
        <p className="mt-4 text-xs text-muted-foreground">
          Return and risk metrics need at least two monthly valuation snapshots.
        </p>
      ) : null}
    </div>
  );
}
