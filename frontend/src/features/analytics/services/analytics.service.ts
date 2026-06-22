import type { ApiResponse } from "@/shared/types/api-response.types";
import { apiRequest, type QueryParams } from "@/shared/services/api-client";

import type {
  AnalyticsOverview,
  AnalyticsTrends,
  AnalyticsOlap,
  AnalyticsComparison,
  AnalyticsSuperlatives,
  AnalyticsCoverage,
  AnalyticsFilters,
} from "@/features/analytics/types";

export const ANALYTICS_ENDPOINTS = {
  overview: "/api/v1/analytics/overview",
  trends: "/api/v1/analytics/trends",
  olap: "/api/v1/analytics/olap",
  comparisons: "/api/v1/analytics/comparisons",
  superlatives: "/api/v1/analytics/superlatives",
  coverage: "/api/v1/analytics/coverage",
} as const;

function toParams(
  filters: Record<string, unknown>,
): QueryParams {
  const params: QueryParams = {};

  for (const [key, value] of Object.entries(filters)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }

    if (key === "venue" && value === "all") {
      continue;
    }

    const normalizedKey =
      key === "dateRangeStart"
        ? "dateStart"
        : key === "dateRangeEnd"
          ? "dateEnd"
          : key;

    params[normalizedKey] = value as string | number | boolean;
  }

  return params;
}

export async function fetchAnalyticsOverview(
  filters: AnalyticsFilters = {},
): Promise<ApiResponse<AnalyticsOverview>> {
  return apiRequest<ApiResponse<AnalyticsOverview>>(
    ANALYTICS_ENDPOINTS.overview,
    { method: "GET", params: toParams(filters as Record<string, unknown>) },
  );
}

export async function fetchAnalyticsTrends(
  filters: Record<string, unknown>,
): Promise<ApiResponse<AnalyticsTrends>> {
  return apiRequest<ApiResponse<AnalyticsTrends>>(
    ANALYTICS_ENDPOINTS.trends,
    { method: "GET", params: toParams(filters) },
  );
}

export async function fetchAnalyticsOlap(
  filters: Record<string, unknown>,
): Promise<ApiResponse<AnalyticsOlap>> {
  return apiRequest<ApiResponse<AnalyticsOlap>>(
    ANALYTICS_ENDPOINTS.olap,
    { method: "GET", params: toParams(filters) },
  );
}

export async function fetchAnalyticsComparisons(
  filters: Record<string, unknown>,
): Promise<ApiResponse<AnalyticsComparison>> {
  return apiRequest<ApiResponse<AnalyticsComparison>>(
    ANALYTICS_ENDPOINTS.comparisons,
    { method: "GET", params: toParams(filters) },
  );
}

export async function fetchAnalyticsSuperlatives(
  filters: Record<string, unknown>,
): Promise<ApiResponse<AnalyticsSuperlatives>> {
  return apiRequest<ApiResponse<AnalyticsSuperlatives>>(
    ANALYTICS_ENDPOINTS.superlatives,
    { method: "GET", params: toParams(filters) },
  );
}

export async function fetchAnalyticsCoverage(
  filters: AnalyticsFilters = {},
): Promise<ApiResponse<AnalyticsCoverage>> {
  return apiRequest<ApiResponse<AnalyticsCoverage>>(
    ANALYTICS_ENDPOINTS.coverage,
    { method: "GET", params: toParams(filters as Record<string, unknown>) },
  );
}
