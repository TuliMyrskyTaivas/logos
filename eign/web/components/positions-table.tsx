import type { PortfolioPosition } from "@/lib/types";
import { formatDate, formatMoney, formatPercent, formatQuantity } from "@/lib/format";
import { unpricedReasonLabel } from "@/lib/metrics";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";

export function PositionsTable({
  positions,
  totalValue,
  currency,
}: {
  positions: readonly PortfolioPosition[];
  totalValue: number;
  currency: string;
}) {
  if (positions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No positions yet. Register a first position through the API to start tracking the portfolio.
      </p>
    );
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>Position</TableHeaderCell>
          <TableHeaderCell className="text-right">Quantity</TableHeaderCell>
          <TableHeaderCell className="text-right">Price</TableHeaderCell>
          <TableHeaderCell>As of</TableHeaderCell>
          <TableHeaderCell className="text-right">Value, {currency}</TableHeaderCell>
          <TableHeaderCell className="text-right">Weight</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {positions.map((position) => {
          const weight =
            totalValue > 0 && typeof position.valueBase === "number"
              ? position.valueBase / totalValue
              : null;
          return (
            <TableRow key={position.assetId}>
              <TableCell>
                <div className="font-medium">{position.name}</div>
                <div className="text-xs text-muted-foreground">
                  {position.assetClassCode} · {position.currency}
                </div>
              </TableCell>
              <TableCell className="text-right">{formatQuantity(position.quantity)}</TableCell>
              <TableCell className="text-right">
                {position.priced ? (
                  formatMoney(position.price, position.priceCurrency ?? position.currency)
                ) : (
                  <span className="text-xs text-negative">{unpricedReasonLabel(position.unpricedReason)}</span>
                )}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {position.priced
                  ? `${formatDate(position.priceDate)} · ${position.priceSource ?? "manual"}`
                  : "—"}
              </TableCell>
              <TableCell className="text-right">{formatMoney(position.valueBase, currency)}</TableCell>
              <TableCell className="text-right">{formatPercent(weight)}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
