import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { IdentityScreen } from "@/components/identity-screen";
import { loadSession } from "@/lib/session";

import "./globals.css";

export const metadata: Metadata = {
  title: "Eign — private investment portfolio",
  description: "Valuation, performance and planning for a private investment portfolio.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await loadSession();

  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        {session.kind === "ready" ? (
          <AppShell user={session.user} devIdentity={session.identity.dev}>
            {children}
          </AppShell>
        ) : session.kind === "anonymous" ? (
          <IdentityScreen
            title="Client certificate required"
            detail="Eign identifies users by the mTLS client certificate verified by nginx. No identity reached this server."
            steps={[
              "In development, set EIGN_DEV_LOGIN to the login to act as.",
              "In production, requests must pass through nginx with ssl_verify_client on.",
            ]}
          />
        ) : (
          <IdentityScreen title="Access denied" detail={session.detail} />
        )}
      </body>
    </html>
  );
}
