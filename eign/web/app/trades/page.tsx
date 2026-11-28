import { ApiErrorPanel } from "@/components/api-error-panel";
import { TradesView } from "@/components/trades/trades-view";
import { describeError, fetchAssets, fetchTrades } from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function TradesPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  try {
    const [trades, assets] = await Promise.all([fetchTrades(identity), fetchAssets(identity)]);
    return <TradesView trades={trades} assets={assets} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Trades are unavailable"
        detail={describeError(error)}
        hint="The page reads /trades and /assets from the Eign API."
      />
    );
  }
}
