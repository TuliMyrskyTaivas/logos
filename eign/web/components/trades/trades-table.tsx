"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { Asset, Trade, TradeType } from "@/lib/types";
import { formatDate, formatMoney, formatQuantity } from "@/lib/format";
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

const columnHelper = createColumnHelper<Trade>();

export function TradesTable({
  trades,
  assets,
  onEdit,
  onDelete,
}: {
  trades: readonly Trade[];
  assets: readonly Asset[];
  onEdit: (trade: Trade) => void;
  onDelete: (trade: Trade) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "tradeDate", desc: true }]);
  const [assetFilter, setAssetFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | TradeType>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const assetsById = useMemo(
    () => new Map(assets.map((asset) => [asset.id, asset])),
    [assets],
  );

  const data = useMemo(
    () =>
      trades.filter((trade) => {
        if (assetFilter && String(trade.assetId) !== assetFilter) return false;
        if (typeFilter && trade.tradeType !== typeFilter) return false;
        if (dateFrom && trade.tradeDate < dateFrom) return false;
        if (dateTo && trade.tradeDate > dateTo) return false;
        return true;
      }),
    [trades, assetFilter, typeFilter, dateFrom, dateTo],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor("tradeDate", {
        header: "Date",
        cell: (info) => formatDate(info.getValue()),
      }),
      columnHelper.accessor("assetId", {
        header: "Position",
        cell: (info) => {
          const asset = assetsById.get(info.getValue());
          return (
            <div>
              <div className="font-medium">{asset?.name ?? `#${info.getValue()}`}</div>
              {asset ? (
                <div className="text-xs text-muted-foreground">{asset.assetClassCode}</div>
              ) : null}
            </div>
          );
        },
        enableSorting: false,
      }),
      columnHelper.accessor("tradeType", {
        header: "Direction",
        cell: (info) => (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-semibold",
              info.getValue() === "BUY"
                ? "bg-positive/15 text-positive"
                : "bg-negative/15 text-negative",
            )}
          >
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("quantity", {
        header: "Quantity",
        cell: (info) => formatQuantity(info.getValue()),
        meta: { align: "right" },
      }),
      columnHelper.accessor("price", {
        header: "Price",
        cell: (info) => formatMoney(info.getValue(), info.row.original.currency),
        meta: { align: "right" },
      }),
      columnHelper.accessor("fee", {
        header: "Fee",
        cell: (info) => formatMoney(info.getValue(), info.row.original.currency),
        meta: { align: "right" },
      }),
      columnHelper.display({
        id: "amount",
        header: "Amount",
        cell: (info) => {
          const trade = info.row.original;
          return formatMoney(trade.quantity * trade.price, trade.currency);
        },
        meta: { align: "right" },
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
          const trade = info.row.original;
          return (
            <div className="flex justify-end gap-1">
              <Button size="sm" onClick={() => onEdit(trade)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => onDelete(trade)}>
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
    // See AssetsTable: the array must keep its identity between renders,
    // otherwise the page-index auto-reset loops.
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    autoResetPageIndex: false,
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Position</span>
          <Select value={assetFilter} onChange={(event) => setAssetFilter(event.target.value)}>
            <option value="">All positions</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Direction</span>
          <Select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as "" | TradeType)}
          >
            <option value="">All</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </Select>
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">From</span>
          <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">To</span>
          <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </label>
      </div>

      {table.getRowModel().rows.length === 0 ? (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          {trades.length === 0
            ? "No trades yet. Register the first one to build the position history."
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
