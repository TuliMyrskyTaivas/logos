import { AllocationChart } from "@/components/allocation-chart";
import { ApiErrorPanel } from "@/components/api-error-panel";
import { KpiCard } from "@/components/kpi-card";
import { PerformanceMetrics } from "@/components/metrics-grid";
import { PerformanceChart } from "@/components/performance-chart";
import { PositionsTable } from "@/components/positions-table";
import { Alert } from "@/components/ui/alert";
import { SectionCard } from "@/components/ui/card";
import { RefreshButton } from "@/components/refresh-button";
import {
  describeError,
  fetchPerformance,
  fetchPortfolioSummary,
  type Performance,
  type PortfolioSummary,
} from "@/lib/api";
import { formatDate, formatMoney, formatPercent } from "@/lib/format";
import { toneOf, unpricedReasonLabel } from "@/lib/metrics";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function PortfolioSummaryPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  let summary: PortfolioSummary;
  let performance: Performance;
  try {
    [summary, performance] = await Promise.all([
      fetchPortfolioSummary(identity),
      fetchPerformance(identity),
    ]);
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Portfolio data is unavailable"
        detail={describeError(error)}
        hint="The page reads /portfolio/summary and /portfolio/performance from the Eign API."
      />
    );
  }

  const currency = summary.baseCurrency;
  const pricedCount = summary.positions.filter((position) => position.priced).length;
  const unpriced = summary.positions.filter((position) => !position.priced);
  const periodDetail =
    performance.periodStart && performance.periodEnd
      ? `${formatDate(performance.periodStart)} – ${formatDate(performance.periodEnd)}`
      : "Computed from stored monthly snapshots";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Portfolio summary</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Valuation as of {formatDate(summary.asOf)} in {currency}
          </p>
        </div>
        <RefreshButton />
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Total value"
          value={formatMoney(summary.totalValue, currency)}
          hint={`${pricedCount} of ${summary.positions.length} positions priced`}
        />
        <KpiCard
          label="Income year to date"
          value={formatMoney(summary.incomeYearToDate, currency)}
          hint={
            summary.incomePlanYearToDate > 0
              ? `Plan ${formatMoney(summary.incomePlanYearToDate, currency)}`
              : "No income plan for this year"
          }
        />
        <KpiCard
          label="Annualised TWR"
          value={formatPercent(performance.annualizedTwr)}
          tone={toneOf(performance.annualizedTwr)}
          hint={
            performance.periods > 0 && performance.periodStart
              ? `Since ${formatDate(performance.periodStart)}`
              : "Needs monthly snapshots"
          }
        />
        <KpiCard
          label="XIRR"
          value={formatPercent(performance.xirr)}
          tone={toneOf(performance.xirr)}
          hint="Money-weighted annual return"
        />
      </div>

      {unpriced.length > 0 ? (
        <Alert
          tone="warning"
          title={`${unpriced.length} position${unpriced.length === 1 ? "" : "s"} could not be valued`}
        >
          <ul className="space-y-1">
            {unpriced.map((position) => (
              <li key={position.assetId}>
                {position.name} — {unpricedReasonLabel(position.unpricedReason)}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-5">
        <SectionCard
          className="lg:col-span-2"
          title="Allocation"
          description="Share of the total value by asset class"
        >
          <AllocationChart
            data={summary.byClass.map((item) => ({
              code: item.assetClassCode,
              value: item.value,
              weight: item.weight,
            }))}
            currency={currency}
          />
        </SectionCard>
        <SectionCard
          className="lg:col-span-3"
          title="Performance and risk"
          description={periodDetail}
        >
          <PerformanceMetrics performance={performance} />
        </SectionCard>
      </div>

      <SectionCard
        title="Value and time-weighted index"
        description="Monthly snapshots; the TWR index starts at 100"
      >
        <PerformanceChart monthly={performance.monthly} currency={currency} />
      </SectionCard>

      <SectionCard
        title="Positions"
        description={`${summary.positions.length} position${summary.positions.length === 1 ? "" : "s"} in the portfolio`}
      >
        <PositionsTable
          positions={summary.positions}
          totalValue={summary.totalValue}
          currency={currency}
        />
      </SectionCard>
    </div>
  );
}
