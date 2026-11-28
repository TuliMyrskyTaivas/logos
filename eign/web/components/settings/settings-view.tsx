"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError, type CurrentUser } from "@/lib/types";
import { patchJson } from "@/lib/client-api";
import { formatDate } from "@/lib/format";

import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormError, Input, Select } from "@/components/ui/field";

/** Currencies offered as the portfolio base; metals are quoted per gram. */
const BASE_CURRENCIES = ["RUB", "USD", "EUR", "CNY", "XAU", "XAG"] as const;

function initialRate(user: CurrentUser): string {
  return user.riskFreeRate != null
    ? String(Math.round(user.riskFreeRate * 10000) / 100)
    : "";
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function SettingsView({
  user,
  devIdentity,
}: {
  user: CurrentUser;
  devIdentity: boolean;
}) {
  const router = useRouter();
  const [currency, setCurrency] = useState(user.baseCurrency);
  const [rate, setRate] = useState(() => initialRate(user));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const rateValue = numberOrNull(rate);
  const rateFraction = rateValue === null ? null : rateValue / 100;
  const storedRate = user.riskFreeRate ?? null;
  const rateChanged =
    (rateFraction === null) !== (storedRate === null) ||
    Math.abs((rateFraction ?? 0) - (storedRate ?? 0)) > 1e-9;
  const changed = currency !== user.baseCurrency || rateChanged;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaved(false);

    if (rateValue !== null && (rateValue <= -100 || rateValue > 1000)) {
      setError("Enter the annual rate in percent, for example 16.");
      return;
    }

    setSaving(true);
    try {
      await patchJson("/auth/me", {
        baseCurrency: currency,
        riskFreeRate: rateValue === null ? null : rateValue / 100,
      });
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not save the settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Portfolio preferences of {user.login}. They affect every screen because all values are
          converted to the base currency.
        </p>
      </header>

      <SectionCard
        title="Portfolio"
        description="Base currency and the rate used by the Sharpe and Sortino ratios"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormError message={error} />
          {saved ? (
            <p className="rounded-md border border-positive/40 bg-positive/10 px-3 py-2 text-sm text-positive">
              Settings saved.
            </p>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Base currency"
              htmlFor="settings-currency"
              hint="Fiat currencies are converted with CBR rates; metals are quoted per gram."
            >
              <Select
                id="settings-currency"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              >
                {BASE_CURRENCIES.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Risk-free rate, % per year"
              htmlFor="settings-rate"
              hint={
                user.riskFreeRate != null
                  ? `Currently ${(user.riskFreeRate * 100).toFixed(2)} %; leave empty to use the service default.`
                  : "Empty uses the service default. Example: 16 for OFZ or a deposit."
              }
            >
              <Input
                id="settings-rate"
                value={rate}
                onChange={(event) => setRate(event.target.value)}
                inputMode="decimal"
                placeholder="16"
              />
            </Field>
          </div>

          <div className="flex items-center justify-end gap-3">
            {!changed ? (
              <span className="text-xs text-muted-foreground">No changes</span>
            ) : null}
            <Button type="submit" variant="primary" disabled={saving || !changed}>
              {saving ? "Saving…" : "Save settings"}
            </Button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="Account" description="Identity comes from the client certificate">
        <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Login</dt>
            <dd className="mt-0.5 font-medium">{user.login}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Role</dt>
            <dd className="mt-0.5 font-medium uppercase">{user.role}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Status</dt>
            <dd className={user.isActive ? "mt-0.5 font-medium text-positive" : "mt-0.5 font-medium text-negative"}>
              {user.isActive ? "active" : "deactivated"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Last login</dt>
            <dd className="mt-0.5 font-medium">
              {user.lastLoginAt ? formatDate(user.lastLoginAt.slice(0, 10)) : "never"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Identity source</dt>
            <dd className="mt-0.5 text-muted-foreground">
              {devIdentity
                ? "EIGN_DEV_LOGIN (development only): nginx is not in front of the app."
                : "mTLS client certificate verified by nginx (X-Client-CN)."}
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-muted-foreground">
          Roles are managed by administrators on the Users page; certificates are issued by the
          external CA. Passwords are not used.
        </p>
      </SectionCard>
    </div>
  );
}
