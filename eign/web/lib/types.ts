import type { components } from "./api-types";

export type CurrentUser = components["schemas"]["User"];
export type PortfolioSummary = components["schemas"]["PortfolioSummary"];
export type PortfolioClassSummary = components["schemas"]["PortfolioClassSummary"];
export type PortfolioPosition = components["schemas"]["PortfolioPosition"];
export type Performance = components["schemas"]["Performance"];
export type MonthlyPerformance = components["schemas"]["MonthlyPerformance"];
export type Asset = components["schemas"]["Asset"];
export type AssetClassInfo = components["schemas"]["AssetClassInfo"];
export type AssetUnit = NonNullable<Asset["unit"]>;
export type Trade = components["schemas"]["Trade"];
export type TradeType = NonNullable<Trade["tradeType"]>;
export type TradeCreate = components["schemas"]["TradeCreate"];
export type TradeUpdate = components["schemas"]["TradeUpdate"];
export type AssetCreate = components["schemas"]["AssetCreate"];
export type AssetUpdate = components["schemas"]["AssetUpdate"];
export type IncomePlanFact = components["schemas"]["IncomePlanFact"];
export type IncomeSummary = components["schemas"]["IncomeSummary"];
export type MonthlyIncome = components["schemas"]["MonthlyIncome"];
export type IncomeType = NonNullable<IncomePlanFact["incomeType"]>;
export type IncomeCreate = components["schemas"]["IncomeCreate"];
export type IncomeUpdate = components["schemas"]["IncomeUpdate"];

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = body.detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    // The backend answered with a non-JSON body; fall back to the status line.
  }
  return response.statusText || `HTTP ${response.status}`;
}

export function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.status} ${error.detail}`;
  if (error instanceof Error) return error.message;
  return "Unexpected error";
}
