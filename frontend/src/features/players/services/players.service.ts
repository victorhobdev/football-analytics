import type { ApiResponse } from "@/shared/types/api-response.types";
import type { CompetitionSeasonContextFilters, CompetitionSeasonContextsData } from "@/shared/types/context.types";
import { apiRequest, type QueryParams } from "@/shared/services/api-client";

import type { PlayerProfile, PlayerProfileFilters, PlayersListData, PlayersListFilters } from "@/features/players/types";

export const PLAYERS_ENDPOINTS = {
  list: "/api/v1/players",
  contexts: (playerId: string) => `/api/v1/players/${playerId}/contexts`,
  profile: (playerId: string) => `/api/v1/players/${playerId}`,
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

export async function fetchPlayersList(
  filters: PlayersListFilters = {},
  signal?: AbortSignal,
): Promise<ApiResponse<PlayersListData>> {
  return apiRequest<ApiResponse<PlayersListData>>(PLAYERS_ENDPOINTS.list, {
    method: "GET",
    params: toQueryParams(filters),
    signal,
  });
}

export async function fetchPlayerProfile(
  playerId: string,
  filters: PlayerProfileFilters = {},
): Promise<ApiResponse<PlayerProfile>> {
  return apiRequest<ApiResponse<PlayerProfile>>(PLAYERS_ENDPOINTS.profile(playerId), {
    method: "GET",
    params: toQueryParams(filters),
  });
}

export async function fetchPlayerContexts(
  playerId: string,
  filters: CompetitionSeasonContextFilters = {},
): Promise<ApiResponse<CompetitionSeasonContextsData>> {
  return apiRequest<ApiResponse<CompetitionSeasonContextsData>>(PLAYERS_ENDPOINTS.contexts(playerId), {
    method: "GET",
    params: toQueryParams(filters),
  });
}
