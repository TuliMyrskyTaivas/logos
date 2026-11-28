import { headers } from "next/headers";

const LOGIN_HEADER = "x-client-cn";
const VERIFY_HEADER = "x-ssl-client-verify";

export type Identity = {
  login: string;
  /** True when the login was taken from EIGN_DEV_LOGIN instead of nginx. */
  dev: boolean;
};

/**
 * Resolve the caller identity.
 *
 * In production nginx terminates mTLS and forwards `X-Client-CN` together with
 * `X-SSL-Client-Verify`. Outside nginx (local development) the identity falls
 * back to `EIGN_DEV_LOGIN`, which must never be set in a deployed environment.
 */
export async function resolveIdentity(): Promise<Identity | null> {
  const incoming = await headers();
  const login = incoming.get(LOGIN_HEADER)?.trim();
  const verified = incoming.get(VERIFY_HEADER)?.trim().toUpperCase() === "SUCCESS";
  if (login && verified) return { login, dev: false };

  const devLogin = process.env.EIGN_DEV_LOGIN?.trim();
  return devLogin ? { login: devLogin, dev: true } : null;
}

/** Headers the backend expects from nginx. */
export function identityHeaders(identity: Identity): Record<string, string> {
  return {
    "X-Client-CN": identity.login,
    "X-SSL-Client-Verify": "SUCCESS",
  };
}
