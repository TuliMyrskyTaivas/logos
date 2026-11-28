import { cn } from "@/lib/utils";

export type MetricTone = "neutral" | "positive" | "negative";

export function toneOf(value: number | null | undefined): MetricTone {
  if (typeof value !== "number" || !Number.isFinite(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

const UNPRICED_REASONS: Record<string, string> = {
  no_instrument: "instrument not identified",
  no_price: "no price",
  no_rate: "no FX rate",
};

export function unpricedReasonLabel(reason: string | null | undefined): string {
  if (!reason) return "not priced";
  return UNPRICED_REASONS[reason] ?? reason;
}

export function toneClass(tone: MetricTone): string {
  return cn(
    tone === "positive" && "text-positive",
    tone === "negative" && "text-negative",
    tone === "neutral" && "text-foreground",
  );
}
