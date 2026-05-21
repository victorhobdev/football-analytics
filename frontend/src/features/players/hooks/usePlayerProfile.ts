import { useMemo } from "react";

import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";

import { playersQueryKeys } from "@/features/players/queryKeys";
import { fetchPlayerProfile } from "@/features/players/services/players.service";
import type {
  PlayerProfile,
  PlayerProfileFilters,
  PlayerProfileLocalFilters,
} from "@/features/players/types";

const PLAYER_PROFILE_STALE_TIME_MS = 5 * 60 * 1000;
const PLAYER_PROFILE_GC_TIME_MS = 30 * 60 * 1000;

export function usePlayerProfile(
  playerId: string | null | undefined,
  localFilters: PlayerProfileLocalFilters = {},
  contextOverride: CompetitionSeasonContext | null = null,
) {
  const {
    competitionId: globalCompetitionId,
    seasonId: globalSeasonId,
    venue,
  } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const normalizedPlayerId = playerId?.trim() ?? "";
  const competitionId = contextOverride?.competitionId ?? globalCompetitionId;
  const seasonId = contextOverride?.seasonId ?? globalSeasonId;

  const mergedFilters = useMemo<PlayerProfileFilters>(
    () => ({
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      stageId: localFilters.stageId ?? undefined,
      stageFormat: localFilters.stageFormat ?? undefined,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      includeRecentMatches: localFilters.includeRecentMatches,
      includeHistory: localFilters.includeHistory,
      includeStats: localFilters.includeStats,
    }),
    [
      competitionId,
      localFilters.includeHistory,
      localFilters.includeRecentMatches,
      localFilters.includeStats,
      localFilters.stageFormat,
      localFilters.stageId,
      seasonId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  return useQueryWithCoverage<PlayerProfile>({
    queryKey: playersQueryKeys.profile(normalizedPlayerId || "unknown", mergedFilters),
    queryFn: () => fetchPlayerProfile(normalizedPlayerId, mergedFilters),
    enabled: normalizedPlayerId.length > 0,
    staleTime: PLAYER_PROFILE_STALE_TIME_MS,
    gcTime: PLAYER_PROFILE_GC_TIME_MS,
    isDataEmpty: (data) => data.player.playerId.trim().length === 0,
  });
}
