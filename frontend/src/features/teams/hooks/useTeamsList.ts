import { useMemo } from "react";

import { keepPreviousData } from "@tanstack/react-query";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";

import { teamsQueryKeys } from "@/features/teams/queryKeys";
import { fetchTeamsList } from "@/features/teams/services/teams.service";
import type { TeamsListData, TeamsListFilters, TeamsListLocalFilters } from "@/features/teams/types";

const TEAMS_LIST_STALE_TIME_MS = 10 * 60 * 1000;
const TEAMS_LIST_GC_TIME_MS = 30 * 60 * 1000;

export function useTeamsList(
  localFilters: TeamsListLocalFilters = {},
  contextOverride: CompetitionSeasonContext | null = null,
) {
  const { competitionId: globalCompetitionId, seasonId: globalSeasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const competitionId = contextOverride?.competitionId ?? globalCompetitionId;
  const seasonId = contextOverride?.seasonId ?? globalSeasonId;

  const mergedFilters = useMemo<TeamsListFilters>(() => {
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
      page: localFilters.page,
      pageSize: localFilters.pageSize,
      sortBy: localFilters.sortBy,
      sortDirection: localFilters.sortDirection,
    };
  }, [
    competitionId,
    localFilters.page,
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

  return useQueryWithCoverage<TeamsListData>({
    queryKey: teamsQueryKeys.list(mergedFilters),
    queryFn: () => fetchTeamsList(mergedFilters),
    placeholderData: keepPreviousData,
    staleTime: TEAMS_LIST_STALE_TIME_MS,
    gcTime: TEAMS_LIST_GC_TIME_MS,
    isDataEmpty: (data) => data.items.length === 0,
  });
}
