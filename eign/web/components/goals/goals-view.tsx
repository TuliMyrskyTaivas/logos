"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type {
  AssetClassInfo,
  Goal,
  GoalAllocationProgress,
  GoalProgress,
} from "@/lib/types";
import { formatDate, formatMoney, formatPercent } from "@/lib/format";
import { toneOf } from "@/lib/metrics";
import { cn } from "@/lib/utils";

import { GoalForm } from "@/components/goals/goal-form";
import { KpiCard } from "@/components/kpi-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";

function formatDeltaPoints(delta: number): string {
  const points = delta * 100;
  if (Math.abs(points) < 0.005) return "0.00 pp";
  const sign = points > 0 ? "+" : "\u2212";
  return `${sign}${Math.abs(points).toFixed(2)} pp`;
}

function AllocationRow({ item }: { item: GoalAllocationProgress }) {
  const actual = Math.min(100, Math.max(0, item.actualWeight * 100));
  const target = Math.min(100, Math.max(0, item.targetWeight * 100));
  return (
    <TableRow>
      <TableCell className="font-medium">{item.assetClassCode}</TableCell>
      <TableCell className="text-right">{formatPercent(item.targetWeight, 1)}</TableCell>
      <TableCell className="text-right">{formatPercent(item.actualWeight, 1)}</TableCell>
      <TableCell
        className={cn("text-right font-medium", item.delta >= 0 ? "text-positive" : "text-negative")}
      >
        {formatDeltaPoints(item.delta)}
      </TableCell>
      <TableCell className="w-48">
        <div className="relative h-2 w-full rounded-full bg-muted" title="Actual fill, target marker">
          <div
            className={cn(
              "h-full rounded-full",
              item.delta >= 0 ? "bg-positive" : "bg-primary",
            )}
            style={{ width: `${actual}%` }}
          />
          <span
            aria-hidden
            className="absolute -top-0.5 h-3 w-0.5 bg-foreground/70"
            style={{ left: `calc(${target}% - 1px)` }}
          />
        </div>
      </TableCell>
    </TableRow>
  );
}

export function GoalsView({
  goal,
  progress,
  classes,
}: {
  goal: Goal;
  progress: GoalProgress;
  classes: readonly AssetClassInfo[];
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);

  const allocations = progress.allocations ?? [];
  const hasAllocationTarget = (goal.allocations ?? []).length > 0;
  const hasAnyTarget =
    goal.targetTotalValue != null ||
    goal.targetAnnualReturn != null ||
    hasAllocationTarget;
  const currencyMismatch = goal.currency !== progress.baseCurrency;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Goals</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Target value, allocation and return compared with the portfolio as of{" "}
            {formatDate(progress.asOf)} in {progress.baseCurrency}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {goal.updatedAt ? (
            <span className="text-xs text-muted-foreground">
              Updated {formatDate(goal.updatedAt.slice(0, 10))}
            </span>
          ) : null}
          <Button variant="primary" onClick={() => setEditing(true)}>
            {hasAnyTarget ? "Edit goals" : "Set goals"}
          </Button>
        </div>
      </header>

      {!hasAnyTarget ? (
        <Alert tone="info" title="No goals configured yet">
          Set a target portfolio value (in a currency or in grams of metal), a target allocation per
          asset class, a target annual return — or all three. Progress is recalculated on every visit.
        </Alert>
      ) : null}

      {currencyMismatch && goal.targetTotalValue != null ? (
        <Alert tone="info" title={`Target value is set in ${goal.currency}`}>
          {formatMoney(goal.targetTotalValue, goal.currency)} is converted to{" "}
          {progress.baseCurrency} for the comparison
          {goal.currency.length === 3 && ["XAU", "XAG", "XPT", "XPD"].includes(goal.currency)
            ? " (metal prices are quoted per gram)"
            : ""}
          .
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Portfolio value"
          value={formatMoney(progress.currentValueBase, progress.baseCurrency)}
          hint={`Priced positions as of ${formatDate(progress.asOf)}`}
        />
        <KpiCard
          label="Target value"
          value={formatMoney(progress.targetTotalValueBase, progress.baseCurrency)}
          hint={
            goal.targetTotalValue == null
              ? "No value target"
              : currencyMismatch
                ? `Set as ${formatMoney(goal.targetTotalValue, goal.currency)}`
                : undefined
          }
        />
        <KpiCard
          label="Progress to target"
          value={formatPercent(progress.valueProgress)}
          tone={toneOf(
            progress.valueProgress == null ? null : progress.valueProgress - 1,
          )}
          hint={progress.valueProgress == null ? "Set a value target" : "100 % means reached"}
        />
        <KpiCard
          label="Remaining"
          value={formatMoney(progress.valueGapBase, progress.baseCurrency)}
          tone={toneOf(
            progress.valueGapBase == null ? null : -progress.valueGapBase,
          )}
          hint={progress.valueGapBase != null && progress.valueGapBase < 0 ? "Above target" : undefined}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard
          label="Target annual return"
          value={formatPercent(progress.targetAnnualReturn)}
          hint="Compared with the annualised TWR"
        />
        <KpiCard
          label="Actual annualised TWR"
          value={formatPercent(progress.actualAnnualReturn)}
          tone={toneOf(progress.actualAnnualReturn)}
          hint={
            progress.actualAnnualReturn == null ? "Needs monthly snapshots" : undefined
          }
        />
        <KpiCard
          label="Return gap"
          value={formatPercent(progress.returnGap)}
          tone={toneOf(progress.returnGap)}
          hint={progress.returnGap == null ? "Needs both values" : undefined}
        />
      </div>

      <SectionCard
        title="Target vs actual allocation"
        description="The bar shows the actual weight; the marker is the target"
      >
        {allocations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Neither a target allocation nor a valued position exists yet.
          </p>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Class</TableHeaderCell>
                <TableHeaderCell className="text-right">Target</TableHeaderCell>
                <TableHeaderCell className="text-right">Actual</TableHeaderCell>
                <TableHeaderCell className="text-right">Difference</TableHeaderCell>
                <TableHeaderCell>Weight</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {allocations.map((item) => (
                <AllocationRow key={item.assetClassId} item={item} />
              ))}
            </TableBody>
          </Table>
        )}
      </SectionCard>

      <Modal
        open={editing}
        title="Goal settings"
        description="Saving replaces the whole target distribution."
        onClose={() => setEditing(false)}
      >
        <GoalForm
          goal={goal}
          classes={classes}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            router.refresh();
          }}
        />
      </Modal>
    </div>
  );
}
