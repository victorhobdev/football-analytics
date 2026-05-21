"use client";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { fetchWorldCupRankings } from "@/features/world-cup/services/world-cup.service";
import type { WorldCupRankingsData } from "@/features/world-cup/types/world-cup.types";

export function useWorldCupRankings() {
  return useQueryWithCoverage<WorldCupRankingsData>({
    queryKey: ["world-cup", "rankings"],
    queryFn: () => fetchWorldCupRankings(),
    staleTime: 10 * 60 * 1000,
    isDataEmpty: (data) =>
      !data ||
      (data.scorers.length === 0 &&
        data.teams.length === 0 &&
        data.teamRankings.wins.items.length === 0 &&
        data.editionRankings.goals.items.length === 0 &&
        data.playerRankings.squadAppearances.items.length === 0 &&
        data.finals.items.length === 0),
  });
}
