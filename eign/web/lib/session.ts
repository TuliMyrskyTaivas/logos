import { fetchCurrentUser } from "./api";
import { resolveIdentity, type Identity } from "./identity";
import { describeError, type CurrentUser } from "./types";

export type Session =
  | { kind: "anonymous" }
  | { kind: "rejected"; detail: string }
  | { kind: "ready"; user: CurrentUser; identity: Identity };

/** Load the caller identity and the user record it maps to. */
export async function loadSession(): Promise<Session> {
  try {
    const identity = await resolveIdentity();
    if (!identity) return { kind: "anonymous" };
    const user = await fetchCurrentUser(identity);
    return { kind: "ready", user, identity };
  } catch (error) {
    // Never turn an identity/API failure into an unhandled 500: show the reason.
    return { kind: "rejected", detail: describeError(error) };
  }
}
