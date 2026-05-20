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
  resolveCompetitionSeasonSurface,
  resolveCompetitionSeasonSurfaceSection,
  type CompetitionSeasonSurfaceResolution,
  type CompetitionSeasonSurfaceSection,
} from "@/features/competitions/utils/competition-season-surface";
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

function getSurfaceTypeLabel(resolution: CompetitionSeasonSurfaceResolution): string {
  if (resolution.type === "league") {
    return "Liga";
  }

  if (resolution.type === "hybrid") {
    return "Hibrida";
  }

  return "Copa";
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

function SeasonSectionHeader({
  coverage,
  description,
  eyebrow,
  title,
}: {
  coverage?: CoverageLike;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
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

function EditionSummaryGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 md:grid-cols-3">{children}</div>;
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

function formatHistoricalMatchCount(matchCount: number | null | undefined) {
  if (typeof matchCount !== "number" || !Number.isFinite(matchCount)) {
    return "-";
  }

  return matchCount.toLocaleString("pt-BR");
}

function formatHistoricalMinutes(minutesPlayed: number | null | undefined) {
  if (typeof minutesPlayed !== "number" || !Number.isFinite(minutesPlayed)) {
    return null;
  }

  return `${Math.round(minutesPlayed).toLocaleString("pt-BR")} min`;
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

function HistoricalTopScorerCard({ context }: { context: CompetitionSeasonContext }) {
  const scorerQuery = useEditionTopScorer(context);
  const scorer = scorerQuery.data?.scorer ?? null;
  const scorerHref = scorer ? buildCanonicalPlayerPath(context, scorer.entityId) : null;
  const goalsLabel = scorer ? `${scorer.goals.toLocaleString("pt-BR")} gols` : null;
  const minutesLabel = formatHistoricalMinutes(scorer?.minutesPlayed);
  const detail = scorerQuery.isLoading
    ? "Calculando..."
    : scorerQuery.isError
      ? "Sem dados disponíveis."
      : scorer
        ? [
            goalsLabel,
            minutesLabel,
            scorerQuery.isPartial ? "Cobertura parcial." : null,
            "",
          ]
            .filter(Boolean)
            .join(" • ")
        : "Dados insuficientes.";

  const value = scorerQuery.isLoading ? (
    "..."
  ) : scorer && scorerHref ? (
    <Link className="text-[#003526] transition-colors hover:text-[#054d39] hover:underline" href={scorerHref}>
      {scorer.entityName}
    </Link>
  ) : scorer ? (
    scorer.entityName
  ) : (
    "Nao identificado"
  );

  return (
    <HistoricalHeroCard
      detail={detail}
      label="Artilheiro"
      tone={scorerQuery.isPartial ? "soft" : "base"}
      value={value}
    />
  );
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
}: {
  context: CompetitionSeasonContext;
  description: string;
  resolution: CompetitionSeasonSurfaceResolution;
  title: string;
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

  const stages = useMemo(
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

  const hasPartialCoverage = stages.some((stage) => stage.coverage.status === "partial");

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
          {stages.map(({ stage, ties, isLoading, isError }) => (
            <ProfilePanel className="space-y-4" key={stage.stageId} tone={stage.isCurrent ? "soft" : "base"}>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{stage.stageName ?? stage.stageId}</ProfileTag>
                  {stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stage.stageFormat)}</ProfileTag> : null}
                </div>
              </div>

              {isError ? (
                <ProfileAlert title="Falha ao carregar esta fase" tone="warning">
                  Os confrontos desta etapa nao puderam ser carregados agora.
                </ProfileAlert>
              ) : null}

              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 2 }, (_, index) => (
                    <LoadingSkeleton height={110} key={`${stage.stageId}-loading-${index}`} />
                  ))}
                </div>
              ) : null}

              {!isLoading && !isError && ties.length === 0 ? (
                <EmptyState
                  className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                  description="Sem confrontos."
                  title="Sem confrontos"
                />
              ) : null}

              {!isLoading && ties.length > 0 ? (
                <div className="grid gap-3">
                  {ties.map((tie) => (
                    <div
                      className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4"
                      key={tie.tieId}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <ProfileTag>Confronto {tie.tieOrder}</ProfileTag>
                        {tie.resolutionType ? <ProfileTag>{tie.resolutionType}</ProfileTag> : null}
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
                        <span>{tie.matchCount} jogos</span>
                        {tie.winnerTeamName ? <span>• classificado: {tie.winnerTeamName}</span> : null}
                        {formatDateWindow(tie.firstLegAt, tie.lastLegAt) ? (
                          <span>• {formatDateWindow(tie.firstLegAt, tie.lastLegAt)}</span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
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

  if (!stage) {
    return (
      <ProfileAlert title="Fase classificatoria indisponivel" tone="warning">
        A estrutura atual nao identificou uma fase de tabela para esta edicao.
      </ProfileAlert>
    );
  }

  if (groupQueries.length === 0) {
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

function LeagueHeroSummary({ context }: { context: CompetitionSeasonContext }) {
  const standingsQuery = useSeasonFinalStandings(context);
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const champion = resolveChampionFromStandings(standingsQuery.data?.rows ?? []);
  const analyticsMatchCount = analyticsQuery.data?.seasonSummary.matchCount;
  const standingsMatchCount = resolveLeagueMatchCountFromStandings(standingsQuery.data?.rows ?? []);
  const resolvedMatchCount = analyticsMatchCount ?? standingsMatchCount;

  return (
    <EditionSummaryGrid>
      <HistoricalHeroCard
        detail={
          champion
            ? "Fonte: classificacao final."
            : "Sem lider consolidado na classificacao final."
        }
        label="Campeao"
        value={standingsQuery.isLoading ? "..." : champion?.teamName ?? "Nao identificado"}
      />
      <HistoricalTopScorerCard context={context} />
      <HistoricalHeroCard
        detail={
          analyticsMatchCount !== undefined
            ? "Fonte: analytics da edicao."
            : standingsMatchCount !== null
              ? "Fonte: classificacao final."
              : "Total da edicao indisponivel no contrato atual."
        }
        label="Partidas jogadas"
        value={
          analyticsQuery.isLoading && resolvedMatchCount === null
            ? "..."
            : formatHistoricalMatchCount(resolvedMatchCount)
        }
      />
    </EditionSummaryGrid>
  );
}

function CupHeroSummary({
  context,
  championTieQuery,
}: {
  context: CompetitionSeasonContext;
  championTieQuery: ReturnType<typeof useStageTies>;
}) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);

  return (
    <EditionSummaryGrid>
      <HistoricalHeroCard
        detail={
          championTie?.winnerTeamName
            ? "Fonte: chave final."
            : "Chave final sem vencedor consolidado no contrato atual."
        }
        label="Campeao"
        value={championTieQuery.isLoading ? "..." : championTie?.winnerTeamName ?? "Nao identificado"}
      />
      <HistoricalTopScorerCard context={context} />
      <HistoricalHeroCard
        detail={
          analyticsQuery.data?.seasonSummary.matchCount !== undefined
            ? "Fonte: analytics da edicao."
            : "Total da edicao indisponivel no contrato atual."
        }
        label="Partidas jogadas"
        value={
          analyticsQuery.isLoading
            ? "..."
            : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount)
        }
      />
    </EditionSummaryGrid>
  );
}

function HybridHeroSummary({
  championTieQuery,
  context,
}: {
  championTieQuery: ReturnType<typeof useStageTies>;
  context: CompetitionSeasonContext;
}) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const championTie = resolveChampionTie(championTieQuery.data?.ties ?? []);

  return (
    <EditionSummaryGrid>
      <HistoricalHeroCard
        detail={
          championTie?.winnerTeamName
            ? "Fonte: mata-mata final."
            : "Mata-mata final sem vencedor consolidado no contrato atual."
        }
        label="Campeao"
        value={championTieQuery.isLoading ? "..." : championTie?.winnerTeamName ?? "Nao identificado"}
      />
      <HistoricalTopScorerCard context={context} />
      <HistoricalHeroCard
        detail={
          analyticsQuery.data?.seasonSummary.matchCount !== undefined
            ? "Fonte: analytics da edicao."
            : "Total da edicao indisponivel no contrato atual."
        }
        label="Partidas jogadas"
        value={
          analyticsQuery.isLoading
            ? "..."
            : formatHistoricalMatchCount(analyticsQuery.data?.seasonSummary.matchCount)
        }
      />
    </EditionSummaryGrid>
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

function HybridOverviewSection({
  context,
  resolution,
}: {
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  return (
    <div className="space-y-5">
      <GroupPhaseSummaryPanel context={context} stage={resolution.primaryTableStage} />
      <KnockoutBracketPanel
        context={context}
        description="Fase eliminatoria da edicao."
        resolution={resolution}
        title="Progressao eliminatoria"
      />
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
      label: "Grupos",
      value: groupCount > 0 ? String(groupCount) : "-",
    },
    {
      label: "Fases eliminatorias",
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
          <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Fase grupos</p>
          <p className="mt-1 text-sm font-semibold text-[#111c2d]">
            {resolution.primaryTableStage?.stageName ?? "Nao identificada"}
          </p>
        </div>
        <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.56)] px-3 py-3">
          <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Fase final</p>
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

function buildSurfaceNavLabels(type: CompetitionSeasonSurfaceResolution["type"]): SurfaceNavLabels {
  if (type === "league") {
    return {
      highlights: "Destaques estatisticos",
      matches: "Partidas de fechamento",
      overview: "Classificacao",
      structure: "Tabela completa",
    };
  }

  if (type === "hybrid") {
    return {
      highlights: "Destaques estatisticos",
      matches: "Mata-mata",
      overview: "Visao geral",
      structure: "Fase classificatoria",
    };
  }

  return {
    highlights: "Destaques estatisticos",
    matches: "Confrontos decisivos",
    overview: "Caminho do titulo",
    structure: "Chaveamento",
  };
}

function buildSeasonHeroDescription(resolution: CompetitionSeasonSurfaceResolution): string {
  if (resolution.type === "league") {
    return "";
  }

  if (resolution.type === "hybrid") {
    return "";
  }

  return "";
}

function buildSeasonHeroHighlight(resolution: CompetitionSeasonSurfaceResolution): {
  description: string;
  label: string;
  value: string;
} {
  if (resolution.type === "league") {
    return {
      description: "",
      label: "Leitura principal",
      value: "Classificacao final",
    };
  }

  if (resolution.type === "hybrid") {
    return {
      description: "",
      label: "Leitura principal",
      value: "Grupos + mata-mata",
    };
  }

  return {
    description: "",
    label: "Leitura principal",
    value: "Caminho do titulo",
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

function RoundPickerDropdown({ rounds, activeRoundId, setRoundId, selectedRound }: any) {
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
              {rounds.map((round: any) => {
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
  const navLabels = buildSurfaceNavLabels(resolution.type);

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
  const navLabels = buildSurfaceNavLabels(resolution.type);

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
  const navLabels = buildSurfaceNavLabels(resolution.type);

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<CupHeroBanner context={context} tag="Formato Híbrido" />}
      mainCanvas={
        <>
          {activeSection === "overview" ? <><CupKpiStrip context={context} resolution={resolution} /><HybridOverviewSection context={context} resolution={resolution} /></> : null}
          {activeSection === "structure" ? <GroupPhaseSummaryPanel context={context} stage={resolution.primaryTableStage} /> : null}
          {activeSection === "matches" ? (
            <KnockoutBracketPanel
              context={context}
              description="Fase eliminatoria da edicao."
              resolution={resolution}
              title="Mata-mata finalizado"
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
      secondaryRail={<HybridEditionRail context={context} resolution={resolution} />}
    />
  );
}

export function CompetitionSeasonSurface({
  context,
  initialTab,
}: CompetitionSeasonSurfaceProps) {
  const competitionDefinition = getCompetitionByKey(context.competitionKey);
  const activeSection = resolveCompetitionSeasonSurfaceSection(initialTab);
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
        structure={structureQuery.data}
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





