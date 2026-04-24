"use client";

import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import {
  getCompetitionByKey,
  getCompetitionVisualAssetId,
  SUPPORTED_COMPETITIONS,
  type CompetitionDef,
} from "@/config/competitions.registry";
import { listSeasonsForCompetition, type SeasonDef } from "@/config/seasons.registry";
import { competitionStructureQueryKeys } from "@/features/competitions/queryKeys";
import { fetchCompetitionAnalytics } from "@/features/competitions/services/competition-hub.service";
import type {
  CompetitionAnalyticsData,
  CompetitionAnalyticsFilters,
} from "@/features/competitions/types";
import { playersQueryKeys } from "@/features/players/queryKeys";
import { fetchPlayerProfile, fetchPlayersList } from "@/features/players/services/players.service";
import type {
  PlayerListItem,
  PlayerProfile,
  PlayerProfileFilters,
  PlayersListData,
  PlayersListFilters,
} from "@/features/players/types";
import { teamsQueryKeys } from "@/features/teams/queryKeys";
import { fetchTeamProfile, fetchTeamsList } from "@/features/teams/services/teams.service";
import type {
  TeamListItem,
  TeamProfile,
  TeamProfileFilters,
  TeamsListData,
  TeamsListFilters,
} from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import {
  ProfileAlert,
  ProfileKpi,
  ProfileMetricTile,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { ApiResponse } from "@/shared/types/api-response.types";
import {
  buildPlayerResolverPath,
  buildSeasonHubPath,
  buildTeamResolverPath,
} from "@/shared/utils/context-routing";

type ComparisonMode = "clubs" | "players" | "competitions";
type SideKey = "left" | "right";

type ComparisonSideState = {
  competitionKey: string;
  entityId: string;
  search: string;
  seasonId: string;
};

type ResolvedSide = {
  competition: CompetitionDef;
  season: SeasonDef;
  seasons: SeasonDef[];
};

type MetricFormat = "decimal" | "integer" | "percent";

type ComparisonMetric = {
  format?: MetricFormat;
  higherIsBetter?: boolean | null;
  key: string;
  label: string;
  left?: number | null;
  right?: number | null;
};

type SideIdentity = {
  assetId: number | string | null | undefined;
  category: "clubs" | "competitions" | "players";
  detail: string;
  fallback: string;
  href: string;
  shape?: "circle" | "rounded";
  title: string;
};

const DEFAULT_COMPETITION_KEY = "brasileirao_a";
const DEFAULT_LEFT_SIDE: ComparisonSideState = {
  competitionKey: DEFAULT_COMPETITION_KEY,
  entityId: "",
  search: "",
  seasonId: "2024",
};
const DEFAULT_RIGHT_SIDE: ComparisonSideState = {
  competitionKey: DEFAULT_COMPETITION_KEY,
  entityId: "",
  search: "",
  seasonId: "2025",
};
const LIST_PAGE_SIZE = 80;

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const PERCENT_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 1,
});

const MODE_OPTIONS: Array<{
  label: string;
  summary: string;
  value: ComparisonMode;
}> = [
  {
    label: "Clubes",
    summary: "times por temporada",
    value: "clubs",
  },
  {
    label: "Jogadores",
    summary: "estatísticas disponíveis",
    value: "players",
  },
  {
    label: "Campeonatos",
    summary: "edições e formatos",
    value: "competitions",
  },
];

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function getFallbackCompetition(): CompetitionDef {
  return (
    getCompetitionByKey(DEFAULT_COMPETITION_KEY) ??
    (SUPPORTED_COMPETITIONS[0] as CompetitionDef)
  );
}

function buildFallbackLabel(value: string): string {
  const tokens = value
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (tokens.length === 0) {
    return "FA";
  }

  if (tokens.length === 1) {
    return tokens[0].slice(0, 3).toUpperCase();
  }

  return tokens
    .slice(0, 2)
    .map((token) => token[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

function normalizeSearch(value: string): string | undefined {
  const normalizedValue = value.trim();
  return normalizedValue.length > 0 ? normalizedValue : undefined;
}

function resolveDefaultSeasonId(competitionKey: string, currentSeasonId?: string): string {
  const competition = getCompetitionByKey(competitionKey) ?? getFallbackCompetition();
  const seasons = listSeasonsForCompetition(competition);
  const currentSeason = seasons.find((season) => season.id === currentSeasonId);

  return currentSeason?.id ?? seasons[0]?.id ?? "2025";
}

function resolveSide(side: ComparisonSideState): ResolvedSide {
  const competition = getCompetitionByKey(side.competitionKey) ?? getFallbackCompetition();
  const seasons = listSeasonsForCompetition(competition);
  const season = seasons.find((item) => item.id === side.seasonId) ?? seasons[0];

  return {
    competition,
    season: season ?? {
      calendar: competition.seasonCalendar,
      catalogLabel: side.seasonId,
      id: side.seasonId,
      label: side.seasonId,
      queryId: side.seasonId,
    },
    seasons,
  };
}

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return INTEGER_FORMATTER.format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return DECIMAL_FORMATTER.format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return `${PERCENT_FORMATTER.format(value)}%`;
}

function formatMetricValue(value: number | null | undefined, format: MetricFormat = "integer") {
  if (format === "decimal") {
    return formatDecimal(value);
  }

  if (format === "percent") {
    return formatPercent(value);
  }

  return formatInteger(value);
}

function calculatePointsEfficiencyPct(summary: TeamProfile["summary"] | undefined): number | null {
  const points = summary?.points;
  const matchesPlayed = summary?.matchesPlayed;

  if (
    typeof points !== "number" ||
    !Number.isFinite(points) ||
    typeof matchesPlayed !== "number" ||
    !Number.isFinite(matchesPlayed) ||
    matchesPlayed <= 0
  ) {
    return null;
  }

  return (points / (matchesPlayed * 3)) * 100;
}

function formatSignedValue(value: number, format: MetricFormat = "integer"): string {
  const sign = value > 0 ? "+" : "";

  if (format === "percent") {
    return `${sign}${PERCENT_FORMATTER.format(value)} p.p.`;
  }

  if (format === "decimal") {
    return `${sign}${DECIMAL_FORMATTER.format(value)}`;
  }

  return `${sign}${INTEGER_FORMATTER.format(value)}`;
}

function resolveNumericDelta(metric: ComparisonMetric): number | null {
  if (
    typeof metric.left !== "number" ||
    Number.isNaN(metric.left) ||
    typeof metric.right !== "number" ||
    Number.isNaN(metric.right)
  ) {
    return null;
  }

  return metric.left - metric.right;
}

function resolveMetricLeader(metric: ComparisonMetric): SideKey | "tie" | null {
  const delta = resolveNumericDelta(metric);

  if (delta === null || metric.higherIsBetter === null) {
    return null;
  }

  if (delta === 0) {
    return "tie";
  }

  const higherIsBetter = metric.higherIsBetter ?? true;
  const leftLeads = higherIsBetter ? delta > 0 : delta < 0;

  return leftLeads ? "left" : "right";
}

function hasMetricValue(metric: ComparisonMetric): boolean {
  return (
    (typeof metric.left === "number" && Number.isFinite(metric.left)) ||
    (typeof metric.right === "number" && Number.isFinite(metric.right))
  );
}

function calculateAdvantage(metrics: ComparisonMetric[]) {
  return metrics.reduce(
    (summary, metric) => {
      const leader = resolveMetricLeader(metric);

      if (leader === "left") {
        summary.left += 1;
      } else if (leader === "right") {
        summary.right += 1;
      } else if (leader === "tie") {
        summary.tie += 1;
      }

      return summary;
    },
    { left: 0, right: 0, tie: 0 },
  );
}

function calculateGoalsFromAverage(data: CompetitionAnalyticsData | undefined): number | null {
  const matchCount = data?.seasonSummary.matchCount;
  const averageGoals = data?.seasonSummary.averageGoals;

  if (
    typeof matchCount !== "number" ||
    !Number.isFinite(matchCount) ||
    typeof averageGoals !== "number" ||
    !Number.isFinite(averageGoals)
  ) {
    return null;
  }

  return Math.round(matchCount * averageGoals);
}

function sumStageField(
  data: CompetitionAnalyticsData | undefined,
  field: "awayWins" | "draws" | "homeWins" | "inferredTies" | "resolvedTies",
): number | null {
  if (!data || data.stageAnalytics.length === 0) {
    return null;
  }

  return data.stageAnalytics.reduce((total, stage) => total + stage[field], 0);
}

function buildClubMetrics(
  leftProfile: TeamProfile | undefined,
  rightProfile: TeamProfile | undefined,
): ComparisonMetric[] {
  const leftSummary = leftProfile?.summary;
  const rightSummary = rightProfile?.summary;
  const leftStats = leftProfile?.stats;
  const rightStats = rightProfile?.stats;

  const metrics: ComparisonMetric[] = [
    {
      higherIsBetter: null,
      key: "matches",
      label: "Jogos",
      left: leftSummary?.matchesPlayed,
      right: rightSummary?.matchesPlayed,
    },
    {
      key: "wins",
      label: "Vitórias",
      left: leftSummary?.wins,
      right: rightSummary?.wins,
    },
    {
      higherIsBetter: null,
      key: "draws",
      label: "Empates",
      left: leftSummary?.draws,
      right: rightSummary?.draws,
    },
    {
      higherIsBetter: false,
      key: "losses",
      label: "Derrotas",
      left: leftSummary?.losses,
      right: rightSummary?.losses,
    },
    {
      key: "goals-for",
      label: "Gols pró",
      left: leftSummary?.goalsFor,
      right: rightSummary?.goalsFor,
    },
    {
      higherIsBetter: false,
      key: "goals-against",
      label: "Gols contra",
      left: leftSummary?.goalsAgainst,
      right: rightSummary?.goalsAgainst,
    },
    {
      key: "goal-diff",
      label: "Saldo",
      left: leftSummary?.goalDiff,
      right: rightSummary?.goalDiff,
    },
    {
      key: "points",
      label: "Pontos",
      left: leftSummary?.points,
      right: rightSummary?.points,
    },
    {
      format: "decimal",
      key: "points-per-match",
      label: "Pontos/jogo",
      left: leftStats?.pointsPerMatch,
      right: rightStats?.pointsPerMatch,
    },
    {
      format: "percent",
      key: "points-efficiency",
      label: "Aproveitamento",
      left: calculatePointsEfficiencyPct(leftSummary),
      right: calculatePointsEfficiencyPct(rightSummary),
    },
    {
      format: "decimal",
      key: "goals-for-per-match",
      label: "Gols pró/jogo",
      left: leftStats?.goalsForPerMatch,
      right: rightStats?.goalsForPerMatch,
    },
    {
      format: "decimal",
      higherIsBetter: false,
      key: "goals-against-per-match",
      label: "Gols contra/jogo",
      left: leftStats?.goalsAgainstPerMatch,
      right: rightStats?.goalsAgainstPerMatch,
    },
    {
      key: "clean-sheets",
      label: "Jogos sem sofrer gol",
      left: leftStats?.cleanSheets,
      right: rightStats?.cleanSheets,
    },
  ];

  return metrics.filter(hasMetricValue);
}

function buildPlayerMetrics(
  leftProfile: PlayerProfile | undefined,
  rightProfile: PlayerProfile | undefined,
): ComparisonMetric[] {
  const leftSummary = leftProfile?.summary;
  const rightSummary = rightProfile?.summary;
  const leftStats = leftProfile?.stats;
  const rightStats = rightProfile?.stats;
  const leftGoalActions = (leftSummary?.goals ?? 0) + (leftSummary?.assists ?? 0);
  const rightGoalActions = (rightSummary?.goals ?? 0) + (rightSummary?.assists ?? 0);

  const metrics: ComparisonMetric[] = [
    {
      higherIsBetter: null,
      key: "matches",
      label: "Jogos",
      left: leftSummary?.matchesPlayed,
      right: rightSummary?.matchesPlayed,
    },
    {
      higherIsBetter: null,
      key: "minutes",
      label: "Minutos",
      left: leftSummary?.minutesPlayed,
      right: rightSummary?.minutesPlayed,
    },
    {
      key: "goals",
      label: "Gols",
      left: leftSummary?.goals,
      right: rightSummary?.goals,
    },
    {
      key: "assists",
      label: "Assistências",
      left: leftSummary?.assists,
      right: rightSummary?.assists,
    },
    {
      key: "goal-actions",
      label: "G+A",
      left: leftSummary ? leftGoalActions : null,
      right: rightSummary ? rightGoalActions : null,
    },
    {
      key: "shots",
      label: "Finalizações",
      left: leftSummary?.shotsTotal,
      right: rightSummary?.shotsTotal,
    },
    {
      key: "shots-on-target",
      label: "Finalizações certas",
      left: leftSummary?.shotsOnTarget,
      right: rightSummary?.shotsOnTarget,
    },
    {
      format: "percent",
      key: "pass-accuracy",
      label: "Precisão de passe",
      left: leftSummary?.passAccuracyPct,
      right: rightSummary?.passAccuracyPct,
    },
    {
      format: "decimal",
      key: "rating",
      label: "Nota",
      left: leftSummary?.rating,
      right: rightSummary?.rating,
    },
    {
      format: "decimal",
      key: "goals-per-90",
      label: "Gols/90",
      left: leftStats?.goalsPer90,
      right: rightStats?.goalsPer90,
    },
    {
      format: "decimal",
      key: "assists-per-90",
      label: "Assists/90",
      left: leftStats?.assistsPer90,
      right: rightStats?.assistsPer90,
    },
    {
      format: "decimal",
      key: "goal-contrib-per-90",
      label: "G+A/90",
      left: leftStats?.goalContributionsPer90,
      right: rightStats?.goalContributionsPer90,
    },
    {
      format: "decimal",
      key: "shots-per-90",
      label: "Finalizações/90",
      left: leftStats?.shotsPer90,
      right: rightStats?.shotsPer90,
    },
    {
      higherIsBetter: false,
      key: "yellow-cards",
      label: "Cartões amarelos",
      left: leftSummary?.yellowCards,
      right: rightSummary?.yellowCards,
    },
    {
      higherIsBetter: false,
      key: "red-cards",
      label: "Cartões vermelhos",
      left: leftSummary?.redCards,
      right: rightSummary?.redCards,
    },
  ];

  return metrics.filter(hasMetricValue);
}

function buildCompetitionMetrics(
  leftAnalytics: CompetitionAnalyticsData | undefined,
  rightAnalytics: CompetitionAnalyticsData | undefined,
): ComparisonMetric[] {
  const metrics: ComparisonMetric[] = [
    {
      higherIsBetter: null,
      key: "matches",
      label: "Jogos",
      left: leftAnalytics?.seasonSummary.matchCount,
      right: rightAnalytics?.seasonSummary.matchCount,
    },
    {
      higherIsBetter: null,
      key: "goals",
      label: "Gols estimados",
      left: calculateGoalsFromAverage(leftAnalytics),
      right: calculateGoalsFromAverage(rightAnalytics),
    },
    {
      format: "decimal",
      higherIsBetter: null,
      key: "average-goals",
      label: "Média de gols",
      left: leftAnalytics?.seasonSummary.averageGoals,
      right: rightAnalytics?.seasonSummary.averageGoals,
    },
    {
      higherIsBetter: null,
      key: "stages",
      label: "Fases",
      left: leftAnalytics?.seasonSummary.totalStages,
      right: rightAnalytics?.seasonSummary.totalStages,
    },
    {
      higherIsBetter: null,
      key: "table-stages",
      label: "Fases de tabela",
      left: leftAnalytics?.seasonSummary.tableStages,
      right: rightAnalytics?.seasonSummary.tableStages,
    },
    {
      higherIsBetter: null,
      key: "knockout-stages",
      label: "Fases mata-mata",
      left: leftAnalytics?.seasonSummary.knockoutStages,
      right: rightAnalytics?.seasonSummary.knockoutStages,
    },
    {
      higherIsBetter: null,
      key: "groups",
      label: "Grupos",
      left: leftAnalytics?.seasonSummary.groupCount,
      right: rightAnalytics?.seasonSummary.groupCount,
    },
    {
      higherIsBetter: null,
      key: "ties",
      label: "Confrontos mata-mata",
      left: leftAnalytics?.seasonSummary.tieCount,
      right: rightAnalytics?.seasonSummary.tieCount,
    },
    {
      key: "home-wins",
      label: "Vitórias mandante",
      left: sumStageField(leftAnalytics, "homeWins"),
      right: sumStageField(rightAnalytics, "homeWins"),
    },
    {
      higherIsBetter: null,
      key: "draws",
      label: "Empates",
      left: sumStageField(leftAnalytics, "draws"),
      right: sumStageField(rightAnalytics, "draws"),
    },
    {
      key: "away-wins",
      label: "Vitórias visitante",
      left: sumStageField(leftAnalytics, "awayWins"),
      right: sumStageField(rightAnalytics, "awayWins"),
    },
    {
      higherIsBetter: null,
      key: "resolved-ties",
      label: "Chaves resolvidas",
      left: sumStageField(leftAnalytics, "resolvedTies"),
      right: sumStageField(rightAnalytics, "resolvedTies"),
    },
  ];

  return metrics.filter(hasMetricValue);
}

function buildTeamListFilters(side: ResolvedSide, search: string): TeamsListFilters {
  return {
    competitionId: side.competition.id,
    pageSize: LIST_PAGE_SIZE,
    search: normalizeSearch(search),
    seasonId: side.season.queryId,
    sortBy: "points",
    sortDirection: "desc",
  };
}

function buildPlayerListFilters(side: ResolvedSide, search: string): PlayersListFilters {
  return {
    competitionId: side.competition.id,
    pageSize: LIST_PAGE_SIZE,
    search: normalizeSearch(search),
    seasonId: side.season.queryId,
    sortBy: "goals",
    sortDirection: "desc",
  };
}

function buildTeamProfileFilters(side: ResolvedSide): TeamProfileFilters {
  return {
    competitionId: side.competition.id,
    includeStats: true,
    seasonId: side.season.queryId,
  };
}

function buildPlayerProfileFilters(side: ResolvedSide): PlayerProfileFilters {
  return {
    competitionId: side.competition.id,
    includeStats: true,
    seasonId: side.season.queryId,
  };
}

function buildCompetitionAnalyticsFilters(side: ResolvedSide): CompetitionAnalyticsFilters {
  return {
    competitionKey: side.competition.key,
    seasonLabel: side.season.label,
  };
}

function buildContextInput(side: ResolvedSide) {
  return {
    competitionId: side.competition.id,
    competitionKey: side.competition.key,
    seasonId: side.season.queryId,
  };
}

function getTeamFromList(items: TeamListItem[], teamId: string): TeamListItem | null {
  return items.find((team) => team.teamId === teamId) ?? null;
}

function getPlayerFromList(items: PlayerListItem[], playerId: string): PlayerListItem | null {
  return items.find((player) => player.playerId === playerId) ?? null;
}

function buildSideIdentity(input: {
  mode: ComparisonMode;
  player?: PlayerListItem | null;
  playerProfile?: PlayerProfile;
  side: ComparisonSideState;
  sideContext: ResolvedSide;
  team?: TeamListItem | null;
  teamProfile?: TeamProfile;
}): SideIdentity {
  const contextLabel = `${input.sideContext.competition.shortName} ${input.sideContext.season.label}`;

  if (input.mode === "clubs") {
    const teamName =
      input.teamProfile?.team.teamName ?? input.team?.teamName ?? "Selecione um clube";
    const teamId = input.teamProfile?.team.teamId ?? input.team?.teamId ?? input.side.entityId;

    return {
      assetId: teamId,
      category: "clubs",
      detail: contextLabel,
      fallback: buildFallbackLabel(teamName),
      href: teamId ? buildTeamResolverPath(teamId, buildContextInput(input.sideContext)) : "/teams",
      title: teamName,
    };
  }

  if (input.mode === "players") {
    const playerName =
      input.playerProfile?.player.playerName ?? input.player?.playerName ?? "Selecione um jogador";
    const playerId =
      input.playerProfile?.player.playerId ?? input.player?.playerId ?? input.side.entityId;
    const teamName =
      input.playerProfile?.player.teamName ??
      input.player?.teamName ??
      input.player?.teamContextLabel ??
      contextLabel;

    return {
      assetId: playerId,
      category: "players",
      detail: teamName,
      fallback: buildFallbackLabel(playerName),
      href: playerId
        ? buildPlayerResolverPath(playerId, buildContextInput(input.sideContext))
        : "/players",
      shape: "circle",
      title: playerName,
    };
  }

  return {
    assetId: getCompetitionVisualAssetId(input.sideContext.competition),
    category: "competitions",
    detail: input.sideContext.season.label,
    fallback: buildFallbackLabel(input.sideContext.competition.shortName),
    href: buildSeasonHubPath({
      competitionKey: input.sideContext.competition.key,
      seasonLabel: input.sideContext.season.label,
    }),
    title: input.sideContext.competition.name,
  };
}

function ComparisonIcon({
  className,
  mode,
}: {
  className?: string;
  mode: ComparisonMode;
}) {
  const sharedClassName = className ?? "h-4 w-4";

  if (mode === "players") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M6 19c1.6-2.8 4-4.2 6-4.2S16.4 16.2 18 19"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (mode === "competitions") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M8 6h8m-7 4h6m-8 8h10l2-8H5l2 8Z"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
      <path
        d="M12 4.5 18 7v5.2c0 3.2-2 5.8-6 7.3-4-1.5-6-4.1-6-7.3V7l6-2.5Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function SideConfigurator({
  mode,
  onChange,
  optionsError,
  optionsLoading,
  playerOptions,
  side,
  sideContext,
  sideLabel,
  teamOptions,
}: {
  mode: ComparisonMode;
  onChange: (patch: Partial<ComparisonSideState>) => void;
  optionsError?: Error | null;
  optionsLoading: boolean;
  playerOptions: PlayerListItem[];
  side: ComparisonSideState;
  sideContext: ResolvedSide;
  sideLabel: string;
  teamOptions: TeamListItem[];
}) {
  const isEntityMode = mode !== "competitions";
  const entityOptions = mode === "clubs" ? teamOptions : playerOptions;

  return (
    <ProfilePanel className="space-y-4 border-white/80 bg-white/84">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
            {sideLabel}
          </p>
          <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
            {sideContext.competition.shortName} {sideContext.season.label}
          </h2>
        </div>
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#e9f2ff] text-[#003526]">
          <ComparisonIcon className="h-5 w-5" mode={mode} />
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
          Competição
          <select
            className="h-[54px] rounded-[1.1rem] border border-[rgba(191,201,195,0.52)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none"
            onChange={(event) => {
              const competitionKey = event.target.value;
              onChange({
                competitionKey,
                entityId: "",
                search: "",
                seasonId: resolveDefaultSeasonId(competitionKey, side.seasonId),
              });
            }}
            value={side.competitionKey}
          >
            {SUPPORTED_COMPETITIONS.map((competition) => (
              <option key={competition.key} value={competition.key}>
                {competition.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
          Temporada
          <select
            className="h-[54px] rounded-[1.1rem] border border-[rgba(191,201,195,0.52)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none"
            onChange={(event) => {
              onChange({
                entityId: "",
                seasonId: event.target.value,
              });
            }}
            value={sideContext.season.id}
          >
            {sideContext.seasons.map((season) => (
              <option key={season.id} value={season.id}>
                {season.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isEntityMode ? (
        <>
          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Busca
            <input
              className="h-[54px] rounded-[1.1rem] border border-[rgba(191,201,195,0.52)] bg-[#f9f9ff] px-4 text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none placeholder:text-[#707974]"
              onChange={(event) => {
                onChange({
                  entityId: "",
                  search: event.target.value,
                });
              }}
              placeholder={mode === "clubs" ? "Ex.: Flamengo, Botafogo" : "Ex.: Arrascaeta, Mbappe"}
              type="search"
              value={side.search}
            />
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            {mode === "clubs" ? "Clube" : "Jogador"}
            <select
              className="h-[54px] rounded-[1.1rem] border border-[rgba(191,201,195,0.52)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none disabled:cursor-not-allowed disabled:opacity-60"
              disabled={optionsLoading || entityOptions.length === 0}
              onChange={(event) => {
                onChange({
                  entityId: event.target.value,
                });
              }}
              value={side.entityId}
            >
              <option value="">
                {optionsLoading
                  ? "Carregando..."
                  : mode === "clubs"
                    ? "Selecione o clube"
                    : "Selecione o jogador"}
              </option>
              {mode === "clubs"
                ? teamOptions.map((team) => (
                    <option key={team.teamId} value={team.teamId}>
                      {team.position ? `${team.position}º - ${team.teamName}` : team.teamName}
                    </option>
                  ))
                : playerOptions.map((player) => (
                    <option key={player.playerId} value={player.playerId}>
                      {player.teamName
                        ? `${player.playerName} - ${player.teamName}`
                        : player.playerName}
                    </option>
                  ))}
            </select>
          </label>
        </>
      ) : null}

      {optionsLoading ? <LoadingSkeleton height={64} /> : null}

      {optionsError ? (
        <ProfileAlert title="Falha ao carregar opções" tone="warning">
          <p>{optionsError.message}</p>
        </ProfileAlert>
      ) : null}
    </ProfilePanel>
  );
}

function IdentityCard({
  identity,
  label,
  side,
}: {
  identity: SideIdentity;
  label: string;
  side: SideKey;
}) {
  return (
    <Link
      className={joinClasses(
        "group relative flex min-h-[12rem] w-full flex-col items-start gap-4 overflow-hidden rounded-[1.65rem] border p-5 pr-12 text-white shadow-[0_30px_78px_-54px_rgba(0,53,38,0.7)] transition-transform hover:-translate-y-0.5 sm:flex-row",
        side === "left"
          ? "border-emerald-200/14 bg-[radial-gradient(circle_at_top_left,rgba(139,214,182,0.28),transparent_44%),linear-gradient(135deg,#06271d_0%,#0b3c2d_56%,#0f513c_100%)]"
          : "border-sky-200/14 bg-[radial-gradient(circle_at_top_right,rgba(175,210,255,0.22),transparent_44%),linear-gradient(135deg,#0d1f34_0%,#14395d_58%,#1f557a_100%)]",
      )}
      href={identity.href}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-white/6" />
      <ProfileMedia
        alt={identity.title}
        assetId={identity.assetId}
        category={identity.category}
        className="relative h-20 w-20 border-white/18 bg-white/12"
        fallback={identity.fallback}
        fallbackClassName="text-white"
        imageClassName="p-2"
        shape={identity.shape}
        tone="contrast"
        linkBehavior="none"
      />
      <div className="relative min-w-0 flex-1">
        <p className="text-[0.64rem] font-bold uppercase tracking-[0.2em] text-white/58">
          {label}
        </p>
        <h3 className="mt-2 line-clamp-2 font-[family:var(--font-profile-headline)] text-[1.65rem] font-extrabold leading-tight tracking-[-0.04em] text-white">
          {identity.title}
        </h3>
        <p className="mt-3 inline-flex rounded-full bg-white/12 px-3 py-1 text-xs font-semibold text-white/78">
          {identity.detail}
        </p>
      </div>
      <span className="absolute right-5 top-5 text-sm font-bold text-white transition-transform group-hover:translate-x-0.5">
        -&gt;
      </span>
    </Link>
  );
}

type ComparisonMetricGroup = {
  id: string;
  metrics: ComparisonMetric[];
  title: string;
};

function groupComparisonMetrics(
  mode: ComparisonMode,
  metrics: ComparisonMetric[],
): ComparisonMetricGroup[] {
  const groups =
    mode === "clubs"
      ? [
          {
            id: "overview",
            keys: ["matches", "wins", "points", "points-per-match", "points-efficiency"],
            title: "Visão geral",
          },
          {
            id: "attack",
            keys: ["goals-for", "goals-for-per-match", "goal-diff"],
            title: "Produção ofensiva",
          },
          {
            id: "defense",
            keys: ["goals-against", "goals-against-per-match", "clean-sheets", "losses"],
            title: "Controle defensivo",
          },
          {
            id: "balance",
            keys: ["draws"],
            title: "Equilíbrio",
          },
        ]
      : mode === "players"
        ? [
            {
              id: "overview",
              keys: ["matches", "minutes", "rating", "goal-actions"],
              title: "Visão geral",
            },
            {
              id: "attack",
              keys: [
                "goals",
                "assists",
                "goals-per-90",
                "assists-per-90",
                "goal-contrib-per-90",
                "shots",
                "shots-on-target",
                "shots-per-90",
              ],
              title: "Produção ofensiva",
            },
            {
              id: "build",
              keys: ["pass-accuracy"],
              title: "Construção / passe",
            },
            {
              id: "discipline",
              keys: ["yellow-cards", "red-cards"],
              title: "Disciplina",
            },
          ]
        : [
            {
              id: "volume",
              keys: ["matches", "goals", "average-goals", "home-wins", "draws", "away-wins"],
              title: "Volume da edição",
            },
            {
              id: "format",
              keys: [
                "stages",
                "table-stages",
                "knockout-stages",
                "groups",
                "ties",
                "resolved-ties",
              ],
              title: "Formato e estrutura",
            },
          ];
  const usedKeys = new Set<string>();
  const groupedMetrics = groups
    .map((group) => {
      const groupKeys = new Set(group.keys);
      const groupMetrics = metrics.filter((metric) => groupKeys.has(metric.key));

      groupMetrics.forEach((metric) => usedKeys.add(metric.key));

      return {
        id: group.id,
        metrics: groupMetrics,
        title: group.title,
      };
    })
    .filter((group) => group.metrics.length > 0);
  const remainingMetrics = metrics.filter((metric) => !usedKeys.has(metric.key));

  if (remainingMetrics.length > 0) {
    groupedMetrics.push({
      id: "other",
      metrics: remainingMetrics,
      title: "Outras métricas",
    });
  }

  return groupedMetrics;
}

function getMetricMagnitude(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.abs(value) : 0;
}

function getMetricBarWidth(
  value: number | null | undefined,
  leftValue: number | null | undefined,
  rightValue: number | null | undefined,
): number {
  const maxMagnitude = Math.max(getMetricMagnitude(leftValue), getMetricMagnitude(rightValue));

  if (maxMagnitude <= 0) {
    return 8;
  }

  return Math.max(8, (getMetricMagnitude(value) / maxMagnitude) * 100);
}

function MetricValuePill({
  format,
  isLeader,
  side,
  value,
}: {
  format: MetricFormat;
  isLeader: boolean;
  side: SideKey;
  value: number | null | undefined;
}) {
  const hasValue = typeof value === "number" && Number.isFinite(value);

  return (
    <span
      className={joinClasses(
        "inline-flex min-w-[4.75rem] justify-center rounded-full px-3 py-1.5 text-sm font-extrabold tabular-nums",
        !hasValue
          ? "bg-[rgba(240,243,255,0.78)] text-[#8190a3]"
          : isLeader
            ? side === "left"
              ? "bg-[#003526] text-white"
              : "bg-[#14395d] text-white"
            : "bg-white text-[#1f2d40]",
      )}
    >
      {formatMetricValue(value, format)}
    </span>
  );
}

function MetricComparisonCard({
  leftLabel,
  metric,
  rightLabel,
}: {
  leftLabel: string;
  metric: ComparisonMetric;
  rightLabel: string;
}) {
  const leader = resolveMetricLeader(metric);
  const format = metric.format ?? "integer";
  const leftWidth = getMetricBarWidth(metric.left, metric.left, metric.right);
  const rightWidth = getMetricBarWidth(metric.right, metric.left, metric.right);

  return (
    <article className="rounded-[1.15rem] border border-[rgba(216,227,251,0.64)] bg-[rgba(248,250,255,0.72)] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.78)]">
      <div className="grid gap-3 md:grid-cols-[minmax(6rem,0.85fr)_minmax(14rem,1.6fr)_minmax(6rem,0.85fr)] md:items-center">
        <div className="flex items-center justify-start gap-2 md:justify-end">
          <MetricValuePill
            format={format}
            isLeader={leader === "left"}
            side="left"
            value={metric.left}
          />
        </div>

        <div className="min-w-0">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-[#1f2d40]">{metric.label}</p>
            {leader && leader !== "tie" ? (
              <span className="rounded-full bg-[#d8e3fb] px-2 py-0.5 text-[0.56rem] font-bold uppercase tracking-[0.14em] text-[#305c4a]">
                Destaque
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-1.5" aria-label={`${metric.label}: ${leftLabel} contra ${rightLabel}`}>
            <div className="flex h-3 items-center justify-end rounded-full bg-[rgba(216,227,251,0.72)]">
              <span
                className={joinClasses(
                  "block h-3 rounded-full",
                  leader === "left" ? "bg-[#003526]" : "bg-[#8da0bd]",
                )}
                style={{ width: `${leftWidth}%` }}
              />
            </div>
            <div className="flex h-3 items-center rounded-full bg-[rgba(216,227,251,0.72)]">
              <span
                className={joinClasses(
                  "block h-3 rounded-full",
                  leader === "right" ? "bg-[#14395d]" : "bg-[#8da0bd]",
                )}
                style={{ width: `${rightWidth}%` }}
              />
            </div>
          </div>
          <div className="mt-1.5 flex justify-between text-[0.65rem] font-medium text-[#8190a3]">
            <span className="truncate">{leftLabel}</span>
            <span className="truncate text-right">{rightLabel}</span>
          </div>
        </div>

        <div className="flex items-center justify-start gap-2">
          <MetricValuePill
            format={format}
            isLeader={leader === "right"}
            side="right"
            value={metric.right}
          />
        </div>
      </div>
    </article>
  );
}

function ComparisonMetricsTable({
  leftLabel,
  metrics,
  mode,
  rightLabel,
}: {
  leftLabel: string;
  metrics: ComparisonMetric[];
  mode: ComparisonMode;
  rightLabel: string;
}) {
  if (metrics.length === 0) {
    return (
      <EmptyState
        description="Escolha os dois lados do comparativo ou ajuste o recorte para carregar métricas disponíveis."
        title="Comparativo aguardando dados"
      />
    );
  }

  const groups = groupComparisonMetrics(mode, metrics);

  return (
    <ProfilePanel className="space-y-5 border-white/70 bg-[radial-gradient(circle_at_12%_0%,rgba(139,214,182,0.16),transparent_34%),radial-gradient(circle_at_88%_0%,rgba(31,85,122,0.14),transparent_34%),linear-gradient(180deg,rgba(243,247,241,0.94)_0%,rgba(248,250,255,0.96)_48%,rgba(245,249,245,0.94)_100%)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Métricas lado a lado
          </p>
          <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.05em] text-[#111c2d]">
            Comparativo consolidado
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <ProfileTag>{metrics.length} métricas</ProfileTag>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {groups.map((group) => (
          <section
            className="rounded-[1.45rem] border border-white/70 bg-white/72 p-4 shadow-[0_22px_58px_-50px_rgba(17,28,45,0.24)]"
            key={group.id}
          >
            <header className="mb-3 flex items-center gap-2">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#e4f6ee] text-[#003526]">
                <ComparisonIcon className="h-4 w-4" mode={mode} />
              </span>
              <h3 className="font-[family:var(--font-profile-headline)] text-lg font-extrabold text-[#111c2d]">
                {group.title}
              </h3>
            </header>
            <div className="space-y-2">
              {group.metrics.map((metric) => (
                <MetricComparisonCard
                  key={metric.key}
                  leftLabel={leftLabel}
                  metric={metric}
                  rightLabel={rightLabel}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </ProfilePanel>
  );
}

function QueryAlert({
  error,
  title,
}: {
  error: Error | null | undefined;
  title: string;
}) {
  if (!error) {
    return null;
  }

  return (
    <ProfileAlert title={title} tone="warning">
      <p>{error.message}</p>
    </ProfileAlert>
  );
}

export function HeadToHeadPageContent() {
  const [mode, setMode] = useState<ComparisonMode>("clubs");
  const [leftSide, setLeftSide] = useState<ComparisonSideState>(DEFAULT_LEFT_SIDE);
  const [rightSide, setRightSide] = useState<ComparisonSideState>(DEFAULT_RIGHT_SIDE);

  const leftContext = useMemo(() => resolveSide(leftSide), [leftSide]);
  const rightContext = useMemo(() => resolveSide(rightSide), [rightSide]);
  const leftTeamListFilters = useMemo(
    () => buildTeamListFilters(leftContext, leftSide.search),
    [leftContext, leftSide.search],
  );
  const rightTeamListFilters = useMemo(
    () => buildTeamListFilters(rightContext, rightSide.search),
    [rightContext, rightSide.search],
  );
  const leftPlayerListFilters = useMemo(
    () => buildPlayerListFilters(leftContext, leftSide.search),
    [leftContext, leftSide.search],
  );
  const rightPlayerListFilters = useMemo(
    () => buildPlayerListFilters(rightContext, rightSide.search),
    [rightContext, rightSide.search],
  );
  const leftTeamProfileFilters = useMemo(
    () => buildTeamProfileFilters(leftContext),
    [leftContext],
  );
  const rightTeamProfileFilters = useMemo(
    () => buildTeamProfileFilters(rightContext),
    [rightContext],
  );
  const leftPlayerProfileFilters = useMemo(
    () => buildPlayerProfileFilters(leftContext),
    [leftContext],
  );
  const rightPlayerProfileFilters = useMemo(
    () => buildPlayerProfileFilters(rightContext),
    [rightContext],
  );
  const leftCompetitionFilters = useMemo(
    () => buildCompetitionAnalyticsFilters(leftContext),
    [leftContext],
  );
  const rightCompetitionFilters = useMemo(
    () => buildCompetitionAnalyticsFilters(rightContext),
    [rightContext],
  );

  const leftTeamsQuery = useQuery<ApiResponse<TeamsListData>, Error>({
    enabled: mode === "clubs",
    queryFn: () => fetchTeamsList(leftTeamListFilters),
    queryKey: teamsQueryKeys.list(leftTeamListFilters),
    staleTime: 5 * 60 * 1000,
  });
  const rightTeamsQuery = useQuery<ApiResponse<TeamsListData>, Error>({
    enabled: mode === "clubs",
    queryFn: () => fetchTeamsList(rightTeamListFilters),
    queryKey: teamsQueryKeys.list(rightTeamListFilters),
    staleTime: 5 * 60 * 1000,
  });
  const leftPlayersQuery = useQuery<ApiResponse<PlayersListData>, Error>({
    enabled: mode === "players",
    queryFn: () => fetchPlayersList(leftPlayerListFilters),
    queryKey: playersQueryKeys.list(leftPlayerListFilters),
    staleTime: 5 * 60 * 1000,
  });
  const rightPlayersQuery = useQuery<ApiResponse<PlayersListData>, Error>({
    enabled: mode === "players",
    queryFn: () => fetchPlayersList(rightPlayerListFilters),
    queryKey: playersQueryKeys.list(rightPlayerListFilters),
    staleTime: 5 * 60 * 1000,
  });
  const leftTeamProfileQuery = useQuery<ApiResponse<TeamProfile>, Error>({
    enabled: mode === "clubs" && leftSide.entityId.length > 0,
    queryFn: () => fetchTeamProfile(leftSide.entityId, leftTeamProfileFilters),
    queryKey: teamsQueryKeys.profile(leftSide.entityId || "none", leftTeamProfileFilters),
    staleTime: 5 * 60 * 1000,
  });
  const rightTeamProfileQuery = useQuery<ApiResponse<TeamProfile>, Error>({
    enabled: mode === "clubs" && rightSide.entityId.length > 0,
    queryFn: () => fetchTeamProfile(rightSide.entityId, rightTeamProfileFilters),
    queryKey: teamsQueryKeys.profile(rightSide.entityId || "none", rightTeamProfileFilters),
    staleTime: 5 * 60 * 1000,
  });
  const leftPlayerProfileQuery = useQuery<ApiResponse<PlayerProfile>, Error>({
    enabled: mode === "players" && leftSide.entityId.length > 0,
    queryFn: () => fetchPlayerProfile(leftSide.entityId, leftPlayerProfileFilters),
    queryKey: playersQueryKeys.profile(leftSide.entityId || "none", leftPlayerProfileFilters),
    staleTime: 5 * 60 * 1000,
  });
  const rightPlayerProfileQuery = useQuery<ApiResponse<PlayerProfile>, Error>({
    enabled: mode === "players" && rightSide.entityId.length > 0,
    queryFn: () => fetchPlayerProfile(rightSide.entityId, rightPlayerProfileFilters),
    queryKey: playersQueryKeys.profile(rightSide.entityId || "none", rightPlayerProfileFilters),
    staleTime: 5 * 60 * 1000,
  });
  const leftCompetitionQuery = useQuery<ApiResponse<CompetitionAnalyticsData>, Error>({
    enabled: mode === "competitions",
    queryFn: () => fetchCompetitionAnalytics(leftCompetitionFilters),
    queryKey: competitionStructureQueryKeys.analytics(leftCompetitionFilters),
    staleTime: 5 * 60 * 1000,
  });
  const rightCompetitionQuery = useQuery<ApiResponse<CompetitionAnalyticsData>, Error>({
    enabled: mode === "competitions",
    queryFn: () => fetchCompetitionAnalytics(rightCompetitionFilters),
    queryKey: competitionStructureQueryKeys.analytics(rightCompetitionFilters),
    staleTime: 5 * 60 * 1000,
  });

  const leftTeamOptions = leftTeamsQuery.data?.data.items ?? [];
  const rightTeamOptions = rightTeamsQuery.data?.data.items ?? [];
  const leftPlayerOptions = leftPlayersQuery.data?.data.items ?? [];
  const rightPlayerOptions = rightPlayersQuery.data?.data.items ?? [];
  const leftTeam = getTeamFromList(leftTeamOptions, leftSide.entityId);
  const rightTeam = getTeamFromList(rightTeamOptions, rightSide.entityId);
  const leftPlayer = getPlayerFromList(leftPlayerOptions, leftSide.entityId);
  const rightPlayer = getPlayerFromList(rightPlayerOptions, rightSide.entityId);
  const leftTeamProfile = leftTeamProfileQuery.data?.data;
  const rightTeamProfile = rightTeamProfileQuery.data?.data;
  const leftPlayerProfile = leftPlayerProfileQuery.data?.data;
  const rightPlayerProfile = rightPlayerProfileQuery.data?.data;
  const leftCompetitionAnalytics = leftCompetitionQuery.data?.data;
  const rightCompetitionAnalytics = rightCompetitionQuery.data?.data;
  const metrics = useMemo(() => {
    if (mode === "clubs") {
      return buildClubMetrics(leftTeamProfile, rightTeamProfile);
    }

    if (mode === "players") {
      return buildPlayerMetrics(leftPlayerProfile, rightPlayerProfile);
    }

    return buildCompetitionMetrics(leftCompetitionAnalytics, rightCompetitionAnalytics);
  }, [
    leftCompetitionAnalytics,
    leftPlayerProfile,
    leftTeamProfile,
    mode,
    rightCompetitionAnalytics,
    rightPlayerProfile,
    rightTeamProfile,
  ]);
  const advantage = useMemo(() => calculateAdvantage(metrics), [metrics]);
  const leftIdentity = buildSideIdentity({
    mode,
    player: leftPlayer,
    playerProfile: leftPlayerProfile,
    side: leftSide,
    sideContext: leftContext,
    team: leftTeam,
    teamProfile: leftTeamProfile,
  });
  const rightIdentity = buildSideIdentity({
    mode,
    player: rightPlayer,
    playerProfile: rightPlayerProfile,
    side: rightSide,
    sideContext: rightContext,
    team: rightTeam,
    teamProfile: rightTeamProfile,
  });
  const isComparisonLoading =
    mode === "clubs"
      ? leftTeamProfileQuery.isLoading || rightTeamProfileQuery.isLoading
      : mode === "players"
        ? leftPlayerProfileQuery.isLoading || rightPlayerProfileQuery.isLoading
        : leftCompetitionQuery.isLoading || rightCompetitionQuery.isLoading;
  const needsEntitySelection =
    mode !== "competitions" && (leftSide.entityId.length === 0 || rightSide.entityId.length === 0);
  const leftLabel = mode === "competitions" ? "Edição A" : "Lado A";
  const rightLabel = mode === "competitions" ? "Edição B" : "Lado B";

  const updateSide = (sideKey: SideKey, patch: Partial<ComparisonSideState>) => {
    if (sideKey === "left") {
      setLeftSide((current) => ({ ...current, ...patch }));
      return;
    }

    setRightSide((current) => ({ ...current, ...patch }));
  };

  return (
    <ProfileShell className="space-y-6">
      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="relative grid min-w-0 gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.42fr)]">
          <div className="min-w-0 space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag>Hub de comparativos</ProfileTag>
              <ProfileTag>{leftContext.season.label} vs {rightContext.season.label}</ProfileTag>
              <ProfileTag>{MODE_OPTIONS.find((option) => option.value === mode)?.summary}</ProfileTag>
            </div>

            <div className="min-w-0 max-w-3xl">
              <p className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-[#57657a]">
                <ComparisonIcon className="h-4 w-4" mode={mode} />
                Head-to-head
              </p>
              <h1 className="mt-3 break-words font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-[1] text-[#111c2d] sm:text-4xl md:text-[2.85rem]">
                Compare clubes, jogadores e edições
              </h1>
            </div>

            <div className="space-y-2">
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.2em] text-[#57657a]">
                Tipo de comparativo
              </p>
              <div
                className="grid gap-2 sm:grid-cols-3"
                role="tablist"
                aria-label="Tipo de comparativo"
              >
                {MODE_OPTIONS.map((option) => {
                  const isActive = option.value === mode;

                  return (
                    <button
                      aria-selected={isActive}
                      className={joinClasses(
                        "flex min-h-[4.35rem] min-w-0 items-center gap-3 rounded-[1rem] border px-3.5 py-3 text-left transition duration-200",
                        isActive
                          ? "border-[rgba(0,81,59,0.2)] bg-white/90 text-[#003526] shadow-[0_14px_34px_-24px_rgba(17,28,45,0.58)]"
                          : "border-transparent bg-transparent text-[#45536a] hover:border-white/78 hover:bg-white/58 hover:text-[#00513b]",
                      )}
                      key={option.value}
                      onClick={() => {
                        setMode(option.value);
                        setLeftSide((current) => ({ ...current, entityId: "", search: "" }));
                        setRightSide((current) => ({ ...current, entityId: "", search: "" }));
                      }}
                      role="tab"
                      type="button"
                    >
                      <span
                        className={joinClasses(
                          "grid h-9 w-9 shrink-0 place-items-center rounded-full border",
                          isActive
                            ? "border-[rgba(0,81,59,0.14)] bg-[rgba(0,81,59,0.07)] text-[#00513b]"
                            : "border-[rgba(87,101,122,0.14)] bg-[rgba(216,227,251,0.44)] text-[#57657a]",
                        )}
                      >
                        <ComparisonIcon className="h-4 w-4" mode={option.value} />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[0.76rem] font-black uppercase tracking-[0.14em]">
                          {option.label}
                        </span>
                        <span className="mt-1 block text-xs font-semibold leading-snug text-[#68778c]">
                          {option.summary}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <aside className="grid min-w-0 content-start gap-3">
            <ProfileKpi
              hint="métricas carregadas"
              label="Base"
              value={metrics.length}
            />
            <div className="grid grid-cols-3 gap-2">
              <ProfileMetricTile label="A" value={advantage.left} />
              <ProfileMetricTile label="Iguais" value={advantage.tie} tone="soft" />
              <ProfileMetricTile label="B" value={advantage.right} />
            </div>
          </aside>
        </div>
      </ProfilePanel>

      <section className="grid gap-4 xl:grid-cols-2">
        <SideConfigurator
          mode={mode}
          onChange={(patch) => updateSide("left", patch)}
          optionsError={
            mode === "clubs"
              ? leftTeamsQuery.error
              : mode === "players"
                ? leftPlayersQuery.error
                : null
          }
          optionsLoading={
            mode === "clubs"
              ? leftTeamsQuery.isLoading
              : mode === "players"
                ? leftPlayersQuery.isLoading
                : false
          }
          playerOptions={leftPlayerOptions}
          side={leftSide}
          sideContext={leftContext}
          sideLabel={leftLabel}
          teamOptions={leftTeamOptions}
        />
        <SideConfigurator
          mode={mode}
          onChange={(patch) => updateSide("right", patch)}
          optionsError={
            mode === "clubs"
              ? rightTeamsQuery.error
              : mode === "players"
                ? rightPlayersQuery.error
                : null
          }
          optionsLoading={
            mode === "clubs"
              ? rightTeamsQuery.isLoading
              : mode === "players"
                ? rightPlayersQuery.isLoading
                : false
          }
          playerOptions={rightPlayerOptions}
          side={rightSide}
          sideContext={rightContext}
          sideLabel={rightLabel}
          teamOptions={rightTeamOptions}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-stretch">
        <IdentityCard identity={leftIdentity} label={leftLabel} side="left" />
        <div className="flex items-center justify-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full border border-[rgba(191,201,195,0.55)] bg-white/84 font-[family:var(--font-profile-headline)] text-lg font-extrabold text-[#003526] shadow-[0_18px_42px_-34px_rgba(17,28,45,0.28)]">
            VS
          </span>
        </div>
        <IdentityCard identity={rightIdentity} label={rightLabel} side="right" />
      </section>

      <QueryAlert
        error={
          mode === "clubs"
            ? leftTeamProfileQuery.error ?? rightTeamProfileQuery.error
            : mode === "players"
              ? leftPlayerProfileQuery.error ?? rightPlayerProfileQuery.error
              : leftCompetitionQuery.error ?? rightCompetitionQuery.error
        }
        title="Falha ao carregar o comparativo"
      />

      {needsEntitySelection ? (
        <EmptyState
          description="Selecione um item em cada lado para montar a tabela de métricas."
          title={mode === "clubs" ? "Escolha os dois clubes" : "Escolha os dois jogadores"}
        />
      ) : null}

      {isComparisonLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={92} />
          <LoadingSkeleton height={220} />
        </div>
      ) : null}

      {!isComparisonLoading && !needsEntitySelection ? (
        <ComparisonMetricsTable
          leftLabel={leftIdentity.title}
          metrics={metrics}
          mode={mode}
          rightLabel={rightIdentity.title}
        />
      ) : null}
    </ProfileShell>
  );
}
