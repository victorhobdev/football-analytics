"use client";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { fetchWorldCupTeam } from "@/features/world-cup/services/world-cup.service";
import type { WorldCupTeamData } from "@/features/world-cup/types/world-cup.types";

export function useWorldCupTeam(teamId: string) {
  return useQueryWithCoverage<WorldCupTeamData>({
    queryKey: ["world-cup", "team", teamId],
    queryFn: () => fetchWorldCupTeam(teamId),
    staleTime: 10 * 60 * 1000,
    isDataEmpty: (data) => !data || !data.team,
  });
}
