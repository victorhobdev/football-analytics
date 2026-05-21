import { useMemo } from "react";

import { keepPreviousData } from "@tanstack/react-query";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";

import { marketQueryKeys } from "@/features/market/queryKeys";
import { fetchMarketTransfers } from "@/features/market/services/market.service";
import type {
  MarketTransfersData,
  MarketTransfersFilters,
  MarketTransfersLocalFilters,
} from "@/features/market/types";

const MARKET_TRANSFERS_STALE_TIME_MS = 10 * 60 * 1000;
const MARKET_TRANSFERS_GC_TIME_MS = 30 * 60 * 1000;

export function useMarketTransfers(
  localFilters: MarketTransfersLocalFilters = {},
  contextOverride: CompetitionSeasonContext | null = null,
) {
  const { competitionId: globalCompetitionId, seasonId: globalSeasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const competitionId = contextOverride?.competitionId ?? globalCompetitionId;
  const seasonId = contextOverride?.seasonId ?? globalSeasonId;

  const mergedFilters = useMemo<MarketTransfersFilters>(() => {
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
      clubSearch: localFilters.clubSearch?.trim() || undefined,
      teamDirection: localFilters.teamDirection,
      typeId: localFilters.typeId,
      hasAmount: localFilters.hasAmount,
      minAmount: localFilters.minAmount,
      maxAmount: localFilters.maxAmount,
      page: localFilters.page,
      pageSize: localFilters.pageSize,
      sortBy: localFilters.sortBy,
      sortDirection: localFilters.sortDirection,
    };
  }, [
    competitionId,
    localFilters.hasAmount,
    localFilters.clubSearch,
    localFilters.maxAmount,
    localFilters.minAmount,
    localFilters.page,
    localFilters.pageSize,
    localFilters.search,
    localFilters.sortBy,
    localFilters.sortDirection,
    localFilters.teamDirection,
    localFilters.typeId,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  return useQueryWithCoverage<MarketTransfersData>({
    queryKey: marketQueryKeys.transfers(mergedFilters),
    queryFn: () => fetchMarketTransfers(mergedFilters),
    placeholderData: keepPreviousData,
    staleTime: MARKET_TRANSFERS_STALE_TIME_MS,
    gcTime: MARKET_TRANSFERS_GC_TIME_MS,
    isDataEmpty: (data) => data.items.length === 0,
  });
}
