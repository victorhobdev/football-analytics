import { apiRequest } from "@/shared/services/api-client";
import type { ApiResponse } from "@/shared/types/api-response.types";

import type {
  WorldCupEditionData,
  WorldCupHubData,
  WorldCupRankingsData,
  WorldCupTeamData,
  WorldCupTeamsData,
} from "@/features/world-cup/types/world-cup.types";

export const WORLD_CUP_HUB_ENDPOINT = "/api/v1/world-cup/hub";
export const WORLD_CUP_EDITION_ENDPOINT = "/api/v1/world-cup/editions";
export const WORLD_CUP_TEAMS_ENDPOINT = "/api/v1/world-cup/teams";
export const WORLD_CUP_RANKINGS_ENDPOINT = "/api/v1/world-cup/rankings";

export async function fetchWorldCupHub(): Promise<ApiResponse<WorldCupHubData>> {
  return apiRequest<ApiResponse<WorldCupHubData>>(WORLD_CUP_HUB_ENDPOINT, {
    method: "GET",
  });
}

export async function fetchWorldCupEdition(seasonLabel: string): Promise<ApiResponse<WorldCupEditionData>> {
  return apiRequest<ApiResponse<WorldCupEditionData>>(
    `${WORLD_CUP_EDITION_ENDPOINT}/${encodeURIComponent(seasonLabel.trim())}`,
    {
      method: "GET",
    },
  );
}

export async function fetchWorldCupTeams(): Promise<ApiResponse<WorldCupTeamsData>> {
  return apiRequest<ApiResponse<WorldCupTeamsData>>(WORLD_CUP_TEAMS_ENDPOINT, {
    method: "GET",
  });
}

export async function fetchWorldCupTeam(teamId: string): Promise<ApiResponse<WorldCupTeamData>> {
  return apiRequest<ApiResponse<WorldCupTeamData>>(
    `${WORLD_CUP_TEAMS_ENDPOINT}/${encodeURIComponent(teamId.trim())}`,
    {
      method: "GET",
    },
  );
}

export async function fetchWorldCupRankings(): Promise<ApiResponse<WorldCupRankingsData>> {
  return apiRequest<ApiResponse<WorldCupRankingsData>>(WORLD_CUP_RANKINGS_ENDPOINT, {
    method: "GET",
  });
}
