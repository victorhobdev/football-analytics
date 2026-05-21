"use client";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { fetchWorldCupEdition } from "@/features/world-cup/services/world-cup.service";
import type { WorldCupEditionData } from "@/features/world-cup/types/world-cup.types";

export function useWorldCupEdition(seasonLabel: string) {
  return useQueryWithCoverage<WorldCupEditionData>({
    queryKey: ["world-cup", "edition", seasonLabel],
    queryFn: () => fetchWorldCupEdition(seasonLabel),
    staleTime: 10 * 60 * 1000,
    isDataEmpty: (data) => !data || !data.edition,
  });
}
