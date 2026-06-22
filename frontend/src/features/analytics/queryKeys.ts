import { buildQueryKey } from "@/shared/utils/queryKeys";

const ANALYTICS_DOMAIN = "analytics";

export const analyticsQueryKeys = {
  all: () => buildQueryKey(ANALYTICS_DOMAIN, "all"),
  overview: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "overview", filters),
  trends: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "trends", filters),
  olap: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "olap", filters),
  comparisons: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "comparisons", filters),
  superlatives: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "superlatives", filters),
  coverage: (filters?: Record<string, unknown>) =>
    buildQueryKey(ANALYTICS_DOMAIN, "coverage", filters),
};
