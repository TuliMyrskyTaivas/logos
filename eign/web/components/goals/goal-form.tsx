"use client";

import { useMemo, useState, type FormEvent } from "react";

import { ApiError, type AssetClassInfo, type Goal } from "@/lib/types";
import { putJson } from "@/lib/client-api";
import { formatPercent } from "@/lib/format";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/field";

type WeightState = Record<number, string>;

function initialWeights(goal: Goal, classes: readonly AssetClassInfo[]): WeightState {
  const stored = new Map(
    (goal.allocations ?? []).map((item) => [item.assetClassId, item.targetWeight]),
  );
  const result: WeightState = {};
  for (const item of classes) {
    const weight = stored.get(item.id);
    result[item.id] = weight != null ? String(Math.round(weight * 10000) / 100) : "";
  }
  return result;
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function GoalForm({
  goal,
  classes,
  onSaved,
  onCancel,
}: {
  goal: Goal;
  classes: readonly AssetClassInfo[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [currency, setCurrency] = useState(goal.currency);
  const [targetValue, setTargetValue] = useState(
    goal.targetTotalValue != null ? String(goal.targetTotalValue) : "",
  );
  const [targetReturn, setTargetReturn] = useState(
    goal.targetAnnualReturn != null
      ? String(Math.round(goal.targetAnnualReturn * 10000) / 100)
      : "",
  );
  const [weights, setWeights] = useState<WeightState>(() => initialWeights(goal, classes));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const total = useMemo(
    () =>
      classes.reduce((sum, item) => sum + (numberOrNull(weights[item.id] ?? "") ?? 0), 0),
    [classes, weights],
  );
  const weightMismatch = Math.abs(total - 100) > 0.005;

  function setWeight(classId: number, value: string) {
    setWeights((previous) => ({ ...previous, [classId]: value }));
  }

  function distributeEvenly() {
    if (classes.length === 0) return;
    const share = Math.floor(10000 / classes.length) / 100;
    const next: WeightState = {};
    classes.forEach((item, index) => {
      const value = index === classes.length - 1 ? 100 - share * (classes.length - 1) : share;
      next[item.id] = value.toFixed(2).replace(/\.?0+$/, "");
    });
    setWeights(next);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const code = currency.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(code)) {
      setError("Currency must be a three-letter code, for example RUB or XAU (per gram).");
      return;
    }
    const parsedTarget = numberOrNull(targetValue);
    if (parsedTarget !== null && parsedTarget <= 0) {
      setError("The target value must be greater than zero.");
      return;
    }
    const parsedReturn = numberOrNull(targetReturn);
    if (parsedReturn !== null && (parsedReturn < -100 || parsedReturn > 1000)) {
      setError("The target annual return is entered in percent, for example 15.");
      return;
    }
    if (weightMismatch) {
      setError(
        `Target weights must sum to exactly 100 %, currently ${formatPercent(total / 100, 2)}.`,
      );
      return;
    }

    const allocations = classes
      .map((item) => ({
        assetClassId: item.id,
        targetWeight: (numberOrNull(weights[item.id] ?? "") ?? 0) / 100,
      }))
      .filter((item) => item.targetWeight > 0);

    setSaving(true);
    try {
      await putJson("/goals", {
        currency: code,
        targetTotalValue: parsedTarget,
        targetAnnualReturn: parsedReturn === null ? null : parsedReturn / 100,
        allocations,
      });
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the goals.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Target value"
          htmlFor="goal-value"
          hint="Empty means no value target."
        >
          <Input
            id="goal-value"
            value={targetValue}
            onChange={(event) => setTargetValue(event.target.value)}
            inputMode="decimal"
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field
          label="Currency of the target"
          htmlFor="goal-currency"
          hint="A fiat code or a metal code such as XAU (per gram)."
        >
          <Input
            id="goal-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            maxLength={3}
          />
        </Field>
        <Field
          label="Target annual return, %"
          htmlFor="goal-return"
          hint="Compared with the annualised TWR."
          className="sm:col-span-2"
        >
          <Input
            id="goal-return"
            value={targetReturn}
            onChange={(event) => setTargetReturn(event.target.value)}
            inputMode="decimal"
          />
        </Field>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Target allocation</p>
            <p className="text-xs text-muted-foreground">
              Percent of the portfolio per asset class; the sum must be 100 %.
            </p>
          </div>
          <Button size="sm" onClick={distributeEvenly}>
            Distribute evenly
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {classes.map((item) => (
            <label key={item.id} className="flex items-center gap-3">
              <span className="w-20 shrink-0 text-sm font-medium">{item.code}</span>
              <Input
                value={weights[item.id] ?? ""}
                onChange={(event) => setWeight(item.id, event.target.value)}
                inputMode="decimal"
                placeholder="0"
                aria-label={`${item.code} target weight in percent`}
              />
              <span className="text-sm text-muted-foreground">%</span>
            </label>
          ))}
        </div>
        <p
          className={
            weightMismatch ? "text-sm font-medium text-negative" : "text-sm text-muted-foreground"
          }
        >
          Sum: {formatPercent(total / 100, 2)}
          {weightMismatch ? " — adjust the weights to exactly 100 %" : " ✓"}
        </p>
      </div>

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving || weightMismatch}>
          {saving ? "Saving…" : "Save goals"}
        </Button>
      </div>
    </form>
  );
}
