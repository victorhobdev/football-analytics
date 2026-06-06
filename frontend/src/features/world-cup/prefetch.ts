import type { QueryClient } from "@tanstack/react-query";

import {
  fetchWorldCupEdition,
  fetchWorldCupRankings,
  fetchWorldCupTeam,
  fetchWorldCupTeams,
} from "@/features/world-cup/services/world-cup.service";

const WORLD_CUP_STALE_TIME_MS = 10 * 60 * 1000;

export function prefetchWorldCupEdition(queryClient: QueryClient, seasonLabel: string) {
  const normalizedSeasonLabel = seasonLabel.trim();

  if (normalizedSeasonLabel.length === 0) {
    return Promise.resolve();
  }

  return queryClient.prefetchQuery({
    queryKey: ["world-cup", "edition", normalizedSeasonLabel],
    queryFn: () => fetchWorldCupEdition(normalizedSeasonLabel),
    staleTime: WORLD_CUP_STALE_TIME_MS,
  });
}

export function prefetchWorldCupTeam(queryClient: QueryClient, teamId: string) {
  const normalizedTeamId = teamId.trim();

  if (normalizedTeamId.length === 0) {
    return Promise.resolve();
  }

  return queryClient.prefetchQuery({
    queryKey: ["world-cup", "team", normalizedTeamId],
    queryFn: () => fetchWorldCupTeam(normalizedTeamId),
    staleTime: WORLD_CUP_STALE_TIME_MS,
  });
}

export function prefetchWorldCupTeams(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: ["world-cup", "teams"],
    queryFn: () => fetchWorldCupTeams(),
    staleTime: WORLD_CUP_STALE_TIME_MS,
  });
}

export function prefetchWorldCupRankings(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: ["world-cup", "rankings"],
    queryFn: () => fetchWorldCupRankings(),
    staleTime: WORLD_CUP_STALE_TIME_MS,
  });
}
