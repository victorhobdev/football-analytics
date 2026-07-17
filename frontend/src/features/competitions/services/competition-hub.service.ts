import { apiRequest, type QueryParams } from "@/shared/services/api-client";
import type { ApiResponse } from "@/shared/types/api-response.types";

import type {
  CompetitionAnalyticsData,
  CompetitionAnalyticsFilters,
  CompetitionEditionsData,
  CompetitionEditionsFilters,
  CompetitionHistoricalStatsData,
  CompetitionHistoricalStatsFilters,
  CompetitionStructureData,
  CompetitionStructureFilters,
  StageTiesData,
  StageTiesFilters,
  TeamJourneyHistoryData,
  TeamJourneyHistoryFilters,
} from "@/features/competitions/types/competition-structure.types";

const COMPETITION_STRUCTURE_ENDPOINT = "/api/v1/competition-structure";
const COMPETITION_ANALYTICS_ENDPOINT = "/api/v1/competition-analytics";
const COMPETITION_EDITIONS_ENDPOINT = "/api/v1/competition-editions";
const COMPETITION_HISTORICAL_STATS_ENDPOINT = "/api/v1/competition-historical-stats";
const STAGE_TIES_ENDPOINT = "/api/v1/ties";
const TEAM_JOURNEY_HISTORY_ENDPOINT = "/api/v1/team-journey-history";

function toQueryParams(filters: Record<string, unknown>): QueryParams {
  const queryParams: QueryParams = {};

  for (const [key, value] of Object.entries(filters)) {
    if (value === null || value === undefined) {
      continue;
    }

    if (typeof value === "string" && value.trim().length === 0) {
      continue;
    }

    queryParams[key] = value as string | number | boolean;
  }

  return queryParams;
}

export async function fetchCompetitionStructure(
  filters: CompetitionStructureFilters,
): Promise<ApiResponse<CompetitionStructureData>> {
  return apiRequest<ApiResponse<CompetitionStructureData>>(COMPETITION_STRUCTURE_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
  });
}

export async function fetchCompetitionAnalytics(
  filters: CompetitionAnalyticsFilters,
): Promise<ApiResponse<CompetitionAnalyticsData>> {
  return apiRequest<ApiResponse<CompetitionAnalyticsData>>(COMPETITION_ANALYTICS_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
  });
}

export async function fetchCompetitionEditions(
  filters: CompetitionEditionsFilters,
  signal?: AbortSignal,
): Promise<ApiResponse<CompetitionEditionsData>> {
  return apiRequest<ApiResponse<CompetitionEditionsData>>(COMPETITION_EDITIONS_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
    signal,
  });
}

export async function fetchCompetitionHistoricalStats(
  filters: CompetitionHistoricalStatsFilters,
): Promise<ApiResponse<CompetitionHistoricalStatsData>> {
  return apiRequest<ApiResponse<CompetitionHistoricalStatsData>>(COMPETITION_HISTORICAL_STATS_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
  });
}

export async function fetchStageTies(
  filters: StageTiesFilters,
): Promise<ApiResponse<StageTiesData>> {
  return apiRequest<ApiResponse<StageTiesData>>(STAGE_TIES_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
  });
}

export async function fetchTeamJourneyHistory(
  filters: TeamJourneyHistoryFilters,
): Promise<ApiResponse<TeamJourneyHistoryData>> {
  return apiRequest<ApiResponse<TeamJourneyHistoryData>>(TEAM_JOURNEY_HISTORY_ENDPOINT, {
    method: "GET",
    params: toQueryParams(filters as Record<string, unknown>),
  });
}
