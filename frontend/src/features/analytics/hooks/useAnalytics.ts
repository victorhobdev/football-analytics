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

/**
 * Predicates that determine whether an analytics payload should be considered
 * "empty" for the purposes of empty-state UI. The default object check in
 * useQueryWithCoverage never triggers because every response carries structural
 * keys (scope/summary/...) even when there are zero matches, so each analytics
 * view needs a domain-specific rule.
 */
const isEmptyPredicates = {
  overview: (data: AnalyticsOverview): boolean =>
    data.summary.totalMatches === 0,
  trends: (data: AnalyticsTrends): boolean => data.series.length === 0,
  olap: (data: AnalyticsOlap): boolean => data.rows.length === 0,
  comparisons: (data: AnalyticsComparison): boolean =>
    (data.entityA?.matches ?? 0) === 0 && (data.entityB?.matches ?? 0) === 0,
  superlatives: (data: AnalyticsSuperlatives): boolean =>
    data.records.length === 0,
  coverage: (data: AnalyticsCoverage): boolean => data.totalMatches === 0,
};

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
    isDataEmpty: isEmptyPredicates.overview,
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
    isDataEmpty: isEmptyPredicates.trends,
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
    isDataEmpty: isEmptyPredicates.olap,
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
    isDataEmpty: isEmptyPredicates.comparisons,
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
    isDataEmpty: isEmptyPredicates.superlatives,
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
    isDataEmpty: isEmptyPredicates.coverage,
    staleTime: ANALYTICS_STALE_TIME_MS,
  });
}
