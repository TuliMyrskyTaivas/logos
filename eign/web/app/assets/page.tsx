import { ApiErrorPanel } from "@/components/api-error-panel";
import { AssetsView } from "@/components/assets/assets-view";
import {
  describeError,
  fetchAssetClasses,
  fetchAssets,
  fetchTrades,
} from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function AssetsPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  try {
    const [assets, classes, trades] = await Promise.all([
      fetchAssets(identity),
      fetchAssetClasses(identity),
      fetchTrades(identity),
    ]);
    const lockedAssetIds = [...new Set(trades.map((trade) => trade.assetId))];

    return <AssetsView assets={assets} classes={classes} lockedAssetIds={lockedAssetIds} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Positions are unavailable"
        detail={describeError(error)}
        hint="The page reads /assets, /asset-classes and /trades from the Eign API."
      />
    );
  }
}
