"use client";

import { useMemo, useState, type ReactNode } from "react";

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
import { getStageFormatLabel } from "@/features/competitions/utils/competition-structure";
import { fetchMatchesList } from "@/features/matches/services/matches.service";
import type { MatchesListData } from "@/features/matches/types";
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

const HISTORICAL_HERO_TEST_IMAGE_SRC = "/images/competition-season/champion-celebration-test.jpg";

function formatKickoff(value: string | null | undefined): string {
  if (!value) {
    return "Data nao informada";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Data nao informada";
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

  const primaryTransition = stage.transitions[0];
  const slotCount = resolveTransitionSlotCount(stage);
  const targetLabel = primaryTransition?.toStageName ?? primaryTransition?.toStageId ?? "mata-mata";

  if (!slotCount) {
    return targetLabel;
  }

  if (stage.stageFormat === "group_table" && stage.groups.length > 0) {
    return `${slotCount} por grupo avancam para ${targetLabel}`;
  }

  return `${slotCount} vagas para ${targetLabel}`;
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
    return "Jogo unico";
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
  description: string;
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
        <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">{description}</p>
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
                alt={`Logo da competicao ${context.competitionName}`}
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
  minutesPlayed: number | null;
  teamId?: string | null;
  teamName?: string | null;
};

type HistoricalTopScorerData = {
  scorer: HistoricalTopScorer | null;
};

function compareHistoricalTopScorers(left: RankingTableRow, right: RankingTableRow): number {
  const leftGoals = typeof left.metricValue === "number" && Number.isFinite(left.metricValue) ? left.metricValue : Number.NEGATIVE_INFINITY;
  const rightGoals = typeof right.metricValue === "number" && Number.isFinite(right.metricValue) ? right.metricValue : Number.NEGATIVE_INFINITY;

  if (leftGoals !== rightGoals) {
    return rightGoals - leftGoals;
  }

  const leftMinutes =
    typeof left.minutesPlayed === "number" && Number.isFinite(left.minutesPlayed) ? left.minutesPlayed : Number.POSITIVE_INFINITY;
  const rightMinutes =
    typeof right.minutesPlayed === "number" && Number.isFinite(right.minutesPlayed) ? right.minutesPlayed : Number.POSITIVE_INFINITY;

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

async function fetchEditionTopScorer(context: CompetitionSeasonContext): Promise<ApiResponse<HistoricalTopScorerData>> {
  const rankingDefinition = getRankingDefinition("player-goals");

  if (!rankingDefinition) {
    return {
      data: { scorer: null },
      meta: {
        coverage: {
          label: "Ranking player-goals indisponivel no registry.",
          status: "unknown",
        },
      },
    };
  }

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
        minSampleValue: 0,
        page,
        pageSize: 100,
        seasonId: context.seasonId,
        sortDirection: "desc",
      },
    });

    firstResponse ??= response;
    rows.push(...(response.data.rows ?? []));
    totalPages = response.meta?.pagination?.totalPages ?? 1;
    page += 1;
  } while (page <= totalPages);

  const scorerRow = [...rows].sort(compareHistoricalTopScorers)[0] ?? null;

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
            minutesPlayed:
              typeof scorerRow.minutesPlayed === "number" && Number.isFinite(scorerRow.minutesPlayed)
                ? scorerRow.minutesPlayed
                : null,
            teamId: typeof scorerRow.teamId === "string" ? scorerRow.teamId : null,
            teamName: typeof scorerRow.teamName === "string" ? scorerRow.teamName : null,
          }
        : null,
    },
    meta: firstResponse?.meta,
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
    normalizedValue.includes("last_16") ||
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

  return value ?? "o mata-mata";
}

function resolveHybridStructureHeadline(
  resolution: CompetitionSeasonSurfaceResolution,
): string {
  if (resolution.primaryTableStage?.stageFormat === "group_table") {
    return "Fase de grupos -> mata-mata";
  }

  if (resolution.primaryTableStage?.stageFormat === "league_table") {
    return "Fase classificatoria -> mata-mata";
  }

  return "Fase de tabela -> mata-mata";
}

function resolveHybridStructureDetail(stage: CompetitionStructureStage | null): string {
  if (!stage || stage.transitions.length === 0) {
    return "Transicao consolidada para o mata-mata.";
  }

  const slotCount = resolveTransitionSlotCount(stage);
  const transitionTarget = formatHybridStageTargetLabel(
    stage.transitions[0]?.toStageName ?? stage.transitions[0]?.toStageId,
  );

  if (stage.stageFormat === "group_table" && slotCount) {
    return `${slotCount} avancam por grupo ate ${transitionTarget}`;
  }

  if (slotCount) {
    return `${slotCount} equipes avancam ate ${transitionTarget}`;
  }

  return `Transicao consolidada ate ${transitionTarget}`;
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

function resolveLeagueMatchCountFromStandings(rows: StandingsTableRow[]): number | null {
  if (rows.length === 0) {
    return null;
  }

  const totalMatchesPlayed = rows.reduce((sum, row) => sum + row.matchesPlayed, 0);

  if (!Number.isFinite(totalMatchesPlayed) || totalMatchesPlayed <= 0 || totalMatchesPlayed % 2 !== 0) {
    return null;
  }

  return totalMatchesPlayed / 2;
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
  const src = playerId ? `/api/visual-assets/players/${encodeURIComponent(playerId)}` : null;
  const initials = playerName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-emerald-400/30 bg-[#003526]"
      style={{ width: size, height: size }}
    >
      <span className="text-sm font-bold text-white/70">{initials}</span>
      {src ? (
        <img
          alt={playerName}
          className="absolute inset-0 h-full w-full object-cover bg-[#003526]"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
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
            <th className="py-3.5 px-3 text-center text-[0.68rem] font-bold uppercase tracking-widest text-[#515f74]" title="Vitorias">V</th>
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
                className="transition-colors hover:bg-[#f0f3ff]"
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
  title,
}: {
  context: CompetitionSeasonContext;
  description: string;
  query: ReturnType<typeof useSeasonFinalStandings> | ReturnType<typeof useStandingsTable>;
  rowsLimit?: number;
  title: string;
}) {
  const rows = rowsLimit ? query.data?.rows.slice(0, rowsLimit) ?? [] : query.data?.rows ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[0.7rem] font-bold uppercase tracking-widest text-[#515f74]">{title}</p>
          <p className="mt-1 max-w-2xl text-sm text-[#515f74]">{description}</p>
        </div>
        {query.coverage.status !== "complete" ? (
          <ProfileCoveragePill coverage={query.coverage} />
        ) : null}
      </div>

      {query.isError && rows.length === 0 ? (
        <ProfileAlert title="Nao foi possivel carregar a classificacao final" tone="critical">
          Tente novamente em instantes.
        </ProfileAlert>
      ) : null}

      {query.isPartial ? (
        <PartialDataBanner
          className="rounded-xl border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={query.coverage}
          message="Cobertura parcial: a classificacao pode estar incompleta."
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
          description="Classificacao indisponivel."
          title="Sem classificacao"
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
        eyebrow="Partidas concluidas"
        title={title}
      />

      {matchesQuery.isError && matches.length === 0 ? (
        <ProfileAlert title="Nao foi possivel carregar as partidas marcantes" tone="critical">
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
                    {match.homeTeamName ?? "Mandante"} vs {match.awayTeamName ?? "Visitante"}
                  </p>
                  <p className="mt-1 text-sm text-[#57657a]">{formatKickoff(match.kickoffAt)}</p>
                </div>
                <div className="text-right">
                  <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {typeof match.homeScore === "number" && typeof match.awayScore === "number"
                      ? `${match.homeScore} - ${match.awayScore}`
                      : "VS"}
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
  description: string;
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
          Os confrontos desta etapa nao puderam ser carregados agora.
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
          {column.stageState.stage.stageName ?? column.stageState.stage.stageId}
        </p>
        {column.stageState.isError ? (
          <ProfileAlert title="Fase indisponivel" tone="warning">
            Nao foi possivel montar esta coluna.
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
            description="Nao ha fases eliminatorias suficientes para montar o chaveamento."
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
                    {snapshotState.finalStage?.stage.stageName ?? "Final"}
                  </p>

                  {snapshotState.finalStage?.isLoading ? <LoadingSkeleton height={180} /> : null}

                  {snapshotState.finalStage?.isError ? (
                    <ProfileAlert title="Final indisponivel" tone="warning">
                      Nao foi possivel carregar o confronto decisivo.
                    </ProfileAlert>
                  ) : null}

                  {!snapshotState.finalStage?.isLoading && !snapshotState.finalStage?.isError && (snapshotState.finalStage?.ties.length ?? 0) === 0 ? (
                    <EmptyState
                      className="mt-4 rounded-[1.2rem] border-white/10 bg-white/8 text-white"
                      description="Sem confronto consolidado para a decisao."
                      title="Final indisponivel"
                    />
                  ) : null}

                  {!snapshotState.finalStage?.isLoading && !snapshotState.finalStage?.isError && (snapshotState.finalStage?.ties.length ?? 0) > 0 ? (
                    (() => {
                      const tie = snapshotState.finalStage?.ties[0];
                      const championName = tie?.winnerTeamName ?? "Campeao";
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
                                <div className="flex items-center justify-between gap-2.5">
                                  <div className="flex min-w-0 items-center gap-2.5">
                                    <TeamBadge size={32} teamId={team.teamId} teamName={team.teamName} />
                                    <span className={team.isWinner ? "truncate text-[1rem] font-extrabold text-white" : "truncate text-[1rem] font-semibold text-white/88"}>
                                      {team.teamName}
                                    </span>
                                  </div>
                                  <span className="font-[family:var(--font-profile-headline)] text-[1.9rem] font-extrabold leading-none text-white">
                                    {team.goals}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="rounded-[1rem] border border-[rgba(166,242,209,0.16)] bg-[rgba(255,255,255,0.06)] px-3 py-3">
                            <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                              Campeao
                            </p>
                            <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.52rem] font-extrabold text-white">
                              {championName}
                            </p>
                            <p className="mt-1.5 text-[0.8rem] text-[#d7efe4]">
                              {formatTieResolutionLabel(tie) ?? "Decisao da edicao"} • {formatTieMatchCountLabel(tie.matchCount)}
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
                Etapas preliminares ou de colocacao aparecem fora do bracket principal.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {snapshotState.supportingStages.map((stage) => (
                <div
                  className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-white px-4 py-4"
                  key={`supporting-${stage.stage.stageId}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <ProfileTag>{stage.stage.stageName ?? stage.stage.stageId}</ProfileTag>
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
          description="Nao ha fases eliminatorias suficientes para montar o chaveamento."
          title="Sem chaveamento"
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-4">
          {stages.map((stageState) => (
            <ProfilePanel className="space-y-4" key={stageState.stage.stageId} tone={stageState.stage.isCurrent ? "soft" : "base"}>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{stageState.stage.stageName ?? stageState.stage.stageId}</ProfileTag>
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

function ChampionPathPanel({
  championName,
  context,
  resolution,
}: {
  championName: string | null;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
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

  const pathRows = useMemo(
    () =>
      resolution.knockoutStages.flatMap((stage, index) => {
        const ties = queries[index]?.data?.data?.ties ?? [];
        return ties
          .filter((tie) => championName && tie.winnerTeamName === championName)
          .map((tie) => ({
            stageName: stage.stageName ?? stage.stageId,
            tie,
          }));
      }),
    [championName, queries, resolution.knockoutStages],
  );

  return (
    <ProfilePanel className="space-y-4" tone="soft">
      <SeasonSectionHeader
        description="Confrontos do campeao em cada fase eliminatoria."
        eyebrow="Caminho do campeao"
        title={championName ? `${championName} ate o titulo` : "Progressao do campeao"}
      />

      {pathRows.length === 0 ? (
        <EmptyState
          className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
          description="Caminho do campeao indisponivel."
          title="Sem caminho consolidado"
        />
      ) : (
        <div className="grid gap-3">
          {pathRows.map(({ stageName, tie }) => (
            <div
              className="rounded-[1.2rem] border border-[rgba(191,201,195,0.55)] bg-white/88 px-4 py-4"
              key={`${stageName}-${tie.tieId}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <ProfileTag>{stageName}</ProfileTag>
                {tie.resolutionType ? <ProfileTag>{tie.resolutionType}</ProfileTag> : null}
              </div>
              <p className="mt-3 font-semibold text-[#111c2d]">
                {tie.homeTeamName ?? "Mandante"} {tie.homeGoals} x {tie.awayGoals} {tie.awayTeamName ?? "Visitante"}
              </p>
              <p className="mt-1 text-sm text-[#57657a]">
                {tie.matchCount} jogos{formatDateWindow(tie.firstLegAt, tie.lastLegAt) ? ` • ${formatDateWindow(tie.firstLegAt, tie.lastLegAt)}` : ""}
              </p>
            </div>
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
      <ProfileAlert title="Fase classificatoria indisponivel" tone="warning">
        A estrutura atual nao identificou uma fase de tabela para esta edicao.
      </ProfileAlert>
    );
  }

  if (groupQueries.length === 0 || (groupQueriesSettled && !hasGroupRows)) {
    return (
      <FinalStandingsPanel
        context={context}
        description="A fase classificatoria desta edicao foi encerrada e a tabela final segue como referencia central."
        query={finalStandingsQuery}
        title={stage.stageName ?? "Fase classificatoria"}
      />
    );
  }

  return (
    <ProfilePanel className="space-y-5">
      <SeasonSectionHeader
        description="Cada grupo mostra a classificacao final da fase classificatoria, sem tratar a edicao como temporada em andamento."
        eyebrow="Fase classificatoria"
        title={stage.stageName ?? "Fase classificatoria"}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {groupQueries.map((groupQuery) => (
          <ProfilePanel className="space-y-4" key={groupQuery.group.groupId} tone="soft">
            <SeasonSectionHeader
              coverage={groupQuery.coverage}
              description="Classificacao final do grupo."
              eyebrow="Grupo"
              title={groupQuery.group.groupName ?? groupQuery.group.groupId}
            />

            {groupQuery.isError ? (
              <ProfileAlert title="Nao foi possivel carregar este grupo" tone="warning">
                Tente novamente em instantes.
              </ProfileAlert>
            ) : null}

            {groupQuery.isLoading ? <LoadingSkeleton height={220} /> : null}

            {!groupQuery.isLoading && !groupQuery.isError && (groupQuery.data?.rows.length ?? 0) === 0 ? (
              <EmptyState
                className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                description="Ainda nao ha linhas suficientes para este grupo."
                title="Sem classificacao"
              />
            ) : null}

            {!groupQuery.isLoading && (groupQuery.data?.rows.length ?? 0) > 0 ? (
              <DataTable
                columns={columns}
                data={groupQuery.data?.rows ?? []}
                emptyDescription="Sem linhas para exibir."
                emptyTitle="Sem classificacao"
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
        <ProfileAlert title="Nao foi possivel carregar este ranking" tone="critical">
          Tente novamente em instantes ou siga para outro destaque da edicao.
        </ProfileAlert>
      ) : null}

      {rankingQuery.isPartial ? (
        <PartialDataBanner
          className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={rankingQuery.coverage}
          message="Este ranking ainda cobre apenas parte da edicao."
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
          description="Ainda nao ha linhas suficientes para esta edicao."
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
          Os destaques principais desta edicao nao puderam ser carregados agora.
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
        <ProfileAlert title="Estrutura indisponivel para analytics avancados" tone="warning">
          Sem a estrutura tipada da edicao, o produto nao consegue abrir comparativos estruturais desta temporada.
        </ProfileAlert>
      )}
    </div>
  );
}

function LeagueOverviewSection({ context }: { context: CompetitionSeasonContext }) {
  const finalStandingsQuery = useSeasonFinalStandings(context);
  const { roundId } = useGlobalFiltersState();

  return (
    <div className="space-y-5">
      {roundId ? (
        <ProfileAlert title="Resumo da edicao acima do filtro de rodada" tone="info">
          O resumo principal desta surface permanece na classificacao final da edicao. O filtro de rodada segue preservado para listas, rankings e saidas externas.
        </ProfileAlert>
      ) : null}

      <FinalStandingsPanel
        context={context}
        description="A leitura principal da liga encerrada comeca na tabela final. Sem semantica inventada para zonas que o contrato atual nao sustenta."
        query={finalStandingsQuery}
        title="Classificacao final"
      />
    </div>
  );
}

function SeasonFactsCard({
  context,
}: {
  context: CompetitionSeasonContext;
}) {
  const standingsQuery = useSeasonFinalStandings(context);
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const closingMatchesQuery = useSeasonClosingMatches(context, 1);
  const champion = resolveChampionFromStandings(standingsQuery.data?.rows ?? []);
  const analyticsMatchCount = analyticsQuery.data?.seasonSummary.matchCount;
  const standingsMatchCount = resolveLeagueMatchCountFromStandings(standingsQuery.data?.rows ?? []);
  const resolvedMatchCount = analyticsMatchCount ?? standingsMatchCount;
  const lastMatchDate = closingMatchesQuery.data?.items[0]?.kickoffAt ?? null;
  const lastMatchFormatted = lastMatchDate
    ? DATE_FORMATTER.format(new Date(lastMatchDate))
    : null;

  const facts: Array<{ label: string; value: string }> = [
    {
      label: "Campeao",
      value: standingsQuery.isLoading
        ? "..."
        : (champion?.teamName ?? "Nao identificado"),
    },
    {
      label: "Partidas",
      value:
        analyticsQuery.isLoading && standingsQuery.isLoading
          ? "..."
          : formatHistoricalMatchCount(resolvedMatchCount),
    },
    {
      label: "Times",
      value: standingsQuery.isLoading
        ? "..."
        : (standingsQuery.data?.rows.length
            ? String(standingsQuery.data.rows.length)
            : "-"),
    },
    {
      label: "Encerramento",
      value:
        closingMatchesQuery.isLoading
          ? "..."
          : (lastMatchFormatted ?? "-"),
    },
  ];

  return (
    <ProfilePanel className="space-y-4">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Edicao</p>
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
    </ProfilePanel>
  );
}

function ClosingMatchesRailPanel({ context }: { context: CompetitionSeasonContext }) {
  const matchesQuery = useSeasonClosingMatches(context, 4);
  const matches = matchesQuery.data?.items ?? [];

  return (
    <ProfilePanel className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Fechamento</p>
          <p className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
            Ultimas partidas
          </p>
        </div>
        {matchesQuery.coverage.status !== "complete" ? (
          <ProfileCoveragePill coverage={matchesQuery.coverage} />
        ) : null}
      </div>

      {matchesQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <LoadingSkeleton height={72} key={`rail-match-loading-${i}`} />
          ))}
        </div>
      ) : null}

      {!matchesQuery.isLoading && matches.length === 0 ? (
        <EmptyState
          className="rounded-[1.1rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Sem partidas registradas."
          title="Sem partidas"
        />
      ) : null}

      {!matchesQuery.isLoading && matches.length > 0 ? (
        <div className="space-y-2">
          {matches.map((match) => (
            <Link
              className="block rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-3 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
              href={`/matches/${encodeURIComponent(match.matchId)}?competitionId=${encodeURIComponent(context.competitionId)}&seasonId=${encodeURIComponent(context.seasonId)}`}
              key={match.matchId}
            >
              <p className="text-[0.65rem] uppercase tracking-[0.14em] text-[#57657a]">
                {resolveMatchDisplayContext(match).summary}
              </p>
              <p className="mt-1.5 text-sm font-semibold text-[#111c2d]">
                {match.homeTeamName ?? "Mandante"}{" "}
                <span className="font-normal text-[#57657a]">
                  {typeof match.homeScore === "number" && typeof match.awayScore === "number"
                    ? `${match.homeScore}–${match.awayScore}`
                    : "vs"}
                </span>{" "}
                {match.awayTeamName ?? "Visitante"}
              </p>
            </Link>
          ))}
        </div>
      ) : null}
    </ProfilePanel>
  );
}

function ExploreEditionCard({ context }: { context: CompetitionSeasonContext }) {
  const filterInput = useSeasonFilterInput(context);

  const links: Array<{ href: string; label: string; hint: string }> = [
    { href: buildMatchesPath(filterInput), label: "Partidas", hint: "Lista completa da edicao" },
    { href: buildRankingPath("player-goals", filterInput), label: "Rankings", hint: "Artilharia e estatisticas" },
    { href: buildTeamsPath(filterInput), label: "Times", hint: "Perfis canonicos da edicao" },
  ];

  return (
    <ProfilePanel className="space-y-4" tone="soft">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Exploracao</p>
        <p className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
          Aprofunde a edicao
        </p>
      </div>
      <div className="space-y-2">
        {links.map((link) => (
          <Link
            className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-white/80 px-4 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
            href={link.href}
            key={link.label}
          >
            <div>
              <p className="text-sm font-semibold text-[#111c2d]">{link.label}</p>
              <p className="text-[0.68rem] text-[#57657a]">{link.hint}</p>
            </div>
            <span className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">→</span>
          </Link>
        ))}
      </div>
    </ProfilePanel>
  );
}

// ─── Copa / Híbrido — Hero Banner escuro ─────────────────────────────────────

function CupHeroBanner({
  context,
  tag,
}: {
  context: CompetitionSeasonContext;
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
    <div className="relative h-56 overflow-hidden rounded-xl bg-[#022e21] md:h-64">
      <div className="absolute inset-0 bg-gradient-to-r from-[#011a13] via-[#022e21]/80 to-transparent" />
      <div className="absolute -right-12 -top-12 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
      <div className="absolute bottom-0 left-1/3 h-48 w-48 rounded-full bg-emerald-600/10 blur-3xl" />

      <div className="relative z-10 flex h-full items-center gap-8 px-8 md:px-10">
        <div className="relative flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[rgba(191,201,195,0.55)] bg-white shadow-2xl md:h-28 md:w-28">
          <span className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#003526]">
            {initials || "FA"}
          </span>
          {logoSrc ? (
            <img
              alt={`Logo ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-contain bg-white p-3"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
              src={logoSrc}
            />
          ) : null}
        </div>

        <div className="space-y-3">
          <span className="inline-block rounded-full bg-emerald-500 px-3 py-1 text-[0.65rem] font-extrabold uppercase tracking-[0.2em] text-white">
            {tag}
          </span>
          <h1 className="font-[family:var(--font-profile-headline)] text-[2.6rem] font-extrabold leading-none tracking-[-0.04em] text-white md:text-[3.2rem]">
            {context.competitionName}
          </h1>
          <p className="text-sm font-medium italic text-emerald-200/70">
            {context.seasonLabel}
          </p>
        </div>
      </div>
    </div>
  );
}

function CupKpiStrip({
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
  const matchCount = analyticsQuery.data?.seasonSummary.matchCount;
  const knockoutCount = resolution.knockoutStages.length;
  const coverageStatus = analyticsQuery.isLoading
    ? "Calculando"
    : analyticsQuery.coverage.status === "complete"
      ? "Total"
      : "Parcial";
  const isCoverageTotal = analyticsQuery.coverage.status === "complete";

  return (
    <div className="flex flex-wrap gap-3">
      <div className="rounded-xl bg-[#f0f3ff] px-6 py-4">
        <p className="text-[0.65rem] font-bold uppercase tracking-widest text-[#515f74]">
          {resolution.type === "hybrid" ? "Fases" : "Fases eliminatorias"}
        </p>
        <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
          {knockoutCount > 0 ? String(knockoutCount).padStart(2, "0") : "--"}
        </p>
      </div>
      <div className="rounded-xl bg-[#f0f3ff] px-6 py-4">
        <p className="text-[0.65rem] font-bold uppercase tracking-widest text-[#515f74]">Partidas</p>
        <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
          {analyticsQuery.isLoading ? "..." : formatHistoricalMatchCount(matchCount)}
        </p>
      </div>
      <div className={`rounded-xl px-6 py-4 ${isCoverageTotal ? "bg-[#a6f2d1]" : "bg-[#f0f3ff]"}`}>
        <p className="text-[0.65rem] font-bold uppercase tracking-widest text-[#00513b]">Cobertura</p>
        <div className="mt-1 flex items-center gap-1">
          <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold uppercase text-[#003526]">
            {analyticsQuery.isLoading ? "..." : coverageStatus}
          </p>
          {isCoverageTotal ? <span className="text-lg text-[#003526]">✓</span> : null}
        </div>
      </div>
    </div>
  );
}

// ─── Rail cards visuais ───────────────────────────────────────────────────────

function TopScorerRailCard({ context }: { context: CompetitionSeasonContext }) {
  const scorerQuery = useEditionTopScorer(context);
  const scorer = scorerQuery.data?.scorer ?? null;
  const scorerHref = scorer ? buildCanonicalPlayerPath(context, scorer.entityId) : null;

  return (
    <div className="relative overflow-hidden rounded-xl bg-[#003526] p-5 text-white">
      <div className="absolute right-0 top-0 h-24 w-24 rounded-full bg-emerald-400/10 blur-3xl" />
      <p className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-emerald-400">
        Artilheiro da temporada
      </p>

      <div className="mt-4">
        {scorerQuery.isLoading ? (
          <div className="flex items-center gap-3">
            <div className="h-14 w-14 animate-pulse rounded-full bg-white/10" />
            <div className="space-y-2 flex-1">
              <div className="h-5 w-32 animate-pulse rounded bg-white/10" />
              <div className="h-4 w-20 animate-pulse rounded bg-white/10" />
            </div>
          </div>
        ) : scorer ? (
          <div className="flex items-center gap-4">
            <PlayerPhoto playerId={scorer.entityId} playerName={scorer.entityName} size={56} />
            <div className="space-y-0.5 min-w-0">
              {scorerHref ? (
                <Link
                  className="block font-[family:var(--font-profile-headline)] text-xl font-extrabold leading-tight text-white transition-opacity hover:opacity-80 truncate"
                  href={scorerHref}
                >
                  {scorer.entityName}
                </Link>
              ) : (
                <p className="font-[family:var(--font-profile-headline)] text-xl font-extrabold leading-tight truncate">
                  {scorer.entityName}
                </p>
              )}
              {scorer.teamName ? (
                <p className="text-xs font-medium uppercase tracking-wide text-emerald-400/80 truncate">
                  {scorer.teamName}
                </p>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm font-medium text-white/60">Não identificado</p>
        )}
      </div>

      {scorer ? (
        <div className="mt-5 flex items-end justify-between border-t border-white/10 pt-4">
          <div>
            <p className="text-[0.6rem] font-bold uppercase tracking-widest text-emerald-400/60">Gols</p>
            <p className="font-[family:var(--font-profile-headline)] text-4xl font-black">
              {String(scorer.goals).padStart(2, "0")}
            </p>
          </div>
          {scorer.minutesPlayed ? (
            <div className="text-right">
              <p className="text-[0.6rem] font-bold uppercase tracking-widest text-emerald-400/60">Minutos</p>
              <p className="font-[family:var(--font-profile-headline)] text-xl font-bold">
                {Math.round(scorer.minutesPlayed).toLocaleString("pt-BR")}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function LastResultsRailCard({ context }: { context: CompetitionSeasonContext }) {
  const matchesQuery = useSeasonClosingMatches(context, 3);
  const matches = matchesQuery.data?.items ?? [];

  return (
    <div className="rounded-xl bg-[#f0f3ff] p-5">
      <p className="text-[0.65rem] font-extrabold uppercase tracking-widest text-[#003526]">
        Ultimos resultados
      </p>
      <div className="mt-4 space-y-2">
        {matchesQuery.isLoading ? (
          Array.from({ length: 3 }, (_, i) => (
            <div className="h-10 animate-pulse rounded-lg bg-[#e7eeff]" key={`lr-skel-${i}`} />
          ))
        ) : matches.length === 0 ? (
          <p className="text-xs text-[#515f74]">Sem resultados registrados.</p>
        ) : (
          matches.map((match) => (
            <Link
              className="flex items-center justify-between rounded-lg bg-white px-3 py-2.5 text-xs font-bold shadow-sm transition-colors hover:bg-[#f9f9ff]"
              href={`/matches/${encodeURIComponent(match.matchId)}?competitionId=${encodeURIComponent(context.competitionId)}&seasonId=${encodeURIComponent(context.seasonId)}`}
              key={match.matchId}
            >
              <span className="max-w-[90px] truncate text-[#111c2d]">{match.homeTeamName ?? "Mandante"}</span>
              <span className="mx-2 shrink-0 rounded bg-[#f0f3ff] px-2 py-0.5 text-[0.7rem] font-bold text-[#003526]">
                {typeof match.homeScore === "number" && typeof match.awayScore === "number"
                  ? `${match.homeScore} - ${match.awayScore}`
                  : "vs"}
              </span>
              <span className="max-w-[90px] truncate text-right text-[#111c2d]">{match.awayTeamName ?? "Visitante"}</span>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

function LeagueEditionRail({ context }: { context: CompetitionSeasonContext }) {
  return (
    <>
      <SeasonFactsCard context={context} />
      <TopScorerRailCard context={context} />
      <LastResultsRailCard context={context} />
      <ExploreEditionCard context={context} />
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
        description="A classificacao final da edicao e a ancora principal da leitura da liga."
        query={finalStandingsQuery}
        title="Classificacao final"
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
  championTieQuery,
  context,
  resolution,
}: {
  championTieQuery: ReturnType<typeof useStageTies>;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);

  return (
    <ChampionPathPanel
      championName={championTie?.winnerTeamName ?? null}
      context={context}
      resolution={resolution}
    />
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
      description="Chaveamento completo da edicao."
      resolution={resolution}
      title="Chaveamento finalizado"
    />
  );
}

function CupFactsCard({
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

  const facts: Array<{ label: string; value: string }> = [
    {
      label: "Campeao",
      value: championTieQuery.isLoading
        ? "..."
        : (championTie?.winnerTeamName ?? "Nao identificado"),
    },
    {
      label: "Partidas",
      value: analyticsQuery.isLoading
        ? "..."
        : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount),
    },
    {
      label: "Fases eliminatorias",
      value: resolution.knockoutStages.length > 0
        ? String(resolution.knockoutStages.length)
        : "-",
    },
    {
      label: "Formato",
      value: resolution.editionLabel ?? "Copa",
    },
  ];

  return (
    <ProfilePanel className="space-y-4">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Edicao</p>
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
    </ProfilePanel>
  );
}

function CupEditionRail({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  return (
    <>
      <CupFactsCard context={context} resolution={resolution} />
      <ClosingMatchesRailPanel context={context} />
      <ExploreEditionCard context={context} />
    </>
  );
}

// ─── Bloco 5 — Canvas do hibrido ─────────────────────────────────────────────

function HybridActionLink({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  return (
    <Link
      className="inline-flex items-center rounded-full border border-[rgba(191,201,195,0.5)] bg-white px-3 py-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#404944] transition-colors hover:border-[#8bd6b6] hover:bg-[#f0faf6] hover:text-[#003526]"
      href={href}
    >
      {label}
    </Link>
  );
}

function HybridSecondaryActions({ context }: { context: CompetitionSeasonContext }) {
  const filterInput = useSeasonFilterInput(context);

  return (
    <>
      <HybridActionLink href={buildMatchesPath(filterInput)} label="Partidas" />
      <HybridActionLink href={buildRankingPath("player-goals", filterInput)} label="Rankings" />
      <HybridActionLink href={buildTeamsPath(filterInput)} label="Times" />
      <HybridActionLink href={buildPlayersPath(filterInput)} label="Jogadores" />
    </>
  );
}

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
    : championTie?.winnerTeamName ?? "Campeao nao identificado";
  const finalDecisionDate =
    championTie ? formatLongDate(championTie.lastLegAt ?? championTie.firstLegAt) : null;
  const structureHeadline = resolveHybridStructureHeadline(resolution);
  const structureDetail = resolveHybridStructureDetail(resolution.primaryTableStage);
  const matchCount = analyticsQuery.isLoading
    ? "..."
    : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount);
  const topScorer = topScorerQuery.data?.scorer ?? null;
  const topScorerName = topScorerQuery.isLoading ? "..." : (topScorer?.entityName ?? "Artilharia indisponivel");
  const topScorerDetail = topScorer ? (
    <>
      <span className="font-semibold text-[#003526]">{topScorer.goals} gols</span>
      {topScorer.teamName ? ` • ${topScorer.teamName}` : ""}
    </>
  ) : (
    "Ranking historico do torneio nao consolidado."
  );
  const heroImageSrc = championArtwork?.src ?? HISTORICAL_HERO_TEST_IMAGE_SRC;
  const summaryValue = (
    <>
      <span className="font-extrabold text-[#003526]">{matchCount}</span>
      <span className="mx-2 text-[#8fa097]">•</span>
      <span className="font-extrabold text-[#003526]">{resolution.stageCount} fases</span>
    </>
  );

  return (
    <div className="relative overflow-hidden rounded-[1.7rem] border border-[rgba(191,201,195,0.5)] bg-[radial-gradient(circle_at_top_right,rgba(194,241,214,0.42),transparent_26%),linear-gradient(180deg,#f7fbf8_0%,#edf6f1_100%)] px-5 py-5 shadow-[0_34px_80px_-52px_rgba(17,28,45,0.32)] md:px-6 md:py-6">
      <div className="absolute right-[-8%] top-[-18%] h-56 w-56 rounded-full bg-[rgba(5,77,57,0.08)] blur-3xl" />
      <div className="absolute bottom-[-24%] left-[14%] h-48 w-48 rounded-full bg-[rgba(166,242,209,0.22)] blur-3xl" />

      <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.96fr)] xl:items-stretch">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            {["Edicao encerrada", "Hibrida"].map((tag) => (
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
              Resumo da edicao
            </p>
            <div className="mt-4">
              <HybridHeroSummaryItem
                label="Campeao"
                media={championTie ? <TeamBadge size={44} teamId={championTie.winnerTeamId} teamName={championName} /> : null}
                value={championName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[2.05rem] font-extrabold leading-none tracking-[-0.05em] text-[#111c2d]"
              />
              <HybridHeroSummaryItem
                label="Final"
                value={finalDecisionDate ?? "Data nao informada"}
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
          {!isHeroPhotoUnavailable ? (
            <img
              alt={`Celebracao do campeao da ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-cover"
              onError={() => setIsHeroPhotoUnavailable(true)}
              src={heroImageSrc}
            />
          ) : null}
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,24,18,0.12)_0%,rgba(3,24,18,0.44)_48%,rgba(3,24,18,0.78)_100%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,224,130,0.2),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(166,242,209,0.18),transparent_26%)]" />

          {isHeroPhotoUnavailable ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-28 w-28 rounded-full border border-white/16 bg-white/10 blur-[1px]" />
            </div>
          ) : null}

          <div className="absolute inset-x-4 bottom-4">
            <div className="rounded-[1.3rem] border border-white/12 bg-[rgba(7,24,18,0.52)] px-4 py-4 backdrop-blur-sm">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#bfe6d6]">
                Campeao
              </p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold leading-none tracking-[-0.04em] text-white">
                {championName}
              </p>
              <p className="mt-2 text-sm text-[#d7efe4]">
                {finalDecisionDate ?? "Data da final nao informada"}
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
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
          Leitura da edicao
        </p>
        <h2 className="font-[family:var(--font-profile-headline)] text-[1.7rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
          {structureHeadline}
        </h2>
        <p className="text-sm/6 text-[#57657a]">{structureDetail}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
          {resolution.stageCount} fases
        </span>
        <span className="rounded-full border border-[rgba(191,201,195,0.52)] bg-[rgba(240,243,255,0.88)] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
          {matchCount} partidas
        </span>
      </div>
    </div>
  );
}

function HybridHighlightLink({
  description,
  href,
  label,
}: {
  description: string;
  href: string;
  label: string;
}) {
  return (
    <Link
      className="rounded-[1.3rem] border border-[rgba(191,201,195,0.52)] bg-white px-4 py-4 transition-[transform,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5 hover:border-[#8bd6b6] hover:shadow-[0_22px_58px_-42px_rgba(17,28,45,0.22)] active:scale-[0.985]"
      href={href}
    >
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">Destaque</p>
      <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
        {label}
      </h3>
      <p className="mt-2 text-sm/6 text-[#57657a]">{description}</p>
      <p className="mt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
        Abrir
      </p>
    </Link>
  );
}

function HybridHighlightsPanel({
  context,
}: {
  context: CompetitionSeasonContext;
}) {
  const filterInput = useSeasonFilterInput(context);
  const searchParams = useSearchParams();

  return (
    <ProfilePanel className="space-y-4">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Destaques da edicao</p>
        <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[1.9rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
          Exploracoes prioritarias
        </h2>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <HybridHighlightLink
          description="Artilharia completa e recorte ofensivo da temporada."
          href={buildRankingPath("player-goals", filterInput)}
          label="Artilharia completa"
        />
        <HybridHighlightLink
          description="Progressao do campeao no mata-mata ate a decisao."
          href={buildSeasonSurfaceHref(context, "matches", searchParams)}
          label="Caminho do campeao"
        />
        <HybridHighlightLink
          description="Perfis e contexto das equipes registradas na edicao."
          href={buildTeamsPath(filterInput)}
          label="Times participantes"
        />
      </div>
    </ProfilePanel>
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
      <ProfileAlert title="Fase de tabela indisponivel" tone="warning">
        A estrutura atual nao identificou uma fase classificatoria para esta edicao.
      </ProfileAlert>
    );
  }

  if (isGroupTable) {
    const previewCount = Math.min(Math.max(transitionSlots ?? 2, 2), 3);
    const groupQueriesSettled =
      groupQueries.length > 0 && groupQueries.every((groupQuery) => !groupQuery.isLoading);
    const hasGroupRows = groupQueries.some((groupQuery) => (groupQuery.data?.rows.length ?? 0) > 0);

    if (groupQueries.length === 0 || (groupQueriesSettled && !hasGroupRows)) {
      return (
        <FinalStandingsPanel
          context={context}
          description="A classificacao final da fase de grupos segue como referencia principal desta edicao encerrada."
          query={finalStandingsQuery}
          title={stage.stageName ?? resolveHybridTableSectionLabel(stage)}
        />
      );
    }

    return (
      <ProfilePanel className="space-y-5">
        <SeasonSectionHeader
          description="Leitura sintetica dos grupos, com foco em classificacao final e transicao para o mata-mata."
          eyebrow="Fase de tabela"
          title={stage.stageName ?? resolveHybridTableSectionLabel(stage)}
        />

        <div className="grid gap-3 md:grid-cols-3">
          <HistoricalHeroCard
            detail="Grupos consolidados na estrutura da edicao."
            label="Grupos"
            tone="soft"
            value={String(stage.groups.length)}
          />
          <HistoricalHeroCard
            detail={transitionSlots ? "Numero de vagas por grupo para a etapa seguinte." : "Sem regra de progressao consolidada."}
            label="Corte"
            tone="soft"
            value={transitionSlots ? `${transitionSlots} por grupo` : "-"}
          />
          <HistoricalHeroCard
            detail={transitionSummary ?? "Sem transicao consolidada para a fase seguinte."}
            label="Transicao"
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
                  description="Classificacao final do grupo."
                  eyebrow="Grupo"
                  title={groupQuery.group.groupName ?? groupQuery.group.groupId}
                />

                {groupQuery.isError ? (
                  <ProfileAlert title="Grupo indisponivel" tone="warning">
                    Nao foi possivel consolidar este grupo agora.
                  </ProfileAlert>
                ) : null}

                {groupQuery.isLoading ? <LoadingSkeleton height={156} /> : null}

                {!groupQuery.isLoading && !groupQuery.isError && previewRows.length === 0 ? (
                  <EmptyState
                    className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                    description="Sem classificacao suficiente neste grupo."
                    title="Sem classificacao"
                  />
                ) : null}

                {!groupQuery.isLoading && !groupQuery.isError && previewRows.length > 0 ? (
                  <div className="space-y-3">
                    {previewRows.map((row) => (
                      <div
                        className="flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.42)] bg-white px-3 py-3"
                        key={`${groupQuery.group.groupId}-${row.teamId}`}
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
                            {row.matchesPlayed} PJ
                          </p>
                        </div>
                      </div>
                    ))}
                    {rows.length > previewRows.length ? (
                      <p className="text-xs text-[#57657a]">
                        +{rows.length - previewRows.length} equipes no fechamento deste grupo.
                      </p>
                    ) : null}
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
        description="Tabela final da fase classificatoria, com foco no corte para o mata-mata."
        eyebrow="Fase de tabela"
        title={stage.stageName ?? resolveHybridTableSectionLabel(stage)}
      />

      <div className="grid gap-3 md:grid-cols-3">
        <HistoricalHeroCard
          detail="Equipes classificadas na fase unica."
          label="Equipes"
          tone="soft"
          value={String(rows.length || stage.expectedTeams || 0)}
        />
        <HistoricalHeroCard
          detail={transitionSummary ?? "Sem regra de progressao consolidada."}
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
        <ProfileAlert title="Fase classificatoria indisponivel" tone="warning">
          Nao foi possivel carregar a tabela final desta etapa.
        </ProfileAlert>
      ) : null}

      {finalStandingsQuery.isLoading ? <LoadingSkeleton height={220} /> : null}

      {!finalStandingsQuery.isLoading && !finalStandingsQuery.isError && previewRows.length === 0 ? (
        <EmptyState
          className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
          description="Sem linhas consolidadas para esta fase."
          title="Sem classificacao"
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
      <HybridHighlightsPanel context={context} />
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
      label: "Campeao",
      value: championTieQuery.isLoading
        ? "..."
        : (championTie?.winnerTeamName ?? "Nao identificado"),
    },
    {
      label: "Partidas",
      value: analyticsQuery.isLoading
        ? "..."
        : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount),
    },
    {
      label: tableSectionLabel,
      value: groupCount > 0 ? `${groupCount} grupos` : (resolution.primaryTableStage?.stageName ?? "-"),
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
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">Edicao</p>
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
            {resolution.editionLabel ?? "Formato hibrido"}
          </p>
        </div>
        <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.56)] px-3 py-3">
          <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Decisao</p>
          <p className="mt-1 text-sm font-semibold text-[#111c2d]">
            {resolution.finalKnockoutStage?.stageName ?? "Nao identificado"}
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
      <ClosingMatchesRailPanel context={context} />
      <ExploreEditionCard context={context} />
    </>
  );
}

function buildSurfaceNavLabels(
  resolution: CompetitionSeasonSurfaceResolution,
): SurfaceNavLabels {
  if (resolution.type === "league") {
    return {
      highlights: "Destaques estatisticos",
      matches: "Partidas de fechamento",
      overview: "Classificacao",
      structure: "Tabela completa",
    };
  }

  if (resolution.type === "hybrid") {
    return {
      highlights: "Destaques estatisticos",
      matches: "Mata-mata",
      overview: "Visao geral",
      structure: resolveHybridNavigationStructureLabel(resolution.primaryTableStage),
    };
  }

  return {
    highlights: "Destaques estatisticos",
    matches: "Confrontos decisivos",
    overview: "Caminho do titulo",
    structure: "Chaveamento",
  };
}

function LeaguePageHeader({
  context,
  tag,
}: {
  context: CompetitionSeasonContext;
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
    <div className="flex items-end gap-6 px-4 md:px-8 pt-8 pb-4">
      <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[rgba(191,201,195,0.55)] bg-white shadow-sm md:h-20 md:w-20">
        <span className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
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

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="inline-block rounded bg-[#e7eeff] px-2 py-0.5 text-[0.6rem] font-bold uppercase tracking-widest text-[#003526]">
            {tag}
          </span>
        </div>
        <h1 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-none tracking-[-0.03em] text-[#111c2d] md:text-4xl">
          {context.competitionName}
        </h1>
        <p className="text-sm font-semibold text-[#515f74]">
          Temporada {context.seasonLabel}
        </p>
      </div>
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
        className="flex items-center gap-2 rounded-lg bg-[#003526] px-4 py-2 cursor-pointer shadow-sm transition-transform active:scale-95"
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

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<LeaguePageHeader context={context} tag="Pontos Corridos" />}
      mainCanvas={
        <>
          {activeSection === "overview" ? <LeagueOverviewSection context={context} /> : null}
          {activeSection === "structure" ? <LeagueStructureSection context={context} /> : null}
          {activeSection === "rounds" ? <RoundsSection context={context} /> : null}
          {activeSection === "matches" ? (
            <ClosingMatchesPanel
              context={context}
              description="Partidas concluidas desta temporada."
              title="Partidas marcantes da temporada"
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={null} /> : null}
        </>
      }
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
          href: buildSeasonSurfaceHref(context, "rounds", searchParams),
          isActive: activeSection === "rounds",
          key: "rounds",
          label: "Rodada a Rodada",
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
      secondaryRail={<LeagueEditionRail context={context} />}
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
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const navLabels = buildSurfaceNavLabels(resolution);

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<CupHeroBanner context={context} tag="Copa" />}
      mainCanvas={
        <>
          {activeSection === "overview" ? (
            <><CupKpiStrip context={context} resolution={resolution} /><CupOverviewSection championTieQuery={championTieQuery} context={context} resolution={resolution} /></>
          ) : null}
          {activeSection === "structure" ? <CupStructureSection context={context} resolution={resolution} /> : null}
          {activeSection === "matches" ? (
            <ClosingMatchesPanel
              context={context}
              description="Os confrontos mais importantes da edicao."
              title="Confrontos decisivos"
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={structure} /> : null}
        </>
      }
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
      secondaryRail={<CupEditionRail context={context} resolution={resolution} />}
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
      description="Snapshot do chaveamento, com progressao da fase eliminatoria ate a final."
      resolution={resolution}
      title="Chaveamento ate a final"
      variant="snapshot"
    />
  );
  const matchesBracket = (
    <KnockoutBracketPanel
      context={context}
      description="Fase eliminatoria da edicao."
      resolution={resolution}
      title="Chaveamento final"
      variant="snapshot"
    />
  );

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<HybridHistoricalHero context={context} resolution={resolution} />}
      summaryStrip={activeSection === "overview" ? <HybridStructureStrip context={context} resolution={resolution} /> : null}
      mainCanvas={
        <>
          {activeSection === "overview" ? <HybridOverviewSection context={context} resolution={resolution} /> : null}
          {activeSection === "structure" ? <GroupPhaseSummaryPanel context={context} stage={resolution.primaryTableStage} /> : null}
          {activeSection === "matches" ? matchesBracket : null}
        </>
      }
      navAside={<HybridSecondaryActions context={context} />}
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
      supportingModules={activeSection === "overview" ? overviewBracket : null}
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
            description="Carregando..."
            eyebrow="Carregando"
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
            description="Estrutura da edicao indisponivel."
            eyebrow="Estrutura indisponivel"
            highlightDescription="Tente recarregar a pagina."
            highlightLabel="Estado"
            highlightValue="Estrutura ausente"
            tags={[context.seasonLabel, "Indisponivel"]}
            title={`${context.competitionName} ${context.seasonLabel}`}
          />
        }
        mainCanvas={
          <ProfileAlert title="Nao foi possivel carregar a estrutura da edicao" tone="critical">
            Sem esse contrato nao e possivel diferenciar com seguranca o desenho de copa ou hibrido.
          </ProfileAlert>
        }
        navItems={[
          {
            href: buildSeasonHubPath(context),
            isActive: true,
            key: "overview",
            label: "Resumo da edicao",
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





