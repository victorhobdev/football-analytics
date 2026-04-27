import { getMetric } from "@/config/metrics.registry";
import type { RankingDefinition } from "@/config/ranking.types";
import { apiRequest, type QueryParams } from "@/shared/services/api-client";
import type { ApiResponse } from "@/shared/types/api-response.types";

import type { RankingFetchInput, RankingQueryFilters, RankingTableData } from "@/features/rankings/types";

function assertRankingMetricExists(rankingDefinition: RankingDefinition): void {
  if (getMetric(rankingDefinition.metricKey)) {
    return;
  }

  throw new Error(
    `RankingDefinition invalido: "${rankingDefinition.id}" referencia metricKey "${rankingDefinition.metricKey}" inexistente no metrics.registry.ts.`,
  );
}

function normalizeRankingEndpoint(rankingDefinition: RankingDefinition): string {
  const endpoint = rankingDefinition.endpoint.trim();

  if (endpoint.length === 0) {
    throw new Error(`RankingDefinition invalido: "${rankingDefinition.id}" possui endpoint vazio.`);
  }

  return endpoint;
}

function toQueryParams(filters: RankingQueryFilters = {}): QueryParams {
  const queryParams: QueryParams = {};

  for (const [key, value] of Object.entries(filters as Record<string, unknown>)) {
    if (value === null || value === undefined) {
      continue;
    }

    if (typeof value === "string" && value.trim().length === 0) {
      continue;
    }
    if (
      (key === "competitionId" || key === "seasonId") &&
      typeof value === "string" &&
      value.trim().toLowerCase() === "all"
    ) {
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

export async function fetchRanking({ rankingDefinition, filters = {} }: RankingFetchInput): Promise<ApiResponse<RankingTableData>> {
  assertRankingMetricExists(rankingDefinition);

  return apiRequest<ApiResponse<RankingTableData>>(normalizeRankingEndpoint(rankingDefinition), {
    method: "GET",
    params: toQueryParams(filters),
  });
}

export function validateRankingDefinition(rankingDefinition: RankingDefinition): void {
  assertRankingMetricExists(rankingDefinition);
  normalizeRankingEndpoint(rankingDefinition);
}
