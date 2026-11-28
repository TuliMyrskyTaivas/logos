export function ApiErrorPanel({
  title,
  detail,
  hint,
}: {
  title: string;
  detail: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-negative/40 bg-card p-6">
      <h2 className="text-base font-semibold text-negative">{title}</h2>
      <p className="mt-2 break-words text-sm text-muted-foreground">{detail}</p>
      <p className="mt-4 text-xs text-muted-foreground">
        {hint ?? "Check that the Eign API is running and reachable at EIGN_API_URL."}
      </p>
    </div>
  );
}
