"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { ApiError, type Asset, type Trade } from "@/lib/types";
import { deleteResource } from "@/lib/client-api";

import { TradeForm } from "@/components/trades/trade-form";
import { TradesTable } from "@/components/trades/trades-table";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";

type FormTarget = { kind: "create" } | { kind: "edit"; trade: Trade };

export function TradesView({
  trades,
  assets,
}: {
  trades: readonly Trade[];
  assets: readonly Asset[];
}) {
  const router = useRouter();
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [deleting, setDeleting] = useState<Trade | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const assetsById = new Map(assets.map((asset) => [asset.id, asset]));
  const handleEdit = useCallback((trade: Trade) => {
    setTarget({ kind: "edit", trade });
  }, []);
  const handleDelete = useCallback((trade: Trade) => {
    setDeleteError(null);
    setDeleting(trade);
  }, []);

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteResource(`/trades/${deleting.id}`);
      setDeleting(null);
      router.refresh();
    } catch (caught) {
      setDeleteError(caught instanceof ApiError ? caught.detail : "Could not delete the trade.");
    } finally {
      setBusy(false);
    }
  }

  const deletingAsset = deleting ? assetsById.get(deleting.assetId) : undefined;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Trades</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {trades.length} trade{trades.length === 1 ? "" : "s"}; every change recalculates the
            position at the weighted average cost.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => setTarget({ kind: "create" })}
          disabled={assets.length === 0}
        >
          Register trade
        </Button>
      </header>

      {assets.length === 0 ? (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          Create a position first: a trade always belongs to one.
        </p>
      ) : null}

      <TradesTable
        trades={trades}
        assets={assets}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <Modal
        open={target !== null}
        title={target?.kind === "edit" ? "Correct trade" : "Register trade"}
        description={
          target?.kind === "edit"
            ? "The position is recalculated from the whole remaining trade history."
            : "The price and fee are given in the position currency."
        }
        onClose={() => setTarget(null)}
      >
        {target ? (
          <TradeForm
            assets={assets}
            trade={target.kind === "edit" ? target.trade : null}
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
        title={`Delete the trade of ${deletingAsset?.name ?? "the position"}?`}
        description="The position is recalculated from the remaining trades."
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
              {busy ? "Deleting…" : "Delete trade"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
