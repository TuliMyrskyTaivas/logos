import { ApiErrorPanel } from "@/components/api-error-panel";
import { GoalsView } from "@/components/goals/goals-view";
import { describeError, fetchAssetClasses, fetchGoalProgress, fetchGoals } from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function GoalsPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  try {
    const [goal, progress, classes] = await Promise.all([
      fetchGoals(identity),
      fetchGoalProgress(identity),
      fetchAssetClasses(identity),
    ]);
    return <GoalsView goal={goal} progress={progress} classes={classes} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Goals are unavailable"
        detail={describeError(error)}
        hint="The page reads /goals, /goals/progress and /asset-classes from the Eign API."
      />
    );
  }
}
