import { useMemo } from "react";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";

import { analyticsQueryKeys } from "@/features/analytics/queryKeys";
import {
  fetchAnalyticsOverview,
  fetchAnalyticsTrends,
  fetchAnalyticsOlap,
  fetchAnalyticsComparisons,
  fetchAnalyticsSuperlatives,
  fetchAnalyticsCoverage,
} from "@/features/analytics/services/analytics.service";
import type {
  AnalyticsFilters,
  AnalyticsOverview,
  AnalyticsTrends,
  AnalyticsOlap,
  AnalyticsComparison,
  AnalyticsSuperlatives,
  AnalyticsCoverage,
} from "@/features/analytics/types";

const ANALYTICS_STALE_TIME_MS = 60_000;

function useMergedAnalyticsFilters(extraFilters: AnalyticsFilters | Record<string, unknown> = {}) {
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();

  return useMemo<AnalyticsFilters>(
    () => ({
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
      ...extraFilters,
    }),
    [
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
      extraFilters,
    ],
  );
}

function toAnalyticsRecord(filters: AnalyticsFilters): Record<string, unknown> {
  return filters as Record<string, unknown>;
}

export function useAnalyticsOverview(
  extraFilters: AnalyticsFilters = {},
) {
  const mergedFilters = useMergedAnalyticsFilters(extraFilters);

  return useQueryWithCoverage<AnalyticsOverview>({
    queryKey: analyticsQueryKeys.overview(mergedFilters as Record<string, unknown>),
    queryFn: () => fetchAnalyticsOverview(toAnalyticsRecord(mergedFilters)),
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}

export function useAnalyticsTrends(
  filters: Record<string, unknown>,
) {
  const mergedFilters = useMergedAnalyticsFilters(filters);

  return useQueryWithCoverage<AnalyticsTrends>({
    queryKey: analyticsQueryKeys.trends(toAnalyticsRecord(mergedFilters)),
    queryFn: () => fetchAnalyticsTrends(toAnalyticsRecord(mergedFilters)),
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}

export function useAnalyticsOlap(
  filters: Record<string, unknown>,
) {
  const mergedFilters = useMergedAnalyticsFilters(filters);

  return useQueryWithCoverage<AnalyticsOlap>({
    queryKey: analyticsQueryKeys.olap(toAnalyticsRecord(mergedFilters)),
    queryFn: () => fetchAnalyticsOlap(toAnalyticsRecord(mergedFilters)),
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}

export function useAnalyticsComparisons(
  filters: Record<string, unknown>,
  enabled = true,
) {
  const mergedFilters = useMergedAnalyticsFilters(filters);

  return useQueryWithCoverage<AnalyticsComparison>({
    queryKey: analyticsQueryKeys.comparisons(toAnalyticsRecord(mergedFilters)),
    queryFn: () => fetchAnalyticsComparisons(toAnalyticsRecord(mergedFilters)),
    enabled,
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}

export function useAnalyticsSuperlatives(
  filters: Record<string, unknown>,
) {
  const mergedFilters = useMergedAnalyticsFilters(filters);

  return useQueryWithCoverage<AnalyticsSuperlatives>({
    queryKey: analyticsQueryKeys.superlatives(toAnalyticsRecord(mergedFilters)),
    queryFn: () => fetchAnalyticsSuperlatives(toAnalyticsRecord(mergedFilters)),
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}

export function useAnalyticsCoverage(
  extraFilters: AnalyticsFilters = {},
) {
  const mergedFilters = useMergedAnalyticsFilters(extraFilters);

  return useQueryWithCoverage<AnalyticsCoverage>({
    queryKey: analyticsQueryKeys.coverage(mergedFilters as Record<string, unknown>),
    queryFn: () => fetchAnalyticsCoverage(toAnalyticsRecord(mergedFilters)),
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}
