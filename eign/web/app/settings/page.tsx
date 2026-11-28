import { ApiErrorPanel } from "@/components/api-error-panel";
import { SettingsView } from "@/components/settings/settings-view";
import { describeError, fetchCurrentUser } from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  try {
    const user = await fetchCurrentUser(identity);
    return <SettingsView user={user} devIdentity={identity.dev} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Settings are unavailable"
        detail={describeError(error)}
        hint="The page reads /auth/me from the Eign API."
      />
    );
  }
}
