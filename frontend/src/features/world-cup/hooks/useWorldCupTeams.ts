"use client";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { fetchWorldCupTeams } from "@/features/world-cup/services/world-cup.service";
import type { WorldCupTeamsData } from "@/features/world-cup/types/world-cup.types";

export function useWorldCupTeams() {
  return useQueryWithCoverage<WorldCupTeamsData>({
    queryKey: ["world-cup", "teams"],
    queryFn: () => fetchWorldCupTeams(),
    staleTime: 10 * 60 * 1000,
    isDataEmpty: (data) => !data || data.teams.length === 0,
  });
}
