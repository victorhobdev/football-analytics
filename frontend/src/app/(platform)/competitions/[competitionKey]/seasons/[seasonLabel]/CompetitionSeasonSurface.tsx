"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  getCompetitionById,
  getCompetitionByKey,
  getCompetitionVisualAssetId,
} from "@/config/competitions.registry";
import { formatMetricValue } from "@/config/metrics.registry";
import { getRankingDefinition } from "@/config/ranking.registry";
import type { RankingDefinition, RankingSortDirection } from "@/config/ranking.types";
import { SeasonCompetitionAnalyticsSection } from "@/features/competitions/components/SeasonCompetitionAnalyticsSection";
import { CompetitionSeasonSurfaceShell } from "@/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell";
import { useCompetitionAnalytics } from "@/features/competitions/hooks/useCompetitionAnalytics";
import { useCompetitionStructure } from "@/features/competitions/hooks/useCompetitionStructure";
import { useStageTies } from "@/features/competitions/hooks/useStageTies";
import { competitionStructureQueryKeys } from "@/features/competitions/queryKeys";
import { fetchStageTies } from "@/features/competitions/services/competition-hub.service";
import type {
  CompetitionAnalyticsData,
  CompetitionStructureData,
  CompetitionStructureStage,
  StageTie,
} from "@/features/competitions/types";
import {
  mapCompetitionSeasonSurfaceSectionToLegacyTab,
  normalizeCompetitionSeasonSurfaceSection,
  resolveCompetitionSeasonSurface,
  resolveCompetitionSeasonSurfaceSection,
  resolveHybridTableSectionLabel,
  type CompetitionSeasonSurfaceResolution,
  type CompetitionSeasonSurfaceSection,
} from "@/features/competitions/utils/competition-season-surface";
import { resolveSeasonChampionArtwork } from "@/features/competitions/utils/champion-media";
import {
  getStageFormatLabel,
  localizeCompetitionStageName,
} from "@/features/competitions/utils/competition-structure";
import { fetchMatchesList } from "@/features/matches/services/matches.service";
import type { MatchListItem, MatchesListData } from "@/features/matches/types";
import { resolveMatchDisplayContext } from "@/features/matches/utils/match-context";
import { useRankingTable } from "@/features/rankings/hooks";
import { fetchRanking } from "@/features/rankings/services";
import type { RankingTableRow } from "@/features/rankings/types";
import { useStandingsTable } from "@/features/standings/hooks";
import { standingsQueryKeys } from "@/features/standings/queryKeys";
import { fetchGroupStandings, fetchStandings } from "@/features/standings/services/standings.service";
import type { StandingsTableData, StandingsTableRow } from "@/features/standings/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { DataTable } from "@/shared/components/data-display/DataTable";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfilePanel,
  ProfileTabs,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { useGlobalFilters, useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { ApiResponse } from "@/shared/types/api-response.types";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import {
  buildCanonicalPlayerPath,
  buildCanonicalTeamPath,
  buildMatchesPath,
  buildPlayersPath,
  buildRankingPath,
  buildRetainedFilterQueryString,
  buildSeasonHubPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type CompetitionSeasonSurfaceProps = {
  context: CompetitionSeasonContext;
  initialTab?: string | null;
};

type SurfaceNavLabels = {
  highlights: string;
  matches: string;
  overview: string;
  structure: string;
};

type CoverageLike = {
  label?: string;
  percentage?: number;
  status: "complete" | "empty" | "partial" | "unknown";
};

type GroupStandingsQueryState = {
  coverage: CoverageLike;
  data: StandingsTableData | null;
  group: CompetitionStructureStage["groups"][number];
  isError: boolean;
  isLoading: boolean;
};

type KnockoutStageQueryState = {
  coverage: CoverageLike;
  isError: boolean;
  isLoading: boolean;
  stage: CompetitionStructureStage;
  ties: StageTie[];
};

type ChampionLeadRoundsSummary = {
  count: number | null;
  isError: boolean;
  isLoading: boolean;
};

type BracketSide = "left" | "right";

type BracketSnapshotColumn = {
  leftTies: StageTie[];
  rightTies: StageTie[];
  stageState: KnockoutStageQueryState;
};

type BracketTeamReference = {
  teamId?: string | null;
  teamName?: string | null;
};

type HistoricalRankingLeader = {
  entityId: string;
  entityName: string;
  metricValue: number;
  matchesPlayed: number | null;
  minutesPlayed: number | null;
  teamId?: string | null;
  teamName?: string | null;
};

type HistoricalRankingLeaderData = {
  leader: HistoricalRankingLeader | null;
};

type HistoricalRankingLeadersData = {
  leaders: HistoricalRankingLeader[];
};

type TeamMetricInsight = {
  metricValue: number;
  teamId: string | null;
  teamName: string;
};

type MatchMetricInsight = {
  awayScore: number;
  awayTeamId: string | null;
  awayTeamName: string;
  homeScore: number;
  homeTeamId: string | null;
  homeTeamName: string;
  kickoffAt: string | null;
  matchId: string;
  metricValue: number;
};

type CompletedSeasonMatch = MatchListItem & {
  awayScore: number;
  homeScore: number;
};

type TeamSeasonMatchResult = {
  isUnbeaten: boolean;
  isWin: boolean;
  kickoffTimestamp: number;
  matchId: string;
};

type TeamSeasonAggregate = {
  awayGoalDiff: number;
  awayGoalsFor: number;
  awayPoints: number;
  finalPosition: number | null;
  goalsAgainst: number;
  goalsFor: number;
  homeGoalDiff: number;
  homeGoalsFor: number;
  homePoints: number;
  key: string;
  longestUnbeatenStreak: number;
  longestUnbeatenStreakEndedAt: number;
  longestWinningStreak: number;
  longestWinningStreakEndedAt: number;
  matchResults: TeamSeasonMatchResult[];
  teamId: string | null;
  teamName: string;
};

type EditionRailInsights = {
  bestAttack: TeamMetricInsight | null;
  bestDefense: TeamMetricInsight | null;
  bestHomeTeam: TeamMetricInsight | null;
  bestAwayTeam: TeamMetricInsight | null;
  highestScoringMatch: MatchMetricInsight | null;
  longestUnbeatenRun: TeamMetricInsight | null;
  longestWinningRun: TeamMetricInsight | null;
  standingsQuery: ReturnType<typeof useSeasonFinalStandings>;
  matchesQuery: ReturnType<typeof useSeasonAllMatches>;
  worstAwayTeam: TeamMetricInsight | null;
};

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  month: "short",
});

const DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
});

const LONG_DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "numeric",
  month: "long",
});

const MATCHES_LIST_ALL_PAGES_SIZE = 100;
const EDITION_TOP_RATED_PLAYERS_LIMIT = 3;
const EDITION_TOP_RATED_PLAYERS_MIN_MATCHES = 5;

function formatKickoff(value: string | null | undefined): string {
  if (!value) {
    return "Data não informada";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Data não informada";
  }

  return DATE_TIME_FORMATTER.format(parsedDate);
}

function formatDateWindow(
  startingAt: string | null | undefined,
  endingAt: string | null | undefined,
): string | null {
  if (!startingAt && !endingAt) {
    return null;
  }

  const parsedStart = startingAt ? new Date(startingAt) : null;
  const parsedEnd = endingAt ? new Date(endingAt) : null;
  const hasValidStart = parsedStart !== null && !Number.isNaN(parsedStart.getTime());
  const hasValidEnd = parsedEnd !== null && !Number.isNaN(parsedEnd.getTime());

  if (hasValidStart && hasValidEnd) {
    const formattedStart = DATE_FORMATTER.format(parsedStart);
    const formattedEnd = DATE_FORMATTER.format(parsedEnd);
    return formattedStart === formattedEnd ? formattedStart : `${formattedStart} - ${formattedEnd}`;
  }

  if (hasValidStart) {
    return DATE_FORMATTER.format(parsedStart);
  }

  if (hasValidEnd) {
    return DATE_FORMATTER.format(parsedEnd);
  }

  return null;
}

function buildSeasonSurfaceHref(
  context: CompetitionSeasonContext,
  section: CompetitionSeasonSurfaceSection,
  searchParams: ReturnType<typeof useSearchParams>,
): string {
  const basePath = buildSeasonHubPath(context);
  const retainedQuery = new URLSearchParams(
    buildRetainedFilterQueryString(searchParams).replace(/^\?/, ""),
  );

  retainedQuery.delete("tab");

  if (section !== "overview") {
    retainedQuery.set("tab", mapCompetitionSeasonSurfaceSectionToLegacyTab(section));
  }

  const serialized = retainedQuery.toString();
  return serialized.length > 0 ? `${basePath}?${serialized}` : basePath;
}

function useStandingsColumns(context: CompetitionSeasonContext) {
  return useMemo<ColumnDef<StandingsTableRow>[]>(
    () => [
      { accessorKey: "position", header: "Pos" },
      {
        accessorKey: "teamName",
        header: "Equipe",
        cell: ({ row }) => (
          <Link
            className="font-semibold text-[#003526] transition-colors hover:text-[#00513b]"
            href={buildCanonicalTeamPath(context, row.original.teamId)}
          >
            {row.original.teamName ?? row.original.teamId}
          </Link>
        ),
      },
      { accessorKey: "matchesPlayed", header: "PJ" },
      { accessorKey: "wins", header: "V" },
      { accessorKey: "draws", header: "E" },
      { accessorKey: "losses", header: "D" },
      { accessorKey: "goalsFor", header: "GP" },
      { accessorKey: "goalsAgainst", header: "GC" },
      { accessorKey: "goalDiff", header: "SG" },
      { accessorKey: "points", header: "Pts" },
    ],
    [context],
  );
}

function useSeasonFilterInput(context: CompetitionSeasonContext) {
  const { roundId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();

  return useMemo(
    () => ({
      competitionId: context.competitionId,
      seasonId: context.seasonId,
      roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
    }),
    [
      context.competitionId,
      context.seasonId,
      roundId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      venue,
    ],
  );
}

function useSeasonFinalStandings(context: CompetitionSeasonContext, stageId?: string | null) {
  return useQueryWithCoverage<StandingsTableData>({
    queryKey: standingsQueryKeys.table({
      competitionId: context.competitionId,
      seasonId: context.seasonId,
      stageId: stageId ?? undefined,
    }),
    queryFn: () =>
      fetchStandings({
        competitionId: context.competitionId,
        seasonId: context.seasonId,
        stageId: stageId ?? undefined,
      }),
    enabled: Boolean(context.competitionId && context.seasonId),
    staleTime: 5 * 60 * 1000,
    gcTime: 20 * 60 * 1000,
    isDataEmpty: (data) => data.rows.length === 0,
  });
}

function useSeasonChampionLeadRounds(
  context: CompetitionSeasonContext,
  championTeamId: string | null | undefined,
  rounds: StandingsRound[],
): ChampionLeadRoundsSummary {
  const queries = useQueries({
    queries: rounds.map((round) => ({
      queryKey: standingsQueryKeys.table({
        competitionId: context.competitionId,
        seasonId: context.seasonId,
        roundId: round.roundId,
      }),
      queryFn: () =>
        fetchStandings({
          competitionId: context.competitionId,
          seasonId: context.seasonId,
          roundId: round.roundId,
        }),
      enabled: Boolean(context.competitionId && context.seasonId && championTeamId && round.roundId),
      staleTime: 5 * 60 * 1000,
      gcTime: 20 * 60 * 1000,
    })),
  });

  return useMemo(() => {
    if (!championTeamId || rounds.length === 0) {
      return {
        count: null,
        isError: false,
        isLoading: false,
      };
    }

    if (queries.some((query) => query.isLoading)) {
      return {
        count: null,
        isError: false,
        isLoading: true,
      };
    }

    if (queries.some((query) => query.isError || !query.data?.data)) {
      return {
        count: null,
        isError: true,
        isLoading: false,
      };
    }

    return {
      count: queries.reduce((sum, query) => {
        const leader = resolveChampionFromStandings(query.data?.data.rows ?? []);
        return leader?.teamId === championTeamId ? sum + 1 : sum;
      }, 0),
      isError: false,
      isLoading: false,
    };
  }, [championTeamId, queries, rounds.length]);
}

function useSeasonClosingMatches(context: CompetitionSeasonContext, pageSize = 6) {
  return useQueryWithCoverage<MatchesListData>({
    queryKey: ["matches", "season-closing", context.competitionId, context.seasonId, pageSize],
    queryFn: () =>
      fetchMatchesList({
        competitionId: context.competitionId,
        seasonId: context.seasonId,
        page: 1,
        pageSize,
        sortBy: "kickoffAt",
        sortDirection: "desc",
      }),
    enabled: Boolean(context.competitionId && context.seasonId),
    staleTime: 5 * 60 * 1000,
    gcTime: 20 * 60 * 1000,
    isDataEmpty: (data) => data.items.length === 0,
  });
}

async function fetchSeasonAllMatches(context: CompetitionSeasonContext): Promise<ApiResponse<MatchesListData>> {
  const initialResponse = await fetchMatchesList({
    competitionId: context.competitionId,
    seasonId: context.seasonId,
    page: 1,
    pageSize: MATCHES_LIST_ALL_PAGES_SIZE,
    sortBy: "kickoffAt",
    sortDirection: "desc",
  });
  const totalPages = initialResponse.meta?.pagination?.totalPages ?? 1;

  if (totalPages <= 1) {
    return initialResponse;
  }

  const remainingResponses = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      fetchMatchesList({
        competitionId: context.competitionId,
        seasonId: context.seasonId,
        page: index + 2,
        pageSize: MATCHES_LIST_ALL_PAGES_SIZE,
        sortBy: "kickoffAt",
        sortDirection: "desc",
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

function useSeasonAllMatches(context: CompetitionSeasonContext) {
  return useQueryWithCoverage<MatchesListData>({
    queryKey: ["matches", "season-all", context.competitionId, context.seasonId],
    queryFn: () => fetchSeasonAllMatches(context),
    enabled: Boolean(context.competitionId && context.seasonId),
    staleTime: 5 * 60 * 1000,
    gcTime: 20 * 60 * 1000,
    isDataEmpty: (data) => data.items.length === 0,
  });
}

function useGroupStandingsQueries(
  context: CompetitionSeasonContext,
  stage: CompetitionStructureStage | null,
): GroupStandingsQueryState[] {
  const groups = useMemo(() => stage?.groups ?? [], [stage]);

  const queries = useQueries({
    queries: groups.map((group) => ({
      queryKey: standingsQueryKeys.group({
        competitionKey: context.competitionKey,
        seasonLabel: context.seasonLabel,
        stageId: stage?.stageId ?? undefined,
        groupId: group.groupId,
      }),
      queryFn: () =>
        fetchGroupStandings({
          competitionKey: context.competitionKey,
          seasonLabel: context.seasonLabel,
          stageId: stage?.stageId ?? undefined,
          groupId: group.groupId,
        }),
      enabled: Boolean(context.competitionKey && context.seasonLabel && stage?.stageId && group.groupId),
      staleTime: 5 * 60 * 1000,
      gcTime: 20 * 60 * 1000,
    })),
  });

  return useMemo(
    () =>
      groups.map((group, index) => ({
        coverage: queries[index]?.data?.meta?.coverage
          ? {
              status: queries[index].data.meta.coverage.status,
              label: queries[index].data.meta.coverage.label ?? undefined,
              percentage: queries[index].data.meta.coverage.percentage ?? undefined,
            }
          : { status: "unknown" as const },
        data: queries[index]?.data?.data ?? null,
        group,
        isError: queries[index]?.isError ?? false,
        isLoading: queries[index]?.isLoading ?? false,
      })),
    [groups, queries],
  );
}

function resolveChampionFromStandings(rows: StandingsTableRow[]): StandingsTableRow | null {
  return rows[0] ?? null;
}

function resolveChampionTie(ties: StageTie[]): StageTie | null {
  if (ties.length === 0) {
    return null;
  }

  return ties.find((tie) => tie.winnerTeamId || tie.winnerTeamName) ?? ties[0];
}

function normalizeTeamIdentityKey(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const normalized = value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  return normalized.length > 0 ? normalized : null;
}

function buildTeamIdentityCandidates(
  teamId: string | null | undefined,
  teamName: string | null | undefined,
): string[] {
  const candidates = new Set<string>();
  const normalizedId = normalizeTeamIdentityKey(teamId);
  const normalizedName = normalizeTeamIdentityKey(teamName);

  if (normalizedId) {
    candidates.add(`id:${normalizedId}`);
  }

  if (normalizedName) {
    candidates.add(`name:${normalizedName}`);
  }

  return [...candidates];
}

function matchesTeamIdentity(
  left: BracketTeamReference,
  right: BracketTeamReference,
): boolean {
  const leftCandidates = buildTeamIdentityCandidates(left.teamId, left.teamName);
  const rightCandidates = buildTeamIdentityCandidates(right.teamId, right.teamName);

  return leftCandidates.some((candidate) => rightCandidates.includes(candidate));
}

function buildTieParticipants(tie: StageTie): BracketTeamReference[] {
  return [
    {
      teamId: tie.homeTeamId,
      teamName: tie.homeTeamName,
    },
    {
      teamId: tie.awayTeamId,
      teamName: tie.awayTeamName,
    },
  ].filter((team) => team.teamId || team.teamName);
}

function buildAdvancingTeamReference(tie: StageTie): BracketTeamReference[] {
  if (tie.winnerTeamId || tie.winnerTeamName) {
    return [
      {
        teamId: tie.winnerTeamId,
        teamName: tie.winnerTeamName,
      },
    ];
  }

  return buildTieParticipants(tie);
}

function tieFeedsParticipant(tie: StageTie, participant: BracketTeamReference): boolean {
  return buildAdvancingTeamReference(tie).some((team) => matchesTeamIdentity(team, participant));
}

function buildParticipantsFromTies(ties: StageTie[]): BracketTeamReference[] {
  return ties.flatMap((tie) => buildTieParticipants(tie));
}

function splitStageTiesFallback(ties: StageTie[]): Pick<BracketSnapshotColumn, "leftTies" | "rightTies"> {
  const midpoint = Math.ceil(ties.length / 2);

  return {
    leftTies: ties.slice(0, midpoint),
    rightTies: ties.slice(midpoint),
  };
}

function resolveSnapshotColumns(
  primaryStages: KnockoutStageQueryState[],
): BracketSnapshotColumn[] {
  const sideStages = primaryStages.slice(0, -1);
  const finalTie = primaryStages.at(-1)?.ties[0] ?? null;
  const columnsByStageId = new Map<string, BracketSnapshotColumn>();
  let nextStageParticipants: Record<BracketSide, BracketTeamReference[]> | null = finalTie
    ? {
        left: [
          {
            teamId: finalTie.homeTeamId,
            teamName: finalTie.homeTeamName,
          },
        ].filter((team) => team.teamId || team.teamName),
        right: [
          {
            teamId: finalTie.awayTeamId,
            teamName: finalTie.awayTeamName,
          },
        ].filter((team) => team.teamId || team.teamName),
      }
    : null;

  for (let index = sideStages.length - 1; index >= 0; index -= 1) {
    const stageState = sideStages[index];
    const fallback = splitStageTiesFallback(stageState.ties);

    if (!nextStageParticipants) {
      columnsByStageId.set(stageState.stage.stageId, {
        leftTies: fallback.leftTies,
        rightTies: fallback.rightTies,
        stageState,
      });
      nextStageParticipants = {
        left: buildParticipantsFromTies(fallback.leftTies),
        right: buildParticipantsFromTies(fallback.rightTies),
      };
      continue;
    }

    const currentParticipants = nextStageParticipants;
    const leftTies = stageState.ties.filter((tie) =>
      currentParticipants.left.some((participant) => tieFeedsParticipant(tie, participant)),
    );
    const rightTies = stageState.ties.filter((tie) =>
      currentParticipants.right.some((participant) => tieFeedsParticipant(tie, participant)),
    );
    const assignedTieIds = new Set([...leftTies, ...rightTies].map((tie) => tie.tieId));
    const unassignedTies = stageState.ties.filter((tie) => !assignedTieIds.has(tie.tieId));
    const canUseProgression = leftTies.length > 0 && rightTies.length > 0;
    const resolvedLeftTies = canUseProgression ? [...leftTies] : [...fallback.leftTies];
    const resolvedRightTies = canUseProgression ? [...rightTies] : [...fallback.rightTies];

    if (canUseProgression) {
      for (const tie of unassignedTies) {
        if (resolvedLeftTies.length <= resolvedRightTies.length) {
          resolvedLeftTies.push(tie);
        } else {
          resolvedRightTies.push(tie);
        }
      }
    }

    columnsByStageId.set(stageState.stage.stageId, {
      leftTies: resolvedLeftTies,
      rightTies: resolvedRightTies,
      stageState,
    });
    nextStageParticipants = {
      left: buildParticipantsFromTies(resolvedLeftTies),
      right: buildParticipantsFromTies(resolvedRightTies),
    };
  }

  return sideStages.map((stageState) => {
    const resolved = columnsByStageId.get(stageState.stage.stageId);

    if (resolved) {
      return resolved;
    }

    const fallback = splitStageTiesFallback(stageState.ties);

    return {
      leftTies: fallback.leftTies,
      rightTies: fallback.rightTies,
      stageState,
    };
  });
}

function normalizeStageIdentityValue(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function isRoundOf16Stage(stage: CompetitionStructureStage): boolean {
  const stageIdentities = [stage.stageCode, stage.stageId, stage.stageName]
    .map((value) => normalizeStageIdentityValue(value))
    .filter(Boolean);

  return stageIdentities.some(
    (value) =>
      value.includes("round_of_16") ||
      value.includes("last_16") ||
      value.includes("oitavas") ||
      value.includes("eighth_final") ||
      value.includes("eighth_finals"),
  );
}

function resolvePrimaryKnockoutStages(stages: KnockoutStageQueryState[]): KnockoutStageQueryState[] {
  const roundOf16Index = stages.findIndex((stage) => isRoundOf16Stage(stage.stage));
  return roundOf16Index >= 0 ? stages.slice(roundOf16Index) : stages;
}

function resolvePrimaryKnockoutStructureStages(
  stages: CompetitionStructureStage[],
): CompetitionStructureStage[] {
  const roundOf16Index = stages.findIndex((stage) => isRoundOf16Stage(stage));
  return roundOf16Index >= 0 ? stages.slice(roundOf16Index) : stages;
}

function formatCupStageCount(count: number): string {
  if (count <= 0) {
    return "fases indisponíveis";
  }

  return count === 1 ? "1 fase" : `${count} fases`;
}

function resolveCupPrimaryStages(
  resolution: CompetitionSeasonSurfaceResolution,
): CompetitionStructureStage[] {
  const knockoutStages = resolution.knockoutStages.filter((stage) => stage.stageFormat === "knockout");
  return resolvePrimaryKnockoutStructureStages(
    knockoutStages.length > 0 ? knockoutStages : resolution.knockoutStages,
  );
}

function resolveCupOpeningStage(
  resolution: CompetitionSeasonSurfaceResolution,
): CompetitionStructureStage | null {
  return resolveCupPrimaryStages(resolution)[0] ?? resolution.knockoutStages[0] ?? null;
}

function resolveCupFinalStage(
  resolution: CompetitionSeasonSurfaceResolution,
): CompetitionStructureStage | null {
  return resolveCupPrimaryStages(resolution).at(-1) ?? resolution.finalKnockoutStage;
}

function resolveCupParticipantCount(
  resolution: CompetitionSeasonSurfaceResolution,
  analyticsData?: CompetitionAnalyticsData | null,
): {
  count: number | null;
  source: "analytics" | "structure" | "unavailable";
} {
  const participantStage = resolution.knockoutStages[0] ?? resolveCupOpeningStage(resolution);

  if (typeof participantStage?.expectedTeams === "number" && participantStage.expectedTeams > 0) {
    return {
      count: participantStage.expectedTeams,
      source: "structure",
    };
  }

  const openingStageAnalytics =
    (participantStage
      ? analyticsData?.stageAnalytics.find((stage) => stage.stageId === participantStage.stageId && stage.teamCount > 0)
      : null) ??
    [...(analyticsData?.stageAnalytics ?? [])]
      .filter((stage) => stage.teamCount > 0)
      .sort((left, right) => {
        const leftOrder = left.stageOrder ?? Number.MAX_SAFE_INTEGER;
        const rightOrder = right.stageOrder ?? Number.MAX_SAFE_INTEGER;

        if (leftOrder !== rightOrder) {
          return leftOrder - rightOrder;
        }

        return right.teamCount - left.teamCount;
      })[0] ??
    null;

  if (openingStageAnalytics) {
    return {
      count: openingStageAnalytics.teamCount,
      source: "analytics",
    };
  }

  return {
    count: null,
    source: "unavailable",
  };
}

function resolveCupStageRangeLabel(
  resolution: CompetitionSeasonSurfaceResolution,
): string {
  const openingStage = resolveCupOpeningStage(resolution);
  const finalStage = resolveCupFinalStage(resolution);
  const openingLabel = openingStage
    ? localizeSeasonStageName(openingStage.stageName ?? openingStage.stageId)
    : null;
  const finalLabel = finalStage
    ? localizeSeasonStageName(finalStage.stageName ?? finalStage.stageId)
    : null;

  if (openingLabel && finalLabel && openingLabel !== finalLabel) {
    return `${openingLabel} até ${finalLabel.toLowerCase()}`;
  }

  return finalLabel ?? openingLabel ?? "Chave eliminatória";
}

function resolveTransitionSlotCount(stage: CompetitionStructureStage | null | undefined): number | null {
  if (!stage || stage.transitions.length === 0) {
    return null;
  }

  const totalSlots = stage.transitions.reduce((sum, transition) => {
    const start = transition.positionFrom ?? transition.positionTo;
    const end = transition.positionTo ?? transition.positionFrom;

    if (typeof start !== "number" || typeof end !== "number") {
      return sum;
    }

    const slotCount = Math.abs(end - start) + 1;
    return sum + slotCount;
  }, 0);

  return totalSlots > 0 ? totalSlots : null;
}

function resolveTransitionSummary(stage: CompetitionStructureStage | null | undefined): string | null {
  if (!stage || stage.transitions.length === 0) {
    return null;
  }

  const transitionsByTarget = new Map<string, number>();
  for (const transition of stage.transitions) {
    const targetLabel = transition.toStageName ?? transition.toStageId ?? "mata-mata";
    const start = transition.positionFrom ?? transition.positionTo;
    const end = transition.positionTo ?? transition.positionFrom;

    if (typeof start !== "number" || typeof end !== "number") {
      continue;
    }

    const slotCount = Math.abs(end - start) + 1;
    transitionsByTarget.set(targetLabel, (transitionsByTarget.get(targetLabel) ?? 0) + slotCount);
  }

  if (transitionsByTarget.size === 0) {
    return null;
  }

  const suffix = stage.stageFormat === "group_table" && stage.groups.length > 0 ? " por grupo" : " vagas";
  return [...transitionsByTarget.entries()]
    .map(([targetLabel, slotCount]) => `${slotCount}${suffix} -> ${formatHybridStageTargetLabel(targetLabel)}`)
    .join(" • ");
}

function formatTieResolutionLabel(tie: StageTie): string | null {
  if (tie.hasPenaltiesMatch) {
    return "Penaltis";
  }

  if (tie.hasExtraTimeMatch) {
    return "Prorrogacao";
  }

  if (!tie.resolutionType) {
    return null;
  }

  if (tie.resolutionType === "aggregate") {
    return "Agregado";
  }

  if (tie.resolutionType === "single_match") {
    return "Jogo único";
  }

  return tie.resolutionType.replace(/_/g, " ");
}

function formatTieMatchCountLabel(matchCount: number): string {
  return matchCount === 1 ? "1 jogo" : `${matchCount} jogos`;
}

function useKnockoutStageQueries(
  context: CompetitionSeasonContext,
  resolution: CompetitionSeasonSurfaceResolution,
): KnockoutStageQueryState[] {
  const queries = useQueries({
    queries: resolution.knockoutStages.map((stage) => ({
      queryKey: competitionStructureQueryKeys.ties({
        competitionKey: context.competitionKey,
        seasonLabel: context.seasonLabel,
        stageId: stage.stageId,
      }),
      queryFn: () =>
        fetchStageTies({
          competitionKey: context.competitionKey,
          seasonLabel: context.seasonLabel,
          stageId: stage.stageId,
        }),
      enabled: Boolean(context.competitionKey && context.seasonLabel && stage.stageId),
      staleTime: 5 * 60 * 1000,
      gcTime: 20 * 60 * 1000,
    })),
  });

  return useMemo(
    () =>
      resolution.knockoutStages.map((stage, index) => ({
        coverage: queries[index]?.data?.meta?.coverage ?? { status: "unknown" as const },
        isError: queries[index]?.isError ?? false,
        isLoading: queries[index]?.isLoading ?? false,
        stage,
        ties: queries[index]?.data?.data?.ties ?? [],
      })),
    [queries, resolution.knockoutStages],
  );
}

function SeasonSectionHeader({
  align = "start",
  coverage,
  description,
  eyebrow,
  title,
}: {
  align?: "center" | "start";
  coverage?: CoverageLike;
  description?: string;
  eyebrow: string;
  title: string;
}) {
  const wrapperClass =
    align === "center"
      ? "flex flex-col items-center gap-3 text-center"
      : "flex flex-wrap items-start justify-between gap-4";
  const copyClass = align === "center" ? "mx-auto max-w-3xl text-center" : undefined;

  return (
    <div className={wrapperClass}>
      <div className={copyClass}>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">{eyebrow}</p>
        <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
          {title}
        </h2>
        {description ? <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">{description}</p> : null}
      </div>
      {coverage && coverage.status !== "complete" ? <ProfileCoveragePill coverage={coverage} /> : null}
    </div>
  );
}

function SeasonHeroBlock({
  context,
  description,
  eyebrow,
  highlightDescription,
  highlightLabel,
  highlightValue,
  summary,
  tags = [],
  title,
}: {
  context: CompetitionSeasonContext;
  description?: string;
  eyebrow?: string;
  highlightDescription?: string;
  highlightLabel?: string;
  highlightValue?: string;
  summary?: ReactNode;
  tags?: string[];
  title: string;
}) {
  const competitionLogoSrc = context.competitionId
    ? `/api/visual-assets/competitions/${encodeURIComponent(context.competitionId)}`
    : null;
  const competitionInitials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="relative overflow-hidden rounded-[1.45rem] bg-[linear-gradient(128deg,#033727_0%,#054d39_44%,#12372b_100%)] px-5 py-5 text-white md:px-6 md:py-6">
      <div className="absolute right-[-6%] top-[-18%] h-56 w-56 rounded-full bg-[rgba(139,214,182,0.18)] blur-3xl" />
      <div className="absolute bottom-[-18%] right-[18%] h-48 w-48 rounded-full bg-[rgba(166,242,209,0.1)] blur-3xl" />

      <div className="relative space-y-6">
        {tags.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            {tags.map((tag) => (
              <span
                className="rounded-full border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.08)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#e5f5ee]"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[auto_minmax(0,1fr)_minmax(260px,0.75fr)] xl:items-end">
          <div className="flex h-20 w-20 items-center justify-center rounded-[1.3rem] border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.12)] p-4 shadow-[0_18px_40px_-28px_rgba(17,28,45,0.75)]">
            {competitionLogoSrc ? (
              <img
                alt={`Logo da competição ${context.competitionName}`}
                className="h-full w-full object-contain"
                src={competitionLogoSrc}
              />
            ) : (
              <span className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-white">
                {competitionInitials || "FA"}
              </span>
            )}
          </div>

          <div className="space-y-2">
            {eyebrow ? (
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">{eyebrow}</p>
            ) : null}
            <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.45rem] font-extrabold tracking-[-0.05em] text-white md:text-[3rem]">
              {title}
            </h1>
            {description ? <p className="max-w-3xl text-sm/6 text-[#d7efe4]">{description}</p> : null}
          </div>

          {highlightLabel || highlightValue ? (
            <div className="rounded-[1.35rem] border border-[rgba(255,255,255,0.12)] bg-[rgba(7,24,18,0.22)] px-4 py-4 shadow-[0_18px_40px_-28px_rgba(17,28,45,0.9)]">
              {highlightLabel ? (
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">{highlightLabel}</p>
              ) : null}
              {highlightValue ? (
                <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.65rem] font-extrabold text-white">
                  {highlightValue}
                </p>
              ) : null}
              {highlightDescription ? <p className="mt-2 text-xs/5 text-[#d7efe4]">{highlightDescription}</p> : null}
            </div>
          ) : null}
        </div>

        {summary ? <div>{summary}</div> : null}
      </div>
    </div>
  );
}

type HistoricalTopScorer = {
  entityId: string;
  entityName: string;
  goals: number;
  matchesPlayed: number | null;
  minutesPlayed: number | null;
  teamId?: string | null;
  teamName?: string | null;
};

type HistoricalTopScorerData = {
  scorer: HistoricalTopScorer | null;
};

async function fetchEditionTopScorer(context: CompetitionSeasonContext): Promise<ApiResponse<HistoricalTopScorerData>> {
  const rankingDefinition = getRankingDefinition("player-goals");

  if (!rankingDefinition) {
    return {
      data: { scorer: null },
      meta: {
        coverage: {
          label: "Ranking de artilharia indisponível no registro.",
          status: "unknown",
        },
      },
    };
  }

  const response = await fetchRanking({
    rankingDefinition,
    filters: {
      competitionId: context.competitionId,
      freshnessClass: "season",
      minSampleValue: 0,
      page: 1,
      pageSize: 1,
      seasonId: context.seasonId,
      sortDirection: "desc",
    },
  });
  const scorerRow = response.data.rows?.[0] ?? null;

  return {
    data: {
      scorer: scorerRow
        ? {
            entityId: scorerRow.entityId,
            entityName: scorerRow.entityName?.trim() || scorerRow.entityId,
            goals:
              typeof scorerRow.metricValue === "number" && Number.isFinite(scorerRow.metricValue)
                ? scorerRow.metricValue
                : 0,
            matchesPlayed:
              typeof scorerRow.matchesPlayed === "number" && Number.isFinite(scorerRow.matchesPlayed)
                ? scorerRow.matchesPlayed
                : null,
            minutesPlayed:
              typeof scorerRow.minutesPlayed === "number" && Number.isFinite(scorerRow.minutesPlayed)
                ? scorerRow.minutesPlayed
                : null,
            teamId: typeof scorerRow.teamId === "string" ? scorerRow.teamId : null,
            teamName: typeof scorerRow.teamName === "string" ? scorerRow.teamName : null,
          }
        : null,
    },
    meta: response.meta,
  };
}

function useEditionTopScorer(context: CompetitionSeasonContext) {
  return useQueryWithCoverage<HistoricalTopScorerData>({
    enabled: Boolean(context.competitionId && context.seasonId),
    gcTime: 30 * 60 * 1000,
    isDataEmpty: (data) => data.scorer === null,
    queryFn: () => fetchEditionTopScorer(context),
    queryKey: ["competition-season-top-scorer", context.competitionId, context.seasonId],
    staleTime: 10 * 60 * 1000,
  });
}

function resolveRankingMetricValue(row: RankingTableRow, fallback: number): number {
  return typeof row.metricValue === "number" && Number.isFinite(row.metricValue)
    ? row.metricValue
    : fallback;
}

function resolveRankingMinutes(row: RankingTableRow, fallback: number): number {
  return typeof row.minutesPlayed === "number" && Number.isFinite(row.minutesPlayed)
    ? row.minutesPlayed
    : fallback;
}

function resolveRankingMatchesPlayed(row: RankingTableRow, fallback: number): number {
  return typeof row.matchesPlayed === "number" && Number.isFinite(row.matchesPlayed)
    ? row.matchesPlayed
    : fallback;
}

function mapHistoricalRankingLeader(row: RankingTableRow): HistoricalRankingLeader {
  const matchesPlayed = resolveRankingMatchesPlayed(row, Number.NaN);

  return {
    entityId: row.entityId,
    entityName: row.entityName?.trim() || row.entityId,
    matchesPlayed: Number.isFinite(matchesPlayed) ? matchesPlayed : null,
    metricValue: resolveRankingMetricValue(row, 0),
    minutesPlayed:
      typeof row.minutesPlayed === "number" && Number.isFinite(row.minutesPlayed)
        ? row.minutesPlayed
        : null,
    teamId: typeof row.teamId === "string" ? row.teamId : null,
    teamName: typeof row.teamName === "string" ? row.teamName : null,
  };
}

function compareHistoricalRatings(left: RankingTableRow, right: RankingTableRow): number {
  const leftRating = resolveRankingMetricValue(left, Number.NEGATIVE_INFINITY);
  const rightRating = resolveRankingMetricValue(right, Number.NEGATIVE_INFINITY);

  if (leftRating !== rightRating) {
    return rightRating - leftRating;
  }

  const leftMinutes = resolveRankingMinutes(left, Number.NEGATIVE_INFINITY);
  const rightMinutes = resolveRankingMinutes(right, Number.NEGATIVE_INFINITY);

  if (leftMinutes !== rightMinutes) {
    return rightMinutes - leftMinutes;
  }

  const leftName = (left.entityName ?? left.entityId ?? "").trim();
  const rightName = (right.entityName ?? right.entityId ?? "").trim();
  const nameComparison = leftName.localeCompare(rightName, "pt-BR", { sensitivity: "base" });

  if (nameComparison !== 0) {
    return nameComparison;
  }

  return left.entityId.localeCompare(right.entityId, "pt-BR", { sensitivity: "base" });
}

function compareHistoricalAssists(left: RankingTableRow, right: RankingTableRow): number {
  const leftAssists = resolveRankingMetricValue(left, Number.NEGATIVE_INFINITY);
  const rightAssists = resolveRankingMetricValue(right, Number.NEGATIVE_INFINITY);

  if (leftAssists !== rightAssists) {
    return rightAssists - leftAssists;
  }

  const leftMinutes = resolveRankingMinutes(left, Number.POSITIVE_INFINITY);
  const rightMinutes = resolveRankingMinutes(right, Number.POSITIVE_INFINITY);

  if (leftMinutes !== rightMinutes) {
    return leftMinutes - rightMinutes;
  }

  const leftName = (left.entityName ?? left.entityId ?? "").trim();
  const rightName = (right.entityName ?? right.entityId ?? "").trim();
  const nameComparison = leftName.localeCompare(rightName, "pt-BR", { sensitivity: "base" });

  if (nameComparison !== 0) {
    return nameComparison;
  }

  return left.entityId.localeCompare(right.entityId, "pt-BR", { sensitivity: "base" });
}

async function fetchAllHistoricalRankingRows(
  context: CompetitionSeasonContext,
  rankingDefinition: RankingDefinition,
): Promise<{ firstResponse: ApiResponse<{ rows: RankingTableRow[] }> | null; rows: RankingTableRow[] }> {
  let page = 1;
  let totalPages = 1;
  let firstResponse: ApiResponse<{ rows: RankingTableRow[] }> | null = null;
  const rows: RankingTableRow[] = [];

  do {
    const response = await fetchRanking({
      rankingDefinition,
      filters: {
        competitionId: context.competitionId,
        freshnessClass: "season",
        minSampleValue: rankingDefinition.minSample?.min ?? 0,
        page,
        pageSize: 100,
        seasonId: context.seasonId,
        sortDirection: rankingDefinition.defaultSort,
      },
    });

    firstResponse ??= response;
    rows.push(...(response.data.rows ?? []));
    totalPages = response.meta?.pagination?.totalPages ?? 1;
    page += 1;
  } while (page <= totalPages);

  return {
    firstResponse,
    rows,
  };
}

async function fetchEditionRankingLeader(
  context: CompetitionSeasonContext,
  rankingId: string,
  compareRows: (left: RankingTableRow, right: RankingTableRow) => number,
): Promise<ApiResponse<HistoricalRankingLeaderData>> {
  const rankingDefinition = getRankingDefinition(rankingId);

  if (!rankingDefinition) {
    return {
      data: { leader: null },
      meta: {
        coverage: {
          label: `Ranking ${rankingId} indisponível no registro.`,
          status: "unknown",
        },
      },
    };
  }

  const { firstResponse, rows } = await fetchAllHistoricalRankingRows(context, rankingDefinition);
  const leaderRow = [...rows].sort(compareRows)[0] ?? null;

  return {
    data: {
      leader: leaderRow ? mapHistoricalRankingLeader(leaderRow) : null,
    },
    meta: firstResponse?.meta,
  };
}

async function fetchEditionTopRatedPlayers(context: CompetitionSeasonContext): Promise<ApiResponse<HistoricalRankingLeadersData>> {
  const rankingDefinition = getRankingDefinition("player-rating");

  if (!rankingDefinition) {
    return {
      data: { leaders: [] },
      meta: {
        coverage: {
          label: "Ranking player-rating indisponível no registro.",
          status: "unknown",
        },
      },
    };
  }

  const { firstResponse, rows } = await fetchAllHistoricalRankingRows(context, rankingDefinition);
  const leaders = [...rows]
    .filter((row) => resolveRankingMatchesPlayed(row, 0) >= EDITION_TOP_RATED_PLAYERS_MIN_MATCHES)
    .sort(compareHistoricalRatings)
    .slice(0, EDITION_TOP_RATED_PLAYERS_LIMIT)
    .map(mapHistoricalRankingLeader);

  return {
    data: { leaders },
    meta: firstResponse?.meta,
  };
}

function useEditionTopRatedPlayers(context: CompetitionSeasonContext) {
  return useQueryWithCoverage<HistoricalRankingLeadersData>({
    enabled: Boolean(context.competitionId && context.seasonId),
    gcTime: 30 * 60 * 1000,
    isDataEmpty: (data) => data.leaders.length === 0,
    queryFn: () => fetchEditionTopRatedPlayers(context),
    queryKey: [
      "competition-season-top-rated-players",
      context.competitionId,
      context.seasonId,
      EDITION_TOP_RATED_PLAYERS_LIMIT,
      EDITION_TOP_RATED_PLAYERS_MIN_MATCHES,
    ],
    staleTime: 10 * 60 * 1000,
  });
}

function useEditionTopAssistProvider(context: CompetitionSeasonContext) {
  return useQueryWithCoverage<HistoricalRankingLeaderData>({
    enabled: Boolean(context.competitionId && context.seasonId),
    gcTime: 30 * 60 * 1000,
    isDataEmpty: (data) => data.leader === null,
    queryFn: () => fetchEditionRankingLeader(context, "player-assists", compareHistoricalAssists),
    queryKey: ["competition-season-top-assist-provider", context.competitionId, context.seasonId],
    staleTime: 10 * 60 * 1000,
  });
}

function HistoricalHeroCard({
  detail,
  label,
  tone = "base",
  value,
}: {
  detail: string;
  label: string;
  tone?: "base" | "soft";
  value: ReactNode;
}) {
  return (
    <article
      className={
        tone === "soft"
          ? "rounded-[1.25rem] border border-[rgba(216,227,251,0.7)] bg-[rgba(240,243,255,0.94)] px-4 py-4 shadow-[0_18px_40px_-30px_rgba(17,28,45,0.55)]"
          : "rounded-[1.25rem] border border-white/70 bg-[rgba(255,255,255,0.92)] px-4 py-4 shadow-[0_18px_40px_-30px_rgba(17,28,45,0.55)]"
      }
    >
      <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
      <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
        {value}
      </p>
      <p className="mt-2 text-xs/5 text-[#57657a]">{detail}</p>
    </article>
  );
}

function HybridHeroSummaryItem({
  detail,
  label,
  media,
  value,
  valueClassName,
}: {
  detail?: ReactNode;
  label: string;
  media?: ReactNode;
  value: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="border-b border-[rgba(191,201,195,0.42)] py-4 first:pt-0 last:border-b-0 last:pb-0">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
      <div className="mt-2 flex items-center gap-3">
        {media ? <div className="shrink-0">{media}</div> : null}
        <div className="min-w-0">
          <div
            className={
              valueClassName ??
              "font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-[1.05] tracking-[-0.04em] text-[#111c2d]"
            }
          >
            {value}
          </div>
          {detail ? <div className="mt-1.5 text-sm/5 text-[#57657a]">{detail}</div> : null}
        </div>
      </div>
    </div>
  );
}

function formatLongDate(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return LONG_DATE_FORMATTER.format(parsedDate);
}

function formatHybridStageTargetLabel(value: string | null | undefined): string {
  const normalizedValue = normalizeStageIdentityValue(value);

  if (!normalizedValue) {
    return "o mata-mata";
  }

  if (
    normalizedValue.includes("round_of_16") ||
    normalizedValue === "round_16" ||
    normalizedValue.includes("last_16") ||
    normalizedValue.includes("8th_final") ||
    normalizedValue.includes("eighth_final") ||
    normalizedValue.includes("oitavas")
  ) {
    return "as oitavas";
  }

  if (normalizedValue.includes("quarter") || normalizedValue.includes("quartas")) {
    return "as quartas";
  }

  if (normalizedValue.includes("semi")) {
    return "a semifinal";
  }

  if (normalizedValue.includes("final")) {
    return "a final";
  }

  const localizedLabel = localizeSeasonStageName(value);

  return localizedLabel !== "Fase" ? localizedLabel.toLowerCase() : "o mata-mata";
}

function localizeSeasonStageName(value: string | null | undefined): string {
  return localizeCompetitionStageName(value);
}

function resolveHybridStructureHeadline(
  resolution: CompetitionSeasonSurfaceResolution,
): string {
  if (resolution.primaryTableStage?.stageFormat === "group_table") {
    return "Fase de grupos → mata-mata";
  }

  if (resolution.primaryTableStage?.stageFormat === "league_table") {
    return "Fase classificatória → mata-mata";
  }

  return "Fase de tabela → mata-mata";
}

function resolveHybridStructureDetail(stage: CompetitionStructureStage | null): string {
  if (!stage || stage.transitions.length === 0) {
    return "Transição consolidada para o mata-mata.";
  }

  const slotCount = resolveTransitionSlotCount(stage);
  const transitionTarget = formatHybridStageTargetLabel(
    stage.transitions[0]?.toStageName ?? stage.transitions[0]?.toStageId,
  );

  if (stage.stageFormat === "group_table" && slotCount) {
    return `${slotCount} avançam por grupo até ${transitionTarget}`;
  }

  if (slotCount) {
    return `${slotCount} equipes avançam até ${transitionTarget}`;
  }

  return `Transição consolidada até ${transitionTarget}`;
}

function resolveHybridNavigationStructureLabel(
  stage: CompetitionStructureStage | null,
): string {
  if (stage?.stageFormat === "group_table") {
    return "Grupos";
  }

  if (stage?.stageFormat === "league_table") {
    return "Classificatoria";
  }

  return "Fase de tabela";
}

function formatHistoricalMatchCount(matchCount: number | null | undefined) {
  if (typeof matchCount !== "number" || !Number.isFinite(matchCount)) {
    return "-";
  }

  return matchCount.toLocaleString("pt-BR");
}

function formatAverageGoals(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatRoundCount(roundCount: number | null | undefined) {
  if (typeof roundCount !== "number" || !Number.isFinite(roundCount)) {
    return "-";
  }

  const formattedRoundCount = formatHistoricalMatchCount(roundCount);

  return roundCount === 1 ? `${formattedRoundCount} Rodada` : `${formattedRoundCount} Rodadas`;
}

function resolveLeagueGoalsFromStandings(rows: StandingsTableRow[]): number | null {
  if (rows.length === 0) {
    return null;
  }

  const totalGoalsFor = rows.reduce((sum, row) => sum + row.goalsFor, 0);
  const totalGoalsAgainst = rows.reduce((sum, row) => sum + row.goalsAgainst, 0);

  if (
    !Number.isFinite(totalGoalsFor) ||
    !Number.isFinite(totalGoalsAgainst) ||
    totalGoalsFor < 0 ||
    totalGoalsAgainst < 0 ||
    totalGoalsFor !== totalGoalsAgainst
  ) {
    return null;
  }

  return totalGoalsFor;
}

function normalizeComparableText(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function formatAssistCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  return `${formatHistoricalMatchCount(value)} assistências`;
}

function formatGameCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  const formattedValue = formatHistoricalMatchCount(value);
  return value === 1 ? `${formattedValue} jogo` : `${formattedValue} jogos`;
}

function formatPointCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  return `${formatHistoricalMatchCount(value)} pts`;
}

function resolveGoalCadenceMinutes(
  goals: number | null | undefined,
  minutesPlayed: number | null | undefined,
): number | null {
  if (
    typeof goals !== "number" ||
    !Number.isFinite(goals) ||
    goals <= 0 ||
    typeof minutesPlayed !== "number" ||
    !Number.isFinite(minutesPlayed) ||
    minutesPlayed <= 0
  ) {
    return null;
  }

  return Math.max(1, Math.round(minutesPlayed / goals));
}

function formatMinutesLabel(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  return `${formatHistoricalMatchCount(value)} min`;
}

function compareTeamNames(left: { key: string; teamName: string }, right: { key: string; teamName: string }): number {
  const nameComparison = left.teamName.localeCompare(right.teamName, "pt-BR", { sensitivity: "base" });

  if (nameComparison !== 0) {
    return nameComparison;
  }

  return left.key.localeCompare(right.key, "pt-BR", { sensitivity: "base" });
}

function compareStandingRowNames(left: StandingsTableRow, right: StandingsTableRow): number {
  const leftName = left.teamName?.trim() || left.teamId;
  const rightName = right.teamName?.trim() || right.teamId;
  const nameComparison = leftName.localeCompare(rightName, "pt-BR", { sensitivity: "base" });

  if (nameComparison !== 0) {
    return nameComparison;
  }

  return left.teamId.localeCompare(right.teamId, "pt-BR", { sensitivity: "base" });
}

function compareStandingsByBestAttack(left: StandingsTableRow, right: StandingsTableRow): number {
  if (left.goalsFor !== right.goalsFor) {
    return right.goalsFor - left.goalsFor;
  }

  if (left.position !== right.position) {
    return left.position - right.position;
  }

  return compareStandingRowNames(left, right);
}

function compareStandingsByBestDefense(left: StandingsTableRow, right: StandingsTableRow): number {
  if (left.goalsAgainst !== right.goalsAgainst) {
    return left.goalsAgainst - right.goalsAgainst;
  }

  if (left.position !== right.position) {
    return left.position - right.position;
  }

  return compareStandingRowNames(left, right);
}

function resolveBestPosition(aggregate: TeamSeasonAggregate): number {
  return typeof aggregate.finalPosition === "number" ? aggregate.finalPosition : Number.POSITIVE_INFINITY;
}

function resolveWorstPosition(aggregate: TeamSeasonAggregate): number {
  return typeof aggregate.finalPosition === "number" ? aggregate.finalPosition : Number.NEGATIVE_INFINITY;
}

function compareBestPositions(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  const leftPosition = resolveBestPosition(left);
  const rightPosition = resolveBestPosition(right);

  if (leftPosition === rightPosition) {
    return 0;
  }

  return leftPosition < rightPosition ? -1 : 1;
}

function compareWorstPositions(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  const leftPosition = resolveWorstPosition(left);
  const rightPosition = resolveWorstPosition(right);

  if (leftPosition === rightPosition) {
    return 0;
  }

  return leftPosition > rightPosition ? -1 : 1;
}

function compareAggregatesByBestAttack(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.goalsFor !== right.goalsFor) {
    return right.goalsFor - left.goalsFor;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByBestDefense(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.goalsAgainst !== right.goalsAgainst) {
    return left.goalsAgainst - right.goalsAgainst;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByBestHome(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.homePoints !== right.homePoints) {
    return right.homePoints - left.homePoints;
  }

  if (left.homeGoalDiff !== right.homeGoalDiff) {
    return right.homeGoalDiff - left.homeGoalDiff;
  }

  if (left.homeGoalsFor !== right.homeGoalsFor) {
    return right.homeGoalsFor - left.homeGoalsFor;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByBestAway(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.awayPoints !== right.awayPoints) {
    return right.awayPoints - left.awayPoints;
  }

  if (left.awayGoalDiff !== right.awayGoalDiff) {
    return right.awayGoalDiff - left.awayGoalDiff;
  }

  if (left.awayGoalsFor !== right.awayGoalsFor) {
    return right.awayGoalsFor - left.awayGoalsFor;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByWorstAway(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.awayPoints !== right.awayPoints) {
    return left.awayPoints - right.awayPoints;
  }

  if (left.awayGoalDiff !== right.awayGoalDiff) {
    return left.awayGoalDiff - right.awayGoalDiff;
  }

  if (left.awayGoalsFor !== right.awayGoalsFor) {
    return left.awayGoalsFor - right.awayGoalsFor;
  }

  const positionDelta = compareWorstPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByUnbeatenRun(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.longestUnbeatenStreak !== right.longestUnbeatenStreak) {
    return right.longestUnbeatenStreak - left.longestUnbeatenStreak;
  }

  if (left.longestUnbeatenStreakEndedAt !== right.longestUnbeatenStreakEndedAt) {
    return right.longestUnbeatenStreakEndedAt - left.longestUnbeatenStreakEndedAt;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function compareAggregatesByWinningRun(left: TeamSeasonAggregate, right: TeamSeasonAggregate): number {
  if (left.longestWinningStreak !== right.longestWinningStreak) {
    return right.longestWinningStreak - left.longestWinningStreak;
  }

  if (left.longestWinningStreakEndedAt !== right.longestWinningStreakEndedAt) {
    return right.longestWinningStreakEndedAt - left.longestWinningStreakEndedAt;
  }

  const positionDelta = compareBestPositions(left, right);

  if (positionDelta !== 0) {
    return positionDelta;
  }

  return compareTeamNames(left, right);
}

function resolveCompletedSeasonMatch(match: MatchListItem): CompletedSeasonMatch | null {
  if (
    typeof match.homeScore !== "number" ||
    !Number.isFinite(match.homeScore) ||
    typeof match.awayScore !== "number" ||
    !Number.isFinite(match.awayScore)
  ) {
    return null;
  }

  return {
    ...match,
    awayScore: match.awayScore,
    homeScore: match.homeScore,
  };
}

function resolveKickoffTimestamp(value: string | null | undefined, fallback = Number.NEGATIVE_INFINITY): number {
  if (!value) {
    return fallback;
  }

  const parsedDate = new Date(value);
  return Number.isNaN(parsedDate.getTime()) ? fallback : parsedDate.getTime();
}

function buildStandingsPositionIndex(rows: StandingsTableRow[]): Map<string, number> {
  const index = new Map<string, number>();

  for (const row of rows) {
    index.set(`id:${row.teamId}`, row.position);

    const normalizedName = normalizeComparableText(row.teamName);

    if (normalizedName.length > 0) {
      index.set(`name:${normalizedName}`, row.position);
    }
  }

  return index;
}

function resolveAggregateIdentity(
  teamId: string | null | undefined,
  teamName: string | null | undefined,
  fallbackKey: string,
) {
  const normalizedTeamId = typeof teamId === "string" && teamId.trim().length > 0 ? teamId.trim() : null;
  const resolvedTeamName = typeof teamName === "string" && teamName.trim().length > 0 ? teamName.trim() : normalizedTeamId ?? fallbackKey;
  const normalizedTeamName = normalizeComparableText(resolvedTeamName);
  const key = normalizedTeamId ? `id:${normalizedTeamId}` : normalizedTeamName ? `name:${normalizedTeamName}` : fallbackKey;

  return {
    key,
    teamId: normalizedTeamId,
    teamName: resolvedTeamName,
  };
}

function createTeamSeasonAggregate(
  identity: ReturnType<typeof resolveAggregateIdentity>,
  positionIndex: Map<string, number>,
): TeamSeasonAggregate {
  return {
    awayGoalDiff: 0,
    awayGoalsFor: 0,
    awayPoints: 0,
    finalPosition: positionIndex.get(identity.key) ?? null,
    goalsAgainst: 0,
    goalsFor: 0,
    homeGoalDiff: 0,
    homeGoalsFor: 0,
    homePoints: 0,
    key: identity.key,
    longestUnbeatenStreak: 0,
    longestUnbeatenStreakEndedAt: Number.NEGATIVE_INFINITY,
    longestWinningStreak: 0,
    longestWinningStreakEndedAt: Number.NEGATIVE_INFINITY,
    matchResults: [],
    teamId: identity.teamId,
    teamName: identity.teamName,
  };
}

function buildTeamSeasonAggregates(matches: MatchListItem[], standingsRows: StandingsTableRow[]): TeamSeasonAggregate[] {
  const aggregates = new Map<string, TeamSeasonAggregate>();
  const positionIndex = buildStandingsPositionIndex(standingsRows);

  const completedMatches = matches
    .map(resolveCompletedSeasonMatch)
    .filter((match): match is CompletedSeasonMatch => match !== null);

  completedMatches.forEach((match, index) => {
    const kickoffTimestamp = resolveKickoffTimestamp(match.kickoffAt, index);
    const homeIdentity = resolveAggregateIdentity(match.homeTeamId, match.homeTeamName, `match:${match.matchId}:home`);
    const awayIdentity = resolveAggregateIdentity(match.awayTeamId, match.awayTeamName, `match:${match.matchId}:away`);
    const homeAggregate =
      aggregates.get(homeIdentity.key) ?? createTeamSeasonAggregate(homeIdentity, positionIndex);
    const awayAggregate =
      aggregates.get(awayIdentity.key) ?? createTeamSeasonAggregate(awayIdentity, positionIndex);

    aggregates.set(homeIdentity.key, homeAggregate);
    aggregates.set(awayIdentity.key, awayAggregate);

    const homePoints = match.homeScore > match.awayScore ? 3 : match.homeScore === match.awayScore ? 1 : 0;
    const awayPoints = match.awayScore > match.homeScore ? 3 : match.homeScore === match.awayScore ? 1 : 0;
    const goalDiff = match.homeScore - match.awayScore;

    homeAggregate.goalsFor += match.homeScore;
    homeAggregate.goalsAgainst += match.awayScore;
    homeAggregate.homeGoalsFor += match.homeScore;
    homeAggregate.homeGoalDiff += goalDiff;
    homeAggregate.homePoints += homePoints;
    homeAggregate.matchResults.push({
      isUnbeaten: match.homeScore >= match.awayScore,
      isWin: match.homeScore > match.awayScore,
      kickoffTimestamp,
      matchId: match.matchId,
    });

    awayAggregate.goalsFor += match.awayScore;
    awayAggregate.goalsAgainst += match.homeScore;
    awayAggregate.awayGoalsFor += match.awayScore;
    awayAggregate.awayGoalDiff += -goalDiff;
    awayAggregate.awayPoints += awayPoints;
    awayAggregate.matchResults.push({
      isUnbeaten: match.awayScore >= match.homeScore,
      isWin: match.awayScore > match.homeScore,
      kickoffTimestamp,
      matchId: match.matchId,
    });
  });

  return Array.from(aggregates.values()).map((aggregate) => {
    const orderedResults = [...aggregate.matchResults].sort((left, right) => {
      if (left.kickoffTimestamp !== right.kickoffTimestamp) {
        return left.kickoffTimestamp - right.kickoffTimestamp;
      }

      return left.matchId.localeCompare(right.matchId, "pt-BR", { sensitivity: "base" });
    });

    let currentUnbeaten = 0;
    let currentWinning = 0;

    for (const result of orderedResults) {
      currentUnbeaten = result.isUnbeaten ? currentUnbeaten + 1 : 0;
      currentWinning = result.isWin ? currentWinning + 1 : 0;

      if (
        currentUnbeaten > aggregate.longestUnbeatenStreak ||
        (currentUnbeaten === aggregate.longestUnbeatenStreak &&
          result.kickoffTimestamp > aggregate.longestUnbeatenStreakEndedAt)
      ) {
        aggregate.longestUnbeatenStreak = currentUnbeaten;
        aggregate.longestUnbeatenStreakEndedAt = result.kickoffTimestamp;
      }

      if (
        currentWinning > aggregate.longestWinningStreak ||
        (currentWinning === aggregate.longestWinningStreak &&
          result.kickoffTimestamp > aggregate.longestWinningStreakEndedAt)
      ) {
        aggregate.longestWinningStreak = currentWinning;
        aggregate.longestWinningStreakEndedAt = result.kickoffTimestamp;
      }
    }

    return aggregate;
  });
}

function mapAggregateInsight(aggregate: TeamSeasonAggregate | null, metricValue: number | null | undefined): TeamMetricInsight | null {
  if (!aggregate || typeof metricValue !== "number" || !Number.isFinite(metricValue)) {
    return null;
  }

  return {
    metricValue,
    teamId: aggregate.teamId,
    teamName: aggregate.teamName,
  };
}

function resolveBestAttackInsight(
  standingsRows: StandingsTableRow[],
  teamAggregates: TeamSeasonAggregate[],
): TeamMetricInsight | null {
  const leaderFromStandings = standingsRows.length > 0 ? [...standingsRows].sort(compareStandingsByBestAttack)[0] ?? null : null;

  if (leaderFromStandings) {
    return {
      metricValue: leaderFromStandings.goalsFor,
      teamId: leaderFromStandings.teamId,
      teamName: leaderFromStandings.teamName?.trim() || leaderFromStandings.teamId,
    };
  }

  const leaderFromMatches = [...teamAggregates].sort(compareAggregatesByBestAttack)[0] ?? null;
  return mapAggregateInsight(leaderFromMatches, leaderFromMatches?.goalsFor);
}

function resolveBestDefenseInsight(
  standingsRows: StandingsTableRow[],
  teamAggregates: TeamSeasonAggregate[],
): TeamMetricInsight | null {
  const leaderFromStandings = standingsRows.length > 0 ? [...standingsRows].sort(compareStandingsByBestDefense)[0] ?? null : null;

  if (leaderFromStandings) {
    return {
      metricValue: leaderFromStandings.goalsAgainst,
      teamId: leaderFromStandings.teamId,
      teamName: leaderFromStandings.teamName?.trim() || leaderFromStandings.teamId,
    };
  }

  const leaderFromMatches = [...teamAggregates].sort(compareAggregatesByBestDefense)[0] ?? null;
  return mapAggregateInsight(leaderFromMatches, leaderFromMatches?.goalsAgainst);
}

function resolveMatchClassificationPair(
  match: CompletedSeasonMatch,
  positionIndex: Map<string, number>,
): [number, number] {
  const homePosition =
    positionIndex.get(`id:${match.homeTeamId}`) ??
    positionIndex.get(`name:${normalizeComparableText(match.homeTeamName)}`) ??
    Number.POSITIVE_INFINITY;
  const awayPosition =
    positionIndex.get(`id:${match.awayTeamId}`) ??
    positionIndex.get(`name:${normalizeComparableText(match.awayTeamName)}`) ??
    Number.POSITIVE_INFINITY;

  return homePosition <= awayPosition ? [homePosition, awayPosition] : [awayPosition, homePosition];
}

function compareHighestScoringMatches(
  left: CompletedSeasonMatch,
  right: CompletedSeasonMatch,
  positionIndex: Map<string, number>,
): number {
  const leftTotalGoals = left.homeScore + left.awayScore;
  const rightTotalGoals = right.homeScore + right.awayScore;

  if (leftTotalGoals !== rightTotalGoals) {
    return rightTotalGoals - leftTotalGoals;
  }

  const leftGoalDiff = Math.abs(left.homeScore - left.awayScore);
  const rightGoalDiff = Math.abs(right.homeScore - right.awayScore);

  if (leftGoalDiff !== rightGoalDiff) {
    return rightGoalDiff - leftGoalDiff;
  }

  const [leftBestPosition, leftSecondPosition] = resolveMatchClassificationPair(left, positionIndex);
  const [rightBestPosition, rightSecondPosition] = resolveMatchClassificationPair(right, positionIndex);

  if (leftBestPosition !== rightBestPosition) {
    return leftBestPosition - rightBestPosition;
  }

  if (leftSecondPosition !== rightSecondPosition) {
    return leftSecondPosition - rightSecondPosition;
  }

  const leftKickoffTimestamp = resolveKickoffTimestamp(left.kickoffAt);
  const rightKickoffTimestamp = resolveKickoffTimestamp(right.kickoffAt);

  if (leftKickoffTimestamp !== rightKickoffTimestamp) {
    return rightKickoffTimestamp - leftKickoffTimestamp;
  }

  return left.matchId.localeCompare(right.matchId, "pt-BR", { sensitivity: "base" });
}

function useEditionRailInsights(context: CompetitionSeasonContext): EditionRailInsights {
  const standingsQuery = useSeasonFinalStandings(context);
  const matchesQuery = useSeasonAllMatches(context);

  const insights = useMemo(() => {
    const standingsRows = standingsQuery.data?.rows ?? [];
    const matches = matchesQuery.data?.items ?? [];
    const teamAggregates = buildTeamSeasonAggregates(matches, standingsRows);
    const positionIndex = buildStandingsPositionIndex(standingsRows);
    const completedMatches = matches
      .map(resolveCompletedSeasonMatch)
      .filter((match): match is CompletedSeasonMatch => match !== null);
    const highestScoringMatch = [...completedMatches].sort((left, right) => compareHighestScoringMatches(left, right, positionIndex))[0] ?? null;
    const bestHomeTeam = [...teamAggregates].sort(compareAggregatesByBestHome)[0] ?? null;
    const bestAwayTeam = [...teamAggregates].sort(compareAggregatesByBestAway)[0] ?? null;
    const worstAwayTeam = [...teamAggregates].sort(compareAggregatesByWorstAway)[0] ?? null;
    const longestUnbeatenRun = [...teamAggregates].sort(compareAggregatesByUnbeatenRun)[0] ?? null;
    const longestWinningRun = [...teamAggregates].sort(compareAggregatesByWinningRun)[0] ?? null;

    return {
      bestAttack: resolveBestAttackInsight(standingsRows, teamAggregates),
      bestAwayTeam: mapAggregateInsight(bestAwayTeam, bestAwayTeam?.awayPoints),
      bestDefense: resolveBestDefenseInsight(standingsRows, teamAggregates),
      bestHomeTeam: mapAggregateInsight(bestHomeTeam, bestHomeTeam?.homePoints),
      highestScoringMatch: highestScoringMatch
        ? {
            awayScore: highestScoringMatch.awayScore,
            awayTeamId: highestScoringMatch.awayTeamId ?? null,
            awayTeamName: highestScoringMatch.awayTeamName?.trim() || "Visitante",
            homeScore: highestScoringMatch.homeScore,
            homeTeamId: highestScoringMatch.homeTeamId ?? null,
            homeTeamName: highestScoringMatch.homeTeamName?.trim() || "Mandante",
            kickoffAt: highestScoringMatch.kickoffAt ?? null,
            matchId: highestScoringMatch.matchId,
            metricValue: highestScoringMatch.homeScore + highestScoringMatch.awayScore,
          }
        : null,
      longestUnbeatenRun: mapAggregateInsight(longestUnbeatenRun, longestUnbeatenRun?.longestUnbeatenStreak),
      longestWinningRun: mapAggregateInsight(longestWinningRun, longestWinningRun?.longestWinningStreak),
      worstAwayTeam: mapAggregateInsight(worstAwayTeam, worstAwayTeam?.awayPoints),
    };
  }, [matchesQuery.data?.items, standingsQuery.data?.rows]);

  return {
    ...insights,
    matchesQuery,
    standingsQuery,
  };
}

// ─── Shared visual atoms ──────────────────────────────────────────────────────────────

function TeamBadge({
  size = 28,
  teamId,
  teamName,
}: {
  size?: number;
  teamId?: string | null;
  teamName: string;
}) {
  const src = teamId ? `/api/visual-assets/clubs/${encodeURIComponent(teamId)}` : null;
  const initials = teamName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-[rgba(191,201,195,0.4)] bg-[#f0f3ff]"
      style={{ width: size, height: size }}
    >
      <span className="text-[0.55rem] font-bold text-[#003526]">{initials}</span>
      {src ? (
        <img
          alt={teamName}
          className="absolute inset-0 h-full w-full object-contain bg-[#f0f3ff]"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          src={src}
        />
      ) : null}
    </span>
  );
}

function PlayerPhoto({
  playerId,
  playerName,
  size = 72,
}: {
  playerId?: string | null;
  playerName: string;
  size?: number;
}) {
  const baseSrc = playerId ? `/api/visual-assets/players/${encodeURIComponent(playerId)}` : null;
  const [hasError, setHasError] = useState(false);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const src = useMemo(() => {
    if (!baseSrc) {
      return null;
    }

    return retryAttempt > 0 ? `${baseSrc}${baseSrc.includes("?") ? "&" : "?"}retry=${retryAttempt}` : baseSrc;
  }, [baseSrc, retryAttempt]);
  const initials = playerName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  useEffect(() => {
    setHasError(false);
    setRetryAttempt(0);
  }, [baseSrc]);

  const handleError = () => {
    if (!baseSrc) {
      setHasError(true);
      return;
    }

    if (retryAttempt === 0) {
      setRetryAttempt(1);
      return;
    }

    setHasError(true);
  };

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-emerald-400/30 bg-[#003526]"
      style={{ width: size, height: size }}
    >
      <span className="text-sm font-bold text-white/70">{initials}</span>
      {src && !hasError ? (
        <img
          alt={playerName}
          className="absolute inset-0 h-full w-full object-cover object-[center_20%] bg-[#003526]"
          key={src}
          onError={handleError}
          src={src}
        />
      ) : null}
    </span>
  );
}

// ─── Tabela de classificacao visual (mockup-fiel) ────────────────────────────

function resolveZoneBorderColor(
  position: number,
  totalRows: number,
): string {
  if (totalRows <= 2) return "border-l-transparent";
  const topZone = Math.max(1, Math.ceil(totalRows * 0.25));
  const bottomZone = Math.max(1, Math.ceil(totalRows * 0.2));
  if (position <= topZone) return "border-l-[#003526]";
  if (position > totalRows - bottomZone) return "border-l-[#ba1a1a]";
  return "border-l-transparent";
}

function LeagueStandingsTable({
  context,
  rows,
}: {
  context: CompetitionSeasonContext;
  rows: StandingsTableRow[];
}) {
  const total = rows.length;

  return (
    <div className="overflow-hidden overflow-x-auto rounded-xl bg-white shadow-sm">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="bg-[#f0f3ff]">
            <th className="w-12 py-3.5 px-4 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]">Pos</th>
            <th className="min-w-[180px] py-3.5 px-4 text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]">Clube</th>
            <th className="py-3.5 px-3 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Partidas jogadas">PJ</th>
            <th className="py-3.5 px-3 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Vitórias">V</th>
            <th className="py-3.5 px-3 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Empates">E</th>
            <th className="py-3.5 px-3 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Derrotas">D</th>
            <th className="py-3.5 px-4 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Saldo de gols">SG</th>
            <th className="py-3.5 px-4 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Pontos">Pts</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[rgba(191,201,195,0.18)]">
          {rows.map((row) => {
            const borderColor = resolveZoneBorderColor(row.position, total);
            const sgPositive = row.goalDiff > 0;
            const sgNegative = row.goalDiff < 0;
            return (
              <tr
                className="align-middle transition-colors hover:bg-[#f0f3ff]"
                key={row.teamId ?? row.teamName}
              >
                <td className={`border-l-4 py-3.5 px-4 text-center text-sm font-bold tabular-nums ${borderColor}`}>
                  {row.position}
                </td>
                <td className="py-3.5 px-4">
                  <Link
                    className="flex items-center gap-3 font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
                    href={buildCanonicalTeamPath(context, row.teamId)}
                  >
                    <TeamBadge size={24} teamId={row.teamId} teamName={row.teamName ?? row.teamId ?? ""} />
                    <span>{row.teamName ?? row.teamId}</span>
                  </Link>
                </td>
                <td className="py-3.5 px-3 text-center text-sm font-bold tabular-nums text-[#111c2d]">{row.matchesPlayed}</td>
                <td className="py-3.5 px-3 text-center text-sm tabular-nums text-[#515f74]">{row.wins}</td>
                <td className="py-3.5 px-3 text-center text-sm tabular-nums text-[#515f74]">{row.draws}</td>
                <td className="py-3.5 px-3 text-center text-sm tabular-nums text-[#515f74]">{row.losses}</td>
                <td
                  className={`py-3.5 px-4 text-center text-sm font-bold tabular-nums ${
                    sgPositive ? "text-[#1b6b51]" : sgNegative ? "text-[#ba1a1a]" : "text-[#515f74]"
                  }`}
                >
                  {row.goalDiff > 0 ? `+${row.goalDiff}` : row.goalDiff}
                </td>
                <td className="py-3.5 px-4 text-center text-sm font-extrabold tabular-nums text-[#003526]">
                  {row.points}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FinalStandingsPanel({
  context,
  description,
  query,
  rowsLimit,
  showHeader = true,
  title,
}: {
  context: CompetitionSeasonContext;
  description?: string;
  query: ReturnType<typeof useSeasonFinalStandings> | ReturnType<typeof useStandingsTable>;
  rowsLimit?: number;
  showHeader?: boolean;
  title: string;
}) {
  const rows = rowsLimit ? query.data?.rows.slice(0, rowsLimit) ?? [] : query.data?.rows ?? [];

  return (
    <div className="space-y-4">
      {showHeader || query.coverage.status !== "complete" ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {showHeader ? (
            <div>
              <p className="text-[0.7rem] font-bold uppercase tracking-widest text-[#515f74]">{title}</p>
              {description ? <p className="mt-1 max-w-2xl text-sm text-[#515f74]">{description}</p> : null}
            </div>
          ) : null}
          {query.coverage.status !== "complete" ? (
            <ProfileCoveragePill coverage={query.coverage} />
          ) : null}
        </div>
      ) : null}

      {query.isError && rows.length === 0 ? (
        <ProfileAlert title="Não foi possível carregar a classificação final" tone="critical">
          Tente novamente em instantes.
        </ProfileAlert>
      ) : null}

      {query.isPartial ? (
        <PartialDataBanner
          className="rounded-xl border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={query.coverage}
          message="Cobertura parcial: a classificação pode estar incompleta."
        />
      ) : null}

      {query.isLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={72} />
          <LoadingSkeleton height={220} />
        </div>
      ) : null}

      {!query.isLoading && rows.length === 0 ? (
        <EmptyState
          className="rounded-xl border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Classificação indisponível."
          title="Sem classificação"
        />
      ) : null}

      {!query.isLoading && rows.length > 0 ? (
        <LeagueStandingsTable context={context} rows={rows} />
      ) : null}
    </div>
  );
}

function ClosingMatchesPanel({
  context,
  description,
  title,
}: {
  context: CompetitionSeasonContext;
  description: string;
  title: string;
}) {
  const matchesQuery = useSeasonClosingMatches(context);
  const matches = matchesQuery.data?.items ?? [];

  return (
    <ProfilePanel className="space-y-4">
      <SeasonSectionHeader
        coverage={matchesQuery.coverage}
        description={description}
        eyebrow="Partidas concluídas"
        title={title}
      />

      {matchesQuery.isError && matches.length === 0 ? (
        <ProfileAlert title="Não foi possível carregar as partidas marcantes" tone="critical">
          Tente novamente em instantes.
        </ProfileAlert>
      ) : null}

      {matchesQuery.isPartial ? (
        <PartialDataBanner
          className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={matchesQuery.coverage}
          message="Dados parciais."
        />
      ) : null}

      {matchesQuery.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, index) => (
            <LoadingSkeleton height={88} key={`closing-match-loading-${index}`} />
          ))}
        </div>
      ) : null}

      {!matchesQuery.isLoading && matches.length === 0 ? (
        <EmptyState
          className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Nenhuma partida encontrada."
          title="Sem partidas"
        />
      ) : null}

      {!matchesQuery.isLoading && matches.length > 0 ? (
        <div className="grid gap-3">
          {matches.map((match) => (
            <Link
              className="rounded-[1.3rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4 transition-colors hover:border-[#8bd6b6] hover:bg-white"
              href={`/matches/${encodeURIComponent(match.matchId)}?competitionId=${encodeURIComponent(context.competitionId)}&seasonId=${encodeURIComponent(context.seasonId)}`}
              key={match.matchId}
            >
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                    {resolveMatchDisplayContext(match).summary}
                  </p>
                  <p className="mt-2 font-semibold text-[#111c2d]">
                    {match.homeTeamName ?? "Mandante"} x {match.awayTeamName ?? "Visitante"}
                  </p>
                  <p className="mt-1 text-sm text-[#57657a]">{formatKickoff(match.kickoffAt)}</p>
                </div>
                <div className="text-right">
                  <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {typeof match.homeScore === "number" && typeof match.awayScore === "number"
                      ? `${match.homeScore} - ${match.awayScore}`
                      : "x"}
                  </p>
                  <p className="mt-1 text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                    {match.status ?? "Sem status"}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </ProfilePanel>
  );
}

function KnockoutBracketPanel({
  context,
  description,
  resolution,
  title,
  variant = "stacked",
}: {
  context: CompetitionSeasonContext;
  description?: string;
  resolution: CompetitionSeasonSurfaceResolution;
  title: string;
  variant?: "snapshot" | "stacked";
}) {
  const allStages = useKnockoutStageQueries(context, resolution);
  const stages = useMemo(() => resolvePrimaryKnockoutStages(allStages), [allStages]);

  const hasPartialCoverage = stages.some((stage) => stage.coverage.status === "partial");
  const snapshotState = useMemo(() => {
    const primaryStages = stages.filter((stage) => stage.stage.stageFormat === "knockout");

    return {
      finalStage: primaryStages.at(-1) ?? null,
      primaryStages,
      snapshotColumns: resolveSnapshotColumns(primaryStages),
      supportingStages: stages.filter((stage) => stage.stage.stageFormat !== "knockout"),
    };
  }, [stages]);

  const renderStageCards = (stage: KnockoutStageQueryState) => {
    if (stage.isError) {
      return (
        <ProfileAlert title="Falha ao carregar esta fase" tone="warning">
          Os confrontos desta etapa não puderam ser carregados agora.
        </ProfileAlert>
      );
    }

    if (stage.isLoading) {
      return (
        <div className="space-y-3">
          {Array.from({ length: 2 }, (_, index) => (
            <LoadingSkeleton height={110} key={`${stage.stage.stageId}-loading-${index}`} />
          ))}
        </div>
      );
    }

    if (stage.ties.length === 0) {
      return (
        <EmptyState
          className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
          description="Sem confrontos."
          title="Sem confrontos"
        />
      );
    }

    return (
      <div className="grid gap-3">
        {stage.ties.map((tie) => {
          const resolutionLabel = formatTieResolutionLabel(tie);
          const windowLabel = formatDateWindow(tie.firstLegAt, tie.lastLegAt);

          return (
            <div
              className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4"
              key={tie.tieId}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <ProfileTag>Confronto {tie.tieOrder}</ProfileTag>
                {resolutionLabel ? <ProfileTag>{resolutionLabel}</ProfileTag> : null}
              </div>
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-[#111c2d]">
                    {tie.homeTeamName ?? tie.homeTeamId ?? "Mandante"}
                  </span>
                  <span className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    {tie.homeGoals}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-[#111c2d]">
                    {tie.awayTeamName ?? tie.awayTeamId ?? "Visitante"}
                  </span>
                  <span className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    {tie.awayGoals}
                  </span>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-[#57657a]">
                <span>{formatTieMatchCountLabel(tie.matchCount)}</span>
                {tie.winnerTeamName ? <span>• classificado: {tie.winnerTeamName}</span> : null}
                {windowLabel ? <span>• {windowLabel}</span> : null}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderSnapshotTieCard = (tie: StageTie, side: BracketSide) => (
    <div
      className="rounded-[1.02rem] border border-[rgba(191,201,195,0.5)] bg-white px-3 py-3 shadow-[0_14px_34px_-28px_rgba(17,28,45,0.2)]"
      data-bracket-side={side}
      data-tie-id={tie.tieId}
      key={`${side}-${tie.tieId}`}
    >
      <div className="flex min-h-[0.85rem] items-center justify-center text-center text-[0.58rem] font-semibold uppercase tracking-[0.18em] text-[#6a7890]">
        {formatTieResolutionLabel(tie) ? <span>{formatTieResolutionLabel(tie)}</span> : null}
      </div>
      <div className="mt-2.5 space-y-2">
        {[
          {
            goals: tie.homeGoals,
            isWinner:
              tie.winnerTeamId === tie.homeTeamId ||
              (!!tie.winnerTeamName && tie.winnerTeamName === tie.homeTeamName),
            teamId: tie.homeTeamId,
            teamName: tie.homeTeamName ?? tie.homeTeamId ?? "Mandante",
          },
          {
            goals: tie.awayGoals,
            isWinner:
              tie.winnerTeamId === tie.awayTeamId ||
              (!!tie.winnerTeamName && tie.winnerTeamName === tie.awayTeamName),
            teamId: tie.awayTeamId,
            teamName: tie.awayTeamName ?? tie.awayTeamId ?? "Visitante",
          },
        ].map((team) => (
          <div className="grid grid-cols-[minmax(0,1fr)_1.75rem] items-center gap-2" key={`${tie.tieId}-${team.teamId ?? team.teamName}`}>
            <div className="flex min-w-0 items-center gap-2">
              <TeamBadge size={24} teamId={team.teamId} teamName={team.teamName} />
              <span className={team.isWinner ? "block min-w-0 text-[0.97rem] font-extrabold leading-[1.08rem] text-[#003526]" : "block min-w-0 text-[0.97rem] font-semibold leading-[1.08rem] text-[#111c2d]"}>
                {team.teamName}
              </span>
            </div>
            <span className="w-7 text-right font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-none text-[#111c2d]">
              {team.goals}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  const renderSnapshotStageColumn = (
    column: BracketSnapshotColumn,
    side: BracketSide,
  ) => {
    const ties = side === "left" ? column.leftTies : column.rightTies;
    const headingClass = "px-1 text-center text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]";

    return (
      <div
        className="flex h-full min-w-0 flex-col justify-center gap-2.5"
        data-bracket-column={`${column.stageState.stage.stageId}-${side}`}
        key={`${side}-${column.stageState.stage.stageId}`}
      >
        <p className={headingClass}>
          {localizeSeasonStageName(column.stageState.stage.stageName ?? column.stageState.stage.stageId)}
        </p>
        {column.stageState.isError ? (
          <ProfileAlert title="Fase indisponível" tone="warning">
            Não foi possível montar esta coluna.
          </ProfileAlert>
        ) : null}
        {column.stageState.isLoading ? (
          <div className="space-y-2.5">
            {Array.from({ length: 2 }, (_, index) => (
              <LoadingSkeleton height={96} key={`${side}-${column.stageState.stage.stageId}-${index}`} />
            ))}
          </div>
        ) : null}
        {!column.stageState.isLoading && !column.stageState.isError && ties.length === 0 ? (
          <EmptyState
            className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
            description="Sem confrontos deste lado."
            title="Sem confrontos"
          />
        ) : null}
        {!column.stageState.isLoading && !column.stageState.isError
          ? (
            <div className="space-y-2.5">
              {ties.map((tie) => renderSnapshotTieCard(tie, side))}
            </div>
          )
          : null}
      </div>
    );
  };

  if (variant === "snapshot") {
    return (
      <ProfilePanel className="space-y-5">
        <SeasonSectionHeader
          align="center"
          description={description}
          eyebrow="Chaveamento"
          title={title}
        />

        {hasPartialCoverage ? (
          <PartialDataBanner
            className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
            coverage={{ status: "partial", label: "Cobertura parcial do chaveamento" }}
            message="Chaveamento com dados parciais."
          />
        ) : null}

        {snapshotState.primaryStages.length === 0 ? (
          <EmptyState
            className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
            description="Não há fases eliminatórias suficientes para montar o chaveamento."
            title="Sem chaveamento"
          />
        ) : (
          <div className="overflow-x-auto pb-1">
            <div
              className="grid items-center gap-2.5 xl:gap-3"
              style={{
                gridTemplateColumns: `repeat(${Math.max(snapshotState.snapshotColumns.length, 1)}, minmax(168px, 1.12fr)) minmax(244px, 1.02fr) repeat(${Math.max(snapshotState.snapshotColumns.length, 1)}, minmax(168px, 1.12fr))`,
              }}
            >
              {snapshotState.snapshotColumns.length > 0
                ? snapshotState.snapshotColumns.map((column) => renderSnapshotStageColumn(column, "left"))
                : (
                  <div className="space-y-3">
                    <p className="px-1 text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                      Eliminatoria
                    </p>
                  </div>
                )}

              <div className="flex h-full flex-col justify-center">
                <div className="mx-auto w-full max-w-[280px] rounded-[1.45rem] border border-[rgba(8,48,35,0.32)] bg-[radial-gradient(circle_at_top,rgba(32,108,79,0.24),transparent_48%),linear-gradient(180deg,#042d21_0%,#06533c_54%,#073d2d_100%)] px-4 py-5 text-white shadow-[0_28px_72px_-44px_rgba(0,53,38,0.62)]">
                  <p className="text-center text-[0.66rem] font-semibold uppercase tracking-[0.2em] text-[#bfe6d6]">
                    {localizeSeasonStageName(snapshotState.finalStage?.stage.stageName)}
                  </p>

                  {snapshotState.finalStage?.isLoading ? <LoadingSkeleton height={180} /> : null}

                  {snapshotState.finalStage?.isError ? (
                    <ProfileAlert title="Final indisponível" tone="warning">
                      Não foi possível carregar o confronto decisivo.
                    </ProfileAlert>
                  ) : null}

                  {!snapshotState.finalStage?.isLoading && !snapshotState.finalStage?.isError && (snapshotState.finalStage?.ties.length ?? 0) === 0 ? (
                    <EmptyState
                      className="mt-4 rounded-[1.2rem] border-white/10 bg-white/8 text-white"
                      description="Sem confronto consolidado para a decisão."
                      title="Final indisponível"
                    />
                  ) : null}

                  {!snapshotState.finalStage?.isLoading && !snapshotState.finalStage?.isError && (snapshotState.finalStage?.ties.length ?? 0) > 0 ? (
                    (() => {
                      const tie = snapshotState.finalStage?.ties[0];
                      const championName = tie?.winnerTeamName ?? "Campeão";
                      const dateLabel = tie ? formatDateWindow(tie.firstLegAt, tie.lastLegAt) : null;

                      return tie ? (
                        <div className="mt-4 space-y-4">
                          {dateLabel ? (
                            <p className="text-center text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                              {dateLabel}
                            </p>
                          ) : null}

                          <div className="grid gap-2.5">
                            {[
                              {
                                goals: tie.homeGoals,
                                isWinner:
                                  tie.winnerTeamId === tie.homeTeamId ||
                                  (!!tie.winnerTeamName && tie.winnerTeamName === tie.homeTeamName),
                                teamId: tie.homeTeamId,
                                teamName: tie.homeTeamName ?? tie.homeTeamId ?? "Mandante",
                              },
                              {
                                goals: tie.awayGoals,
                                isWinner:
                                  tie.winnerTeamId === tie.awayTeamId ||
                                  (!!tie.winnerTeamName && tie.winnerTeamName === tie.awayTeamName),
                                teamId: tie.awayTeamId,
                                teamName: tie.awayTeamName ?? tie.awayTeamId ?? "Visitante",
                              },
                            ].map((team) => (
                              <div
                                className={team.isWinner ? "rounded-[1rem] border border-[rgba(166,242,209,0.24)] bg-[rgba(255,255,255,0.08)] px-3 py-3" : "rounded-[1rem] border border-white/10 bg-[rgba(255,255,255,0.04)] px-3 py-3"}
                                key={`final-${team.teamId ?? team.teamName}`}
                              >
                                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
                                  <div className="flex min-w-0 items-center gap-2">
                                    <TeamBadge size={32} teamId={team.teamId} teamName={team.teamName} />
                                    <span
                                      className={
                                        team.isWinner
                                          ? "min-w-0 flex-1 break-words text-[0.95rem] font-extrabold leading-tight text-white"
                                          : "min-w-0 flex-1 break-words text-[0.95rem] font-semibold leading-tight text-white/88"
                                      }
                                    >
                                      {team.teamName}
                                    </span>
                                  </div>
                                  <span className="flex min-w-[2rem] justify-end text-right font-[family:var(--font-profile-headline)] text-[1.8rem] font-extrabold leading-none text-white">
                                    {team.goals}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="rounded-[1rem] border border-[rgba(166,242,209,0.16)] bg-[rgba(255,255,255,0.06)] px-3 py-3">
                            <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                              Campeão
                            </p>
                            <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.52rem] font-extrabold text-white">
                              {championName}
                            </p>
                            <p className="mt-1.5 text-[0.8rem] text-[#d7efe4]">
                              {formatTieResolutionLabel(tie) ?? "Decisão da edição"} • {formatTieMatchCountLabel(tie.matchCount)}
                            </p>
                          </div>
                        </div>
                      ) : null;
                    })()
                  ) : null}
                </div>
              </div>

              {snapshotState.snapshotColumns.length > 0
                ? [...snapshotState.snapshotColumns].reverse().map((column) => renderSnapshotStageColumn(column, "right"))
                : (
                  <div className="space-y-3">
                    <p className="px-1 text-right text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                      Eliminatoria
                    </p>
                  </div>
                )}
            </div>
          </div>
        )}

        {snapshotState.supportingStages.length > 0 ? (
          <div className="space-y-3 rounded-[1.3rem] border border-[rgba(216,227,251,0.72)] bg-[rgba(240,243,255,0.74)] px-4 py-4">
            <div>
              <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Fases complementares</p>
              <p className="mt-1 text-sm text-[#57657a]">
                Etapas preliminares ou de colocação aparecem fora do chaveamento principal.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {snapshotState.supportingStages.map((stage) => (
                <div
                  className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-white px-4 py-4"
                  key={`supporting-${stage.stage.stageId}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <ProfileTag>{localizeSeasonStageName(stage.stage.stageName ?? stage.stage.stageId)}</ProfileTag>
                    {stage.stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stage.stage.stageFormat)}</ProfileTag> : null}
                  </div>
                  <p className="mt-3 text-sm text-[#57657a]">
                    {stage.ties.length > 0
                      ? `${stage.ties.length} confrontos registrados nesta etapa.`
                      : "Sem confrontos consolidados nesta etapa."}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </ProfilePanel>
    );
  }

  return (
    <ProfilePanel className="space-y-4">
      <SeasonSectionHeader
        description={description}
        eyebrow="Chaveamento"
        title={title}
      />

      {hasPartialCoverage ? (
        <PartialDataBanner
          className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={{ status: "partial", label: "Cobertura parcial do chaveamento" }}
          message="Chaveamento com dados parciais."
        />
      ) : null}

      {stages.length === 0 ? (
        <EmptyState
          className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Não há fases eliminatórias suficientes para montar o chaveamento."
          title="Sem chaveamento"
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-4">
          {stages.map((stageState) => (
            <ProfilePanel className="space-y-4" key={stageState.stage.stageId} tone={stageState.stage.isCurrent ? "soft" : "base"}>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{localizeSeasonStageName(stageState.stage.stageName ?? stageState.stage.stageId)}</ProfileTag>
                  {stageState.stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stageState.stage.stageFormat)}</ProfileTag> : null}
                </div>
              </div>
              {renderStageCards(stageState)}
            </ProfilePanel>
          ))}
        </div>
      )}
    </ProfilePanel>
  );
}

function GroupPhaseSummaryPanel({
  context,
  stage,
}: {
  context: CompetitionSeasonContext;
  stage: CompetitionStructureStage | null;
}) {
  const columns = useStandingsColumns(context);
  const groupQueries = useGroupStandingsQueries(context, stage);
  const finalStandingsQuery = useSeasonFinalStandings(context, stage?.stageId);
  const groupQueriesSettled =
    groupQueries.length > 0 && groupQueries.every((groupQuery) => !groupQuery.isLoading);
  const hasGroupRows = groupQueries.some((groupQuery) => (groupQuery.data?.rows.length ?? 0) > 0);

  if (!stage) {
    return (
      <ProfileAlert title="Fase classificatória indisponível" tone="warning">
        A estrutura atual não identificou uma fase de tabela para esta edição.
      </ProfileAlert>
    );
  }

  if (groupQueries.length === 0 || (groupQueriesSettled && !hasGroupRows)) {
    return (
      <FinalStandingsPanel
        context={context}
        description="A fase classificatória desta edição foi encerrada e a tabela final segue como referência central."
        query={finalStandingsQuery}
        title={localizeSeasonStageName(stage.stageName ?? "Fase classificatória")}
      />
    );
  }

  return (
    <ProfilePanel className="space-y-5">
      <SeasonSectionHeader
        eyebrow="Fase classificatória"
        title={localizeSeasonStageName(stage.stageName ?? "Fase classificatória")}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {groupQueries.map((groupQuery) => (
          <ProfilePanel className="space-y-4" key={groupQuery.group.groupId} tone="soft">
            <SeasonSectionHeader
              coverage={groupQuery.coverage}
              eyebrow="Grupo"
              title={groupQuery.group.groupName ?? groupQuery.group.groupId}
            />

            {groupQuery.isError ? (
              <ProfileAlert title="Não foi possível carregar este grupo" tone="warning">
                Tente novamente em instantes.
              </ProfileAlert>
            ) : null}

            {groupQuery.isLoading ? <LoadingSkeleton height={220} /> : null}

            {!groupQuery.isLoading && !groupQuery.isError && (groupQuery.data?.rows.length ?? 0) === 0 ? (
              <EmptyState
                className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                description="Ainda não há linhas suficientes para este grupo."
                title="Sem classificação"
              />
            ) : null}

            {!groupQuery.isLoading && (groupQuery.data?.rows.length ?? 0) > 0 ? (
              <DataTable
                columns={columns}
                data={groupQuery.data?.rows ?? []}
                emptyDescription="Sem linhas para exibir."
                emptyTitle="Sem classificação"
                variant="profile"
              />
            ) : null}
          </ProfilePanel>
        ))}
      </div>
    </ProfilePanel>
  );
}

function RankingPreviewPanel({
  context,
  href,
  rankingDefinition,
}: {
  context: CompetitionSeasonContext;
  href: string;
  rankingDefinition: RankingDefinition;
}) {
  const rankingQuery = useRankingTable(rankingDefinition, {
    localFilters: {
      pageSize: 5,
      sortDirection: rankingDefinition.defaultSort as RankingSortDirection,
    },
  });
  const topRows = rankingQuery.data?.rows.slice(0, 5) ?? [];

  return (
    <ProfilePanel className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Destaque</p>
          <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            {rankingDefinition.label}
          </h3>
          <p className="mt-2 max-w-2xl text-sm/6 text-[#57657a]">{rankingDefinition.description}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {rankingQuery.coverage.status !== "complete" ? <ProfileCoveragePill coverage={rankingQuery.coverage} /> : null}
          <Link
            className="text-xs font-semibold uppercase tracking-[0.16em] text-[#003526] transition-colors hover:text-[#00513b]"
            href={href}
          >
            Ver ranking completo
          </Link>
        </div>
      </div>

      {rankingQuery.isError && topRows.length === 0 ? (
        <ProfileAlert title="Não foi possível carregar este ranking" tone="critical">
          Tente novamente em instantes ou siga para outro destaque da edição.
        </ProfileAlert>
      ) : null}

      {rankingQuery.isPartial ? (
        <PartialDataBanner
          className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={rankingQuery.coverage}
          message="Este ranking ainda cobre apenas parte da edição."
        />
      ) : null}

      {rankingQuery.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, index) => (
            <LoadingSkeleton height={68} key={`${rankingDefinition.id}-loading-${index}`} />
          ))}
        </div>
      ) : null}

      {!rankingQuery.isLoading && topRows.length === 0 ? (
        <EmptyState
          className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Ainda não há linhas suficientes para esta edição."
          title="Sem destaques"
        />
      ) : null}

      {!rankingQuery.isLoading && topRows.length > 0 ? (
        <div className="grid gap-3">
          {topRows.map((row) => {
            const metricValue =
              typeof row.metricValue === "number" && Number.isFinite(row.metricValue)
                ? row.metricValue
                : null;
            const entityHref =
              rankingDefinition.entity === "player"
                ? buildCanonicalPlayerPath(context, row.entityId)
                : rankingDefinition.entity === "team"
                  ? buildCanonicalTeamPath(context, row.entityId)
                  : null;

            const content = (
              <div className="flex items-center justify-between gap-4 rounded-[1.25rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4 transition-colors hover:bg-white">
                <div className="min-w-0">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                    #{row.rank ?? "-"}
                  </p>
                  <p className="mt-2 truncate font-semibold text-[#111c2d]">
                    {row.entityName ?? row.entityId}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[#57657a]">
                    {row.teamName ?? row.position ?? rankingDefinition.entity}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {formatMetricValue(rankingDefinition.metricKey, metricValue)}
                  </p>
                  <p className="mt-1 text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                    {rankingDefinition.label}
                  </p>
                </div>
              </div>
            );

            if (!entityHref) {
              return <div key={row.entityId}>{content}</div>;
            }

            return (
              <Link href={entityHref} key={row.entityId}>
                {content}
              </Link>
            );
          })}
        </div>
      ) : null}
    </ProfilePanel>
  );
}

function EditionHighlightsSection({
  context,
  structure,
}: {
  context: CompetitionSeasonContext;
  structure: CompetitionStructureData | null;
}) {
  const filterInput = useSeasonFilterInput(context);
  const playerGoalsDefinition = getRankingDefinition("player-goals");
  const teamPossessionDefinition = getRankingDefinition("team-possession");

  return (
    <div className="space-y-5">
      {!playerGoalsDefinition || !teamPossessionDefinition ? (
        <ProfileAlert title="Rankings indisponiveis" tone="critical">
          Os destaques principais desta edição não puderam ser carregados agora.
        </ProfileAlert>
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          <RankingPreviewPanel
            context={context}
            href={buildRankingPath(playerGoalsDefinition.id, filterInput)}
            rankingDefinition={playerGoalsDefinition}
          />
          <RankingPreviewPanel
            context={context}
            href={buildRankingPath(teamPossessionDefinition.id, filterInput)}
            rankingDefinition={teamPossessionDefinition}
          />
        </div>
      )}

      {structure ? (
        <SeasonCompetitionAnalyticsSection context={context} structure={structure} />
      ) : (
        <ProfileAlert title="Estrutura indisponível para análises avançadas" tone="warning">
          Sem a estrutura tipada da edição, o produto não consegue abrir comparativos estruturais desta temporada.
        </ProfileAlert>
      )}
    </div>
  );
}

function LeagueOverviewSection({ context }: { context: CompetitionSeasonContext }) {
  const finalStandingsQuery = useSeasonFinalStandings(context);

  return (
    <div className="space-y-5">
      <FinalStandingsPanel
        context={context}
        query={finalStandingsQuery}
        showHeader={false}
        title="Classificação final"
      />
    </div>
  );
}

function LeagueEditionSummaryStrip({
  context,
}: {
  context: CompetitionSeasonContext;
}) {
  const standingsQuery = useSeasonFinalStandings(context);
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const champion = resolveChampionFromStandings(standingsQuery.data?.rows ?? []);
  const championLeadRounds = useSeasonChampionLeadRounds(
    context,
    champion?.teamId,
    standingsQuery.data?.rounds ?? [],
  );
  const totalGoals = resolveLeagueGoalsFromStandings(standingsQuery.data?.rows ?? []);
  const averageGoals = analyticsQuery.data?.seasonSummary.averageGoals;

  const facts: Array<{ label: string; value: string; valueClassName?: string }> = [
    {
      label: "Campeão",
      value: standingsQuery.isLoading
        ? "..."
        : (champion?.teamName ?? "Não identificado"),
      valueClassName: "text-[1.45rem] leading-[1.02] tracking-[-0.04em]",
    },
    {
      label: "Gols na edição",
      value: standingsQuery.isLoading ? "..." : formatMetricValue("goals", totalGoals),
    },
    {
      label: "Media de gols/jogo",
      value: analyticsQuery.isLoading ? "..." : formatAverageGoals(averageGoals),
    },
    {
      label: "Liderança do campeão",
      value:
        standingsQuery.isLoading || championLeadRounds.isLoading
          ? "..."
          : (championLeadRounds.isError
              ? "-"
              : formatRoundCount(championLeadRounds.count)),
    },
  ];

  return (
    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="shrink-0">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
          Resumo da edição
        </p>
        <p className="mt-1 text-sm font-semibold text-[#111c2d]">
          Liga encerrada · {context.seasonLabel}
        </p>
      </div>

      <div className="grid flex-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {facts.map((fact, index) => (
          <div
            className={index > 0 ? "xl:border-l xl:border-[rgba(191,201,195,0.48)] xl:pl-4" : undefined}
            key={fact.label}
          >
            <p className="text-[0.66rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              {fact.label}
            </p>
            <p
              className={`mt-1.5 font-[family:var(--font-profile-headline)] text-[1.18rem] font-extrabold tracking-[-0.03em] text-[#111c2d] ${fact.valueClassName ?? ""}`}
            >
              {fact.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function resolveRailCoverage(coverages: CoverageLike[], label: string): CoverageLike {
  if (coverages.some((coverage) => coverage.status === "partial")) {
    return { label, status: "partial" };
  }

  if (coverages.some((coverage) => coverage.status === "unknown")) {
    return { label, status: "unknown" };
  }

  if (coverages.some((coverage) => coverage.status === "empty")) {
    return { label, status: "empty" };
  }

  return { label, status: "complete" };
}

function CompactSuperlativeTile({
  href,
  label,
  primary,
  secondary,
  unit,
  value,
}: {
  href?: string | null;
  label: string;
  primary: string;
  secondary?: string | null;
  unit?: string | null;
  value: string;
}) {
  const content = (
    <div className="rounded-[1.2rem] border border-[rgba(191,201,195,0.52)] bg-[rgba(255,255,255,0.88)] px-3.5 py-3 shadow-[0_16px_34px_-34px_rgba(17,28,45,0.22)] transition-[transform,border-color,background-color] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:border-[#8bd6b6] hover:bg-white">
      <p className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
        {label}
      </p>
      <div className="mt-2 flex items-end gap-2">
        <p className="font-[family:var(--font-profile-headline)] text-[1.7rem] font-extrabold leading-none tracking-[-0.04em] text-[#003526]">
          {value}
        </p>
        {unit ? (
          <p className="pb-0.5 text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
            {unit}
          </p>
        ) : null}
      </div>
      <p className="mt-2 text-sm font-semibold leading-5 text-[#111c2d]">{primary}</p>
      {secondary ? <p className="mt-1 text-[0.72rem] leading-5 text-[#57657a]">{secondary}</p> : null}
    </div>
  );

  if (href) {
    return (
      <Link
        className="block transition-[transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5 active:scale-[0.99]"
        href={href}
      >
        {content}
      </Link>
    );
  }

  return <div>{content}</div>;
}

function CupOverviewStatCard({
  detail,
  label,
  value,
}: {
  detail: string;
  label: string;
  value: ReactNode;
}) {
  return (
    <article className="relative overflow-hidden rounded-[1.4rem] border border-[rgba(191,201,195,0.52)] bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(240,243,255,0.88)_100%)] p-4 shadow-[0_20px_42px_-34px_rgba(17,28,45,0.28)] md:p-5">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(166,242,209,0.18),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(216,227,251,0.42),transparent_36%)]" />
      <div className="relative space-y-4">
        <span className="inline-flex rounded-full border border-[rgba(191,201,195,0.44)] bg-white/76 px-2.5 py-1 text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#5f7087]">
          {label}
        </span>
        <div>
          <p className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
            {value}
          </p>
          <p className="mt-2 text-[0.8rem]/6 text-[#57657a]">{detail}</p>
        </div>
      </div>
    </article>
  );
}

function CompactTravelRow({
  href,
  label,
  primary,
  value,
}: {
  href?: string | null;
  label: string;
  primary: string;
  value: string;
}) {
  const content = (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-3">
      <div className="min-w-0">
        <p className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
          {label}
        </p>
        <p className="mt-1 text-sm font-semibold leading-5 text-[#111c2d]">{primary}</p>
      </div>
      <p className="text-right font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-[#003526]">
        {value}
      </p>
    </div>
  );

  if (href) {
    return (
      <Link
        className="block transition-[transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5 active:scale-[0.99]"
        href={href}
      >
        {content}
      </Link>
    );
  }

  return <div>{content}</div>;
}

function TopScorerSupportMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[1.15rem] border border-white/10 bg-white/8 px-3.5 py-3 backdrop-blur-sm">
      <p className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-white/62">{label}</p>
      <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.18rem] font-extrabold tracking-[-0.03em] text-white">
        {value}
      </p>
    </div>
  );
}

function TopScorerRailCard({ context }: { context: CompetitionSeasonContext }) {
  const scorerQuery = useEditionTopScorer(context);
  const scorer = scorerQuery.data?.scorer ?? null;
  const scorerHref = scorer ? buildCanonicalPlayerPath(context, scorer.entityId) : null;
  const goalCadence = resolveGoalCadenceMinutes(scorer?.goals, scorer?.minutesPlayed);

  return (
    <ProfilePanel className="relative overflow-hidden p-5 md:p-5" tone="accent">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,224,130,0.22),transparent_24%),radial-gradient(circle_at_bottom_left,rgba(166,242,209,0.18),transparent_34%)]" />
      <div className="relative space-y-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#bfe6d6]">
            Artilheiro
          </p>
          {scorerQuery.coverage.status !== "complete" ? <ProfileCoveragePill coverage={scorerQuery.coverage} /> : null}
        </div>

        {scorerQuery.isLoading ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="h-24 w-24 animate-pulse rounded-full bg-white/10" />
              <div className="flex-1 space-y-2">
                <div className="h-8 w-40 animate-pulse rounded bg-white/10" />
                <div className="h-5 w-28 animate-pulse rounded bg-white/10" />
              </div>
            </div>
            <div className="h-24 w-28 animate-pulse rounded bg-white/10" />
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="h-20 animate-pulse rounded-[1.15rem] bg-white/10" />
              <div className="h-20 animate-pulse rounded-[1.15rem] bg-white/10" />
            </div>
          </div>
        ) : scorer ? (
          <>
            <div className="flex items-start gap-4">
              <PlayerPhoto playerId={scorer.entityId} playerName={scorer.entityName} size={96} />

              <div className="min-w-0 flex-1 pt-1">
                {scorerHref ? (
                  <Link
                    className="block font-[family:var(--font-profile-headline)] text-[2.1rem] font-extrabold leading-[0.94] tracking-[-0.05em] text-white transition-opacity hover:opacity-80"
                    href={scorerHref}
                  >
                    {scorer.entityName}
                  </Link>
                ) : (
                  <p className="font-[family:var(--font-profile-headline)] text-[2.1rem] font-extrabold leading-[0.94] tracking-[-0.05em] text-white">
                    {scorer.entityName}
                  </p>
                )}

                {scorer.teamName ? (
                  <div className="mt-3 flex items-center gap-2 text-sm font-semibold text-[#d7efe4]">
                    <TeamBadge size={28} teamId={scorer.teamId} teamName={scorer.teamName} />
                    <span>{scorer.teamName}</span>
                  </div>
                ) : null}
              </div>
            </div>

            <div>
              <p className="text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-white/58">Gols</p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[5rem] font-extrabold leading-none tracking-[-0.08em] text-white">
                {formatHistoricalMatchCount(scorer.goals)}
              </p>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <TopScorerSupportMetric
                label="Jogos"
                value={formatHistoricalMatchCount(scorer.matchesPlayed)}
              />
              <TopScorerSupportMetric
                label="1 gol a cada"
                value={formatMinutesLabel(goalCadence)}
              />
            </div>
          </>
        ) : (
          <div className="rounded-[1.2rem] border border-white/10 bg-white/6 px-4 py-4 text-sm text-white/72">
            Artilharia indisponível no recorte atual.
          </div>
        )}
      </div>
    </ProfilePanel>
  );
}

function EditionSuperlativesRailCard({ context }: { context: CompetitionSeasonContext }) {
  const insights = useEditionRailInsights(context);
  const topRatedPlayersQuery = useEditionTopRatedPlayers(context);
  const assistProviderQuery = useEditionTopAssistProvider(context);
  const coverage = resolveRailCoverage(
    [
      insights.standingsQuery.coverage,
      insights.matchesQuery.coverage,
      topRatedPlayersQuery.coverage,
      assistProviderQuery.coverage,
    ],
    "Dados parciais dos superlativos",
  );

  const bestAttack = insights.bestAttack;
  const topRatedPlayers = topRatedPlayersQuery.data?.leaders ?? [];
  const topRatedPlayer = topRatedPlayers[0] ?? null;
  const topAssistProvider = assistProviderQuery.data?.leader ?? null;
  const highestScoringMatch = insights.highestScoringMatch;

  const items = [
    {
      href: bestAttack?.teamId ? buildCanonicalTeamPath(context, bestAttack.teamId) : null,
      label: "Melhor ataque",
      primary:
        bestAttack?.teamName ??
        (insights.standingsQuery.isLoading && insights.matchesQuery.isLoading ? "..." : "-"),
      secondary: null,
      value:
        bestAttack
          ? formatMetricValue("goals", bestAttack.metricValue)
          : (insights.standingsQuery.isLoading && insights.matchesQuery.isLoading ? "..." : "-"),
      unit: bestAttack ? "gols" : null,
    },
    {
      href: topRatedPlayer ? buildCanonicalPlayerPath(context, topRatedPlayer.entityId) : null,
      label: "Maior nota",
      primary: topRatedPlayer?.entityName ?? (topRatedPlayersQuery.isLoading ? "..." : "-"),
      secondary: topRatedPlayer?.teamName ?? null,
      value:
        topRatedPlayer
          ? formatMetricValue("player_rating", topRatedPlayer.metricValue)
          : (topRatedPlayersQuery.isLoading ? "..." : "-"),
      unit: null,
    },
    {
      href: topAssistProvider ? buildCanonicalPlayerPath(context, topAssistProvider.entityId) : null,
      label: "Maior assistente",
      primary: topAssistProvider?.entityName ?? (assistProviderQuery.isLoading ? "..." : "-"),
      secondary: topAssistProvider?.teamName ?? null,
      value:
        topAssistProvider
          ? formatHistoricalMatchCount(topAssistProvider.metricValue)
          : (assistProviderQuery.isLoading ? "..." : "-"),
      unit: topAssistProvider ? "assist." : null,
    },
    {
      href: highestScoringMatch
        ? `/matches/${encodeURIComponent(highestScoringMatch.matchId)}?competitionId=${encodeURIComponent(context.competitionId)}&seasonId=${encodeURIComponent(context.seasonId)}`
        : null,
      label: "Jogo com mais gols",
      primary:
        highestScoringMatch
          ? `${highestScoringMatch.homeTeamName} x ${highestScoringMatch.awayTeamName}`
          : (insights.matchesQuery.isLoading ? "..." : "-"),
      secondary:
        highestScoringMatch
          ? `${highestScoringMatch.homeScore} - ${highestScoringMatch.awayScore}`
          : null,
      value:
        highestScoringMatch
          ? formatMetricValue("goals", highestScoringMatch.metricValue)
          : (insights.matchesQuery.isLoading ? "..." : "-"),
      unit: highestScoringMatch ? "gols" : null,
    },
  ];

  return (
    <ProfilePanel className="space-y-3.5 p-4 md:p-5" tone="soft">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
          Superlativos
        </p>
        {coverage.status !== "complete" ? <ProfileCoveragePill coverage={coverage} /> : null}
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2">
        {items.map((item) => (
          <CompactSuperlativeTile
            href={item.href}
            key={item.label}
            label={item.label}
            primary={item.primary}
            secondary={item.secondary}
            unit={item.unit}
            value={item.value}
          />
        ))}
      </div>
    </ProfilePanel>
  );
}

function EditionTravelRailCard({ context }: { context: CompetitionSeasonContext }) {
  const insights = useEditionRailInsights(context);
  const coverage = resolveRailCoverage(
    [insights.standingsQuery.coverage, insights.matchesQuery.coverage],
    "Dados de mando e viagem",
  );

  const bestHomeTeam = insights.bestHomeTeam;
  const bestAwayTeam = insights.bestAwayTeam;
  const worstAwayTeam = insights.worstAwayTeam;
  const longestUnbeatenRun = insights.longestUnbeatenRun;
  const longestWinningRun = insights.longestWinningRun;

  const items = [
    {
      href: bestHomeTeam?.teamId ? buildCanonicalTeamPath(context, bestHomeTeam.teamId) : null,
      label: "Melhor mandante",
      primary: bestHomeTeam?.teamName ?? (insights.matchesQuery.isLoading ? "..." : "-"),
      value: bestHomeTeam ? formatPointCount(bestHomeTeam.metricValue) : (insights.matchesQuery.isLoading ? "..." : "-"),
    },
    {
      href: bestAwayTeam?.teamId ? buildCanonicalTeamPath(context, bestAwayTeam.teamId) : null,
      label: "Melhor visitante",
      primary: bestAwayTeam?.teamName ?? (insights.matchesQuery.isLoading ? "..." : "-"),
      value: bestAwayTeam ? formatPointCount(bestAwayTeam.metricValue) : (insights.matchesQuery.isLoading ? "..." : "-"),
    },
    {
      href: worstAwayTeam?.teamId ? buildCanonicalTeamPath(context, worstAwayTeam.teamId) : null,
      label: "Pior visitante",
      primary: worstAwayTeam?.teamName ?? (insights.matchesQuery.isLoading ? "..." : "-"),
      value: worstAwayTeam ? formatPointCount(worstAwayTeam.metricValue) : (insights.matchesQuery.isLoading ? "..." : "-"),
    },
    {
      href: longestUnbeatenRun?.teamId ? buildCanonicalTeamPath(context, longestUnbeatenRun.teamId) : null,
      label: "Maior sequência invicta",
      primary: longestUnbeatenRun?.teamName ?? (insights.matchesQuery.isLoading ? "..." : "-"),
      value:
        longestUnbeatenRun
          ? formatGameCount(longestUnbeatenRun.metricValue)
          : (insights.matchesQuery.isLoading ? "..." : "-"),
    },
    {
      href: longestWinningRun?.teamId ? buildCanonicalTeamPath(context, longestWinningRun.teamId) : null,
      label: "Maior sequência de vitórias",
      primary: longestWinningRun?.teamName ?? (insights.matchesQuery.isLoading ? "..." : "-"),
      value:
        longestWinningRun
          ? formatGameCount(longestWinningRun.metricValue)
          : (insights.matchesQuery.isLoading ? "..." : "-"),
    },
  ];

  return (
    <ProfilePanel className="space-y-3.5 p-4 md:p-5" tone="soft">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
          Mandos e sequências
        </p>
        {coverage.status !== "complete" ? <ProfileCoveragePill coverage={coverage} /> : null}
      </div>

      <div className="divide-y divide-[rgba(191,201,195,0.42)]">
        {items.map((item) => (
          <CompactTravelRow
            href={item.href}
            key={item.label}
            label={item.label}
            primary={item.primary}
            value={item.value}
          />
        ))}
      </div>
    </ProfilePanel>
  );
}

function EditionRailInsightsCards({ context }: { context: CompetitionSeasonContext }) {
  return (
    <>
      <EditionSuperlativesRailCard context={context} />
      <EditionTravelRailCard context={context} />
    </>
  );
}

// ─── Copa — Hero histórico ───────────────────────────────────────────────────

function CupHistoricalHero({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const [isHeroPhotoUnavailable, setIsHeroPhotoUnavailable] = useState(false);
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const topScorerQuery = useEditionTopScorer(context);
  const competitionDefinition = getCompetitionById(context.competitionId);
  const visualAssetId = getCompetitionVisualAssetId(competitionDefinition);
  const competitionLogoSrc = visualAssetId
    ? `/api/visual-assets/competitions/${encodeURIComponent(visualAssetId)}`
    : null;
  const competitionInitials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");
  const championArtwork = resolveSeasonChampionArtwork(context.competitionKey, context.seasonLabel);
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);
  const championName = championTieQuery.isLoading
    ? "..."
    : championTie?.winnerTeamName ?? "Campeão não identificado";
  const finalDecisionDate =
    championTie ? formatLongDate(championTie.lastLegAt ?? championTie.firstLegAt) : null;
  const matchCount = analyticsQuery.isLoading
    ? "..."
    : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount);
  const primaryStageCount = resolveCupPrimaryStages(resolution).length || resolution.knockoutStages.length;
  const participantCount = resolveCupParticipantCount(resolution, analyticsQuery.data ?? null).count;
  const topScorer = topScorerQuery.data?.scorer ?? null;
  const topScorerName = topScorerQuery.isLoading ? "..." : (topScorer?.entityName ?? "Artilharia indisponível");
  const topScorerDetail = topScorer ? (
    <>
      <span className="font-semibold text-[#003526]">{topScorer.goals} gols</span>
      {topScorer.teamName ? ` • ${topScorer.teamName}` : ""}
    </>
  ) : (
    "Ranking histórico da copa não consolidado."
  );
  const summaryValue = (
    <>
      <span className="font-extrabold text-[#003526]">{matchCount}</span>
      <span className="mx-2 text-[#8fa097]">•</span>
      <span className="font-extrabold text-[#003526]">{formatCupStageCount(primaryStageCount)}</span>
      {participantCount ? (
        <>
          <span className="mx-2 text-[#8fa097]">•</span>
          <span className="font-extrabold text-[#003526]">{participantCount} clubes</span>
        </>
      ) : null}
    </>
  );
  const heroImageSrc = championArtwork?.src ?? null;

  useEffect(() => {
    setIsHeroPhotoUnavailable(false);
  }, [heroImageSrc]);

  return (
    <div className="relative overflow-hidden rounded-[1.7rem] border border-[rgba(191,201,195,0.5)] bg-[radial-gradient(circle_at_top_right,rgba(194,241,214,0.42),transparent_26%),linear-gradient(180deg,#f7fbf8_0%,#edf6f1_100%)] px-5 py-5 shadow-[0_34px_80px_-52px_rgba(17,28,45,0.32)] md:px-6 md:py-6">
      <div className="absolute right-[-8%] top-[-18%] h-56 w-56 rounded-full bg-[rgba(5,77,57,0.08)] blur-3xl" />
      <div className="absolute bottom-[-24%] left-[14%] h-48 w-48 rounded-full bg-[rgba(166,242,209,0.22)] blur-3xl" />

      <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.96fr)] xl:items-stretch">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            {["Edição encerrada", "Mata-mata"].map((tag) => (
              <span
                className="rounded-full border border-[rgba(0,53,38,0.12)] bg-[rgba(255,255,255,0.72)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#0d4a37]"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start">
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-[1.35rem] border border-[rgba(191,201,195,0.55)] bg-white shadow-[0_24px_50px_-34px_rgba(17,28,45,0.42)]">
              <span className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
                {competitionInitials || "FA"}
              </span>
              {competitionLogoSrc ? (
                <img
                  alt={`Logo ${context.competitionName}`}
                  className="absolute inset-0 h-full w-full object-contain bg-white p-3"
                  onError={(event) => {
                    (event.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                  src={competitionLogoSrc}
                />
              ) : null}
            </div>

            <div className="space-y-3">
              <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.65rem] font-extrabold leading-[0.95] tracking-[-0.06em] text-[#111c2d] md:text-[3.25rem]">
                {context.competitionName} {context.seasonLabel}
              </h1>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-5 py-5 shadow-[0_28px_68px_-48px_rgba(17,28,45,0.22)]">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              Resumo da copa
            </p>
            <div className="mt-4">
              <HybridHeroSummaryItem
                label="Campeão"
                media={championTie ? <TeamBadge size={44} teamId={championTie.winnerTeamId} teamName={championName} /> : null}
                value={championName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[2.05rem] font-extrabold leading-none tracking-[-0.05em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                label="Final"
                value={finalDecisionDate ?? "Data não informada"}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-[1.02] tracking-[-0.04em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                detail={topScorerDetail}
                label="Artilheiro"
                media={<PlayerPhoto playerId={topScorer?.entityId} playerName={topScorer?.entityName ?? topScorerName} size={52} />}
                value={topScorerName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-[1.02] tracking-[-0.04em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                label="Resumo"
                value={summaryValue}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold leading-[1.05] tracking-[-0.04em] text-[#111c2d]"
              />
            </div>
          </div>
        </div>

        <div className="relative min-h-[360px] overflow-hidden rounded-[1.6rem] border border-[rgba(8,48,35,0.18)] bg-[#0a3528] shadow-[0_36px_80px_-48px_rgba(0,53,38,0.7)]">
          {heroImageSrc && !isHeroPhotoUnavailable ? (
            <img
              alt={`Celebração do campeão da ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-cover"
              onError={() => setIsHeroPhotoUnavailable(true)}
              src={heroImageSrc}
            />
          ) : null}
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,24,18,0.12)_0%,rgba(3,24,18,0.44)_48%,rgba(3,24,18,0.78)_100%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,224,130,0.2),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(166,242,209,0.18),transparent_26%)]" />

          {isHeroPhotoUnavailable || !heroImageSrc ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-28 w-28 rounded-full border border-white/16 bg-white/10 blur-[1px]" />
            </div>
          ) : null}

          <div className="absolute inset-x-4 bottom-4">
            <div className="rounded-[1.3rem] border border-white/12 bg-[rgba(7,24,18,0.52)] px-4 py-4 backdrop-blur-sm">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                Campeão
              </p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold leading-none tracking-[-0.04em] text-white">
                {championName}
              </p>
              <p className="mt-2 text-sm text-[#d7efe4]">
                {finalDecisionDate ?? "Data da final não informada"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CupStructureStrip({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const primaryStageCount = resolveCupPrimaryStages(resolution).length || resolution.knockoutStages.length;
  const matchCount = analyticsQuery.isLoading
    ? "..."
    : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount);
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);
  const finalDecisionDate =
    championTie ? formatLongDate(championTie.lastLegAt ?? championTie.firstLegAt) : null;
  const stageRangeLabel = resolveCupStageRangeLabel(resolution);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-extrabold text-[#111c2d]">Mata-mata puro</span>
      <span className="text-[#8fa097]">•</span>
      <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        {stageRangeLabel}
      </span>
      <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        {formatCupStageCount(primaryStageCount)}
      </span>
      <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        {matchCount} partidas
      </span>
      {finalDecisionDate ? (
        <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
          Final em {finalDecisionDate}
        </span>
      ) : null}
    </div>
  );
}

function LeagueEditionRail({ context }: { context: CompetitionSeasonContext }) {
  return (
    <>
      <TopScorerRailCard context={context} />
      <EditionRailInsightsCards context={context} />
    </>
  );
}
function LeagueStructureSection({ context }: { context: CompetitionSeasonContext }) {
  const finalStandingsQuery = useSeasonFinalStandings(context);
  const filteredStandingsQuery = useStandingsTable();
  const shouldShowFilteredSnapshot =
    Boolean(filteredStandingsQuery.data?.selectedRound?.roundId) &&
    filteredStandingsQuery.data?.selectedRound?.roundId !== finalStandingsQuery.data?.currentRound?.roundId;

  return (
    <div className="space-y-5">
      <FinalStandingsPanel
        context={context}
        description="A classificação final da edição é a âncora principal da leitura da liga."
        query={finalStandingsQuery}
        title="Classificação final"
      />

      {shouldShowFilteredSnapshot ? (
        <FinalStandingsPanel
          context={context}
          description={`Recorte adicional preservado pela URL para a ${filteredStandingsQuery.data?.selectedRound?.label ?? "rodada selecionada"}.`}
          query={filteredStandingsQuery}
          rowsLimit={8}
          title={filteredStandingsQuery.data?.selectedRound?.label ?? "Recorte adicional"}
        />
      ) : null}
    </div>
  );
}

// ─── Bloco 4 — Canvas da copa ────────────────────────────────────────────────

function CupOverviewSection({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const primaryStages = resolveCupPrimaryStages(resolution);
  const openingStage = resolveCupOpeningStage(resolution);
  const finalStage = resolveCupFinalStage(resolution);
  const participantCountState = resolveCupParticipantCount(resolution, analyticsQuery.data ?? null);
  const participantCountValue =
    participantCountState.count !== null
      ? formatHistoricalMatchCount(participantCountState.count)
      : (analyticsQuery.isLoading ? "..." : "-");
  const participantCountDetail =
    participantCountState.source === "structure"
      ? "Estimativa vinda da estrutura da etapa inicial."
      : participantCountState.source === "analytics"
        ? "Derivado do total de equipes consolidadas na primeira fase da edição."
        : "Participantes não consolidados na estrutura.";
  const seasonSummary = analyticsQuery.data?.seasonSummary ?? null;
  const summaryBadges = [
    seasonSummary?.matchCount ? `${formatHistoricalMatchCount(seasonSummary.matchCount)} partidas` : null,
    seasonSummary?.tieCount ? `${formatHistoricalMatchCount(seasonSummary.tieCount)} confrontos` : null,
    primaryStages.length > 0 ? formatCupStageCount(primaryStages.length) : null,
  ].filter((badge): badge is string => Boolean(badge));

  return (
    <div className="space-y-5">
      <ProfilePanel className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.5),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(166,242,209,0.16),transparent_30%)]" />
        <div className="relative space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Visão geral</p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
                Leitura da copa
              </h2>
              <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
                Leitura direta da edição eliminatória, sem fase de grupos ou tabela classificatória.
              </p>
            </div>
            {summaryBadges.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                {summaryBadges.map((badge) => (
                  <span
                    className="inline-flex rounded-full border border-[rgba(191,201,195,0.44)] bg-white/76 px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#455468]"
                    key={badge}
                  >
                    {badge}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <CupOverviewStatCard
            detail="A edição é tratada como torneio eliminatório puro."
            label="Formato"
            value={resolution.editionLabel ?? "Mata-mata"}
            />
            <CupOverviewStatCard
            detail="Primeira etapa exibida no chaveamento principal."
            label="Entrada"
            value={openingStage ? localizeSeasonStageName(openingStage.stageName ?? openingStage.stageId) : "-"}
            />
            <CupOverviewStatCard
            detail="Última etapa eliminatória consolidada."
            label="Decisão"
            value={finalStage ? localizeSeasonStageName(finalStage.stageName ?? finalStage.stageId) : "-"}
            />
            <CupOverviewStatCard
            detail={participantCountDetail}
            label="Clubes"
            value={participantCountValue}
            />
          </div>

          {primaryStages.length > 0 ? (
            <div className="relative overflow-hidden rounded-[1.5rem] border border-[rgba(191,201,195,0.52)] bg-[linear-gradient(180deg,rgba(255,255,255,0.84)_0%,rgba(241,245,255,0.72)_100%)] p-4 shadow-[0_18px_42px_-36px_rgba(17,28,45,0.22)] md:p-5">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(216,227,251,0.34),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(166,242,209,0.14),transparent_32%)]" />
              <div className="relative">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                      Trilha principal
                    </p>
                    <p className="mt-1 text-sm text-[#57657a]">
                      Sequência do chaveamento principal até a decisão da edição.
                    </p>
                  </div>
                  <span className="inline-flex rounded-full border border-[rgba(191,201,195,0.44)] bg-white/78 px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
                    {formatCupStageCount(primaryStages.length)}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2 md:gap-3">
                  {primaryStages.map((stage, index) => (
                    <div className="flex items-center gap-2 md:gap-3" key={stage.stageId}>
                      <span className="inline-flex rounded-full border border-[rgba(191,201,195,0.56)] bg-white/86 px-3.5 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#455468] shadow-[0_14px_28px_-24px_rgba(17,28,45,0.25)]">
                        {localizeSeasonStageName(stage.stageName ?? stage.stageId)}
                      </span>
                      {index < primaryStages.length - 1 ? (
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(191,201,195,0.52)] bg-white/74 text-[0.9rem] font-semibold text-[#7b8c87]">
                          →
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
              description="A estrutura não trouxe fases eliminatórias suficientes para descrever a trilha."
              title="Sem trilha consolidada"
            />
          )}
        </div>
      </ProfilePanel>

      <EditionSuperlativesRailCard context={context} />
    </div>
  );
}

function CupStructureSection({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  return (
    <KnockoutBracketPanel
      context={context}
      description="Fases e confrontos da copa, com ida/volta, agregado e classificados quando o dado existe."
      resolution={resolution}
      title="Chaveamento da copa"
    />
  );
}

// ─── Bloco 5 — Canvas do hibrido ─────────────────────────────────────────────

function HybridHistoricalHero({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const [isHeroPhotoUnavailable, setIsHeroPhotoUnavailable] = useState(false);
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const topScorerQuery = useEditionTopScorer(context);
  const competitionDefinition = getCompetitionById(context.competitionId);
  const visualAssetId = getCompetitionVisualAssetId(competitionDefinition);
  const competitionLogoSrc = visualAssetId
    ? `/api/visual-assets/competitions/${encodeURIComponent(visualAssetId)}`
    : null;
  const competitionInitials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");
  const championArtwork = resolveSeasonChampionArtwork(context.competitionKey, context.seasonLabel);

  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);
  const championName = championTieQuery.isLoading
    ? "..."
    : championTie?.winnerTeamName ?? "Campeão não identificado";
  const finalDecisionDate =
    championTie ? formatLongDate(championTie.lastLegAt ?? championTie.firstLegAt) : null;
  const structureHeadline = resolveHybridStructureHeadline(resolution);
  const structureDetail = resolveHybridStructureDetail(resolution.primaryTableStage);
  const matchCount = analyticsQuery.isLoading
    ? "..."
    : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount);
  const topScorer = topScorerQuery.data?.scorer ?? null;
  const topScorerName = topScorerQuery.isLoading ? "..." : (topScorer?.entityName ?? "Artilharia indisponível");
  const topScorerDetail = topScorer ? (
    <>
      <span className="font-semibold text-[#003526]">{topScorer.goals} gols</span>
      {topScorer.teamName ? ` • ${topScorer.teamName}` : ""}
    </>
  ) : (
    "Ranking histórico do torneio não consolidado."
  );
  const heroImageSrc = championArtwork?.src ?? null;
  const summaryValue = (
    <>
      <span className="font-extrabold text-[#003526]">{matchCount}</span>
      <span className="mx-2 text-[#8fa097]">•</span>
      <span className="font-extrabold text-[#003526]">{resolution.stageCount} fases</span>
    </>
  );

  useEffect(() => {
    setIsHeroPhotoUnavailable(false);
  }, [heroImageSrc]);

  return (
    <div className="relative overflow-hidden rounded-[1.7rem] border border-[rgba(191,201,195,0.5)] bg-[radial-gradient(circle_at_top_right,rgba(194,241,214,0.42),transparent_26%),linear-gradient(180deg,#f7fbf8_0%,#edf6f1_100%)] px-5 py-5 shadow-[0_34px_80px_-52px_rgba(17,28,45,0.32)] md:px-6 md:py-6">
      <div className="absolute right-[-8%] top-[-18%] h-56 w-56 rounded-full bg-[rgba(5,77,57,0.08)] blur-3xl" />
      <div className="absolute bottom-[-24%] left-[14%] h-48 w-48 rounded-full bg-[rgba(166,242,209,0.22)] blur-3xl" />

      <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.96fr)] xl:items-stretch">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            {["Edição encerrada", "Hibrida"].map((tag) => (
              <span
                className="rounded-full border border-[rgba(0,53,38,0.12)] bg-[rgba(255,255,255,0.72)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#0d4a37]"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start">
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-[1.35rem] border border-[rgba(191,201,195,0.55)] bg-white shadow-[0_24px_50px_-34px_rgba(17,28,45,0.42)]">
              <span className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
                {competitionInitials || "FA"}
              </span>
              {competitionLogoSrc ? (
                <img
                  alt={`Logo ${context.competitionName}`}
                  className="absolute inset-0 h-full w-full object-contain bg-white p-3"
                  onError={(event) => {
                    (event.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                  src={competitionLogoSrc}
                />
              ) : null}
            </div>

            <div className="space-y-3">
              <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.65rem] font-extrabold leading-[0.95] tracking-[-0.06em] text-[#111c2d] md:text-[3.25rem]">
                {context.competitionName} {context.seasonLabel}
              </h1>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-5 py-5 shadow-[0_28px_68px_-48px_rgba(17,28,45,0.22)]">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              Resumo da edição
            </p>
            <div className="mt-4">
              <HybridHeroSummaryItem
                label="Campeão"
                media={championTie ? <TeamBadge size={44} teamId={championTie.winnerTeamId} teamName={championName} /> : null}
                value={championName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[2.05rem] font-extrabold leading-none tracking-[-0.05em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                label="Final"
                value={finalDecisionDate ?? "Data não informada"}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-[1.02] tracking-[-0.04em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                detail={topScorerDetail}
                label="Artilheiro"
                media={<PlayerPhoto playerId={topScorer?.entityId} playerName={topScorer?.entityName ?? topScorerName} size={52} />}
                value={topScorerName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-[1.02] tracking-[-0.04em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                label="Resumo"
                value={summaryValue}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold leading-[1.05] tracking-[-0.04em] text-[#111c2d]"
              />
            </div>
          </div>
        </div>

        <div className="relative min-h-[360px] overflow-hidden rounded-[1.6rem] border border-[rgba(8,48,35,0.18)] bg-[#0a3528] shadow-[0_36px_80px_-48px_rgba(0,53,38,0.7)]">
          {heroImageSrc && !isHeroPhotoUnavailable ? (
            <img
              alt={`Celebração do campeão da ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-cover"
              onError={() => setIsHeroPhotoUnavailable(true)}
              src={heroImageSrc}
            />
          ) : null}
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,24,18,0.12)_0%,rgba(3,24,18,0.44)_48%,rgba(3,24,18,0.78)_100%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,224,130,0.2),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(166,242,209,0.18),transparent_26%)]" />

          {isHeroPhotoUnavailable || !heroImageSrc ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-28 w-28 rounded-full border border-white/16 bg-white/10 blur-[1px]" />
            </div>
          ) : null}

          <div className="absolute inset-x-4 bottom-4">
            <div className="rounded-[1.3rem] border border-white/12 bg-[rgba(7,24,18,0.52)] px-4 py-4 backdrop-blur-sm">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                Campeão
              </p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold leading-none tracking-[-0.04em] text-white">
                {championName}
              </p>
              <p className="mt-2 text-sm text-[#d7efe4]">
                {finalDecisionDate ?? "Data da final não informada"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HybridStructureStrip({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const matchCount = analyticsQuery.isLoading
    ? "..."
    : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount);
  const structureHeadline = resolveHybridStructureHeadline(resolution);
  const structureDetail = resolveHybridStructureDetail(resolution.primaryTableStage);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-extrabold text-[#111c2d]">{structureHeadline}</span>
      <span className="text-[#8fa097]">•</span>
      <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        {resolution.stageCount} fases
      </span>
      <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        {matchCount} partidas
      </span>
      {structureDetail ? (
        <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
          {structureDetail}
        </span>
      ) : null}
    </div>
  );
}

function HybridTableOverviewPanel({
  context,
  stage,
}: {
  context: CompetitionSeasonContext;
  stage: CompetitionStructureStage | null;
}) {
  const isGroupTable = stage?.stageFormat === "group_table";
  const groupQueries = useGroupStandingsQueries(context, isGroupTable ? stage : null);
  const finalStandingsQuery = useSeasonFinalStandings(
    context,
    !isGroupTable ? stage?.stageId : null,
  );
  const transitionSlots = resolveTransitionSlotCount(stage);
  const transitionSummary = resolveTransitionSummary(stage);

  if (!stage) {
    return (
      <ProfileAlert title="Fase de tabela indisponível" tone="warning">
        A estrutura atual não identificou uma fase classificatória para esta edição.
      </ProfileAlert>
    );
  }

  if (isGroupTable) {
    const previewCount = stage.expectedTeams ?? (transitionSlots !== null ? transitionSlots + 2 : 8);
    const groupQueriesSettled =
      groupQueries.length > 0 && groupQueries.every((groupQuery) => !groupQuery.isLoading);
    const hasGroupRows = groupQueries.some((groupQuery) => (groupQuery.data?.rows.length ?? 0) > 0);

    if (groupQueries.length === 0 || (groupQueriesSettled && !hasGroupRows)) {
      return (
        <FinalStandingsPanel
          context={context}
          description="A classificação final da fase de grupos segue como referência principal desta edição encerrada."
          query={finalStandingsQuery}
          title={localizeSeasonStageName(stage.stageName ?? resolveHybridTableSectionLabel(stage))}
        />
      );
    }

    return (
      <ProfilePanel className="space-y-5">
        <SeasonSectionHeader
          eyebrow="Fase de tabela"
          title={localizeSeasonStageName(stage.stageName ?? resolveHybridTableSectionLabel(stage))}
        />

        <div className="grid gap-3 md:grid-cols-3">
          <HistoricalHeroCard
            detail="Grupos consolidados na estrutura da edição."
            label="Grupos"
            tone="soft"
            value={String(stage.groups.length)}
          />
          <HistoricalHeroCard
            detail={transitionSlots ? "Número de vagas por grupo para a etapa seguinte." : "Sem regra de progressão consolidada."}
            label="Corte"
            tone="soft"
            value={transitionSlots ? `${transitionSlots} por grupo` : "-"}
          />
          <HistoricalHeroCard
            detail={transitionSummary ?? "Sem transição consolidada para a fase seguinte."}
            label="Transição"
            tone="soft"
            value={stage.transitions[0]?.toStageName ?? "Mata-mata"}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          {groupQueries.map((groupQuery) => {
            const rows = groupQuery.data?.rows ?? [];
            const previewRows = rows.slice(0, previewCount);

            return (
              <ProfilePanel className="space-y-4" key={`overview-${groupQuery.group.groupId}`} tone="soft">
                <SeasonSectionHeader
                  coverage={groupQuery.coverage}
                  eyebrow="Grupo"
                  title={groupQuery.group.groupName ?? groupQuery.group.groupId}
                />

                {groupQuery.isError ? (
                  <ProfileAlert title="Grupo indisponível" tone="warning">
                    Não foi possível consolidar este grupo agora.
                  </ProfileAlert>
                ) : null}

                {groupQuery.isLoading ? <LoadingSkeleton height={156} /> : null}

                {!groupQuery.isLoading && !groupQuery.isError && previewRows.length === 0 ? (
                  <EmptyState
                    className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                    description="Sem classificação suficiente neste grupo."
                    title="Sem classificação"
                  />
                ) : null}

                {!groupQuery.isLoading && !groupQuery.isError && previewRows.length > 0 ? (
                  <div className="space-y-2">
                    {previewRows.map((row) => {
                      const isClassified = transitionSlots !== null && row.position <= transitionSlots;
                      return (
                        <div
                          className={
                            isClassified
                              ? "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(3,53,38,0.2)] bg-[rgba(139,214,182,0.1)] px-3 py-2.5"
                              : "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.42)] bg-white px-3 py-2.5"
                          }
                          key={`${groupQuery.group.groupId}-${row.teamId}`}
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${isClassified ? "bg-[rgba(3,53,38,0.12)] text-[#003526]" : "bg-[rgba(3,53,38,0.06)] text-[#57657a]"}`}>
                              {row.position}
                            </span>
                            <TeamBadge size={26} teamId={row.teamId} teamName={row.teamName ?? row.teamId} />
                            <Link
                              className="truncate text-sm font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
                              href={buildCanonicalTeamPath(context, row.teamId)}
                            >
                              {row.teamName ?? row.teamId}
                            </Link>
                          </div>
                          <div className="flex items-center gap-3 text-right">
                            <div className="hidden sm:block">
                              <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">V</p>
                              <p className="text-xs font-bold text-[#57657a]">{row.wins}</p>
                            </div>
                            <div className="hidden sm:block">
                              <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">SG</p>
                              <p className={`text-xs font-bold ${
                                row.goalDiff > 0 ? "text-[#1b6b51]" : row.goalDiff < 0 ? "text-[#ba1a1a]" : "text-[#57657a]"
                              }`}>
                                {row.goalDiff > 0 ? `+${row.goalDiff}` : row.goalDiff}
                              </p>
                            </div>
                            <div>
                              <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">Pts</p>
                              <p className={`text-sm font-extrabold ${isClassified ? "text-[#003526]" : "text-[#111c2d]"}`}>{row.points}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </ProfilePanel>
            );
          })}
        </div>
      </ProfilePanel>
    );
  }

  const rows = finalStandingsQuery.data?.rows ?? [];
  const previewRows = rows.slice(0, Math.min(rows.length, 8));
  const cutoffRow =
    transitionSlots && rows.length >= transitionSlots ? rows[transitionSlots - 1] : null;

  return (
    <ProfilePanel className="space-y-5">
      <SeasonSectionHeader
        description="Tabela final da fase classificatória, com foco no corte para o mata-mata."
        eyebrow="Fase de tabela"
        title={localizeSeasonStageName(stage.stageName ?? resolveHybridTableSectionLabel(stage))}
      />

      <div className="grid gap-3 md:grid-cols-3">
        <HistoricalHeroCard
          detail="Equipes classificadas na fase única."
          label="Equipes"
          tone="soft"
          value={String(rows.length || stage.expectedTeams || 0)}
        />
        <HistoricalHeroCard
          detail={transitionSummary ?? "Sem regra de progressão consolidada."}
          label="Corte"
          tone="soft"
          value={cutoffRow ? `${cutoffRow.position}º ${cutoffRow.teamName}` : "-"}
        />
        <HistoricalHeroCard
          detail="Jogos disputados por equipe no fechamento da fase."
          label="Carga"
          tone="soft"
          value={rows[0] ? `${rows[0].matchesPlayed} PJ` : "-"}
        />
      </div>

      {finalStandingsQuery.isError ? (
        <ProfileAlert title="Fase classificatória indisponível" tone="warning">
          Não foi possível carregar a tabela final desta etapa.
        </ProfileAlert>
      ) : null}

      {finalStandingsQuery.isLoading ? <LoadingSkeleton height={220} /> : null}

      {!finalStandingsQuery.isLoading && !finalStandingsQuery.isError && previewRows.length === 0 ? (
        <EmptyState
          className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
          description="Sem linhas consolidadas para esta fase."
          title="Sem classificação"
        />
      ) : null}

      {!finalStandingsQuery.isLoading && !finalStandingsQuery.isError && previewRows.length > 0 ? (
        <div className="grid gap-3">
          {previewRows.map((row) => {
            const isCutLine = cutoffRow?.teamId === row.teamId;

            return (
              <div
                className={
                  isCutLine
                    ? "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(3,53,38,0.22)] bg-[rgba(139,214,182,0.14)] px-3 py-3"
                    : "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.42)] bg-white px-3 py-3"
                }
                key={`league-overview-${row.teamId}`}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[rgba(3,53,38,0.08)] text-xs font-bold text-[#003526]">
                    {row.position}
                  </span>
                  <TeamBadge size={28} teamId={row.teamId} teamName={row.teamName ?? row.teamId} />
                  <Link
                    className="truncate text-sm font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
                    href={buildCanonicalTeamPath(context, row.teamId)}
                  >
                    {row.teamName ?? row.teamId}
                  </Link>
                </div>
                <div className="text-right">
                  <p className="text-sm font-extrabold text-[#111c2d]">{row.points} pts</p>
                  <p className="text-[0.66rem] uppercase tracking-[0.16em] text-[#57657a]">
                    {row.goalDiff >= 0 ? `+${row.goalDiff}` : row.goalDiff} SG
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </ProfilePanel>
  );
}

function HybridOverviewSection({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  return (
    <div className="space-y-5">
      <HybridFactsCard context={context} resolution={resolution} />
      <HybridTableOverviewPanel context={context} stage={resolution.primaryTableStage} />
    </div>
  );
}

function HybridFactsCard({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);
  const groupCount = resolution.primaryTableStage?.groups.length ?? 0;
  const tableSectionLabel = resolveHybridTableSectionLabel(resolution.primaryTableStage);

  const facts: Array<{ label: string; value: string }> = [
    {
      label: "Campeão",
      value: championTieQuery.isLoading
        ? "..."
        : (championTie?.winnerTeamName ?? "Não identificado"),
    },
    {
      label: "Partidas",
      value: analyticsQuery.isLoading
        ? "..."
        : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount),
    },
    {
      label: tableSectionLabel,
      value: groupCount > 0
        ? `${groupCount} grupos`
        : (resolution.primaryTableStage
            ? localizeSeasonStageName(resolution.primaryTableStage.stageName ?? resolution.primaryTableStage.stageId)
            : "-"),
    },
    {
      label: "Mata-mata",
      value: resolution.knockoutStages.length > 0
        ? String(resolution.knockoutStages.length)
        : "-",
    },
  ];

  return (
    <ProfilePanel className="space-y-4">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Edição</p>
        <p className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
          {context.competitionName}
        </p>
        <p className="mt-1 text-sm text-[#57657a]">{context.seasonLabel}</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {facts.map((fact) => (
          <div
            className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-3 py-3"
            key={fact.label}
          >
            <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">{fact.label}</p>
            <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-base font-extrabold text-[#111c2d]">
              {fact.value}
            </p>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.56)] px-3 py-3">
          <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Estrutura</p>
          <p className="mt-1 text-sm font-semibold text-[#111c2d]">
            {resolution.editionLabel ?? "Formato híbrido"}
          </p>
        </div>
        <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.56)] px-3 py-3">
          <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Decisão</p>
          <p className="mt-1 text-sm font-semibold text-[#111c2d]">
            {resolution.finalKnockoutStage
              ? localizeSeasonStageName(resolution.finalKnockoutStage.stageName ?? resolution.finalKnockoutStage.stageId)
              : "Não identificado"}
          </p>
        </div>
      </div>
    </ProfilePanel>
  );
}

function HybridEditionRail({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  return (
    <>
      <HybridFactsCard context={context} resolution={resolution} />
      <EditionRailInsightsCards context={context} />
    </>
  );
}

function buildSurfaceNavLabels(
  resolution: CompetitionSeasonSurfaceResolution,
): SurfaceNavLabels {
  if (resolution.type === "league") {
    return {
      highlights: "Destaques estatísticos",
      matches: "Partidas",
      overview: "Classificação",
      structure: "Classificação",
    };
  }

  if (resolution.type === "hybrid") {
    return {
      highlights: "Destaques estatísticos",
      matches: "Mata-mata",
      overview: "Visão geral",
      structure: resolveHybridNavigationStructureLabel(resolution.primaryTableStage),
    };
  }

  return {
    highlights: "Destaques",
    matches: "Partidas",
    overview: "Visão geral",
    structure: "Chaveamento",
  };
}

function LeaguePageHeader({
  context,
  navigation,
  tag,
}: {
  context: CompetitionSeasonContext;
  navigation?: ReactNode;
  tag: string;
}) {
  const compDef = getCompetitionById(context.competitionId);
  const visualAssetId = getCompetitionVisualAssetId(compDef);
  const logoSrc = visualAssetId
    ? `/api/visual-assets/competitions/${encodeURIComponent(visualAssetId)}`
    : null;
  const initials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="flex flex-col gap-3 px-1 py-1.5 md:px-2 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <div className="relative flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[rgba(191,201,195,0.55)] bg-white shadow-sm md:h-12 md:w-12">
          <span className="font-[family:var(--font-profile-headline)] text-base font-extrabold text-[#003526] md:text-lg">
            {initials || "FA"}
          </span>
          {logoSrc ? (
            <img
              alt={`Logo ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-contain bg-white p-2"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
              src={logoSrc}
            />
          ) : null}
        </div>

        <div className="min-w-0">
          <h1 className="truncate py-0.5 font-[family:var(--font-profile-headline)] text-2xl font-extrabold leading-[1.12] tracking-[-0.04em] text-[#111c2d] md:text-3xl">
            {context.competitionName}
          </h1>
          <p className="mt-0.5 text-[0.7rem] font-bold uppercase tracking-[0.16em] text-[#515f74]">
            {tag} · {context.seasonLabel}
          </p>
        </div>
      </div>

      {navigation ? <div className="min-w-0 lg:flex-1">{navigation}</div> : null}
    </div>
  );
}

// ─── Rodada a Rodada ──────────────────────────────────────────────────────────

type StandingsRound = StandingsTableData["rounds"][number];

function RoundPickerDropdown({
  activeRoundId,
  rounds,
  selectedRound,
  setRoundId,
}: {
  activeRoundId: string | null;
  rounds: StandingsRound[];
  selectedRound?: StandingsRound | null;
  setRoundId: (roundId: string | null) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative inline-block">
      <button 
        className="button-pill button-pill-primary gap-2"
        onClick={() => setIsOpen(!isOpen)}
        type="button"
      >
        <span className="text-[10px] font-bold uppercase tracking-widest text-white/80">Rodada:</span>
        <span className="text-xs font-extrabold text-white">
          {selectedRound?.label?.replace(/rodada\s*/i, "").trim() ?? activeRoundId ?? "Todas"}
        </span>
        <svg
          className="h-4 w-4 text-white/80"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {isOpen ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 top-12 z-50 w-[260px] rounded-xl border border-[rgba(191,201,195,0.55)] bg-white p-4 shadow-[0_12px_40px_-12px_rgba(0,0,0,0.2)]">
            <div className="mb-3 flex items-center justify-between border-b border-[rgba(191,201,195,0.3)] pb-2">
              <span className="text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]">
                Selecione a rodada
              </span>
              <button className="text-[#515f74] hover:text-black" onClick={() => setIsOpen(false)} type="button">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
            <div className="grid grid-cols-6 gap-1.5">
              {rounds.map((round) => {
                const isActive = round.roundId === (activeRoundId ?? selectedRound?.roundId);
                const shortLabel = round.label.replace(/rodada\s*/i, "").trim();
                return (
                  <button
                    className={`flex h-8 w-8 items-center justify-center rounded-md text-[0.7rem] font-bold tabular-nums transition-colors ${
                      isActive
                        ? "bg-[#003526] text-white shadow-md"
                        : "border border-[#dce3f9] bg-[#f0f3ff] text-[#515f74] hover:bg-[#e1e7fa]"
                    }`}
                    key={round.roundId}
                    onClick={() => {
                      setRoundId(isActive ? null : round.roundId);
                      setIsOpen(false);
                    }}
                    title={`Rodada ${shortLabel}`}
                    type="button"
                  >
                    {shortLabel}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function RoundsSection({ context }: { context: CompetitionSeasonContext }) {
  const { setRoundId, roundId: activeRoundId } = useGlobalFilters();
  const standingsQuery = useStandingsTable();
  const rows = standingsQuery.data?.rows ?? [];
  const selectedRound = standingsQuery.data?.selectedRound;
  const rounds = standingsQuery.data?.rounds ?? [];

  return (
    <div className="space-y-5">
      {/* Round picker dropdown */}
      {rounds.length > 1 ? (
        <div className="flex items-center gap-3">
          <RoundPickerDropdown 
            activeRoundId={activeRoundId} 
            rounds={rounds} 
            selectedRound={selectedRound} 
            setRoundId={setRoundId} 
          />
          {standingsQuery.coverage.status !== "complete" ? (
            <ProfileCoveragePill coverage={standingsQuery.coverage} />
          ) : null}
          {selectedRound?.startingAt ? (
            <span className="text-[0.68rem] font-semibold tracking-wide text-[#515f74]">
              {formatDateWindow(selectedRound.startingAt, selectedRound.endingAt)}
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Removed old selected round indicator since details are now near the button */}

      {standingsQuery.isLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={56} />
          <LoadingSkeleton height={320} />
        </div>
      ) : rows.length === 0 && !standingsQuery.isLoading ? (
        <EmptyState
          className="rounded-xl border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description={rounds.length > 0 ? "Selecione uma rodada para ver a tabela." : "Sem rodadas disponíveis para esta edição."}
          title="Nenhuma rodada selecionada"
        />
      ) : (
        <LeagueStandingsTable context={context} rows={rows} />
      )}
    </div>
  );
}

function LeagueSeasonSurface({
  activeSection,
  context,
  resolution,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const searchParams = useSearchParams();
  const navLabels = buildSurfaceNavLabels(resolution);
  const filterInput = useSeasonFilterInput(context);
  const shouldShowClassification =
    activeSection === "overview" || activeSection === "structure" || activeSection === "matches";
  const navItems = [
    {
      href: buildSeasonSurfaceHref(context, "overview", searchParams),
      isActive: shouldShowClassification,
      key: "overview",
      label: navLabels.overview,
    },
    {
      href: buildSeasonSurfaceHref(context, "rounds", searchParams),
      isActive: activeSection === "rounds",
      key: "rounds",
      label: "Rodada a rodada",
    },
    {
      href: buildSeasonSurfaceHref(context, "highlights", searchParams),
      isActive: activeSection === "highlights",
      key: "highlights",
      label: navLabels.highlights,
    },
    {
      href: buildPlayersPath(filterInput),
      isActive: false,
      key: "players",
      label: "Jogadores",
    },
    {
      href: buildTeamsPath(filterInput),
      isActive: false,
      key: "teams",
      label: "Times",
    },
    {
      href: buildMatchesPath(filterInput),
      isActive: false,
      key: "matches",
      label: navLabels.matches,
    },
  ];
  const navigation = (
    <ProfileTabs
      ariaLabel="Navegacao da edição"
      className="rounded-[1.1rem] !p-2 md:!p-2 lg:justify-end"
      items={navItems}
    />
  );

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      density="compact"
      hero={<LeaguePageHeader context={context} navigation={navigation} tag="Pontos Corridos" />}
      summaryStrip={<LeagueEditionSummaryStrip context={context} />}
      mainCanvas={
        <>
          {shouldShowClassification ? <LeagueOverviewSection context={context} /> : null}
          {activeSection === "rounds" ? <RoundsSection context={context} /> : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={null} /> : null}
        </>
      }
      navItems={[]}
      secondaryRail={<LeagueEditionRail context={context} />}
      showLocalBreadcrumbs={false}
    />
  );
}


function CupSeasonSurface({
  activeSection,
  context,
  resolution,
  structure,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
  structure: CompetitionStructureData | null;
}) {
  const searchParams = useSearchParams();
  const navLabels = buildSurfaceNavLabels(resolution);
  const overviewBracket = (
    <KnockoutBracketPanel
      context={context}
      resolution={resolution}
      title="Chaveamento até a final"
      variant="snapshot"
    />
  );

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<CupHistoricalHero context={context} resolution={resolution} />}
      summaryStrip={activeSection === "overview" ? <CupStructureStrip context={context} resolution={resolution} /> : null}
      mainCanvas={
        <>
          {activeSection === "overview" ? (
            <div className="space-y-6">
              {overviewBracket}
              <CupOverviewSection context={context} resolution={resolution} />
            </div>
          ) : null}
          {activeSection === "structure" ? <CupStructureSection context={context} resolution={resolution} /> : null}
          {activeSection === "matches" ? (
            <ClosingMatchesPanel
              context={context}
              description="Partidas finais e confrontos de maior peso na edição encerrada."
              title="Partidas da copa"
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={structure} /> : null}
        </>
      }
      navAside={null}
      navItems={[
        {
          href: buildSeasonSurfaceHref(context, "overview", searchParams),
          isActive: activeSection === "overview",
          key: "overview",
          label: navLabels.overview,
        },
        {
          href: buildSeasonSurfaceHref(context, "structure", searchParams),
          isActive: activeSection === "structure",
          key: "structure",
          label: navLabels.structure,
        },
        {
          href: buildSeasonSurfaceHref(context, "matches", searchParams),
          isActive: activeSection === "matches",
          key: "matches",
          label: navLabels.matches,
        },
        {
          href: buildSeasonSurfaceHref(context, "highlights", searchParams),
          isActive: activeSection === "highlights",
          key: "highlights",
          label: navLabels.highlights,
        },
      ]}
      secondaryRail={null}
      showLocalBreadcrumbs={false}
      supportingModules={null}
    />
  );
}

function HybridSeasonSurface({
  activeSection,
  context,
  resolution,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const searchParams = useSearchParams();
  const navLabels = buildSurfaceNavLabels(resolution);
  const overviewBracket = (
    <KnockoutBracketPanel
      context={context}
      resolution={resolution}
      title="Chaveamento até a final"
      variant="snapshot"
    />
  );
  const matchesBracket = (
    <KnockoutBracketPanel
      context={context}
      resolution={resolution}
      title="Chaveamento da edição"
      variant="stacked"
    />
  );

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<HybridHistoricalHero context={context} resolution={resolution} />}
      summaryStrip={activeSection === "overview" ? <HybridStructureStrip context={context} resolution={resolution} /> : null}
      mainCanvas={
        <>
          {activeSection === "overview" ? (
            <div className="space-y-6">
              {overviewBracket}
              <HybridOverviewSection context={context} resolution={resolution} />
            </div>
          ) : null}
          {activeSection === "structure" ? <GroupPhaseSummaryPanel context={context} stage={resolution.primaryTableStage} /> : null}
          {activeSection === "matches" ? matchesBracket : null}
        </>
      }
      navAside={null}
      navItems={[
        {
          href: buildSeasonSurfaceHref(context, "overview", searchParams),
          isActive: activeSection === "overview",
          key: "overview",
          label: navLabels.overview,
        },
        {
          href: buildSeasonSurfaceHref(context, "structure", searchParams),
          isActive: activeSection === "structure",
          key: "structure",
          label: navLabels.structure,
        },
        {
          href: buildSeasonSurfaceHref(context, "matches", searchParams),
          isActive: activeSection === "matches",
          key: "matches",
          label: navLabels.matches,
        },
      ]}
      secondaryRail={null}
      showLocalBreadcrumbs={false}
      supportingModules={null}
    />
  );
}

export function CompetitionSeasonSurface({
  context,
  initialTab,
}: CompetitionSeasonSurfaceProps) {
  const competitionDefinition = getCompetitionByKey(context.competitionKey);
  const requestedSection = resolveCompetitionSeasonSurfaceSection(initialTab);
  const structureQuery = useCompetitionStructure({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const resolution = useMemo(
    () =>
      resolveCompetitionSeasonSurface({
        competitionType: competitionDefinition?.type,
        structure: structureQuery.data,
      }),
    [competitionDefinition?.type, structureQuery.data],
  );
  const activeSection = normalizeCompetitionSeasonSurfaceSection(requestedSection, resolution.type);

  // Bloco 7: guard de loading para tipos que dependem de estrutura antes de resolver o canvas.
  // Liga (domestic_league) pode renderizar imediatamente sem estrutura.
  // Copa e hibrido precisam da estrutura para determinar o canvas correto.
  const needsStructure = competitionDefinition?.type !== "domestic_league";
  if (needsStructure && structureQuery.isLoading) {
    return (
      <CompetitionSeasonSurfaceShell
        context={context}
        hero={
          <SeasonHeroBlock
            context={context}
            eyebrow={context.seasonLabel}
            tags={[context.seasonLabel]}
            title={`${context.competitionName} ${context.seasonLabel}`}
          />
        }
        mainCanvas={
          <div className="space-y-3">
            <LoadingSkeleton height={88} />
            <LoadingSkeleton height={220} />
            <LoadingSkeleton height={160} />
          </div>
        }
        navItems={[
          {
            href: buildSeasonHubPath(context),
            isActive: true,
            key: "overview",
            label: "Carregando",
          },
        ]}
      />
    );
  }

  if (structureQuery.isError && needsStructure) {
    return (
      <CompetitionSeasonSurfaceShell
        context={context}
        hero={
          <SeasonHeroBlock
            context={context}
            description="Estrutura da edição indisponível."
            eyebrow="Estrutura indisponível"
            highlightDescription="Tente recarregar a página."
            highlightLabel="Estado"
            highlightValue="Estrutura ausente"
            tags={[context.seasonLabel, "Indisponivel"]}
            title={`${context.competitionName} ${context.seasonLabel}`}
          />
        }
        mainCanvas={
          <ProfileAlert title="Não foi possível carregar a estrutura da edição" tone="critical">
            Sem esse contrato não é possível diferenciar com segurança o desenho de copa ou híbrido.
          </ProfileAlert>
        }
        navItems={[
          {
            href: buildSeasonHubPath(context),
            isActive: true,
            key: "overview",
            label: "Resumo da edição",
          },
        ]}
      />
    );
  }

  if (resolution.type === "league") {
    return <LeagueSeasonSurface activeSection={activeSection} context={context} resolution={resolution} />;
  }

  if (resolution.type === "hybrid") {
    return (
      <HybridSeasonSurface
        activeSection={activeSection}
        context={context}
        resolution={resolution}
      />
    );
  }

  return (
    <CupSeasonSurface
      activeSection={activeSection}
      context={context}
      resolution={resolution}
      structure={structureQuery.data}
    />
  );
}





