"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import {
  ApiError,
  type Asset,
  type AssetClassInfo,
  type TradePlan,
} from "@/lib/types";
import { deleteResource } from "@/lib/client-api";
import { formatMonth } from "@/lib/format";

import { KpiCard } from "@/components/kpi-card";
import { PlanForm } from "@/components/plan/plan-form";
import { PlanTable } from "@/components/plan/plan-table";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormError, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";

type FormTarget = { kind: "create" } | { kind: "edit"; plan: TradePlan };

export function PlanView({
  plans,
  assets,
  classes,
  month,
}: {
  plans: readonly TradePlan[];
  assets: readonly Asset[];
  classes: readonly AssetClassInfo[];
  /** Selected month as `YYYY-MM`. */
  month: string;
}) {
  const router = useRouter();
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [deleting, setDeleting] = useState<TradePlan | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleEdit = useCallback((plan: TradePlan) => {
    setTarget({ kind: "edit", plan });
  }, []);
  const handleDelete = useCallback((plan: TradePlan) => {
    setDeleteError(null);
    setDeleting(plan);
  }, []);

  const counts = useMemo(() => {
    const executed = plans.filter((plan) => plan.status === "executed").length;
    const cancelled = plans.filter((plan) => plan.status === "cancelled").length;
    return { executed, cancelled, open: plans.length - executed - cancelled };
  }, [plans]);

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteResource(`/trade-plan/${deleting.id}`);
      setDeleting(null);
      router.refresh();
    } catch (caught) {
      setDeleteError(caught instanceof ApiError ? caught.detail : "Could not delete the plan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Trade plan</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Plan for {formatMonth(`${month}-01`)}; progress counts the trades of the same month, so
            several trades can fulfil one plan.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1">
            <span className="block text-xs font-medium text-muted-foreground">Month</span>
            <Input
              type="month"
              value={month}
              onChange={(event) => {
                if (/^\d{4}-\d{2}$/.test(event.target.value)) {
                  router.push(`/plan?month=${event.target.value}`);
                }
              }}
            />
          </label>
          <Button variant="primary" onClick={() => setTarget({ kind: "create" })}>
            Plan a trade
          </Button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Plans in the month" value={String(plans.length)} />
        <KpiCard
          label="Executed"
          value={String(counts.executed)}
          tone={counts.executed > 0 ? "positive" : "neutral"}
          hint="Target reached by the month's trades"
        />
        <KpiCard label="Open" value={String(counts.open)} hint="Not executed yet" />
        <KpiCard label="Cancelled" value={String(counts.cancelled)} />
      </div>

      <SectionCard
        title="Planned trades"
        description="Overfulfilment counts: reaching the target is enough"
      >
        <PlanTable
          plans={plans}
          assets={assets}
          classes={classes}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      </SectionCard>

      <Modal
        open={target !== null}
        title={target?.kind === "edit" ? "Change the planned trade" : "Plan a trade"}
        description="A plan is expressed either in money or in units, and targets a position or a whole class."
        onClose={() => setTarget(null)}
      >
        {target ? (
          <PlanForm
            assets={assets}
            classes={classes}
            plan={target.kind === "edit" ? target.plan : null}
            month={month}
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
        title="Delete the planned trade?"
        description="The plan is removed; registered trades stay untouched."
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
              {busy ? "Deleting…" : "Delete plan"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
