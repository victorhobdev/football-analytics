import { useMemo } from "react";

import { keepPreviousData } from "@tanstack/react-query";

import type { RankingDefinition } from "@/config/ranking.types";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { rankingsQueryKeys } from "@/features/rankings/queryKeys";
import { fetchRanking, validateRankingDefinition } from "@/features/rankings/services/rankings.service";
import type {
  RankingCacheProfile,
  RankingFreshnessClass,
  RankingQueryFilters,
  RankingTableData,
  UseRankingTableOptions,
} from "@/features/rankings/types";

const SEASON_CACHE_PROFILE: RankingCacheProfile = {
  freshnessClass: "season",
  staleTimeMs: 10 * 60 * 1000,
  gcTimeMs: 30 * 60 * 1000,
};

const FAST_CACHE_PROFILE: RankingCacheProfile = {
  freshnessClass: "fast",
  staleTimeMs: 5 * 60 * 1000,
  gcTimeMs: 15 * 60 * 1000,
};

function resolveRankingFreshnessClass(
  rankingDefinition: RankingDefinition,
  mergedFilters: RankingQueryFilters,
): RankingFreshnessClass {
  if (mergedFilters.freshnessClass) {
    return mergedFilters.freshnessClass;
  }

  const rankingId = rankingDefinition.id.toLowerCase();
  const isFastById = rankingId.includes("insight") || rankingId.includes("live") || rankingId.includes("form");
  const isFastByTimeRange =
    mergedFilters.lastN !== null ||
    mergedFilters.dateRangeStart !== null ||
    mergedFilters.dateRangeEnd !== null ||
    mergedFilters.roundId !== null;

  return isFastById || isFastByTimeRange ? "fast" : "season";
}

function resolveCacheProfile(rankingDefinition: RankingDefinition, mergedFilters: RankingQueryFilters): RankingCacheProfile {
  const freshnessClass = resolveRankingFreshnessClass(rankingDefinition, mergedFilters);
  return freshnessClass === "fast" ? FAST_CACHE_PROFILE : SEASON_CACHE_PROFILE;
}

export function useRankingTable(rankingDefinition: RankingDefinition, options: UseRankingTableOptions = {}) {
  validateRankingDefinition(rankingDefinition);

  const { localFilters = {}, enabled = true } = options;
  const { competitionId, seasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();

  const mergedFilters = useMemo<RankingQueryFilters>(() => {
    return {
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      stageId: localFilters.stageId,
      stageFormat: localFilters.stageFormat,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      search: localFilters.search?.trim() || undefined,
      page: localFilters.page,
      pageSize: localFilters.pageSize,
      sortDirection: localFilters.sortDirection ?? rankingDefinition.defaultSort,
      minSampleValue: localFilters.minSampleValue ?? rankingDefinition.minSample?.min ?? null,
      freshnessClass: localFilters.freshnessClass,
    };
  }, [
    competitionId,
    localFilters.freshnessClass,
    localFilters.minSampleValue,
    localFilters.page,
    localFilters.pageSize,
    localFilters.search,
    localFilters.stageFormat,
    localFilters.stageId,
    localFilters.sortDirection,
    rankingDefinition.defaultSort,
    rankingDefinition.minSample?.min,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  const cacheProfile = useMemo(
    () => resolveCacheProfile(rankingDefinition, mergedFilters),
    [mergedFilters, rankingDefinition],
  );

  const query = useQueryWithCoverage<RankingTableData>({
    queryKey: rankingsQueryKeys.table(rankingDefinition.id, mergedFilters),
    queryFn: () =>
      fetchRanking({
        rankingDefinition,
        filters: mergedFilters,
      }),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: cacheProfile.staleTimeMs,
    gcTime: cacheProfile.gcTimeMs,
    isDataEmpty: (data) => data.rows.length === 0,
  });

  return {
    ...query,
    cacheProfile,
    mergedFilters,
  };
}
