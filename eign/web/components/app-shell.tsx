import type { ReactNode } from "react";

import { Nav } from "@/components/nav";
import type { CurrentUser } from "@/lib/types";

export function AppShell({
  user,
  devIdentity,
  children,
}: {
  user: CurrentUser;
  devIdentity: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex items-baseline gap-3">
          <span className="text-lg font-semibold tracking-tight">Eign</span>
          <span className="text-sm text-muted-foreground">Private investment portfolio</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {devIdentity ? (
            <span className="rounded-full border border-amber-500/50 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
              dev identity
            </span>
          ) : null}
          <span className="font-medium">{user.login}</span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {user.role}
          </span>
          <span className="text-muted-foreground">{user.baseCurrency}</span>
        </div>
      </header>
      <div className="pt-3">
        <Nav role={user.role} />
      </div>
      <main className="flex-1 py-6">{children}</main>
      <footer className="border-t border-border pt-4 text-xs text-muted-foreground">
        Eign · portfolio data is visible only to {user.login}
      </footer>
    </div>
  );
}
