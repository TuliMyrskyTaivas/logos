"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MonthlyPerformance } from "@/lib/types";
import { formatMoney, formatMonth, toNumber } from "@/lib/format";

type Point = {
  month: string;
  value: number;
  flow: number;
  index: number;
};

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function buildSeries(monthly: readonly MonthlyPerformance[]): Point[] {
  let index = 100;
  return monthly.map((period) => {
    index *= 1 + (period.returnPct ?? 0);
    return {
      month: formatMonth(period.periodDate),
      value: period.value,
      flow: period.flow,
      index: Number(index.toFixed(2)),
    };
  });
}

export function PerformanceChart({
  monthly,
  currency,
}: {
  monthly: readonly MonthlyPerformance[];
  currency: string;
}) {
  const points = buildSeries(monthly);
  if (points.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No valuation snapshots yet. Snapshots are stored by the monthly valuation job.
      </p>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#94a3b8" strokeOpacity={0.3} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <YAxis
            yAxisId="value"
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={64}
            tickFormatter={(value: number) => compact.format(value)}
          />
          <YAxis
            yAxisId="index"
            orientation="right"
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={48}
            domain={["auto", "auto"]}
          />
          <Tooltip
            formatter={(value, name) =>
              name === "Value"
                ? formatMoney(toNumber(value), currency)
                : `${toNumber(value).toFixed(1)}`
            }
          />
          <Area
            yAxisId="value"
            dataKey="value"
            name="Value"
            type="monotone"
            stroke="#2f6feb"
            fill="#2f6feb"
            fillOpacity={0.12}
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Line
            yAxisId="index"
            dataKey="index"
            name="TWR index"
            type="monotone"
            stroke="#2e9e6b"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
