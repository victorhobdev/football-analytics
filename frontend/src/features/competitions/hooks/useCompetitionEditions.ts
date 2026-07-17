import { useMemo } from "react";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { competitionStructureQueryKeys } from "@/features/competitions/queryKeys";
import { fetchCompetitionEditions } from "@/features/competitions/services/competition-hub.service";
import type { CompetitionEditionsData, CompetitionEditionsFilters } from "@/features/competitions/types";

export function useCompetitionEditions(filters: CompetitionEditionsFilters) {
  const normalizedFilters = useMemo(
    () => ({ competitionKey: filters.competitionKey?.trim() || undefined }),
    [filters.competitionKey],
  );

  return useQueryWithCoverage<CompetitionEditionsData>({
    queryKey: competitionStructureQueryKeys.editions(normalizedFilters),
    queryFn: ({ signal }) => fetchCompetitionEditions(normalizedFilters, signal),
    enabled: Boolean(normalizedFilters.competitionKey),
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    isDataEmpty: (data) => data.editions.length === 0,
  });
}
