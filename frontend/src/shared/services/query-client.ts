import { QueryClient } from "@tanstack/react-query";

import { ApiClientError } from "@/shared/services/api-client";

function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1 || !(error instanceof ApiClientError)) {
    return false;
  }

  return error.code === "NETWORK_ERROR" || (error.status !== undefined && error.status >= 500);
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: shouldRetryQuery,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
