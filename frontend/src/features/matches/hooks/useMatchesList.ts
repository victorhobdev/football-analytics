import { useMemo } from "react";

import type { ApiResponse } from "@/shared/types/api-response.types";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { matchesQueryKeys } from "@/features/matches/queryKeys";
import { fetchMatchesList } from "@/features/matches/services/matches.service";
import type {
  MatchesListData,
  MatchesListFilters,
  MatchesListLocalFilters,
} from "@/features/matches/types";

const MATCHES_LIST_STALE_TIME_MS = 5 * 60 * 1000;
const MATCHES_LIST_GC_TIME_MS = 20 * 60 * 1000;
const MATCHES_LIST_ALL_PAGES_SIZE = 100;

async function fetchAllMatchesListPages(
  filters: MatchesListFilters,
): Promise<ApiResponse<MatchesListData>> {
  const initialResponse = await fetchMatchesList({
    ...filters,
    page: 1,
    pageSize: MATCHES_LIST_ALL_PAGES_SIZE,
  });
  const totalPages = initialResponse.meta?.pagination?.totalPages ?? 1;

  if (totalPages <= 1) {
    return initialResponse;
  }

  const remainingResponses = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      fetchMatchesList({
        ...filters,
        page: index + 2,
        pageSize: MATCHES_LIST_ALL_PAGES_SIZE,
      }),
    ),
  );

  return {
    ...initialResponse,
    data: {
      ...initialResponse.data,
      items: [
        ...initialResponse.data.items,
        ...remainingResponses.flatMap((response) => response.data.items),
      ],
    },
  };
}

export function useMatchesList(localFilters: MatchesListLocalFilters = {}) {
  const { competitionId, seasonId, teamId: globalTeamId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();

  const mergedFilters = useMemo<MatchesListFilters>(() => {
    const search = localFilters.search?.trim();
    const status = localFilters.status?.trim();

    return {
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      search: search && search.length > 0 ? search : undefined,
      status: status && status.length > 0 ? status : undefined,
      teamId: localFilters.teamId ?? globalTeamId ?? undefined,
      page: localFilters.allPages ? undefined : localFilters.page,
      pageSize: localFilters.allPages ? undefined : localFilters.pageSize,
      sortBy: localFilters.sortBy,
      sortDirection: localFilters.sortDirection,
    };
  }, [
    competitionId,
    globalTeamId,
    localFilters.allPages,
    localFilters.page,
    localFilters.pageSize,
    localFilters.search,
    localFilters.sortBy,
    localFilters.sortDirection,
    localFilters.status,
    localFilters.teamId,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  const queryKeyFilters = useMemo(
    () => ({
      ...mergedFilters,
      allPages: localFilters.allPages ?? false,
    }),
    [localFilters.allPages, mergedFilters],
  );

  return useQueryWithCoverage<MatchesListData>({
    queryKey: matchesQueryKeys.list(queryKeyFilters),
    queryFn: () =>
      localFilters.allPages ? fetchAllMatchesListPages(mergedFilters) : fetchMatchesList(mergedFilters),
    enabled: localFilters.enabled,
    staleTime: MATCHES_LIST_STALE_TIME_MS,
    gcTime: MATCHES_LIST_GC_TIME_MS,
    isDataEmpty: (data) => data.items.length === 0,
  });
}
