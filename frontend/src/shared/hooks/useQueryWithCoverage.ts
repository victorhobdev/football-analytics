import { useMemo } from "react";

import { useQuery, type QueryKey, type UseQueryOptions } from "@tanstack/react-query";

import type { ApiResponse, ApiResponseMeta } from "@/shared/types/api-response.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import type { ApiError } from "@/shared/types/error.types";

const UNKNOWN_COVERAGE: CoverageState = { status: "unknown" };

type UseQueryWithCoverageOptions<TData, TQueryKey extends QueryKey = QueryKey> = Omit<
  UseQueryOptions<ApiResponse<TData>, ApiError, ApiResponse<TData>, TQueryKey>,
  "queryKey"
> & {
  queryKey: TQueryKey;
  isDataEmpty?: (data: TData) => boolean;
};

export type QueryWithCoverageResult<TData> = {
  data: TData | undefined;
  meta: ApiResponseMeta | undefined;
  isLoading: boolean;
  isError: boolean;
  error: ApiError | null;
  isEmpty: boolean;
  isPartial: boolean;
  coverage: CoverageState;
};

function isEmptyData(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }

  if (Array.isArray(value)) {
    return value.length === 0;
  }

  if (typeof value === "object") {
    return Object.keys(value as Record<string, unknown>).length === 0;
  }

  return false;
}

function normalizeError(error: ApiError | null): ApiError | null {
  if (!error) {
    return null;
  }

  return {
    message: error.message,
    code: error.code,
    status: error.status,
    details: error.details,
  };
}

export function useQueryWithCoverage<TData, TQueryKey extends QueryKey = QueryKey>(
  options: UseQueryWithCoverageOptions<TData, TQueryKey>,
): QueryWithCoverageResult<TData> {
  const { isDataEmpty, ...queryOptions } = options;

  const query = useQuery(queryOptions);

  return useMemo(() => {
    const coverage = query.data?.meta?.coverage ?? UNKNOWN_COVERAGE;
    const data = query.data?.data;
    const emptyByCoverage = coverage.status === "empty";
    const emptyByData = data !== undefined ? (isDataEmpty ? isDataEmpty(data) : isEmptyData(data)) : false;

    return {
      data,
      meta: query.data?.meta,
      isLoading: query.isLoading,
      isError: query.isError,
      error: normalizeError(query.error),
      isEmpty: emptyByCoverage || emptyByData,
      isPartial: coverage.status === "partial",
      coverage,
    };
  }, [isDataEmpty, query.data, query.error, query.isError, query.isLoading]);
}
