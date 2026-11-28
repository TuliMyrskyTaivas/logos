import { ApiErrorPanel } from "@/components/api-error-panel";
import { IncomeView } from "@/components/income/income-view";
import {
  describeError,
  fetchAssets,
  fetchIncomeRows,
  fetchIncomeSummary,
} from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

function resolveYear(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number(raw);
  const current = new Date().getUTCFullYear();
  if (!Number.isInteger(parsed) || parsed < 2000 || parsed > 2200) return current;
  return parsed;
}

export default async function IncomePage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string | string[] }>;
}) {
  const identity = await resolveIdentity();
  if (!identity) return null;

  const year = resolveYear((await searchParams).year);

  try {
    const [rows, summary, assets] = await Promise.all([
      fetchIncomeRows(identity, year),
      fetchIncomeSummary(identity, year),
      fetchAssets(identity),
    ]);
    return <IncomeView rows={rows} summary={summary} assets={assets} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Income is unavailable"
        detail={describeError(error)}
        hint="The page reads /income, /income/summary and /assets from the Eign API."
      />
    );
  }
}
