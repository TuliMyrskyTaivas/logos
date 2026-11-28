import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type AlertTone = "warning" | "error" | "info";

const TONE_CLASS: Record<AlertTone, string> = {
  warning: "border-l-4 border-l-amber-500",
  error: "border-l-4 border-l-negative",
  info: "border-l-4 border-l-primary",
};

export function Alert({
  tone = "warning",
  title,
  children,
}: {
  tone?: AlertTone;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-card px-4 py-3", TONE_CLASS[tone])}>
      <p className="text-sm font-medium">{title}</p>
      {children ? <div className="mt-1 text-sm text-muted-foreground">{children}</div> : null}
    </div>
  );
}
