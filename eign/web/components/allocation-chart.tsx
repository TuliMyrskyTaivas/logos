"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatMoney, formatPercent, toNumber } from "@/lib/format";

const COLORS = ["#2f6feb", "#2e9e6b", "#d9822b", "#8b5cf6", "#d64550", "#0ea5a4", "#a3a30f", "#7c8592"];

export type AllocationSlice = {
  code: string;
  value: number;
  weight: number;
};

export function AllocationChart({
  data,
  currency,
}: {
  data: readonly AllocationSlice[];
  currency: string;
}) {
  const slices = [...data].filter((slice) => slice.value > 0).sort((a, b) => b.value - a.value);
  if (slices.length === 0) {
    return <p className="text-sm text-muted-foreground">No valued positions yet.</p>;
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="h-56 w-full sm:w-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="code"
              innerRadius={54}
              outerRadius={86}
              paddingAngle={2}
              strokeWidth={0}
              isAnimationActive={false}
            >
              {slices.map((slice, index) => (
                <Cell key={slice.code} fill={COLORS[index % COLORS.length] ?? "#7c8592"} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => formatMoney(toNumber(value), currency)} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex-1 space-y-2">
        {slices.map((slice, index) => (
          <li key={slice.code} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="inline-block size-2.5 rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] ?? "#7c8592" }}
              />
              {slice.code}
            </span>
            <span className="text-muted-foreground">
              {formatPercent(slice.weight)}
              <span className="ml-2 text-foreground">{formatMoney(slice.value, currency)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
