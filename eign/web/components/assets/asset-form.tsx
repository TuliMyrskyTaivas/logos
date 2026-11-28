"use client";

import { useState, type FormEvent } from "react";

import { ApiError, type Asset, type AssetClassInfo, type AssetUnit } from "@/lib/types";
import { patchJson, postJson } from "@/lib/client-api";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Select } from "@/components/ui/field";

const UNITS: AssetUnit[] = ["share", "bond", "unit", "RUB", "g", "oz"];
const METAL_CLASS = "METAL";

type FormState = {
  assetClassId: string;
  name: string;
  ticker: string;
  isin: string;
  metalCode: string;
  unit: AssetUnit;
  currency: string;
  quantity: string;
  avgPurchasePrice: string;
  currentPrice: string;
  custodian: string;
};

function initialState(asset: Asset | null): FormState {
  return {
    assetClassId: asset ? String(asset.assetClassId) : "",
    name: asset?.name ?? "",
    ticker: asset?.ticker ?? "",
    isin: asset?.isin ?? "",
    metalCode: asset?.metalCode ?? "",
    unit: asset?.unit ?? "share",
    currency: asset?.currency ?? "RUB",
    quantity: asset ? String(asset.quantity) : "0",
    avgPurchasePrice: asset?.avgPurchasePrice != null ? String(asset.avgPurchasePrice) : "",
    currentPrice: asset?.currentPrice != null ? String(asset.currentPrice) : "",
    custodian: asset?.custodian ?? "",
  };
}

function text(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function AssetForm({
  classes,
  asset,
  locked,
  onSaved,
  onCancel,
}: {
  classes: readonly AssetClassInfo[];
  asset: Asset | null;
  /** True when the position already has trades, so quantity is derived. */
  locked: boolean;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormState>(() => initialState(asset));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedClass = classes.find((item) => String(item.id) === form.assetClassId);
  const isMetal = selectedClass?.code === METAL_CLASS;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const assetClassId = Number(form.assetClassId);
    if (!Number.isInteger(assetClassId) || assetClassId <= 0) {
      setError("Choose an asset class.");
      return;
    }
    const name = form.name.trim();
    if (!name) {
      setError("Name is required.");
      return;
    }
    const currency = form.currency.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(currency)) {
      setError("Currency must be a three-letter code, for example RUB or USD.");
      return;
    }
    if (isMetal && !text(form.metalCode)) {
      setError("Metal code is required for a METAL position, for example XAU.");
      return;
    }

    const quantity = numberOrNull(form.quantity);
    const avgPurchasePrice = numberOrNull(form.avgPurchasePrice);
    const currentPrice = numberOrNull(form.currentPrice);
    if (quantity !== null && quantity < 0) {
      setError("Quantity cannot be negative.");
      return;
    }
    if ((avgPurchasePrice ?? 0) < 0 || (currentPrice ?? 0) < 0) {
      setError("Prices cannot be negative.");
      return;
    }

    const payload = {
      assetClassId,
      name,
      unit: form.unit,
      currency,
      ticker: text(form.ticker),
      isin: text(form.isin),
      metalCode: isMetal ? text(form.metalCode) : null,
      currentPrice,
      custodian: text(form.custodian),
      ...(locked ? {} : { quantity: quantity ?? 0, avgPurchasePrice }),
    };

    setSaving(true);
    try {
      if (asset) {
        await patchJson(`/assets/${asset.id}`, payload);
      } else {
        await postJson("/assets", payload);
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the position.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" htmlFor="asset-name">
          <Input
            id="asset-name"
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
            placeholder="SBER"
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field label="Asset class" htmlFor="asset-class">
          <Select
            id="asset-class"
            value={form.assetClassId}
            onChange={(event) => update("assetClassId", event.target.value)}
          >
            <option value="">Choose…</option>
            {classes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} — {item.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ticker" htmlFor="asset-ticker" hint="Used to fetch MOEX quotes.">
          <Input
            id="asset-ticker"
            value={form.ticker}
            onChange={(event) => update("ticker", event.target.value)}
          />
        </Field>
        <Field label="ISIN" htmlFor="asset-isin" hint="Optional, searched on MOEX first.">
          <Input
            id="asset-isin"
            value={form.isin}
            onChange={(event) => update("isin", event.target.value)}
          />
        </Field>
        {isMetal ? (
          <Field label="Metal code" htmlFor="asset-metal" hint="XAU, XAG, XPT, XPD.">
            <Input
              id="asset-metal"
              value={form.metalCode}
              onChange={(event) => update("metalCode", event.target.value.toUpperCase())}
            />
          </Field>
        ) : null}
        <Field label="Unit" htmlFor="asset-unit">
          <Select
            id="asset-unit"
            value={form.unit}
            onChange={(event) => update("unit", event.target.value as AssetUnit)}
          >
            {UNITS.map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Currency" htmlFor="asset-currency">
          <Input
            id="asset-currency"
            value={form.currency}
            onChange={(event) => update("currency", event.target.value.toUpperCase())}
            maxLength={3}
          />
        </Field>
        <Field
          label="Quantity"
          htmlFor="asset-quantity"
          hint={locked ? "Derived from trades and cannot be edited." : undefined}
        >
          <Input
            id="asset-quantity"
            value={form.quantity}
            onChange={(event) => update("quantity", event.target.value)}
            inputMode="decimal"
            disabled={locked}
          />
        </Field>
        <Field
          label="Average purchase price"
          htmlFor="asset-avg"
          hint={locked ? "Derived from trades and cannot be edited." : undefined}
        >
          <Input
            id="asset-avg"
            value={form.avgPurchasePrice}
            onChange={(event) => update("avgPurchasePrice", event.target.value)}
            inputMode="decimal"
            disabled={locked}
          />
        </Field>
        <Field label="Current price" htmlFor="asset-price" hint="Used when no market quote exists.">
          <Input
            id="asset-price"
            value={form.currentPrice}
            onChange={(event) => update("currentPrice", event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field label="Custodian" htmlFor="asset-custodian">
          <Input
            id="asset-custodian"
            value={form.custodian}
            onChange={(event) => update("custodian", event.target.value)}
          />
        </Field>
      </div>

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? "Saving…" : asset ? "Save changes" : "Create position"}
        </Button>
      </div>
    </form>
  );
}
