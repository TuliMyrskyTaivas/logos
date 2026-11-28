"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { ApiError, type Asset, type IncomePlanFact, type IncomeSummary } from "@/lib/types";
import { deleteResource } from "@/lib/client-api";
import { formatMoney, formatPercent, formatSignedMoney } from "@/lib/format";
import { toneOf } from "@/lib/metrics";

import { IncomeChart } from "@/components/income/income-chart";
import { IncomeForm } from "@/components/income/income-form";
import { IncomeTable } from "@/components/income/income-table";
import { KpiCard } from "@/components/kpi-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormError, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";

const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

type FormTarget = { kind: "create" } | { kind: "edit"; row: IncomePlanFact };

function yearOptions(selected: number): number[] {
  const current = new Date().getUTCFullYear();
  const years = new Set<number>();
  for (let year = current - 5; year <= current + 1; year += 1) years.add(year);
  years.add(selected);
  return [...years].sort((a, b) => b - a);
}

export function IncomeView({
  rows,
  summary,
  assets,
}: {
  rows: readonly IncomePlanFact[];
  summary: IncomeSummary;
  assets: readonly Asset[];
}) {
  const router = useRouter();
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [deleting, setDeleting] = useState<IncomePlanFact | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleEdit = useCallback((row: IncomePlanFact) => {
    setTarget({ kind: "edit", row });
  }, []);
  const handleDelete = useCallback((row: IncomePlanFact) => {
    setDeleteError(null);
    setDeleting(row);
  }, []);

  const now = new Date();
  const todayYear = now.getUTCFullYear();
  const todayMonth = now.getUTCMonth() + 1;
  const cutoff =
    summary.year < todayYear ? 12 : summary.year === todayYear ? todayMonth : 0;
  const toDate = summary.months.filter(
    (item) => Number(item.month.slice(5, 7)) <= cutoff && cutoff > 0,
  );
  const plannedToDate = toDate.reduce((sum, item) => sum + item.plannedBase, 0);
  const actualToDate = toDate.reduce((sum, item) => sum + item.actualBase, 0);
  const execution = plannedToDate > 0 ? actualToDate / plannedToDate : null;
  const windowLabel =
    cutoff === 0
      ? "Nothing due yet"
      : cutoff === 12
        ? `Full year ${summary.year}`
        : `Jan–${MONTH_LABELS[cutoff - 1] ?? ""} ${summary.year}`;

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteResource(`/income/${deleting.id}`);
      setDeleting(null);
      router.refresh();
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError ? caught.detail : "Could not delete the income row.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Income</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Plan and fact of dividends, coupons and interest, converted to{" "}
            {summary.baseCurrency} for the totals.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1">
            <span className="block text-xs font-medium text-muted-foreground">Year</span>
            <Select
              value={String(summary.year)}
              onChange={(event) => router.push(`/income?year=${event.target.value}`)}
            >
              {yearOptions(summary.year).map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </Select>
          </label>
          <Button variant="primary" onClick={() => setTarget({ kind: "create" })}>
            Add income
          </Button>
        </div>
      </header>

      {summary.unconvertedCount > 0 ? (
        <Alert
          tone="warning"
          title={`${summary.unconvertedCount} amount${summary.unconvertedCount === 1 ? "" : "s"} could not be converted`}
        >
          The monthly totals skip rows whose currency has no known rate.
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={`Planned ${summary.year}`}
          value={formatMoney(summary.plannedYearToDate, summary.baseCurrency)}
          hint="Whole year, including future months"
        />
        <KpiCard
          label={`Actual ${summary.year}`}
          value={formatMoney(summary.actualYearToDate, summary.baseCurrency)}
          hint={`${summary.months.reduce((sum, item) => sum + item.factCount, 0)} received rows`}
        />
        <KpiCard
          label="Execution to date"
          value={formatPercent(execution)}
          tone={toneOf(execution === null ? null : execution - 1)}
          hint={windowLabel}
        />
        <KpiCard
          label="Gap to plan"
          value={formatSignedMoney(
            plannedToDate === 0 ? null : actualToDate - plannedToDate,
            summary.baseCurrency,
          )}
          tone={toneOf(plannedToDate === 0 ? null : actualToDate - plannedToDate)}
          hint={windowLabel}
        />
      </div>

      <SectionCard
        title="Planned vs received"
        description={`Per month of ${summary.year} in ${summary.baseCurrency}`}
      >
        <IncomeChart summary={summary} />
      </SectionCard>

      <SectionCard
        title="Income rows"
        description={`${rows.length} row${rows.length === 1 ? "" : "s"} in ${summary.year}`}
      >
        <IncomeTable rows={rows} assets={assets} onEdit={handleEdit} onDelete={handleDelete} />
      </SectionCard>

      <Modal
        open={target !== null}
        title={target?.kind === "edit" ? "Correct income row" : "Add income"}
        description="Attach the row to a position when the payment comes from it, or leave it at portfolio level."
        onClose={() => setTarget(null)}
      >
        {target ? (
          <IncomeForm
            assets={assets}
            row={target.kind === "edit" ? target.row : null}
            onCancel={() => setTarget(null)}
            onSaved={() => {
              setTarget(null);
              router.refresh();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        open={deleting !== null}
        title="Delete the income row?"
        description="The entry is removed from the plan and from the totals."
        onClose={() => setDeleting(null)}
        className="max-w-md"
      >
        <div className="space-y-4">
          <FormError message={deleteError} />
          <div className="flex justify-end gap-2">
            <Button onClick={() => setDeleting(null)} disabled={busy}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} disabled={busy}>
              {busy ? "Deleting…" : "Delete row"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
