import { ApiErrorPanel } from "@/components/api-error-panel";
import { PlanView } from "@/components/plan/plan-view";
import { describeError, fetchAssetClasses, fetchAssets, fetchTradePlans } from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

function resolveMonth(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw && /^\d{4}-\d{2}$/.test(raw)) return raw;
  return new Date().toISOString().slice(0, 7);
}

export default async function PlanPage({
  searchParams,
}: {
  searchParams: Promise<{ month?: string | string[] }>;
}) {
  const identity = await resolveIdentity();
  if (!identity) return null;

  const month = resolveMonth((await searchParams).month);

  try {
    const [plans, assets, classes] = await Promise.all([
      fetchTradePlans(identity, month),
      fetchAssets(identity),
      fetchAssetClasses(identity),
    ]);
    return <PlanView plans={plans} assets={assets} classes={classes} month={month} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="The trade plan is unavailable"
        detail={describeError(error)}
        hint="The page reads /trade-plan, /assets and /asset-classes from the Eign API."
      />
    );
  }
}
