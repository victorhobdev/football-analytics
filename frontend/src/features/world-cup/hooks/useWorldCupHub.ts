"use client";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";

import { fetchWorldCupHub } from "@/features/world-cup/services/world-cup.service";
import type { WorldCupHubData } from "@/features/world-cup/types/world-cup.types";

export function useWorldCupHub() {
  return useQueryWithCoverage<WorldCupHubData>({
    queryKey: ["world-cup", "hub"],
    queryFn: () => fetchWorldCupHub(),
    staleTime: 10 * 60 * 1000,
    isDataEmpty: (data) => !data || data.editions.length === 0,
  });
}
