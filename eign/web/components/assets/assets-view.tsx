"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { ApiError, type Asset, type AssetClassInfo } from "@/lib/types";
import { deleteResource } from "@/lib/client-api";

import { AssetForm } from "@/components/assets/asset-form";
import { AssetsTable } from "@/components/assets/assets-table";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";

type FormTarget = { kind: "create" } | { kind: "edit"; asset: Asset };

export function AssetsView({
  assets,
  classes,
  lockedAssetIds,
}: {
  assets: readonly Asset[];
  classes: readonly AssetClassInfo[];
  lockedAssetIds: readonly number[];
}) {
  const router = useRouter();
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [deleting, setDeleting] = useState<Asset | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const locked = useMemo(() => new Set(lockedAssetIds), [lockedAssetIds]);
  const handleEdit = useCallback((asset: Asset) => {
    setTarget({ kind: "edit", asset });
  }, []);
  const handleDelete = useCallback((asset: Asset) => {
    setDeleteError(null);
    setDeleting(asset);
  }, []);

  function closeForm() {
    setTarget(null);
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteResource(`/assets/${deleting.id}`);
      setDeleting(null);
      router.refresh();
    } catch (caught) {
      setDeleteError(caught instanceof ApiError ? caught.detail : "Could not delete the position.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Positions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {assets.length} position{assets.length === 1 ? "" : "s"}; quantity and average price follow
            the registered trades.
          </p>
        </div>
        <Button variant="primary" onClick={() => setTarget({ kind: "create" })}>
          New position
        </Button>
      </header>

      <AssetsTable
        assets={assets}
        classes={classes}
        lockedAssetIds={locked}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <Modal
        open={target !== null}
        title={target?.kind === "edit" ? `Edit ${target.asset.name}` : "New position"}
        description="A position holds the units, its market identifiers and the fallback price."
        onClose={closeForm}
      >
        {target ? (
          <AssetForm
            classes={classes}
            asset={target.kind === "edit" ? target.asset : null}
            locked={target.kind === "edit" && locked.has(target.asset.id)}
            onCancel={closeForm}
            onSaved={() => {
              closeForm();
              router.refresh();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        open={deleting !== null}
        title={deleting ? `Delete ${deleting.name}?` : "Delete position"}
        description="The position and all of its trades are removed permanently."
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
              {busy ? "Deleting…" : "Delete position"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
