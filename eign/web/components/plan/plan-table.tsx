"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type FilterFn,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type {
  Asset,
  AssetClassInfo,
  PlanStatus,
  TradePlan,
} from "@/lib/types";
import { formatMoney, formatNumber, formatPercent, formatQuantity } from "@/lib/format";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";

const columnHelper = createColumnHelper<TradePlan>();

const STATUS_STYLES: Record<PlanStatus, string> = {
  planned: "bg-muted text-muted-foreground",
  executed: "bg-positive/15 text-positive",
  cancelled: "bg-negative/15 text-negative",
};

export type Progress = {
  targetText: string;
  filledText: string;
  pct: number | null;
};

/** Describe a plan's progress in its own unit (units or money). */
export function progressOf(
  plan: TradePlan,
  assetsById: Map<number, Asset>,
): Progress {
  const asset = plan.assetId != null ? assetsById.get(plan.assetId) : undefined;
  const pct =
    plan.quantity != null
      ? plan.quantity > 0
        ? plan.filled / plan.quantity
        : null
      : plan.amount != null && plan.amount > 0
        ? plan.filled / plan.amount
        : null;

  if (plan.quantity != null) {
    return {
      targetText: `${formatQuantity(plan.quantity)} ${asset?.unit ?? ""}`.trim(),
      filledText: formatQuantity(plan.filled),
      pct,
    };
  }
  if (asset) {
    return {
      targetText: formatMoney(plan.amount, asset.currency),
      filledText: formatMoney(plan.filled, asset.currency),
      pct,
    };
  }
  return {
    targetText: formatNumber(plan.amount),
    filledText: formatNumber(plan.filled),
    pct,
  };
}

function targetLabel(plan: TradePlan, assetsById: Map<number, Asset>, classes: Map<number, AssetClassInfo>): { title: string; meta: string } {
  if (plan.assetId != null) {
    const asset = assetsById.get(plan.assetId);
    return {
      title: asset?.name ?? `#${plan.assetId}`,
      meta: asset ? `position · ${asset.assetClassCode}` : "position",
    };
  }
  const item = plan.assetClassId != null ? classes.get(plan.assetClassId) : undefined;
  return {
    title: item?.code ?? `class #${plan.assetClassId ?? "?"}`,
    meta: "whole class",
  };
}

export function PlanTable({
  plans,
  assets,
  classes,
  onEdit,
  onDelete,
}: {
  plans: readonly TradePlan[];
  assets: readonly Asset[];
  classes: readonly AssetClassInfo[];
  onEdit: (plan: TradePlan) => void;
  onDelete: (plan: TradePlan) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "target", desc: false }]);
  const [statusFilter, setStatusFilter] = useState<"" | PlanStatus>("");
  const [search, setSearch] = useState("");

  const assetsById = useMemo(() => new Map(assets.map((asset) => [asset.id, asset])), [assets]);
  const classesById = useMemo(
    () => new Map(classes.map((item) => [item.id, item])),
    [classes],
  );

  const data = useMemo(
    () => plans.filter((plan) => (statusFilter ? plan.status === statusFilter : true)),
    [plans, statusFilter],
  );

  const matchesSearch: FilterFn<TradePlan> = useMemo(
    () => (row, _columnId, filterValue: unknown) => {
      const query = String(filterValue ?? "").trim().toLowerCase();
      if (!query) return true;
      const plan = row.original;
      const label = targetLabel(plan, assetsById, classesById);
      return [label.title, label.meta, plan.note, plan.direction]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query);
    },
    [assetsById, classesById],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor((plan) => targetLabel(plan, assetsById, classesById).title, {
        id: "target",
        header: "Target",
        cell: (info) => {
          const label = targetLabel(info.row.original, assetsById, classesById);
          return (
            <div>
              <div className="font-medium">{label.title}</div>
              <div className="text-xs text-muted-foreground">{label.meta}</div>
            </div>
          );
        },
      }),
      columnHelper.accessor("direction", {
        header: "Direction",
        cell: (info) => (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-semibold",
              info.getValue() === "BUY" ? "bg-positive/15 text-positive" : "bg-negative/15 text-negative",
            )}
          >
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.display({
        id: "target_value",
        header: "Planned",
        cell: (info) => progressOf(info.row.original, assetsById).targetText,
        meta: { align: "right" },
      }),
      columnHelper.display({
        id: "progress",
        header: "Filled",
        cell: (info) => {
          const plan = info.row.original;
          const { filledText, pct } = progressOf(plan, assetsById);
          const width = pct === null ? 0 : Math.min(100, Math.max(0, pct * 100));
          return (
            <div className="min-w-32">
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span>{filledText}</span>
                <span className="text-muted-foreground">{formatPercent(pct, 0)}</span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full",
                    plan.status === "executed"
                      ? "bg-positive"
                      : plan.status === "cancelled"
                        ? "bg-negative/50"
                        : "bg-primary",
                  )}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        },
        meta: { align: "right" },
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-semibold capitalize",
              STATUS_STYLES[info.getValue()],
            )}
          >
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("note", {
        header: "Note",
        cell: (info) => (
          <span className="text-xs text-muted-foreground">{info.getValue() ?? "—"}</span>
        ),
        enableSorting: false,
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        cell: (info) => {
          const plan = info.row.original;
          return (
            <div className="flex justify-end gap-1">
              <Button size="sm" onClick={() => onEdit(plan)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => onDelete(plan)}>
                Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [assetsById, classesById, onEdit, onDelete],
  );

  const table = useReactTable({
    // See AssetsTable: copying the array breaks TanStack's memoisation and
    // freezes the page through the page-index auto-reset.
    data,
    columns,
    state: { sorting, globalFilter: search },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearch,
    globalFilterFn: matchesSearch,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    autoResetPageIndex: false,
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex-1 basis-48 space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Search</span>
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Target, direction, note…"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Status</span>
          <Select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as "" | PlanStatus)}
          >
            <option value="">All statuses</option>
            <option value="planned">Planned</option>
            <option value="executed">Executed</option>
            <option value="cancelled">Cancelled</option>
          </Select>
        </label>
      </div>

      {table.getRowModel().rows.length === 0 ? (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          {plans.length === 0
            ? "No planned trades for this month yet."
            : "Nothing matches the current filters."}
        </p>
      ) : (
        <Table>
          <TableHead>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const align = header.column.columnDef.meta?.align === "right";
                  return (
                    <TableHeaderCell
                      key={header.id}
                      className={align ? "text-right" : undefined}
                      aria-sort={
                        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined
                      }
                    >
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 uppercase hover:text-foreground"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span aria-hidden>{sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}</span>
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </TableHeaderCell>
                  );
                })}
              </TableRow>
            ))}
          </TableHead>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cell.column.columnDef.meta?.align === "right" ? "text-right" : undefined}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
