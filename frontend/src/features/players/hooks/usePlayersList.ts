import { useMemo } from "react";

import { keepPreviousData } from "@tanstack/react-query";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";

import { playersQueryKeys } from "@/features/players/queryKeys";
import { fetchPlayersList } from "@/features/players/services/players.service";
import type { PlayersListData, PlayersListFilters, PlayersListLocalFilters } from "@/features/players/types";

const PLAYERS_LIST_STALE_TIME_MS = 10 * 60 * 1000;
const PLAYERS_LIST_GC_TIME_MS = 30 * 60 * 1000;

export function usePlayersList(localFilters: PlayersListLocalFilters = {}) {
  const { competitionId, seasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();

  const mergedFilters = useMemo<PlayersListFilters>(() => {
    const search = localFilters.search?.trim();

    return {
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      stageId: localFilters.stageId ?? undefined,
      stageFormat: localFilters.stageFormat ?? undefined,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      search: search && search.length > 0 ? search : undefined,
      minMinutes: localFilters.minMinutes ?? undefined,
      teamId: localFilters.teamId ?? undefined,
      position: localFilters.position ?? undefined,
      page: localFilters.page,
      pageSize: localFilters.pageSize,
      sortBy: localFilters.sortBy ?? undefined,
      sortDirection: localFilters.sortDirection ?? undefined,
    };
  }, [
    competitionId,
    localFilters.page,
    localFilters.pageSize,
    localFilters.position,
    localFilters.search,
    localFilters.sortBy,
    localFilters.sortDirection,
    localFilters.stageFormat,
    localFilters.stageId,
    localFilters.teamId,
    localFilters.minMinutes,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  return useQueryWithCoverage<PlayersListData>({
    queryKey: playersQueryKeys.list(mergedFilters),
    queryFn: () => fetchPlayersList(mergedFilters),
    placeholderData: keepPreviousData,
    staleTime: PLAYERS_LIST_STALE_TIME_MS,
    gcTime: PLAYERS_LIST_GC_TIME_MS,
    isDataEmpty: (data) => data.items.length === 0,
  });
}
