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

import type { Asset, AssetClassInfo } from "@/lib/types";
import { formatMoney, formatQuantity } from "@/lib/format";

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

const columnHelper = createColumnHelper<Asset>();

const matchesSearch: FilterFn<Asset> = (row, _columnId, filterValue: unknown) => {
  const query = String(filterValue ?? "").trim().toLowerCase();
  if (!query) return true;
  const asset = row.original;
  return [asset.name, asset.ticker, asset.isin, asset.assetClassCode, asset.custodian]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(query);
};

export function AssetsTable({
  assets,
  classes,
  lockedAssetIds,
  onEdit,
  onDelete,
}: {
  assets: readonly Asset[];
  classes: readonly AssetClassInfo[];
  lockedAssetIds: ReadonlySet<number>;
  onEdit: (asset: Asset) => void;
  onDelete: (asset: Asset) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "name", desc: false }]);
  const [search, setSearch] = useState("");
  const [classCode, setClassCode] = useState("");

  const data = useMemo(
    () => assets.filter((asset) => (classCode ? asset.assetClassCode === classCode : true)),
    [assets, classCode],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Position",
        cell: (info) => {
          const asset = info.row.original;
          const meta = [asset.ticker, asset.isin, asset.metalCode].filter(Boolean).join(" · ");
          return (
            <div>
              <div className="font-medium">{asset.name}</div>
              {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
            </div>
          );
        },
      }),
      columnHelper.accessor("assetClassCode", {
        header: "Class",
        cell: (info) => (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("quantity", {
        header: "Quantity",
        cell: (info) => `${formatQuantity(info.getValue())} ${info.row.original.unit}`,
        meta: { align: "right" },
      }),
      columnHelper.accessor("avgPurchasePrice", {
        header: "Avg price",
        cell: (info) =>
          formatMoney(info.getValue() ?? null, info.row.original.currency),
        meta: { align: "right" },
        enableSorting: false,
      }),
      columnHelper.accessor("currentPrice", {
        header: "Current price",
        cell: (info) =>
          formatMoney(info.getValue() ?? null, info.row.original.currency),
        meta: { align: "right" },
        enableSorting: false,
      }),
      columnHelper.accessor("custodian", {
        header: "Custodian",
        cell: (info) => info.getValue() ?? "—",
        enableSorting: false,
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        cell: (info) => {
          const asset = info.row.original;
          return (
            <div className="flex justify-end gap-1">
              <Button size="sm" onClick={() => onEdit(asset)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => onDelete(asset)}>
                Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [onEdit, onDelete],
  );

  const table = useReactTable({
    // TanStack memoises the row model on the identity of `data`: a fresh copy
    // on every render re-creates it, re-triggers its page-index auto-reset and
    // loops forever. Always pass the memoised array itself.
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

  const classCodes = useMemo(() => {
    const used = new Set(assets.map((asset) => asset.assetClassCode));
    return classes.filter((item) => used.has(item.code));
  }, [assets, classes]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex-1 basis-56 space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Search</span>
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Name, ticker, ISIN, custodian…"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Class</span>
          <Select value={classCode} onChange={(event) => setClassCode(event.target.value)}>
            <option value="">All classes</option>
            {classCodes.map((item) => (
              <option key={item.id} value={item.code}>
                {item.code}
              </option>
            ))}
          </Select>
        </label>
      </div>

      {table.getRowModel().rows.length === 0 ? (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          {assets.length === 0
            ? "No positions yet. Create the first one to start tracking the portfolio."
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

      {lockedAssetIds.size > 0 ? (
        <p className="text-xs text-muted-foreground">
          Quantity and average price are derived from trades for positions that already have them.
        </p>
      ) : null}
    </div>
  );
}
