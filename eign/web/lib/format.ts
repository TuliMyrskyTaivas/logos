const LOCALE = "en-US";
const DASH = "\u2014";

const moneyFormats = new Map<string, Intl.NumberFormat | null>();
const numberFormats = new Map<string, Intl.NumberFormat>();

function moneyFormat(currency: string): Intl.NumberFormat | null {
  if (!moneyFormats.has(currency)) {
    try {
      moneyFormats.set(
        currency,
        new Intl.NumberFormat(LOCALE, {
          style: "currency",
          currency,
          maximumFractionDigits: 2,
        }),
      );
    } catch {
      // Not an ISO 4217 code (metals such as XAU are quoted in grams).
      moneyFormats.set(currency, null);
    }
  }
  return moneyFormats.get(currency) ?? null;
}

function numberFormat(digits: number): Intl.NumberFormat {
  const key = digits.toFixed(0);
  let formatter = numberFormats.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    numberFormats.set(key, formatter);
  }
  return formatter;
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  if (Array.isArray(value) && value.length > 0) return toNumber(value[0]);
  return Number.NaN;
}

export function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatMoney(value: number | null | undefined, currency: string): string {
  if (!isFiniteNumber(value)) return DASH;
  const formatter = moneyFormat(currency);
  return formatter ? formatter.format(value) : `${formatNumber(value, 2)} ${currency}`;
}

export function formatSignedMoney(value: number | null | undefined, currency: string): string {
  if (!isFiniteNumber(value)) return DASH;
  const formatted = formatMoney(Math.abs(value), currency);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `\u2212${formatted}`;
  return formatted;
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(value)) return DASH;
  return numberFormat(digits).format(value);
}

export function formatQuantity(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return DASH;
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 6 }).format(value);
}

/** Format a ratio (0.1234) as a percentage string (12.34 %). */
export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(value)) return DASH;
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

export function formatMonth(value: string | null | undefined): string {
  if (!value) return DASH;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(LOCALE, {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}
