import { identityHeaders, type Identity } from "./identity";
import {
  ApiError,
  errorDetail,
  type Asset,
  type AssetClassInfo,
  type CurrentUser,
  type Goal,
  type GoalProgress,
  type IncomePlanFact,
  type IncomeSummary,
  type Performance,
  type PortfolioSummary,
  type Trade,
  type TradePlan,
} from "./types";

export type {
  Asset,
  AssetClassInfo,
  AssetCreate,
  AssetUnit,
  AssetUpdate,
  CurrentUser,
  Goal,
  GoalAllocation,
  GoalAllocationProgress,
  GoalProgress,
  GoalUpdate,
  IncomeCreate,
  IncomePlanFact,
  IncomeSummary,
  IncomeType,
  IncomeUpdate,
  MonthlyIncome,
  MonthlyPerformance,
  Performance,
  PlanStatus,
  PlanStatusInput,
  PortfolioClassSummary,
  PortfolioPosition,
  PortfolioSummary,
  Trade,
  TradeCreate,
  TradePlan,
  TradePlanCreate,
  TradePlanUpdate,
  TradeType,
  TradeUpdate,
} from "./types";
export { ApiError, describeError, isAuthError } from "./types";

function baseUrl(): string {
  return (process.env.EIGN_API_URL ?? "http://localhost:8080").replace(/\/+$/, "");
}

/**
 * Server-side GET against the Eign API.
 *
 * Server components and route handlers use this; browser code goes through the
 * same-origin `/api/*` proxy (`lib/client-api.ts`) instead.
 */
async function request<T>(identity: Identity, path: string): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, {
    headers: identityHeaders(identity),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorDetail(response));
  }
  return (await response.json()) as T;
}

export function fetchCurrentUser(identity: Identity): Promise<CurrentUser> {
  return request<CurrentUser>(identity, "/auth/me");
}

export function fetchPortfolioSummary(identity: Identity): Promise<PortfolioSummary> {
  return request<PortfolioSummary>(identity, "/portfolio/summary");
}

export function fetchPerformance(identity: Identity): Promise<Performance> {
  return request<Performance>(identity, "/portfolio/performance");
}

export function fetchAssetClasses(identity: Identity): Promise<AssetClassInfo[]> {
  return request<AssetClassInfo[]>(identity, "/asset-classes");
}

export function fetchAssets(identity: Identity): Promise<Asset[]> {
  return request<Asset[]>(identity, "/assets");
}

export function fetchTrades(identity: Identity): Promise<Trade[]> {
  return request<Trade[]>(identity, "/trades");
}

export function fetchIncomeRows(
  identity: Identity,
  year: number,
): Promise<IncomePlanFact[]> {
  return request<IncomePlanFact[]>(identity, `/income?year=${year}`);
}

export function fetchIncomeSummary(
  identity: Identity,
  year: number,
): Promise<IncomeSummary> {
  return request<IncomeSummary>(identity, `/income/summary?year=${year}`);
}

export function fetchTradePlans(identity: Identity, month: string): Promise<TradePlan[]> {
  return request<TradePlan[]>(identity, `/trade-plan?month=${month}-01`);
}

export function fetchGoals(identity: Identity): Promise<Goal> {
  return request<Goal>(identity, "/goals");
}

export function fetchGoalProgress(identity: Identity): Promise<GoalProgress> {
  return request<GoalProgress>(identity, "/goals/progress");
}
