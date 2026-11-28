"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { UserRole } from "@/lib/types";
import { cn } from "@/lib/utils";

type NavLink = { href: string; label: string; adminOnly?: boolean };

/** Order matches the navigation order in the app shell. */
const LINKS: readonly NavLink[] = [
  { href: "/portfolio/summary", label: "Summary" },
  { href: "/assets", label: "Positions" },
  { href: "/trades", label: "Trades" },
  { href: "/income", label: "Income" },
  { href: "/plan", label: "Plan" },
  { href: "/goals", label: "Goals" },
  { href: "/users", label: "Users", adminOnly: true },
];

export function Nav({ role }: { role: UserRole }) {
  const pathname = usePathname();
  // `/users` is admin-only: the API enforces it and the page re-checks the
  // role, so hiding the link only keeps the UI honest for regular users.
  const links = LINKS.filter((link) => !link.adminOnly || role === "admin");

  return (
    <nav aria-label="Sections" className="flex flex-wrap items-center gap-1">
      {links.map((link) => {
        const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
