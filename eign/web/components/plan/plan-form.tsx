"use client";

import { useState, type FormEvent } from "react";

import {
  ApiError,
  type Asset,
  type AssetClassInfo,
  type PlanStatusInput,
  type TradePlan,
  type TradeType,
} from "@/lib/types";
import { patchJson, postJson } from "@/lib/client-api";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/components/ui/field";

type TargetMode = "asset" | "class";
type TargetUnit = "quantity" | "amount";

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function PlanForm({
  assets,
  classes,
  plan,
  month,
  onSaved,
  onCancel,
}: {
  assets: readonly Asset[];
  classes: readonly AssetClassInfo[];
  plan: TradePlan | null;
  /** Month preselected when creating from the current view. */
  month: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [formMonth, setFormMonth] = useState(plan ? plan.month.slice(0, 7) : month);
  const [direction, setDirection] = useState<TradeType>(plan?.direction ?? "BUY");
  const [targetMode, setTargetMode] = useState<TargetMode>(
    plan?.assetId != null ? "asset" : "class",
  );
  const [assetId, setAssetId] = useState(plan?.assetId != null ? String(plan.assetId) : "");
  const [classId, setClassId] = useState(
    plan?.assetClassId != null ? String(plan.assetClassId) : "",
  );
  const [unit, setUnit] = useState<TargetUnit>(plan?.quantity != null ? "quantity" : "amount");
  const [quantity, setQuantity] = useState(
    plan?.quantity != null ? String(plan.quantity) : "",
  );
  const [amount, setAmount] = useState(plan?.amount != null ? String(plan.amount) : "");
  const [status, setStatus] = useState<PlanStatusInput>(
    plan?.status === "cancelled" ? "cancelled" : "planned",
  );
  const [note, setNote] = useState(plan?.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedAsset = assets.find((asset) => String(asset.id) === assetId);
  const usesAsset = targetMode === "asset";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!/^\d{4}-\d{2}$/.test(formMonth)) {
      setError("Choose the month the plan belongs to.");
      return;
    }
    if (usesAsset && !selectedAsset) {
      setError("Choose the position to plan.");
      return;
    }
    if (!usesAsset && classId === "") {
      setError("Choose the asset class to plan.");
      return;
    }
    if (unit === "quantity" && !usesAsset) {
      setError("A plan in units needs a position: switch the target to a position or plan an amount.");
      return;
    }

    const parsedQuantity = unit === "quantity" ? numberOrNull(quantity) : null;
    const parsedAmount = unit === "amount" ? numberOrNull(amount) : null;
    const value = unit === "quantity" ? parsedQuantity : parsedAmount;
    if (value === null || value <= 0) {
      setError(
        unit === "quantity"
          ? "Planned quantity must be greater than zero."
          : "Planned amount must be greater than zero.",
      );
      return;
    }

    const target = usesAsset
      ? { assetId: Number(assetId), assetClassId: null }
      : { assetId: null, assetClassId: Number(classId) };
    const trimNote = note.trim() === "" ? null : note.trim();

    setSaving(true);
    try {
      if (plan) {
        await patchJson(`/trade-plan/${plan.id}`, {
          month: `${formMonth}-01`,
          direction,
          ...target,
          quantity: parsedQuantity,
          amount: parsedAmount,
          status,
          note: trimNote,
        });
      } else {
        // Creation requires exactly one of amount/quantity, never both.
        await postJson("/trade-plan", {
          month: `${formMonth}-01`,
          direction,
          ...target,
          ...(parsedQuantity !== null
            ? { quantity: parsedQuantity }
            : { amount: parsedAmount }),
          note: trimNote,
        });
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the plan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Month" htmlFor="plan-month">
          <Input
            id="plan-month"
            type="month"
            value={formMonth}
            onChange={(event) => setFormMonth(event.target.value)}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field label="Direction" htmlFor="plan-direction">
          <Select
            id="plan-direction"
            value={direction}
            onChange={(event) => setDirection(event.target.value as TradeType)}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </Select>
        </Field>
        <Field
          label="Plan for"
          htmlFor="plan-target-mode"
          hint="A class plan counts the trades of every position in that class."
        >
          <Select
            id="plan-target-mode"
            value={targetMode}
            onChange={(event) => setTargetMode(event.target.value as TargetMode)}
          >
            <option value="asset">One position</option>
            <option value="class">A whole asset class</option>
          </Select>
        </Field>
        {usesAsset ? (
          <Field label="Position" htmlFor="plan-asset">
            <Select
              id="plan-asset"
              value={assetId}
              onChange={(event) => setAssetId(event.target.value)}
            >
              <option value="">Choose…</option>
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.name} ({asset.assetClassCode}, {asset.currency})
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Asset class" htmlFor="plan-class">
            <Select
              id="plan-class"
              value={classId}
              onChange={(event) => setClassId(event.target.value)}
            >
              <option value="">Choose…</option>
              {classes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} — {item.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field
          label="Target unit"
          htmlFor="plan-unit"
          hint={usesAsset ? undefined : "Class plans are only possible in money."}
        >
          <Select
            id="plan-unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value as TargetUnit)}
            disabled={!usesAsset}
          >
            <option value="amount">Money</option>
            <option value="quantity">Units</option>
          </Select>
        </Field>
        {unit === "quantity" ? (
          <Field
            label="Planned quantity"
            htmlFor="plan-quantity"
            hint={selectedAsset ? `In ${selectedAsset.unit}.` : undefined}
          >
            <Input
              id="plan-quantity"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              inputMode="decimal"
            />
          </Field>
        ) : (
          <Field
            label="Planned amount"
            htmlFor="plan-amount"
            hint={selectedAsset ? `In ${selectedAsset.currency}.` : "Sum of traded value."}
          >
            <Input
              id="plan-amount"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="decimal"
            />
          </Field>
        )}
        {plan ? (
          <Field
            label="Status"
            htmlFor="plan-status"
            hint="Executed is set automatically when the month's trades reach the target."
          >
            <Select
              id="plan-status"
              value={status}
              onChange={(event) => setStatus(event.target.value as PlanStatusInput)}
            >
              <option value="planned">Planned</option>
              <option value="cancelled">Cancelled</option>
            </Select>
          </Field>
        ) : null}
        <Field label="Note" htmlFor="plan-note" className="sm:col-span-2">
          <Textarea
            id="plan-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={512}
          />
        </Field>
      </div>

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? "Saving…" : plan ? "Save changes" : "Add to plan"}
        </Button>
      </div>
    </form>
  );
}
