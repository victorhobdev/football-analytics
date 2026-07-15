import type { ApiResponse } from "@/shared/types/api-response.types";
import type { CompetitionSeasonContextFilters, CompetitionSeasonContextsData } from "@/shared/types/context.types";
import { apiRequest, type QueryParams } from "@/shared/services/api-client";

import type {
  TeamProfile,
  TeamProfileFilters,
  TeamsListData,
  TeamsListFilters,
} from "@/features/teams/types";

export const TEAMS_ENDPOINTS = {
  list: "/api/v1/teams",
  contexts: (teamId: string) => `/api/v1/teams/${teamId}/contexts`,
  profile: (teamId: string) => `/api/v1/teams/${teamId}`,
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

export async function fetchTeamsList(
  filters: TeamsListFilters = {},
  signal?: AbortSignal,
): Promise<ApiResponse<TeamsListData>> {
  return apiRequest<ApiResponse<TeamsListData>>(TEAMS_ENDPOINTS.list, {
    method: "GET",
    params: toQueryParams(filters),
    signal,
  });
}

export async function fetchTeamContexts(
  teamId: string,
  filters: CompetitionSeasonContextFilters = {},
): Promise<ApiResponse<CompetitionSeasonContextsData>> {
  return apiRequest<ApiResponse<CompetitionSeasonContextsData>>(TEAMS_ENDPOINTS.contexts(teamId), {
    method: "GET",
    params: toQueryParams(filters),
  });
}

export async function fetchTeamProfile(
  teamId: string,
  filters: TeamProfileFilters = {},
): Promise<ApiResponse<TeamProfile>> {
  return apiRequest<ApiResponse<TeamProfile>>(TEAMS_ENDPOINTS.profile(teamId), {
    method: "GET",
    params: toQueryParams(filters),
  });
}
