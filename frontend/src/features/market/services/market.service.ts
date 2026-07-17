import type { ApiResponse } from "@/shared/types/api-response.types";
import { apiRequest, type QueryParams } from "@/shared/services/api-client";

import type { MarketTransfersData, MarketTransfersFilters } from "@/features/market/types";

export const MARKET_ENDPOINTS = {
  transfers: "/api/v1/market/transfers",
} as const;

function toQueryParams<TFilters extends object>(filters: TFilters): QueryParams {
  const queryParams: QueryParams = {};

  for (const [key, value] of Object.entries(filters as Record<string, unknown>)) {
    if (value === null || value === undefined) {
      continue;
    }

    if (typeof value === "string" && value.trim().length === 0) {
      continue;
    }

    if (key === "venue" && value === "all") {
      continue;
    }

    const normalizedKey = key === "dateRangeStart" ? "dateStart" : key === "dateRangeEnd" ? "dateEnd" : key;
    queryParams[normalizedKey] = value as string | number | boolean;
  }

  return queryParams;
}

export async function fetchMarketTransfers(
  filters: MarketTransfersFilters = {},
  signal?: AbortSignal,
): Promise<ApiResponse<MarketTransfersData>> {
  return apiRequest<ApiResponse<MarketTransfersData>>(MARKET_ENDPOINTS.transfers, {
    method: "GET",
    params: toQueryParams(filters),
    signal,
  });
}
