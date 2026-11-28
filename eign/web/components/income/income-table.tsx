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

import type { Asset, IncomePlanFact, IncomeType } from "@/lib/types";
import { formatMoney, formatMonth } from "@/lib/format";

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

const columnHelper = createColumnHelper<IncomePlanFact>();

const TYPE_LABELS: Record<IncomeType, string> = {
  dividend: "Dividend",
  coupon: "Coupon",
  interest: "Interest",
  other: "Other",
};

const matchesSearch: FilterFn<IncomePlanFact> = (row, _columnId, filterValue: unknown) => {
  const query = String(filterValue ?? "").trim().toLowerCase();
  if (!query) return true;
  const row_ = row.original;
  return [row_.note, row_.incomeType, row_.currency]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(query);
};

export function IncomeTable({
  rows,
  assets,
  onEdit,
  onDelete,
}: {
  rows: readonly IncomePlanFact[];
  assets: readonly Asset[];
  onEdit: (row: IncomePlanFact) => void;
  onDelete: (row: IncomePlanFact) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "month", desc: true }]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | IncomeType>("");
  const [assetFilter, setAssetFilter] = useState("");

  const assetsById = useMemo(
    () => new Map(assets.map((asset) => [asset.id, asset])),
    [assets],
  );

  const data = useMemo(
    () =>
      rows.filter((row) => {
        if (typeFilter && row.incomeType !== typeFilter) return false;
        if (assetFilter === "none" && row.assetId !== null) return false;
        if (assetFilter && assetFilter !== "none" && String(row.assetId) !== assetFilter) {
          return false;
        }
        return true;
      }),
    [rows, typeFilter, assetFilter],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor("month", {
        header: "Month",
        cell: (info) => formatMonth(info.getValue()),
      }),
      columnHelper.accessor("assetId", {
        header: "Position",
        cell: (info) => {
          const id = info.getValue();
          if (id === null || id === undefined) {
            return <span className="text-muted-foreground">Portfolio</span>;
          }
          const asset = assetsById.get(id);
          return (
            <div>
              <div className="font-medium">{asset?.name ?? `#${id}`}</div>
              {asset ? (
                <div className="text-xs text-muted-foreground">{asset.assetClassCode}</div>
              ) : null}
            </div>
          );
        },
        enableSorting: false,
      }),
      columnHelper.accessor("incomeType", {
        header: "Type",
        cell: (info) => (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {TYPE_LABELS[info.getValue()] ?? info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("plannedAmount", {
        header: "Planned",
        cell: (info) =>
          info.getValue() == null
            ? "—"
            : formatMoney(info.getValue(), info.row.original.currency),
        meta: { align: "right" },
        enableSorting: false,
      }),
      columnHelper.accessor("actualAmount", {
        header: "Actual",
        cell: (info) =>
          info.getValue() == null ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            formatMoney(info.getValue(), info.row.original.currency)
          ),
        meta: { align: "right" },
        enableSorting: false,
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
          const row = info.row.original;
          return (
            <div className="flex justify-end gap-1">
              <Button size="sm" onClick={() => onEdit(row)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => onDelete(row)}>
                Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [assetsById, onEdit, onDelete],
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
            placeholder="Note, type, currency…"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Type</span>
          <Select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as "" | IncomeType)}
          >
            <option value="">All types</option>
            {(Object.keys(TYPE_LABELS) as IncomeType[]).map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Position</span>
          <Select value={assetFilter} onChange={(event) => setAssetFilter(event.target.value)}>
            <option value="">All sources</option>
            <option value="none">Portfolio (no position)</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </Select>
        </label>
      </div>

      {table.getRowModel().rows.length === 0 ? (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          {rows.length === 0
            ? "No income rows for this year. Add dividends, coupons or interest to plan and track them."
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
