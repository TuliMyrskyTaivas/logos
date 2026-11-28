export function IdentityScreen({
  title,
  detail,
  steps,
}: {
  title: string;
  detail: string;
  steps?: readonly string[];
}) {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-xl items-center px-4">
      <div className="w-full rounded-xl border border-border bg-card p-6 shadow-sm">
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="mt-2 break-words text-sm text-muted-foreground">{detail}</p>
        {steps && steps.length > 0 ? (
          <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
