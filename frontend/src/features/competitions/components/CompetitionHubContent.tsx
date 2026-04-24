"use client";

import { useMemo, type ReactNode } from "react";

import Image from "next/image";
import Link from "next/link";

import {
  getCompetitionVisualAssetId,
  type CompetitionDef,
} from "@/config/competitions.registry";
import { getRankingDefinition } from "@/config/ranking.registry";
import {
  getLatestSeasonForCompetition,
  listSeasonsForCompetition,
  type SeasonDef,
} from "@/config/seasons.registry";
import {
  useCompetitionHistoricalStats,
  useCompetitionStructure,
  useStageTies,
} from "@/features/competitions/hooks";
import { fetchRanking } from "@/features/rankings/services/rankings.service";
import type { RankingTableRow } from "@/features/rankings/types";
import type {
  CompetitionHistoricalStatGroup,
  CompetitionHistoricalStatItem,
  StageTie,
} from "@/features/competitions/types";
import { resolveSeasonChampionArtwork } from "@/features/competitions/utils/champion-media";
import { resolveCompetitionSeasonSurface } from "@/features/competitions/utils/competition-season-surface";
import { fetchStandings } from "@/features/standings/services/standings.service";
import type { StandingsTableData, StandingsTableRow } from "@/features/standings/types";
import { standingsQueryKeys } from "@/features/standings/queryKeys";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import {
  ProfilePanel,
  ProfileCoveragePill,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { CompetitionRouteContextSync } from "@/shared/components/routing/CompetitionRouteContextSync";
import { useQueryWithCoverage } from "@/shared/hooks/useQueryWithCoverage";
import type { ApiResponse } from "@/shared/types/api-response.types";
import {
  buildPlayerResolverPath,
  buildSeasonHubPath,
  buildTeamResolverPath,
} from "@/shared/utils/context-routing";

type CompetitionHubContentProps = {
  competition: CompetitionDef;
};

const HISTORICAL_STATS_AS_OF_YEAR = 2025;
const HISTORICAL_TABLE_LIMIT = 5;

type EditionTopScorer = {
  entityId: string;
  entityName: string;
  goals: number;
  teamId?: string | null;
  teamName?: string | null;
};

type EditionTopScorerData = {
  scorer: EditionTopScorer | null;
};

type RunnerUpSummary = {
  teamId?: string | null;
  teamName?: string | null;
};

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
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

function describeCompetitionType(competition: CompetitionDef): string {
  if (competition.type === "domestic_league") {
    return "Liga nacional";
  }

  if (competition.type === "domestic_cup") {
    return "Copa nacional";
  }

  return "Copa internacional";
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

async function fetchSeasonTopScorer(
  competition: CompetitionDef,
  season: SeasonDef,
): Promise<ApiResponse<EditionTopScorerData>> {
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
      competitionId: competition.id,
      freshnessClass: "season",
      minSampleValue: 0,
      page: 1,
      pageSize: 1,
      seasonId: season.queryId,
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
            teamId: typeof scorerRow.teamId === "string" ? scorerRow.teamId : null,
            teamName: typeof scorerRow.teamName === "string" ? scorerRow.teamName : null,
          }
        : null,
    },
    meta: response.meta,
  };
}

function useSeasonTopScorer(competition: CompetitionDef, season: SeasonDef) {
  return useQueryWithCoverage<EditionTopScorerData>({
    enabled: Boolean(competition.id && season.queryId),
    gcTime: 30 * 60 * 1000,
    isDataEmpty: (data) => data.scorer === null,
    queryFn: () => fetchSeasonTopScorer(competition, season),
    queryKey: ["competition-hub-season-top-scorer", competition.id, season.queryId],
    staleTime: 10 * 60 * 1000,
  });
}

function formatHistoricalValue(item: CompetitionHistoricalStatItem): string {
  const localizeHistoricalTerm = (value: string): string =>
    value
      .replace(/\btitles\b/gi, "títulos")
      .replace(/\btitle\b/gi, "título")
      .replace(/\bgoals\b/gi, "gols")
      .replace(/\bgoal\b/gi, "gol")
      .replace(/\btítulos\b/gi, "Títulos")
      .replace(/\btítulo\b/gi, "Título")
      .replace(/\bgols\b/gi, "Gols")
      .replace(/\bgol\b/gi, "Gol");

  if (item.valueLabel && item.valueLabel.trim().length > 0) {
    return localizeHistoricalTerm(item.valueLabel);
  }

  if (typeof item.value === "number") {
    return formatWholeNumber(item.value);
  }

  if (typeof item.value === "string" && item.value.trim().length > 0) {
    return localizeHistoricalTerm(item.value);
  }

  return "-";
}

function isHistoricalStatsDataEmpty(data: ReturnType<typeof useCompetitionHistoricalStats>["data"]) {
  if (!data) {
    return true;
  }

  return data.champions.items.length === 0 && data.scorers.items.length === 0;
}

function resolveHistoricalRank(item: CompetitionHistoricalStatItem, index: number): number {
  if (typeof item.rank === "number" && Number.isFinite(item.rank) && item.rank > 0) {
    return item.rank;
  }

  return index + 1;
}

function buildHistoricalEntityHref(
  item: CompetitionHistoricalStatItem,
  competition: CompetitionDef,
): string | null {
  if (!item.entityId) {
    return null;
  }

  const contextFilters = {
    competitionId: competition.id,
    competitionKey: competition.key,
  };

  if (item.entityType === "team") {
    return buildTeamResolverPath(item.entityId, contextFilters);
  }

  if (item.entityType === "player") {
    return buildPlayerResolverPath(item.entityId, contextFilters);
  }

  return null;
}

function HistoricalEntityLabel({
  className,
  competition,
  isLeader = false,
  item,
}: {
  className?: string;
  competition: CompetitionDef;
  isLeader?: boolean;
  item: CompetitionHistoricalStatItem;
}) {
  const href = buildHistoricalEntityHref(item, competition);
  const mediaCategory = item.entityType === "player" ? "players" : "clubs";
  const isClubAsset = mediaCategory === "clubs";
  const mediaSizeClass = isClubAsset
    ? (isLeader ? "h-11 w-11 rounded-full" : "h-10 w-10 rounded-full")
    : (isLeader ? "h-11 w-11 rounded-full" : "h-10 w-10 rounded-full");
  const mediaNode = (
    <ProfileMedia
      alt={item.entityName}
      assetId={item.entityId}
      category={mediaCategory}
      className={mediaSizeClass}
      fallback={buildFallbackLabel(item.entityName)}
      fallbackClassName={isClubAsset ? undefined : "text-[0.6rem]"}
      imageClassName={isClubAsset ? "p-1" : "p-1.25"}
      shape="circle"
      linkBehavior="none"
    />
  );

  if (!href || !item.entityId) {
    return (
      <span className="inline-flex min-w-0 items-center gap-2.5">
        {mediaNode}
        <span className={joinClasses("truncate font-semibold text-[#111c2d]", className)}>
          {item.entityName}
        </span>
      </span>
    );
  }

  return (
    <Link
      className="inline-flex min-w-0 items-center gap-2.5 font-semibold text-[#111c2d] transition-colors hover:text-[#0f2035]"
      href={href}
    >
      {mediaNode}
      <span className={joinClasses("truncate", className)}>{item.entityName}</span>
    </Link>
  );
}

function HistoricalStatsTable({
  competition,
  group,
  title,
  valueHeader,
}: {
  competition: CompetitionDef;
  group: CompetitionHistoricalStatGroup;
  title: string;
  valueHeader: string;
}) {
  const rows = group.items.slice(0, HISTORICAL_TABLE_LIMIT);

  if (rows.length === 0) {
    return null;
  }

  return (
    <article className="overflow-hidden rounded-[1.2rem] border border-[rgba(191,201,195,0.52)] bg-white shadow-[0_18px_44px_-42px_rgba(17,28,45,0.28)]">
      <div className="border-b border-[rgba(191,201,195,0.42)] px-4 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-[#6d7b90]">
              Ranking histórico
            </p>
            <h3 className="mt-1 font-[family:var(--font-profile-headline)] text-[1.22rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
              {title}
            </h3>
          </div>
          <p className="text-[0.7rem] font-medium text-[#6d7b90]">{rows.length} registros</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[360px] border-collapse text-left text-sm">
          <tbody className="divide-y divide-[rgba(191,201,195,0.36)]">
            {rows.map((item, index) => {
              const rank = resolveHistoricalRank(item, index);
              const isLeader = rank === 1;

              return (
                <tr
                  className={joinClasses(
                    "align-middle transition-colors",
                    "h-[64px]",
                    isLeader ? "bg-[rgba(248,250,252,0.88)]" : "hover:bg-[rgba(247,249,252,0.92)]",
                  )}
                  key={`${item.statCode}-${item.entityName}-${rank}`}
                >
                  <td className="px-4 py-2">
                    <span
                      className={joinClasses(
                        "inline-flex h-7 min-w-7 items-center justify-center rounded-full border bg-white px-2 text-[0.68rem] font-semibold tabular-nums",
                        rank === 1
                          ? "border-[rgba(90,102,119,0.4)] text-[#111c2d]"
                          : "border-[rgba(160,170,184,0.5)] text-[#57657a]",
                      )}
                    >
                      {rank}
                    </span>
                  </td>
                  <td className="max-w-[16rem] px-4 py-2">
                    <HistoricalEntityLabel
                      className={isLeader ? "text-[#0f2035]" : undefined}
                      competition={competition}
                      isLeader={isLeader}
                      item={item}
                    />
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className="font-[family:var(--font-profile-headline)] text-[1.02rem] font-extrabold tracking-[-0.02em] text-[#111c2d]">
                      {formatHistoricalValue(item)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function CompetitionHistoricalStatsSection({ competition }: { competition: CompetitionDef }) {
  const historicalStatsQuery = useCompetitionHistoricalStats({
    competitionKey: competition.key,
    asOfYear: HISTORICAL_STATS_AS_OF_YEAR,
  });

  if (historicalStatsQuery.isLoading) {
    return (
      <ProfilePanel className="space-y-3">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
          Histórico
        </p>
        <p className="text-sm/6 text-[#57657a]">Carregando estatísticas históricas.</p>
      </ProfilePanel>
    );
  }

  const data = historicalStatsQuery.data;

  if (historicalStatsQuery.isError || !data || isHistoricalStatsDataEmpty(data)) {
    return null;
  }

  return (
    <ProfilePanel className="space-y-6">
      <div className="rounded-[1.2rem] border border-[rgba(191,201,195,0.5)] bg-white px-5 py-5 md:px-6 md:py-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Arquivo histórico
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[1.88rem] font-extrabold tracking-[-0.04em] text-[#111c2d] md:text-[2.05rem]">
              Recordes oficiais da competição
            </h2>
            <p className="mt-2 text-sm/6 text-[#57657a]">
              Maiores campeões e artilheiros históricos da competição.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={historicalStatsQuery.coverage} />
            <ProfileTag>Base {HISTORICAL_STATS_AS_OF_YEAR}</ProfileTag>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <HistoricalStatsTable
          competition={competition}
          group={data.champions}
          title="Maiores campeões"
          valueHeader="Títulos"
        />
        <HistoricalStatsTable
          competition={competition}
          group={data.scorers}
          title="Artilheiros históricos"
          valueHeader="Gols"
        />
      </div>
    </ProfilePanel>
  );
}

function resolveChampionFromStandings(rows: StandingsTableRow[]): StandingsTableRow | null {
  return rows.find((row) => row.position === 1) ?? rows[0] ?? null;
}

function resolveRunnerUpFromStandings(rows: StandingsTableRow[]): StandingsTableRow | null {
  const sortedRows = [...rows].sort((left, right) => left.position - right.position);

  return (
    sortedRows.find((row) => row.position === 2) ??
    sortedRows.find((row) => row.position > 1) ??
    sortedRows[1] ??
    null
  );
}

function resolveChampionTie(ties: StageTie[]): StageTie | null {
  return ties.find((tie) => tie.winnerTeamId || tie.winnerTeamName) ?? ties[0] ?? null;
}

function normalizeComparableText(value: string | null | undefined): string | null {
  const trimmedValue = value?.trim();

  if (!trimmedValue) {
    return null;
  }

  return trimmedValue.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function isResolvedTieTeam(
  teamId: string | null | undefined,
  teamName: string | null | undefined,
  winnerTeamId: string | null | undefined,
  winnerTeamName: string | null | undefined,
): boolean {
  if (winnerTeamId && teamId && winnerTeamId === teamId) {
    return true;
  }

  const normalizedTeamName = normalizeComparableText(teamName);
  const normalizedWinnerTeamName = normalizeComparableText(winnerTeamName);

  return Boolean(
    normalizedTeamName &&
      normalizedWinnerTeamName &&
      normalizedTeamName === normalizedWinnerTeamName,
  );
}

function resolveRunnerUpFromTie(tie: StageTie | null): RunnerUpSummary | null {
  if (!tie) {
    return null;
  }

  if (
    isResolvedTieTeam(
      tie.homeTeamId,
      tie.homeTeamName,
      tie.winnerTeamId,
      tie.winnerTeamName,
    )
  ) {
    return {
      teamId: tie.awayTeamId,
      teamName: tie.awayTeamName,
    };
  }

  if (
    isResolvedTieTeam(
      tie.awayTeamId,
      tie.awayTeamName,
      tie.winnerTeamId,
      tie.winnerTeamName,
    )
  ) {
    return {
      teamId: tie.homeTeamId,
      teamName: tie.homeTeamName,
    };
  }

  return null;
}

function useSeasonChampionStandings(
  competition: CompetitionDef,
  season: SeasonDef,
  enabled: boolean,
) {
  return useQueryWithCoverage<StandingsTableData>({
    queryKey: standingsQueryKeys.table({
      competitionId: competition.id,
      seasonId: season.queryId,
    }),
    queryFn: () =>
      fetchStandings({
        competitionId: competition.id,
        seasonId: season.queryId,
      }),
    enabled: enabled && Boolean(competition.id && season.queryId),
    staleTime: 5 * 60 * 1000,
    gcTime: 20 * 60 * 1000,
    isDataEmpty: (data) => data.rows.length === 0,
  });
}

function CompetitionHero({
  competition,
  latestSeason,
  seasonsCount,
}: {
  competition: CompetitionDef;
  latestSeason: SeasonDef | null;
  seasonsCount: number;
}) {
  const historicalStatsQuery = useCompetitionHistoricalStats({
    competitionKey: competition.key,
    asOfYear: HISTORICAL_STATS_AS_OF_YEAR,
  });
  const visualAssetId = getCompetitionVisualAssetId(competition);
  const artwork = latestSeason
    ? resolveSeasonChampionArtwork(competition.key, latestSeason.label)
    : null;
  const allTimeChampion = historicalStatsQuery.data?.champions.items[0] ?? null;
  const allTimeChampionName = historicalStatsQuery.isLoading
    ? "..."
    : (allTimeChampion?.entityName ?? "Não identificado");
  const allTimeChampionTitles = historicalStatsQuery.isLoading
    ? "..."
    : (allTimeChampion ? formatHistoricalValue(allTimeChampion) : "-");

  return (
    <section className="relative isolate overflow-hidden rounded-[2rem] border border-white/65 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(247,250,248,0.96)_48%,rgba(237,246,241,0.94)_100%)] p-5 shadow-[0_34px_88px_-58px_rgba(17,28,45,0.28)] md:p-6 xl:p-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.7),transparent_54%),radial-gradient(circle_at_top_right,rgba(139,214,182,0.26),transparent_42%)]" />
      <div className="pointer-events-none absolute bottom-[-18%] right-[12%] h-64 w-64 rounded-full bg-[rgba(0,53,38,0.08)] blur-3xl" />

      <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] xl:items-stretch">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileTag className="bg-white text-[#455468]">{competition.region}</ProfileTag>
            <ProfileTag className="bg-white text-[#455468]">{competition.country}</ProfileTag>
            <ProfileTag className="bg-white text-[#455468]">
              {describeCompetitionType(competition)}
            </ProfileTag>
          </div>

          <div className="grid gap-4 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-start">
            <ProfileMedia
              alt={`Logo de ${competition.name}`}
              assetId={visualAssetId}
              category="competitions"
              className="h-20 w-20 shadow-[0_24px_50px_-34px_rgba(17,28,45,0.38)] md:h-24 md:w-24"
              fallback={buildFallbackLabel(competition.shortName)}
              fallbackClassName="text-lg"
              imageClassName="p-3"
            />

            <div className="space-y-3">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#0a3d2c]">
                Página da competição
              </p>
              <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.8rem] font-extrabold leading-[0.95] tracking-[-0.06em] text-[#111c2d] md:text-[3.55rem]">
                {competition.name}
              </h1>
              <p className="max-w-3xl text-sm/7 text-[#57657a] md:text-[0.98rem]">
                Uma competição, várias edições. Escolha a temporada certa para abrir tabela,
                mata-mata, partidas, rankings e perfis no contexto correto.
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-[1.35rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-4 py-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                Temporadas
              </p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.8rem] font-extrabold text-[#111c2d]">
                {formatWholeNumber(seasonsCount)}
              </p>
            </div>
            <div className="rounded-[1.35rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-4 py-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                Última edição
              </p>
              <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.8rem] font-extrabold text-[#111c2d]">
                {latestSeason?.label ?? "-"}
              </p>
            </div>
            <div className="rounded-[1.35rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-4 py-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                Maior campeão
              </p>
              <div className="mt-3 flex min-w-0 items-center gap-3">
                {historicalStatsQuery.isLoading ? null : (
                  <ProfileMedia
                    alt={`Maior campeão ${allTimeChampionName}`}
                    assetId={allTimeChampion?.entityId}
                    category="clubs"
                    className="h-11 w-11 rounded-full"
                    fallback={buildFallbackLabel(allTimeChampionName)}
                    imageClassName="p-1.5"
                    shape="circle"
                  />
                )}
                <div className="min-w-0">
                  <p className="truncate font-[family:var(--font-profile-headline)] text-[1.2rem] font-extrabold leading-tight tracking-[-0.04em] text-[#111c2d]">
                    {allTimeChampionName}
                  </p>
                  <p className="mt-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                    {allTimeChampionTitles}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <aside className="relative min-h-[320px] overflow-hidden rounded-[1.7rem] border border-[rgba(8,48,35,0.16)] bg-[linear-gradient(135deg,#042f22_0%,#0a4a37_100%)] shadow-[0_34px_84px_-56px_rgba(8,25,20,0.62)]">
          {artwork ? (
            <Image
              alt={`Imagem da edição ${competition.name} ${latestSeason?.label ?? ""}`}
              className="object-cover object-center"
              fill
              priority
              sizes="(min-width: 1280px) 360px, 100vw"
              src={artwork.src}
            />
          ) : null}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(166,242,209,0.2),transparent_30%),linear-gradient(180deg,rgba(4,47,34,0.12)_0%,rgba(4,47,34,0.54)_46%,rgba(4,47,34,0.92)_100%)]" />
          <div className="relative flex h-full min-h-[320px] flex-col justify-between p-5 md:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/12 bg-white/10 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/88">
                Catálogo de edições
              </span>
              {latestSeason ? (
                <span className="rounded-full border border-white/12 bg-white/8 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/72">
                  {latestSeason.label}
                </span>
              ) : null}
            </div>

            <div className="space-y-4">
              <ProfileMedia
                alt={`Logo de ${competition.name}`}
                assetId={visualAssetId}
                category="competitions"
                className="h-24 w-24 border-white/16 bg-white/12 text-white"
                fallback={buildFallbackLabel(competition.shortName)}
                fallbackClassName="text-xl text-white"
                imageClassName="p-3"
                tone="contrast"
              />
              <div>
                <p className="text-sm/6 text-[#d7efe4]">
                  Entre por edição para manter filtros, rankings e calendário sempre no recorte
                  correto.
                </p>
                <p className="mt-3 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-white">
                  {seasonsCount > 0 ? `${seasonsCount} temporadas disponíveis` : "Sem temporadas"}
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function SeasonCardStat({
  label,
  media,
  value,
}: {
  label: string;
  media?: ReactNode;
  value: string;
}) {
  return (
    <div className="rounded-[1.05rem] border border-[rgba(191,201,195,0.44)] bg-[rgba(246,248,252,0.82)] px-3 py-3">
      <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
      <div className="mt-2 flex min-w-0 items-center gap-2">
        {media ? <div className="shrink-0">{media}</div> : null}
        <p className="min-w-0 truncate font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
          {value}
        </p>
      </div>
    </div>
  );
}

function SeasonCard({
  competition,
  isLatestSeason,
  season,
}: {
  competition: CompetitionDef;
  isLatestSeason: boolean;
  season: SeasonDef;
}) {
  const structureEnabled = competition.type !== "domestic_league";
  const structureQuery = useCompetitionStructure(
    {
      competitionKey: competition.key,
      seasonLabel: season.label,
    },
    {
      enabled: structureEnabled,
    },
  );
  const resolution = useMemo(
    () =>
      resolveCompetitionSeasonSurface({
        competitionType: competition.type,
        structure: structureQuery.data,
      }),
    [competition.type, structureQuery.data],
  );
  const standingsQuery = useSeasonChampionStandings(
    competition,
    season,
    competition.type === "domestic_league" || resolution.type === "league",
  );
  const finalTiesQuery = useStageTies({
    competitionKey: competition.key,
    seasonLabel: season.label,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const topScorerQuery = useSeasonTopScorer(competition, season);

  const championRow = resolveChampionFromStandings(standingsQuery.data?.rows ?? []);
  const runnerUpRow = resolveRunnerUpFromStandings(standingsQuery.data?.rows ?? []);
  const championTie = resolveChampionTie(finalTiesQuery.data?.ties ?? []);
  const runnerUpTie = resolveRunnerUpFromTie(championTie);
  const shouldUseStandingsChampion =
    competition.type === "domestic_league" || resolution.type === "league";
  const isChampionLoading =
    shouldUseStandingsChampion
      ? standingsQuery.isLoading
      : structureQuery.isLoading || finalTiesQuery.isLoading;
  const championName = isChampionLoading
    ? "..."
    : shouldUseStandingsChampion
      ? (championRow?.teamName ?? "Não identificado")
      : (championTie?.winnerTeamName ?? "Não identificado");
  const championTeamId =
    shouldUseStandingsChampion ? championRow?.teamId : championTie?.winnerTeamId;
  const runnerUpSummary = shouldUseStandingsChampion
    ? {
        teamId: runnerUpRow?.teamId,
        teamName: runnerUpRow?.teamName ?? null,
      }
    : runnerUpTie;
  const runnerUpName = isChampionLoading
    ? "..."
    : (runnerUpSummary?.teamName ?? "Não identificado");
  const topScorer = topScorerQuery.data?.scorer ?? null;
  const topScorerName = topScorerQuery.isLoading
    ? "..."
    : (topScorer?.entityName ?? "Não identificado");
  const seasonHref = buildSeasonHubPath({
    competitionKey: competition.key,
    seasonLabel: season.label,
  });

  return (
    <Link
      className={joinClasses(
        "group relative overflow-hidden rounded-[1.55rem] border px-4 py-4 shadow-[0_18px_58px_-46px_rgba(17,28,45,0.18)] transition-[transform,border-color,background-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-1 hover:border-[#8bd6b6] hover:bg-white hover:shadow-[0_28px_68px_-44px_rgba(17,28,45,0.28)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#00513b] active:scale-[0.985]",
        isLatestSeason
          ? "border-[#8bd6b6] bg-[linear-gradient(180deg,rgba(245,255,250,0.96)_0%,rgba(240,243,255,0.92)_100%)]"
          : "border-[rgba(191,201,195,0.52)] bg-white/88",
      )}
      href={seasonHref}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top_left,rgba(139,214,182,0.22),transparent_52%),linear-gradient(180deg,rgba(240,250,246,0.9)_0%,transparent_100%)]" />
      <div className="relative space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              Temporada
            </p>
            <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-[2.35rem] font-extrabold leading-none tracking-[-0.06em] text-[#111c2d]">
              {season.label}
            </h3>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {isLatestSeason ? <ProfileTag>Mais recente</ProfileTag> : null}
            <ProfileTag>{season.calendar === "annual" ? "Anual" : "Cruzada"}</ProfileTag>
          </div>
        </div>

        <div className="rounded-[1.2rem] border border-[rgba(191,201,195,0.44)] bg-white/86 px-3 py-3">
          <div className="flex items-center gap-3">
            <ProfileMedia
              alt={`Campeão ${championName}`}
              assetId={championTeamId}
              category="clubs"
              className="h-11 w-11 rounded-full"
              fallback={buildFallbackLabel(championName)}
              imageClassName="p-1.5"
              shape="circle"
              linkBehavior="none"
            />
            <div className="min-w-0">
              <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                Campeão
              </p>
              <p className="mt-1 truncate font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
                {championName}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <SeasonCardStat
            label="Artilheiro"
            media={
              topScorerQuery.isLoading ? null : (
                <ProfileMedia
                  alt={`Artilheiro ${topScorerName}`}
                  assetId={topScorer?.entityId}
                  category="players"
                  className="h-8 w-8 rounded-full"
                  fallback={buildFallbackLabel(topScorerName)}
                  imageClassName="p-1"
                  shape="circle"
                  linkBehavior="none"
                />
              )
            }
            value={topScorerName}
          />
          <SeasonCardStat
            label="Vice-campeão"
            media={
              isChampionLoading ? null : (
                <ProfileMedia
                  alt={`Vice-campeão ${runnerUpName}`}
                  assetId={runnerUpSummary?.teamId}
                  category="clubs"
                  className="h-8 w-8 rounded-full"
                  fallback={buildFallbackLabel(runnerUpName)}
                  imageClassName="p-1"
                  shape="circle"
                  linkBehavior="none"
                />
              )
            }
            value={runnerUpName}
          />
        </div>

        <div className="flex items-center justify-between border-t border-[rgba(191,201,195,0.4)] pt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
          <span>Abrir edição</span>
          <span className="transition-transform group-hover:translate-x-1">-&gt;</span>
        </div>
      </div>
    </Link>
  );
}

function SeasonsGrid({
  competition,
  latestSeason,
  seasons,
}: {
  competition: CompetitionDef;
  latestSeason: SeasonDef | null;
  seasons: SeasonDef[];
}) {
  if (seasons.length === 0) {
    return (
      <ProfilePanel className="space-y-4">
        <EmptyState
          className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
          description="Não encontramos temporadas disponíveis para esta competição no catálogo atual."
          title="Sem temporadas"
        />
      </ProfilePanel>
    );
  }

  return (
    <ProfilePanel className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Edições disponíveis
          </p>
          <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2.15rem] font-extrabold tracking-[-0.05em] text-[#111c2d]">
            Escolha a temporada
          </h2>
          <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
            Cada edição abre uma página específica, preservando o contexto correto para partidas,
            tabela, mata-mata, rankings, times e jogadores.
          </p>
        </div>
        <Link
          className="button-pill button-pill-secondary hover:-translate-y-0.5"
          href="/competitions"
        >
          Voltar ao catálogo
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {seasons.map((season) => (
          <SeasonCard
            competition={competition}
            isLatestSeason={latestSeason?.id === season.id}
            key={season.id}
            season={season}
          />
        ))}
      </div>
    </ProfilePanel>
  );
}

export function CompetitionHubContent({ competition }: CompetitionHubContentProps) {
  const seasons = listSeasonsForCompetition(competition);
  const latestSeason = getLatestSeasonForCompetition(competition) ?? null;

  return (
    <CompetitionRouteContextSync competition={competition}>
      <ProfileShell className="space-y-6" variant="plain">
        <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
          <Link className="transition-colors hover:text-[#003526]" href="/competitions">
            Competições
          </Link>
          <span className="text-[#8fa097]">/</span>
          <span>{competition.shortName}</span>
        </div>

        <CompetitionHero
          competition={competition}
          latestSeason={latestSeason}
          seasonsCount={seasons.length}
        />

        <SeasonsGrid competition={competition} latestSeason={latestSeason} seasons={seasons} />

        <CompetitionHistoricalStatsSection competition={competition} />
      </ProfileShell>
    </CompetitionRouteContextSync>
  );
}
