"use client";

import { useState, type FormEvent } from "react";

import { ApiError, type Asset, type Trade, type TradeType } from "@/lib/types";
import { patchJson, postJson } from "@/lib/client-api";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/field";
import { Select, Textarea } from "@/components/ui/field";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function TradeForm({
  assets,
  trade,
  onSaved,
  onCancel,
}: {
  assets: readonly Asset[];
  trade: Trade | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [assetId, setAssetId] = useState(trade ? String(trade.assetId) : "");
  const [tradeType, setTradeType] = useState<TradeType>(trade?.tradeType ?? "BUY");
  const [tradeDate, setTradeDate] = useState(trade?.tradeDate ?? today());
  const [quantity, setQuantity] = useState(trade ? String(trade.quantity) : "");
  const [price, setPrice] = useState(trade ? String(trade.price) : "");
  const [fee, setFee] = useState(trade ? String(trade.fee) : "0");
  const [note, setNote] = useState(trade?.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedAsset = assets.find((asset) => String(asset.id) === assetId);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!trade && !selectedAsset) {
      setError("Choose the position the trade belongs to.");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(tradeDate)) {
      setError("Trade date is required.");
      return;
    }
    const parsedQuantity = numberOrNull(quantity);
    if (parsedQuantity === null || parsedQuantity <= 0) {
      setError("Quantity must be greater than zero.");
      return;
    }
    const parsedPrice = numberOrNull(price);
    if (parsedPrice === null || parsedPrice < 0) {
      setError("Price must be zero or greater.");
      return;
    }
    const parsedFee = numberOrNull(fee) ?? 0;
    if (parsedFee < 0) {
      setError("Fee cannot be negative.");
      return;
    }

    const shared = {
      tradeType,
      tradeDate,
      quantity: parsedQuantity,
      price: parsedPrice,
      fee: parsedFee,
      note: note.trim() === "" ? null : note.trim(),
    };

    setSaving(true);
    try {
      if (trade) {
        await patchJson(`/trades/${trade.id}`, shared);
      } else {
        await postJson("/trades", { ...shared, assetId: Number(assetId) });
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the trade.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Position"
          htmlFor="trade-asset"
          hint={trade ? "The position of a registered trade cannot be changed." : undefined}
        >
          <Select
            id="trade-asset"
            value={assetId}
            onChange={(event) => setAssetId(event.target.value)}
            disabled={trade !== null}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          >
            <option value="">Choose…</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} ({asset.assetClassCode}, {asset.currency})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Direction" htmlFor="trade-type">
          <Select
            id="trade-type"
            value={tradeType}
            onChange={(event) => setTradeType(event.target.value as TradeType)}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </Select>
        </Field>
        <Field label="Trade date" htmlFor="trade-date">
          <Input
            id="trade-date"
            type="date"
            value={tradeDate}
            onChange={(event) => setTradeDate(event.target.value)}
          />
        </Field>
        <Field
          label="Quantity"
          htmlFor="trade-quantity"
          hint={selectedAsset ? `Units of the position (${selectedAsset.unit}).` : undefined}
        >
          <Input
            id="trade-quantity"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field
          label="Price per unit"
          htmlFor="trade-price"
          hint={selectedAsset ? `In ${selectedAsset.currency}.` : undefined}
        >
          <Input
            id="trade-price"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field label="Fee" htmlFor="trade-fee" hint="Commission paid for the trade.">
          <Input
            id="trade-fee"
            value={fee}
            onChange={(event) => setFee(event.target.value)}
            inputMode="decimal"
          />
        </Field>
        <Field label="Note" htmlFor="trade-note" className="sm:col-span-2">
          <Textarea
            id="trade-note"
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
          {saving ? "Saving…" : trade ? "Save changes" : "Register trade"}
        </Button>
      </div>
    </form>
  );
}
