"use client";

import { useState, type FormEvent } from "react";

import { ApiError, type Asset, type IncomePlanFact, type IncomeType } from "@/lib/types";
import { patchJson, postJson } from "@/lib/client-api";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/components/ui/field";

const TYPES: IncomeType[] = ["dividend", "coupon", "interest", "other"];
const TYPE_LABELS: Record<IncomeType, string> = {
  dividend: "Dividend",
  coupon: "Coupon",
  interest: "Interest",
  other: "Other",
};

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function IncomeForm({
  assets,
  row,
  onSaved,
  onCancel,
}: {
  assets: readonly Asset[];
  row: IncomePlanFact | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [month, setMonth] = useState(row ? row.month.slice(0, 7) : currentMonth());
  const [incomeType, setIncomeType] = useState<IncomeType>(row?.incomeType ?? "dividend");
  const [assetId, setAssetId] = useState(row?.assetId != null ? String(row.assetId) : "");
  const [currency, setCurrency] = useState(row?.currency ?? "");
  const [planned, setPlanned] = useState(
    row?.plannedAmount != null ? String(row.plannedAmount) : "",
  );
  const [actual, setActual] = useState(
    row?.actualAmount != null ? String(row.actualAmount) : "",
  );
  const [note, setNote] = useState(row?.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedAsset = assets.find((asset) => String(asset.id) === assetId);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!/^\d{4}-\d{2}$/.test(month)) {
      setError("Choose the income month.");
      return;
    }
    const plannedAmount = numberOrNull(planned);
    const actualAmount = numberOrNull(actual);
    if (plannedAmount === null && actualAmount === null) {
      setError("Fill in the planned amount, the actual amount, or both.");
      return;
    }
    if ((plannedAmount ?? 0) < 0 || (actualAmount ?? 0) < 0) {
      setError("Amounts cannot be negative.");
      return;
    }
    const code = currency.trim().toUpperCase();
    if (code !== "" && !/^[A-Z]{3}$/.test(code)) {
      setError("Currency must be a three-letter code, for example RUB.");
      return;
    }

    const payload = {
      month: `${month}-01`,
      incomeType,
      assetId: assetId === "" ? null : Number(assetId),
      currency: code === "" ? null : code,
      plannedAmount,
      actualAmount,
      note: note.trim() === "" ? null : note.trim(),
    };

    setSaving(true);
    try {
      if (row) {
        await patchJson(`/income/${row.id}`, payload);
      } else {
        await postJson("/income", payload);
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the income row.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Month" htmlFor="income-month">
          <Input
            id="income-month"
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value)}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field label="Type" htmlFor="income-type">
          <Select
            id="income-type"
            value={incomeType}
            onChange={(event) => setIncomeType(event.target.value as IncomeType)}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Position"
          htmlFor="income-asset"
          hint="Leave empty for portfolio-level income, such as account interest."
        >
          <Select
            id="income-asset"
            value={assetId}
            onChange={(event) => setAssetId(event.target.value)}
          >
            <option value="">Portfolio (no position)</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} ({asset.assetClassCode}, {asset.currency})
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Currency"
          htmlFor="income-currency"
          hint={
            selectedAsset
              ? `Empty means ${selectedAsset.currency} (the position currency).`
              : "Empty means the base currency."
          }
        >
          <Input
            id="income-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            maxLength={3}
            placeholder="RUB"
          />
        </Field>
        <Field label="Planned amount" htmlFor="income-planned">
          <Input
            id="income-planned"
            value={planned}
            onChange={(event) => setPlanned(event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field label="Actual amount" htmlFor="income-actual">
          <Input
            id="income-actual"
            value={actual}
            onChange={(event) => setActual(event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field
          label="Note"
          htmlFor="income-note"
          className="sm:col-span-2"
          hint="A position, month and type can only appear once; edit the existing row instead."
        >
          <Textarea
            id="income-note"
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
          {saving ? "Saving…" : row ? "Save changes" : "Add income"}
        </Button>
      </div>
    </form>
  );
}
