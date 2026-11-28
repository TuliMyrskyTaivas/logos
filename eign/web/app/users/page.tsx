import { ApiErrorPanel } from "@/components/api-error-panel";
import { UsersView } from "@/components/users/users-view";
import { describeError, fetchCurrentUser, fetchUsers } from "@/lib/api";
import { resolveIdentity } from "@/lib/identity";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const identity = await resolveIdentity();
  if (!identity) return null;

  try {
    const me = await fetchCurrentUser(identity);
    if (me.role !== "admin") {
      return (
        <ApiErrorPanel
          title="Administrators only"
          detail={`The account ${me.login} has the user role, so user management is not available.`}
          hint="Ask an administrator to grant the admin role if you need to manage accounts."
        />
      );
    }
    const users = await fetchUsers(identity);
    return <UsersView users={users} currentUserId={me.id} />;
  } catch (error) {
    return (
      <ApiErrorPanel
        title="Users are unavailable"
        detail={describeError(error)}
        hint="The page reads /auth/me and /users from the Eign API (administrators only)."
      />
    );
  }
}
