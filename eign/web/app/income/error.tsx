"use client";

import { useEffect } from "react";

import { ApiErrorPanel } from "@/components/api-error-panel";

export default function IncomeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-4">
      <ApiErrorPanel
        title="Could not render the income plan"
        detail={error.message}
        hint="Reload the page. If the problem persists, check the Eign API logs."
      />
      <button
        type="button"
        onClick={reset}
        className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
      >
        Try again
      </button>
    </div>
  );
}
