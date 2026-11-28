import type { MetricTone } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<MetricTone, string> = {
  neutral: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
};

export function KpiCard({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: MetricTone;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-2 text-2xl font-semibold", TONE_CLASS[tone])}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
