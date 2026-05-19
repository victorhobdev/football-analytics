import { apiRequest } from "@/shared/services/api-client";
import type { ApiResponse } from "@/shared/types/api-response.types";

import type {
  WorldCup2022CompetitionHubData,
  WorldCup2022MatchViewData,
  WorldCup2022TeamViewData,
} from "@/features/world-cup-2022/types/world-cup-2022.types";

const WORLD_CUP_2022_ENDPOINTS = {
  competitionHub: "/api/v1/world-cup-2022/competition-hub",
  matchView: (fixtureId: string) => `/api/v1/world-cup-2022/matches/${fixtureId}`,
  teamView: (teamId: string) => `/api/v1/world-cup-2022/teams/${teamId}`,
} as const;

const WORLD_CUP_REQUEST_OPTIONS = {
  method: "GET",
  cache: "no-store" as const,
};

export async function fetchWorldCup2022CompetitionHub(): Promise<
  ApiResponse<WorldCup2022CompetitionHubData>
> {
  return apiRequest<ApiResponse<WorldCup2022CompetitionHubData>>(
    WORLD_CUP_2022_ENDPOINTS.competitionHub,
    WORLD_CUP_REQUEST_OPTIONS,
  );
}

export async function fetchWorldCup2022MatchView(
  fixtureId: string,
): Promise<ApiResponse<WorldCup2022MatchViewData>> {
  return apiRequest<ApiResponse<WorldCup2022MatchViewData>>(
    WORLD_CUP_2022_ENDPOINTS.matchView(fixtureId),
    WORLD_CUP_REQUEST_OPTIONS,
  );
}

export async function fetchWorldCup2022TeamView(
  teamId: string,
): Promise<ApiResponse<WorldCup2022TeamViewData>> {
  return apiRequest<ApiResponse<WorldCup2022TeamViewData>>(
    WORLD_CUP_2022_ENDPOINTS.teamView(teamId),
    WORLD_CUP_REQUEST_OPTIONS,
  );
}
