import { useMemo } from "react";

import { keepPreviousData } from "@tanstack/react-query";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";

import { coachesQueryKeys } from "@/features/coaches/queryKeys";
import { fetchCoachesList } from "@/features/coaches/services/coaches.service";
import type { CoachesListData, CoachesListFilters, CoachesListLocalFilters } from "@/features/coaches/types";

const COACHES_LIST_STALE_TIME_MS = 10 * 60 * 1000;
const COACHES_LIST_GC_TIME_MS = 30 * 60 * 1000;

export function useCoachesList(
  localFilters: CoachesListLocalFilters = {},
  contextOverride: CompetitionSeasonContext | null = null,
) {
  const { competitionId: globalCompetitionId, seasonId: globalSeasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const competitionId = contextOverride?.competitionId ?? globalCompetitionId;
  const seasonId = contextOverride?.seasonId ?? globalSeasonId;

  const mergedFilters = useMemo<CoachesListFilters>(() => {
    const search = localFilters.search?.trim();

    return {
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      search: search && search.length > 0 ? search : undefined,
      minMatches: localFilters.minMatches,
      includeUnknown: localFilters.includeUnknown,
      page: localFilters.page,
      pageSize: localFilters.pageSize,
      sortBy: localFilters.sortBy,
      sortDirection: localFilters.sortDirection,
    };
  }, [
    competitionId,
    localFilters.page,
    localFilters.minMatches,
    localFilters.includeUnknown,
    localFilters.pageSize,
    localFilters.search,
    localFilters.sortBy,
    localFilters.sortDirection,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  return useQueryWithCoverage<CoachesListData>({
    queryKey: coachesQueryKeys.list(mergedFilters),
    queryFn: () => fetchCoachesList(mergedFilters),
    placeholderData: keepPreviousData,
    staleTime: COACHES_LIST_STALE_TIME_MS,
    gcTime: COACHES_LIST_GC_TIME_MS,
    isDataEmpty: (data) => data.items.length === 0,
  });
}
