"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Link from "next/link";

import { useQueryClient } from "@tanstack/react-query";

import { getCompetitionById } from "@/config/competitions.registry";
import { getSeasonById } from "@/config/seasons.registry";
import { MatchesEntrySurface } from "@/features/matches/components";
import { useMatchesList } from "@/features/matches/hooks";
import { matchesQueryKeys } from "@/features/matches/queryKeys";
import { fetchMatchCenter } from "@/features/matches/services/matches.service";
import type {
  MatchCenterFilters,
  MatchListItem,
  MatchesListSortDirection,
} from "@/features/matches/types";
import {
  resolveMatchDisplayContext,
  resolveMatchRoundFilter,
} from "@/features/matches/utils/match-context";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileKpi,
  ProfileTag,
  profileHeadlineVariableClassName,
  profileTypographyClassName,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileRouteCard } from "@/shared/components/profile/ProfileRouteCard";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import {
  buildMatchCenterPath,
  buildPlayersPath,
  buildRankingsHubPath,
  buildSeasonHubTabPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type MatchStatusKey = "cancelled" | "finished" | "live" | "scheduled" | "unknown";

type MatchStatusMeta = {
  label: string;
  badgeClassName: string;
  cardClassName: string;
};

type GroupedMatches = {
  key: string;
  label: string;
  matches: MatchListItem[];
};

const MATCHES_LIST_PAGE_SIZE = 30;

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});

const DATE_GROUP_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "numeric",
  month: "long",
  weekday: "long",
});

const DATE_SHORT_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
});

const TIME_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

function formatInteger(value: number): string {
  return INTEGER_FORMATTER.format(value);
}

function describeVenue(venue: string): string {
  if (venue === "home") {
    return "Casa";
  }

  if (venue === "away") {
    return "Fora";
  }

  return "Todos os mandos";
}

function describeTimeWindow(params: {
  roundId: string | null;
  lastN: number | null;
  dateRangeStart: string | null;
  dateRangeEnd: string | null;
}): string {
  if (params.lastN !== null) {
    return `Últimas ${params.lastN} partidas`;
  }

  if (params.dateRangeStart !== null || params.dateRangeEnd !== null) {
    const startLabel = params.dateRangeStart ?? "...";
    const endLabel = params.dateRangeEnd ?? "...";

    return `${startLabel} até ${endLabel}`;
  }

  if (params.roundId !== null) {
    return `Rodada ${params.roundId}`;
  }

  return "Temporada inteira";
}

function parseKickoffDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate;
}

function normalizeStatus(status: string | null | undefined): MatchStatusKey {
  const normalizedStatus = status?.trim().toLowerCase();

  if (!normalizedStatus) {
    return "unknown";
  }

  if (["live", "inplay", "in_play"].includes(normalizedStatus)) {
    return "live";
  }

  if (["finished", "ft", "full_time"].includes(normalizedStatus)) {
    return "finished";
  }

  if (["scheduled", "ns", "not_started", "upcoming"].includes(normalizedStatus)) {
    return "scheduled";
  }

  if (["cancelled", "postponed", "suspended"].includes(normalizedStatus)) {
    return "cancelled";
  }

  return "unknown";
}

function getMatchStatusMeta(status: string | null | undefined): MatchStatusMeta {
  const statusKey = normalizeStatus(status);

  if (statusKey === "live") {
    return {
      label: "Em aberto",
      badgeClassName: "bg-[#f3f0df] text-[#6c5a00]",
      cardClassName: "border-[#eadf9d] bg-[#fffdf1]",
    };
  }

  if (statusKey === "finished") {
    return {
      label: "Encerrada",
      badgeClassName: "bg-[rgba(216,227,251,0.76)] text-[#3a485b]",
      cardClassName: "border-[rgba(191,201,195,0.5)] bg-white/92",
    };
  }

  if (statusKey === "scheduled") {
    return {
      label: "Sem placar",
      badgeClassName: "bg-[rgba(216,227,251,0.92)] text-[#1f2d40]",
      cardClassName:
        "border-[rgba(216,227,251,0.92)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(240,243,255,0.88)_100%)]",
    };
  }

  if (statusKey === "cancelled") {
    return {
      label: "Adiada",
      badgeClassName: "bg-[#ffdcc3] text-[#6e3900]",
      cardClassName:
        "border-[rgba(255,220,195,0.9)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(255,243,232,0.92)_100%)]",
    };
  }

  return {
    label: status?.trim().length ? status.trim() : "Sem status",
    badgeClassName: "bg-[rgba(216,227,251,0.76)] text-[#57657a]",
    cardClassName: "border-[rgba(191,201,195,0.5)] bg-white/92",
  };
}

function formatDateHeading(value: string | null | undefined): string {
  const parsedDate = parseKickoffDate(value);

  if (!parsedDate) {
    return "Data não informada";
  }

  return DATE_GROUP_FORMATTER.format(parsedDate);
}

function formatDateChip(value: string | null | undefined): string {
  const parsedDate = parseKickoffDate(value);

  if (!parsedDate) {
    return "--";
  }

  return DATE_SHORT_FORMATTER.format(parsedDate);
}

function formatTimeLabel(value: string | null | undefined): string {
  const parsedDate = parseKickoffDate(value);

  if (!parsedDate) {
    return "Horário não informado";
  }

  return TIME_FORMATTER.format(parsedDate);
}

function formatScore(match: MatchListItem): string {
  if (typeof match.homeScore === "number" && typeof match.awayScore === "number") {
    return `${match.homeScore} - ${match.awayScore}`;
  }

  return "x";
}

function getTeamMonogram(teamName: string): string {
  const initials = teamName
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "CLB";
}

function buildDateGroupKey(value: string | null | undefined): string {
  const parsedDate = parseKickoffDate(value);

  if (!parsedDate) {
    return "unknown-date";
  }

  return parsedDate.toISOString().slice(0, 10);
}

function buildMatchGroupKey(match: MatchListItem): string {
  const competitionType = match.competitionType ?? "league";

  if (competitionType === "cup" && match.stageName) {
    return `stage:${match.stageId ?? match.stageName}`;
  }

  if (match.roundId) {
    return `round:${match.roundId}`;
  }

  return `date:${buildDateGroupKey(match.kickoffAt)}`;
}

function buildMatchGroupLabel(match: MatchListItem): string {
  const competitionType = match.competitionType ?? "league";
  const roundName = match.roundName?.trim();

  if (competitionType === "cup" && match.stageName) {
    return match.stageName;
  }

  if (roundName) {
    return /^\d+$/.test(roundName) ? `Rodada ${roundName}` : roundName;
  }

  if (match.roundId) {
    return `Rodada ${match.roundId}`;
  }

  return formatDateHeading(match.kickoffAt);
}

function MatchDiscoveryCard({
  href,
  match,
  onPrefetch,
}: {
  href: string;
  match: MatchListItem;
  onPrefetch: (matchId: string) => void;
}) {
  const statusMeta = getMatchStatusMeta(match.status);
  const displayContext = resolveMatchDisplayContext(match);
  const homeTeamName = match.homeTeamName ?? "Mandante";
  const awayTeamName = match.awayTeamName ?? "Visitante";
  const score = formatScore(match);
  const isScheduled = normalizeStatus(match.status) === "scheduled";

  return (
    <article
      className={`overflow-hidden rounded-[1.55rem] border p-5 transition-colors hover:bg-white ${statusMeta.cardClassName}`}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-[1.2rem] bg-[rgba(240,243,255,0.96)] text-center">
            <span className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              {formatDateChip(match.kickoffAt)}
            </span>
            <span className="mt-1 text-[0.72rem] font-medium text-[#1f2d40]">
              {formatTimeLabel(match.kickoffAt)}
            </span>
          </div>

          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex rounded-full px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] ${statusMeta.badgeClassName}`}
              >
                {statusMeta.label}
              </span>
              {match.competitionName ? <ProfileTag>{match.competitionName}</ProfileTag> : null}
              {displayContext.tags.map((tag) => (
                <ProfileTag key={`${match.matchId}-${tag}`}>{tag}</ProfileTag>
              ))}
            </div>

            <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
              <div className="flex min-w-0 items-center gap-3">
                <ProfileMedia
                  alt={homeTeamName}
                  assetId={match.homeTeamId}
                  category="clubs"
                  className="h-11 w-11 border-[rgba(191,201,195,0.45)] bg-white"
                  fallback={getTeamMonogram(homeTeamName)}
                  fallbackClassName="text-xs"
                  imageClassName="p-1.5"
                  shape="circle"
                />
                <span className="truncate font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
                  {homeTeamName}
                </span>
              </div>
              <span className="inline-flex w-fit rounded-full bg-[#003526] px-4 py-1.5 text-sm font-bold text-white">
                {score}
              </span>
              <div className="flex min-w-0 items-center gap-3">
                <ProfileMedia
                  alt={awayTeamName}
                  assetId={match.awayTeamId}
                  category="clubs"
                  className="h-11 w-11 border-[rgba(191,201,195,0.45)] bg-white"
                  fallback={getTeamMonogram(awayTeamName)}
                  fallbackClassName="text-xs"
                  imageClassName="p-1.5"
                  shape="circle"
                />
                <span className="truncate font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
                  {awayTeamName}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-[#57657a]">
              {match.venueName ? <span>{match.venueName}</span> : null}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-3 lg:items-end">
          <Link
            aria-label={`Abrir central da partida de ${homeTeamName} x ${awayTeamName}`}
            className={`button-pill ${isScheduled ? "button-pill-soft" : "button-pill-primary"}`}
            href={href}
            onFocus={() => {
              onPrefetch(match.matchId);
            }}
            onMouseEnter={() => {
              onPrefetch(match.matchId);
            }}
          >
            Central da partida
          </Link>
          <Link
            className="text-xs font-semibold uppercase tracking-[0.16em] text-[#57657a] transition-colors hover:text-[#003526]"
            href={href}
            onFocus={() => {
              onPrefetch(match.matchId);
            }}
            onMouseEnter={() => {
              onPrefetch(match.matchId);
            }}
          >
            {homeTeamName} x {awayTeamName}
          </Link>
        </div>
      </div>
    </article>
  );
}

function MatchesSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }, (_, index) => (
        <section
          className="rounded-[1.55rem] border border-[rgba(191,201,195,0.5)] bg-white/88 p-5"
          key={`matches-loading-${index}`}
        >
          <div className="grid gap-4 lg:grid-cols-[84px_minmax(0,1fr)_220px] lg:items-center">
            <LoadingSkeleton height={64} />
            <div className="space-y-3">
              <LoadingSkeleton height={12} width="40%" />
              <LoadingSkeleton height={28} width="85%" />
              <LoadingSkeleton height={12} width="55%" />
            </div>
            <div className="space-y-3">
              <LoadingSkeleton height={36} />
              <LoadingSkeleton height={16} />
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}

export default function MatchesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sortDirection, setSortDirection] = useState<MatchesListSortDirection>("desc");
  const queryClient = useQueryClient();
  const prefetchedMatchIdsRef = useRef<Set<string>>(new Set());
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const resolvedContext = useResolvedCompetitionContext();
  const { params: timeRangeParams } = useTimeRange();
  const hasValidContext = Boolean(competitionId && seasonId);

  const matchesQuery = useMatchesList({
    allPages: false,
    enabled: hasValidContext,
    page,
    pageSize: MATCHES_LIST_PAGE_SIZE,
    search,
    sortBy: "kickoffAt",
    sortDirection,
  });

  const competitionName = getCompetitionById(competitionId)?.name;
  const seasonLabel = getSeasonById(seasonId)?.label;
  const contextLabel = [competitionName, seasonLabel].filter(Boolean).join(" · ");

  const detailPrefetchFilters = useMemo<MatchCenterFilters>(
    () => ({
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      includeTimeline: true,
      includeLineups: true,
      includePlayerStats: true,
    }),
    [
      competitionId,
      seasonId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  const prefetchMatchDetail = useCallback(
    (matchId: string) => {
      const normalizedMatchId = matchId.trim();

      if (
        normalizedMatchId.length === 0 ||
        prefetchedMatchIdsRef.current.has(normalizedMatchId)
      ) {
        return;
      }

      prefetchedMatchIdsRef.current.add(normalizedMatchId);

      void queryClient.prefetchQuery({
        queryKey: matchesQueryKeys.center(normalizedMatchId, detailPrefetchFilters),
        queryFn: () => fetchMatchCenter(normalizedMatchId, detailPrefetchFilters),
        staleTime: 5 * 60 * 1000,
      });
    },
    [detailPrefetchFilters, queryClient],
  );

  useEffect(() => {
    prefetchedMatchIdsRef.current.clear();
  }, [detailPrefetchFilters]);

  const buildMatchHref = useCallback(
    (match: MatchListItem) =>
      buildMatchCenterPath(match.matchId, {
        competitionId: match.competitionId ?? competitionId,
        seasonId: match.seasonId ?? seasonId,
        roundId: resolveMatchRoundFilter(match, roundId),
        venue,
        lastN,
        dateRangeStart,
        dateRangeEnd,
      }),
    [competitionId, dateRangeEnd, dateRangeStart, lastN, roundId, seasonId, venue],
  );

  const currentPageMatches = matchesQuery.data?.items ?? [];
  const matchesPagination = matchesQuery.meta?.pagination;
  const totalMatches = matchesPagination?.totalCount ?? currentPageMatches.length;
  const totalPages = Math.max(
    1,
    page,
    matchesPagination?.totalPages ?? Math.ceil(totalMatches / MATCHES_LIST_PAGE_SIZE),
  );

  useEffect(() => {
    setPage(1);
  }, [
    competitionId,
    dateRangeEnd,
    dateRangeStart,
    lastN,
    roundId,
    search,
    seasonId,
    sortDirection,
    venue,
  ]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const groupedMatches = useMemo<GroupedMatches[]>(() => {
    const groups = new Map<string, GroupedMatches>();

    for (const match of currentPageMatches) {
      const key = buildMatchGroupKey(match);
      const existingGroup = groups.get(key);

      if (existingGroup) {
        existingGroup.matches.push(match);
        continue;
      }

      groups.set(key, {
        key,
        label: buildMatchGroupLabel(match),
        matches: [match],
      });
    }

    return Array.from(groups.values());
  }, [currentPageMatches]);

  const currentPageRange = useMemo(() => {
    if (totalMatches === 0 || currentPageMatches.length === 0) {
      return {
        start: 0,
        end: 0,
      };
    }

    const start = (page - 1) * MATCHES_LIST_PAGE_SIZE + 1;
    const end = Math.min(start + currentPageMatches.length - 1, totalMatches);

    return { start, end };
  }, [currentPageMatches.length, page, totalMatches]);

  const visiblePageNumbers = useMemo(() => {
    const maxVisiblePages = 5;
    const safeTotalPages = Math.max(totalPages, 1);
    const startPage = Math.max(
      1,
      Math.min(page - Math.floor(maxVisiblePages / 2), safeTotalPages - maxVisiblePages + 1),
    );
    const endPage = Math.min(safeTotalPages, startPage + maxVisiblePages - 1);

    return Array.from({ length: endPage - startPage + 1 }, (_, index) => startPage + index);
  }, [page, totalPages]);

  const activeWindowLabel = useMemo(() => describeTimeWindow(timeRangeParams), [timeRangeParams]);
  const sortLabel = sortDirection === "desc" ? "Mais recentes primeiro" : "Mais antigas primeiro";
  const seasonHubHref = resolvedContext
    ? buildSeasonHubTabPath(resolvedContext, "calendar", {
        competitionId,
        seasonId,
        roundId,
        venue,
        lastN,
        dateRangeStart,
        dateRangeEnd,
      })
    : "/competitions";
  const teamsHref = buildTeamsPath({
    competitionId,
    seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });
  const playersHref = buildPlayersPath({
    competitionId,
    seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });
  const rankingsHref = buildRankingsHubPath({
    competitionId,
    seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });

  if (!hasValidContext) {
    return <MatchesEntrySurface />;
  }

  return (
    <main
      className={`${profileTypographyClassName} ${profileHeadlineVariableClassName} space-y-6 text-[#111c2d]`}
    >
      <section className="relative isolate overflow-hidden rounded-[2rem] bg-[linear-gradient(180deg,#eef5ff_0%,#f9f9ff_44%,#f4faf7_100%)] p-4 shadow-[0_30px_90px_-55px_rgba(17,28,45,0.42)] md:p-6 xl:p-8">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.95),transparent_52%),radial-gradient(circle_at_top_right,rgba(139,214,182,0.42),transparent_46%)]" />
        <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.95fr)]">
          <section className="overflow-hidden rounded-[1.85rem] bg-[linear-gradient(135deg,#003526_0%,#004e39_100%)] p-6 text-white shadow-[0_34px_90px_-58px_rgba(0,53,38,0.9)]">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/10 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-white/78">
                Acervo
              </span>
              <span className="rounded-full bg-white/10 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-white/78">
                {activeWindowLabel}
              </span>
            </div>

            <div className="mt-6 max-w-3xl">
              <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
                Lista de partidas
              </p>
              <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] md:text-5xl">
                Partidas
              </h1>
              <p className="mt-3 max-w-2xl text-sm/6 text-white/74">
                {contextLabel}. Explore as partidas do recorte e entre direto na central de cada
                jogo.
              </p>
              <Link
                className="mt-5 inline-flex items-center rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/16"
                href={seasonHubHref}
              >
                ← Temporada {seasonLabel ?? "selecionada"}
              </Link>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-1">
              <ProfileKpi
                hint="No recorte atual"
                invert
                label="Jogos no recorte"
                value={matchesQuery.isLoading ? "..." : formatInteger(totalMatches)}
              />
            </div>
          </section>

          <div className="grid gap-4">
            <section className="rounded-[1.6rem] border border-white/60 bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_22px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl">
              <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                Leitura atual
              </p>
              <dl className="mt-4 space-y-3 text-sm text-[#1f2d40]">
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-[#57657a]">Competição</dt>
                  <dd className="text-right font-medium">{competitionName ?? "Todas"}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-[#57657a]">Temporada</dt>
                  <dd className="text-right font-medium">{seasonLabel ?? "Todas"}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-[#57657a]">Mando</dt>
                  <dd className="text-right font-medium">{describeVenue(venue)}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-[#57657a]">Janela</dt>
                  <dd className="text-right font-medium">{activeWindowLabel}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-[#57657a]">Ordenação</dt>
                  <dd className="text-right font-medium">{sortLabel}</dd>
                </div>
              </dl>
            </section>

          </div>
        </div>
      </section>

      {matchesQuery.isError ? (
        <ProfileAlert
          title={
            currentPageMatches.length === 0
              ? "Falha ao carregar a lista"
              : "Lista carregada com alerta"
          }
          tone={currentPageMatches.length === 0 ? "critical" : "warning"}
        >
          <p>{matchesQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-4">
        <ProfileRouteCard
          description="Volte para a temporada antes de aprofundar a análise."
          href={seasonHubHref}
          label="Temporada"
          title="Temporada"
        />
        <ProfileRouteCard
          description="Abra os perfis de time ligados a esta mesma competição, temporada e janela."
          href={teamsHref}
          label="Times"
          title="Times"
        />
        <ProfileRouteCard
          description="Cruze as partidas com atletas e siga para perfis mantendo os mesmos filtros."
          href={playersHref}
          label="Descoberta"
          title="Jogadores"
        />
        <ProfileRouteCard
          description="Compare líderes da temporada sem mudar o contexto das partidas."
          href={rankingsHref}
          label="Leitura comparativa"
          title="Rankings"
        />
      </section>

      {matchesQuery.isPartial ? (
        <PartialDataBanner
          className="rounded-[1.35rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={matchesQuery.coverage}
          message="Algumas partidas ainda estão incompletas nesta temporada. Use a lista como referência, não como leitura exaustiva."
        />
      ) : null}

      <section className="rounded-[1.75rem] border border-white/60 bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_24px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Busca e refinamento local
            </p>
            <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
              Combine busca e ordenação para encontrar a partida certa sem sair desta temporada.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{competitionName ?? "Todas as competições"}</ProfileTag>
            <ProfileTag>{seasonLabel ?? "Todas as temporadas"}</ProfileTag>
            <ProfileTag>{sortLabel}</ProfileTag>
          </div>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Buscar partida
            <div className="flex items-center gap-3 rounded-[1.3rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-xs font-semibold text-[#003526]">
                Q
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none placeholder:text-[#707974]"
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
                placeholder="Ex.: Arsenal"
                type="text"
                value={search}
              />
            </div>
          </label>

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Ordenação por data
            <div className="flex items-center gap-3 rounded-[1.3rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
                Ord
              </span>
              <select
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none"
                onChange={(event) => {
                  setSortDirection(event.target.value as MatchesListSortDirection);
                }}
                value={sortDirection}
              >
                <option value="desc">Mais recentes primeiro</option>
                <option value="asc">Mais antigas primeiro</option>
              </select>
            </div>
          </label>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section className="rounded-[1.75rem] border border-white/60 bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_24px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl">
          <div className="flex flex-col gap-4 border-b border-[rgba(191,201,195,0.55)] pb-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                Acervo
              </p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                Lista de partidas
              </h2>
              <p className="mt-2 max-w-2xl text-sm/6 text-[#57657a]">
                Cada linha abre a central do jogo mantendo competição, temporada e filtros atuais.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.3rem] bg-[rgba(240,243,255,0.96)] px-4 py-3">
                <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                  Página atual
                </p>
                <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                  {matchesQuery.isLoading ? "..." : `${page} de ${totalPages}`}
                </p>
              </div>
              <div className="rounded-[1.3rem] bg-[rgba(240,243,255,0.96)] px-4 py-3">
                <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                  Mostrando
                </p>
                <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                  {matchesQuery.isLoading
                    ? "..."
                    : `${formatInteger(currentPageRange.start)}-${formatInteger(currentPageRange.end)}`}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-8">
            {matchesQuery.isLoading ? <MatchesSkeleton /> : null}

            {!matchesQuery.isLoading && currentPageMatches.length === 0 ? (
              <EmptyState
                description="Nenhuma partida encontrada com os filtros atuais."
                title="Sem partidas"
              />
            ) : null}

            {!matchesQuery.isLoading && currentPageMatches.length > 0 && totalPages > 1 ? (
              <div className="flex flex-col gap-4 rounded-[1.45rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(244,247,252,0.82)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                    Navegação da lista
                  </p>
                  <p className="text-sm text-[#57657a]">
                    Mostrando {formatInteger(currentPageRange.start)} a{" "}
                    {formatInteger(currentPageRange.end)} de {formatInteger(totalMatches)}{" "}
                    partidas.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    className="inline-flex items-center rounded-full border border-[rgba(191,201,195,0.55)] bg-white px-3.5 py-2 text-sm font-semibold text-[#1f2d40] transition-colors hover:border-[rgba(0,53,38,0.24)] hover:text-[#003526] disabled:cursor-not-allowed disabled:opacity-45"
                    disabled={page === 1}
                    onClick={() => {
                      setPage((currentPage) => Math.max(1, currentPage - 1));
                    }}
                    type="button"
                  >
                    Anterior
                  </button>

                  {visiblePageNumbers.map((pageNumber) => (
                    <button
                      aria-current={pageNumber === page ? "page" : undefined}
                      className={`inline-flex h-10 min-w-10 items-center justify-center rounded-full px-3 text-sm font-semibold transition-colors ${
                        pageNumber === page
                          ? "bg-[#003526] text-white"
                          : "border border-[rgba(191,201,195,0.55)] bg-white text-[#1f2d40] hover:border-[rgba(0,53,38,0.24)] hover:text-[#003526]"
                      }`}
                      key={`matches-page-${pageNumber}`}
                      onClick={() => {
                        setPage(pageNumber);
                      }}
                      type="button"
                    >
                      {pageNumber}
                    </button>
                  ))}

                  <button
                    className="inline-flex items-center rounded-full border border-[rgba(191,201,195,0.55)] bg-white px-3.5 py-2 text-sm font-semibold text-[#1f2d40] transition-colors hover:border-[rgba(0,53,38,0.24)] hover:text-[#003526] disabled:cursor-not-allowed disabled:opacity-45"
                    disabled={page === totalPages}
                    onClick={() => {
                      setPage((currentPage) => Math.min(totalPages, currentPage + 1));
                    }}
                    type="button"
                  >
                    Próxima
                  </button>
                </div>
              </div>
            ) : null}

            {!matchesQuery.isLoading
              ? groupedMatches.map((group) => (
                  <section className="space-y-4" key={group.key}>
                    <div className="flex items-center gap-4">
                      <h3 className="font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
                        {group.label}
                      </h3>
                      <div className="h-px flex-1 bg-[rgba(191,201,195,0.55)]" />
                    </div>
                    <div className="space-y-4">
                      {group.matches.map((match) => (
                        <MatchDiscoveryCard
                          href={buildMatchHref(match)}
                          key={match.matchId}
                          match={match}
                          onPrefetch={prefetchMatchDetail}
                        />
                      ))}
                    </div>
                  </section>
                ))
              : null}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-[1.75rem] border border-white/60 bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_22px_56px_-48px_rgba(17,28,45,0.28)] backdrop-blur-xl">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Como usar esta lista
            </p>
            <div className="mt-4 space-y-3 text-sm/6 text-[#57657a]">
              <p>
                Abra uma partida para acompanhar linha do tempo, escalações e estatísticas no mesmo
                contexto deste recorte.
              </p>
              <p>
                Use a busca por time e a ordenação por data para ajustar a leitura do recorte.
              </p>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
