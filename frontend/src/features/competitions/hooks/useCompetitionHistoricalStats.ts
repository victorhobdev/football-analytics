import { useMemo } from "react";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { competitionStructureQueryKeys } from "@/features/competitions/queryKeys";
import { fetchCompetitionHistoricalStats } from "@/features/competitions/services/competition-hub.service";
import type {
  CompetitionHistoricalStatsData,
  CompetitionHistoricalStatsFilters,
} from "@/features/competitions/types/competition-structure.types";

const HISTORICAL_STATS_STALE_TIME_MS = 30 * 60 * 1000;
const HISTORICAL_STATS_GC_TIME_MS = 60 * 60 * 1000;

function isHistoricalStatsEmpty(data: CompetitionHistoricalStatsData): boolean {
  return data.champions.items.length === 0 && data.scorers.items.length === 0;
}

export function useCompetitionHistoricalStats(filters: CompetitionHistoricalStatsFilters) {
  const normalizedFilters = useMemo(
    () => ({
      competitionKey: filters.competitionKey ?? undefined,
      asOfYear: filters.asOfYear ?? undefined,
    }),
    [filters.asOfYear, filters.competitionKey],
  );

  return useQueryWithCoverage<CompetitionHistoricalStatsData>({
    queryKey: competitionStructureQueryKeys.historicalStats(normalizedFilters),
    queryFn: () => fetchCompetitionHistoricalStats(normalizedFilters),
    enabled: Boolean(normalizedFilters.competitionKey),
    staleTime: HISTORICAL_STATS_STALE_TIME_MS,
    gcTime: HISTORICAL_STATS_GC_TIME_MS,
    isDataEmpty: isHistoricalStatsEmpty,
  });
}
