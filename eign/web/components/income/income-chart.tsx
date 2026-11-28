"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IncomeSummary } from "@/lib/types";
import { formatMoney, toNumber } from "@/lib/format";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

type Datum = { month: string; planned: number; actual: number };

function buildSeries(summary: IncomeSummary): Datum[] {
  const byMonth = new Map(summary.months.map((item) => [item.month.slice(0, 7), item]));
  return MONTHS.map((label, index) => {
    const key = `${summary.year}-${String(index + 1).padStart(2, "0")}`;
    const item = byMonth.get(key);
    return {
      month: label,
      planned: item?.plannedBase ?? 0,
      actual: item?.actualBase ?? 0,
    };
  });
}

export function IncomeChart({ summary }: { summary: IncomeSummary }) {
  const data = buildSeries(summary);
  const hasData = data.some((item) => item.planned > 0 || item.actual > 0);
  if (!hasData) {
    return (
      <p className="text-sm text-muted-foreground">
        No planned or received income in {summary.year} yet.
      </p>
    );
  }

  const compact = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  });

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#94a3b8" strokeOpacity={0.3} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={64}
            tickFormatter={(value: number) => compact.format(value)}
          />
          <Tooltip
            formatter={(value, name) => [
              formatMoney(toNumber(value), summary.baseCurrency),
              name === "planned" ? "Planned" : "Actual",
            ]}
          />
          <Legend
            formatter={(value) => (value === "planned" ? "Planned" : "Actual")}
            iconType="circle"
          />
          <Bar dataKey="planned" fill="#94a3b8" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="actual" fill="#2e9e6b" radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
