"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useQueryClient } from "@tanstack/react-query";

import { getCompetitionById } from "@/config/competitions.registry";
import { formatMetricValue } from "@/config/metrics.registry";
import { getSeasonById } from "@/config/seasons.registry";
import { usePlayersList } from "@/features/players/hooks";
import { playersQueryKeys } from "@/features/players/queryKeys";
import { fetchPlayerProfile } from "@/features/players/services/players.service";
import type {
  PlayerListItem,
  PlayerProfileFilters,
  PlayersSortBy,
  PlayersSortDirection,
} from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import { useComparisonStore } from "@/shared/stores/comparison.store";
import {
  appendFilterQueryString,
  buildCanonicalPlayerPath,
  buildCanonicalTeamPath,
  buildPlayerResolverPath,
  buildRankingPath,
  buildSeasonHubTabPath,
  buildTeamsPath,
  buildTeamResolverPath,
} from "@/shared/utils/context-routing";

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});

const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function parseMinMinutes(value: string): number | null {
  const normalizedValue = value.trim();

  if (normalizedValue.length === 0) {
    return null;
  }

  const parsedValue = Number.parseInt(normalizedValue, 10);

  if (!Number.isInteger(parsedValue) || parsedValue < 0) {
    return null;
  }

  return parsedValue;
}

function parseNullableQueryValue(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const normalizedValue = value.trim();
  return normalizedValue.length > 0 ? normalizedValue : null;
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

function getInitials(name: string): string {
  const tokens = name
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0)
    .slice(0, 2);

  if (tokens.length === 0) {
    return "PL";
  }

  return tokens.map((token) => token[0]?.toUpperCase() ?? "").join("");
}

const POSITION_LABELS: Record<string, string> = {
  attacker: "Atacante",
  attackingmidfield: "Meia atacante",
  attackingmidfielder: "Meia atacante",
  cam: "Meia atacante",
  cb: "Zagueiro",
  centerback: "Zagueiro",
  centerforward: "Centroavante",
  centreback: "Zagueiro",
  centreforward: "Centroavante",
  cf: "Centroavante",
  cm: "Meia central",
  cdm: "Volante",
  defender: "Defensor",
  defensivemidfield: "Volante",
  defensivemidfielder: "Volante",
  dm: "Volante",
  forward: "Atacante",
  fullback: "Lateral",
  gk: "Goleiro",
  goalkeeper: "Goleiro",
  keeper: "Goleiro",
  lb: "Lateral esquerdo",
  leftback: "Lateral esquerdo",
  leftmidfield: "Meia esquerda",
  leftmidfielder: "Meia esquerda",
  leftwing: "Ponta esquerda",
  leftwingback: "Ala esquerdo",
  leftwinger: "Ponta esquerda",
  lm: "Meia esquerda",
  lw: "Ponta esquerda",
  midfielder: "Meia",
  ram: "Meia direita",
  rb: "Lateral direito",
  rightback: "Lateral direito",
  rightmidfield: "Meia direita",
  rightmidfielder: "Meia direita",
  rightwing: "Ponta direita",
  rightwingback: "Ala direito",
  rightwinger: "Ponta direita",
  rm: "Meia direita",
  rw: "Ponta direita",
  secondstriker: "Segundo atacante",
  st: "Centroavante",
  striker: "Centroavante",
  wingback: "Ala",
  winger: "Ponta",
};

function normalizePositionKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z]/g, "")
    .toLowerCase();
}

function formatPosition(position: string | null | undefined): string {
  if (!position) {
    return "Sem posição";
  }

  const normalizedPosition = position.trim();
  const mappedPosition = POSITION_LABELS[normalizePositionKey(normalizedPosition)];

  if (mappedPosition) {
    return mappedPosition;
  }

  if (normalizedPosition.length <= 3) {
    return normalizedPosition.toUpperCase();
  }

  return normalizedPosition;
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

function resolveSortByLabel(sortBy: PlayersSortBy): string {
  if (sortBy === "playerName") {
    return "Nome";
  }

  if (sortBy === "minutesPlayed") {
    return "Minutos";
  }

  if (sortBy === "assists") {
    return "Assists";
  }

  if (sortBy === "rating") {
    return "Nota";
  }

  return "Gols";
}

function resolveSortDirectionLabel(sortDirection: PlayersSortDirection): string {
  return sortDirection === "asc" ? "Menor para maior" : "Maior para menor";
}

function shouldShowCoverageNotice(status: string, percentage?: number): boolean {
  if (status !== "partial") {
    return false;
  }

  if (typeof percentage === "number") {
    return percentage < 95;
  }

  return true;
}

function resolveCoverageMessage(percentage?: number): string {
  if (typeof percentage === "number") {
    return `Dados parciais neste recorte (${percentage.toFixed(0)}% coberto).`;
  }

  return "Dados parciais neste recorte.";
}

function formatMinutesCell(value: number | null | undefined): string {
  return formatInteger(value);
}

type PlayersPageIconName =
  | "assist"
  | "compare"
  | "players"
  | "ranking"
  | "search"
  | "shield"
  | "star";

function PlayersPageIcon({
  className,
  icon,
}: {
  className?: string;
  icon: PlayersPageIconName;
}) {
  const sharedClassName = className ?? "h-4 w-4";

  if (icon === "players") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M8.5 11.2a3.1 3.1 0 1 0 0-6.2 3.1 3.1 0 0 0 0 6.2ZM15.5 11.2a3.1 3.1 0 1 0 0-6.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
        <path
          d="M3.8 19c.6-3.1 2.3-4.8 4.7-4.8s4.1 1.7 4.7 4.8M12.7 16c.8-1.2 1.9-1.8 3.2-1.8 2.2 0 3.7 1.6 4.3 4.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "ranking") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M5 18V10h4v8M10 18V5h4v13M15 18v-6h4v6" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4 18.5h16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (icon === "shield") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 18 7v5.4c0 3.3-2 5.8-6 7.1-4-1.3-6-3.8-6-7.1V7l6-2.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "assist") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M5 12h9" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        <path
          d="m11 8 4 4-4 4M18.5 6.5v11"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "compare") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M8 7 4 11l4 4M16 7l4 4-4 4M20 11H4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (icon === "search") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="10.8" cy="10.8" r="5.8" stroke="currentColor" strokeWidth="1.8" />
        <path d="m15.4 15.4 4.1 4.1" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
      <path
        d="m12 4.6 1.9 4 4.4.6-3.2 3.1.8 4.4-3.9-2.1-3.9 2.1.8-4.4-3.2-3.1 4.4-.6 1.9-4Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function PlayersLinkButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: PlayersPageIconName;
  label: string;
}) {
  return (
    <Link
      className="group inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-4 py-2 text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/86 transition-colors hover:border-white/28 hover:bg-white/18"
      href={href}
    >
      <PlayersPageIcon className="h-4 w-4 transition-transform group-hover:scale-110" icon={icon} />
      {label}
    </Link>
  );
}

function PlayersHeroMetric({
  hint,
  icon,
  label,
  value,
}: {
  hint: string;
  icon: PlayersPageIconName;
  label: string;
  value: string;
}) {
  return (
    <article className="group flex min-h-[9.2rem] flex-col justify-between rounded-[1.35rem] border border-white/12 bg-white/10 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/14">
      <div className="flex items-center justify-between gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/12 text-white">
          <PlayersPageIcon className="h-5 w-5" icon={icon} />
        </span>
        <p className="text-right text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/58">
          {label}
        </p>
      </div>
      <p className="mt-4 font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-none tracking-[-0.03em]">
        {value}
      </p>
      <p className="mt-2 text-sm text-white/62">{hint}</p>
    </article>
  );
}

function resolveFeaturedPlayerMetric(player: PlayerListItem, sortBy: PlayersSortBy) {
  if (sortBy === "assists") {
    return { label: "Assists", value: formatInteger(player.assists) };
  }

  if (sortBy === "minutesPlayed") {
    return { label: "Minutos", value: formatInteger(player.minutesPlayed) };
  }

  if (sortBy === "rating") {
    return { label: "Nota", value: formatDecimal(player.rating) };
  }

  const goalInvolvements = (player.goals ?? 0) + (player.assists ?? 0);

  if (sortBy === "playerName") {
    return { label: "G+A", value: formatInteger(goalInvolvements) };
  }

  return { label: "Gols", value: formatInteger(player.goals) };
}

export default function PlayersPage() {
  const searchParams = useSearchParams();
  const selectedStageId = parseNullableQueryValue(searchParams.get("stageId"));
  const selectedStageFormat = parseNullableQueryValue(searchParams.get("stageFormat"));

  const [search, setSearch] = useState("");
  const [minMinutesInput, setMinMinutesInput] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState<PlayersSortBy>("goals");
  const [sortDirection, setSortDirection] = useState<PlayersSortDirection>("desc");

  const deferredSearch = useDeferredValue(search);
  const normalizedMinMinutes = useMemo(() => parseMinMinutes(minMinutesInput), [minMinutesInput]);

  const queryClient = useQueryClient();
  const { competitionId, seasonId, venue } = useGlobalFiltersState();
  const resolvedContext = useResolvedCompetitionContext();
  const { params: timeRangeParams } = useTimeRange();
  const comparisonEntityType = useComparisonStore((state) => state.entityType);
  const selectedIds = useComparisonStore((state) => state.selectedIds);
  const addToComparison = useComparisonStore((state) => state.add);
  const removeFromComparison = useComparisonStore((state) => state.remove);
  const setComparisonEntityType = useComparisonStore((state) => state.setEntityType);

  useEffect(() => {
    setPage(1);
  }, [
    competitionId,
    seasonId,
    deferredSearch,
    normalizedMinMinutes,
    pageSize,
    selectedStageFormat,
    selectedStageId,
    sortBy,
    sortDirection,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
    venue,
  ]);

  const competitionName = getCompetitionById(competitionId)?.name ?? null;
  const seasonLabel = getSeasonById(seasonId)?.label ?? null;
  const activeWindowLabel = useMemo(() => describeTimeWindow(timeRangeParams), [timeRangeParams]);
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const playersQuery = usePlayersList({
    search: deferredSearch,
    minMinutes: normalizedMinMinutes,
    stageId: selectedStageId,
    stageFormat: selectedStageFormat,
    page,
    pageSize,
    sortBy,
    sortDirection,
  });

  const rows = playersQuery.data?.items ?? [];
  const pagination = playersQuery.meta?.pagination;
  const totalCount = pagination?.totalCount ?? rows.length;
  const totalPages = Math.max(pagination?.totalPages ?? 1, 1);
  const currentPage = pagination?.page ?? page;
  const resolvedPageSize = pagination?.pageSize ?? pageSize;
  const currentRangeStart = totalCount === 0 ? 0 : (currentPage - 1) * resolvedPageSize + 1;
  const currentRangeEnd = totalCount === 0 ? 0 : currentRangeStart + rows.length - 1;

  const detailPrefetchFilters = useMemo<PlayerProfileFilters>(
    () => ({
      competitionId,
      seasonId,
      roundId: timeRangeParams.roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
      stageId: selectedStageId,
      stageFormat: selectedStageFormat,
      includeRecentMatches: true,
    }),
    [
      competitionId,
      seasonId,
      selectedStageFormat,
      selectedStageId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  const prefetchPlayerDetail = useCallback(
    (playerId: string) => {
      const normalizedPlayerId = playerId.trim();

      if (normalizedPlayerId.length === 0) {
        return;
      }

      void queryClient.prefetchQuery({
        queryKey: playersQueryKeys.profile(normalizedPlayerId, detailPrefetchFilters),
        queryFn: () => fetchPlayerProfile(normalizedPlayerId, detailPrefetchFilters),
        staleTime: 5 * 60 * 1000,
      });
    },
    [detailPrefetchFilters, queryClient],
  );

  const getPlayerHref = useCallback(
    (playerId: string) =>
      resolvedContext
        ? appendFilterQueryString(
            buildCanonicalPlayerPath(resolvedContext, playerId),
            {
              competitionId,
              seasonId,
              roundId: timeRangeParams.roundId,
              stageId: selectedStageId,
              stageFormat: selectedStageFormat,
              venue,
              lastN: timeRangeParams.lastN,
              dateRangeStart: timeRangeParams.dateRangeStart,
              dateRangeEnd: timeRangeParams.dateRangeEnd,
            },
            ["competitionId", "seasonId"],
          )
        : buildPlayerResolverPath(playerId, {
            competitionId,
            seasonId,
            roundId: timeRangeParams.roundId,
            stageId: selectedStageId,
            stageFormat: selectedStageFormat,
            venue,
            lastN: timeRangeParams.lastN,
            dateRangeStart: timeRangeParams.dateRangeStart,
            dateRangeEnd: timeRangeParams.dateRangeEnd,
          }),
    [
      competitionId,
      resolvedContext,
      seasonId,
      selectedStageFormat,
      selectedStageId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  const getTeamHref = useCallback(
    (player: PlayerListItem) => {
      if (!player.teamId || !player.teamName || (player.teamCount ?? 0) > 1) {
        return null;
      }

      return resolvedContext
        ? appendFilterQueryString(
            buildCanonicalTeamPath(resolvedContext, player.teamId),
            {
              competitionId,
              seasonId,
              roundId: timeRangeParams.roundId,
              stageId: selectedStageId,
              stageFormat: selectedStageFormat,
              venue,
              lastN: timeRangeParams.lastN,
              dateRangeStart: timeRangeParams.dateRangeStart,
              dateRangeEnd: timeRangeParams.dateRangeEnd,
            },
            ["competitionId", "seasonId"],
          )
        : buildTeamResolverPath(player.teamId, {
            competitionId,
            seasonId,
            roundId: timeRangeParams.roundId,
            stageId: selectedStageId,
            stageFormat: selectedStageFormat,
            venue,
            lastN: timeRangeParams.lastN,
            dateRangeStart: timeRangeParams.dateRangeStart,
            dateRangeEnd: timeRangeParams.dateRangeEnd,
          });
    },
    [
      competitionId,
      resolvedContext,
      seasonId,
      selectedStageFormat,
      selectedStageId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  const getTeamAssetHref = useCallback(
    (teamId: string) =>
      resolvedContext
        ? appendFilterQueryString(
            buildCanonicalTeamPath(resolvedContext, teamId),
            {
              competitionId,
              seasonId,
              roundId: timeRangeParams.roundId,
              stageId: selectedStageId,
              stageFormat: selectedStageFormat,
              venue,
              lastN: timeRangeParams.lastN,
              dateRangeStart: timeRangeParams.dateRangeStart,
              dateRangeEnd: timeRangeParams.dateRangeEnd,
            },
            ["competitionId", "seasonId"],
          )
        : buildTeamResolverPath(teamId, {
            competitionId,
            seasonId,
            roundId: timeRangeParams.roundId,
            stageId: selectedStageId,
            stageFormat: selectedStageFormat,
            venue,
            lastN: timeRangeParams.lastN,
            dateRangeStart: timeRangeParams.dateRangeStart,
            dateRangeEnd: timeRangeParams.dateRangeEnd,
          }),
    [
      competitionId,
      resolvedContext,
      seasonId,
      selectedStageFormat,
      selectedStageId,
      timeRangeParams.dateRangeEnd,
      timeRangeParams.dateRangeStart,
      timeRangeParams.lastN,
      timeRangeParams.roundId,
      venue,
    ],
  );

  const handleCompareAction = useCallback(
    (playerId: string) => {
      if (comparisonEntityType !== "player") {
        setComparisonEntityType("player");
      }

      if (selectedIdsSet.has(playerId)) {
        removeFromComparison(playerId);
        return;
      }

      addToComparison(playerId);
    },
    [
      addToComparison,
      comparisonEntityType,
      removeFromComparison,
      selectedIdsSet,
      setComparisonEntityType,
    ],
  );

  const pageSummary = useMemo(() => {
    const totalGoals = rows.reduce((sum, item) => sum + (item.goals ?? 0), 0);
    const totalAssists = rows.reduce((sum, item) => sum + (item.assists ?? 0), 0);
    const totalMinutes = rows.reduce((sum, item) => sum + (item.minutesPlayed ?? 0), 0);
    const ratingValues = rows
      .map((item) => item.rating)
      .filter((rating): rating is number => typeof rating === "number");

    return {
      totalGoals,
      totalAssists,
      totalMinutes,
      goalInvolvements: totalGoals + totalAssists,
      averageRating:
        ratingValues.length > 0
          ? ratingValues.reduce((sum, rating) => sum + rating, 0) / ratingValues.length
          : null,
    };
  }, [rows]);

  const localMinMinutesLabel =
    normalizedMinMinutes === null
      ? "Sem piso de minutos"
      : `Mínimo de ${formatInteger(normalizedMinMinutes)} minutos`;
  const sortLabel = `${resolveSortByLabel(sortBy)} · ${resolveSortDirectionLabel(sortDirection)}`;
  const seasonHubHref = resolvedContext
    ? buildSeasonHubTabPath(resolvedContext, "rankings", {
        competitionId,
        seasonId,
        roundId: timeRangeParams.roundId,
        stageId: selectedStageId,
        stageFormat: selectedStageFormat,
        venue,
        lastN: timeRangeParams.lastN,
        dateRangeStart: timeRangeParams.dateRangeStart,
        dateRangeEnd: timeRangeParams.dateRangeEnd,
      })
    : "/competitions";
  const seasonLinkLabel = resolvedContext ? "Temporada" : "Temporadas";
  const rankingsHref = buildRankingPath("player-goals", {
    competitionId,
    seasonId,
    roundId: timeRangeParams.roundId,
    stageId: selectedStageId,
    stageFormat: selectedStageFormat,
    venue,
    lastN: timeRangeParams.lastN,
    dateRangeStart: timeRangeParams.dateRangeStart,
    dateRangeEnd: timeRangeParams.dateRangeEnd,
  });
  const teamsHref = buildTeamsPath({
    competitionId,
    seasonId,
    roundId: timeRangeParams.roundId,
    stageId: selectedStageId,
    stageFormat: selectedStageFormat,
    venue,
    lastN: timeRangeParams.lastN,
    dateRangeStart: timeRangeParams.dateRangeStart,
    dateRangeEnd: timeRangeParams.dateRangeEnd,
  });
  const featuredPlayers = rows.slice(0, 3);
  const featuredPlayer = featuredPlayers[0] ?? null;
  const featuredPlayerMetric = featuredPlayer
    ? resolveFeaturedPlayerMetric(featuredPlayer, sortBy)
    : null;
  const comparisonHint =
    selectedIds.length === 0
      ? "marque na tabela"
      : selectedIds.length === 1
        ? "falta 1 jogador"
        : "pronta";

  if (playersQuery.isLoading && !playersQuery.data) {
    return (
      <ProfileShell className="space-y-5">
        <LoadingSkeleton height={240} />
        <LoadingSkeleton height={150} />
        <LoadingSkeleton height={480} />
      </ProfileShell>
    );
  }

  if (playersQuery.isError && rows.length === 0) {
    return (
      <ProfileShell className="space-y-5">
        <ProfileAlert title="Falha ao carregar jogadores" tone="critical">
          <p>{playersQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  return (
    <ProfileShell className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#003526]" href="/competitions">
          Competições
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>Jogadores</span>
      </div>

      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(166,242,209,0.24),transparent_30%),radial-gradient(circle_at_88%_0%,rgba(216,227,251,0.2),transparent_34%)]" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-52 w-52 rounded-full bg-white/5 blur-3xl" />

        <div className="relative grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.42fr)] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5 xl:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/10 text-white/82">
                {competitionName ?? "Todas as competições"}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">
                {seasonLabel ?? "Todas as temporadas"}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">{activeWindowLabel}</ProfileTag>
            </div>

            <div className="max-w-3xl">
              <p className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                <PlayersPageIcon className="h-4 w-4" icon="players" />
                Jogadores
              </p>
              <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-5xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-6xl">
                Mapa rápido do elenco disponível
              </h1>
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <PlayersHeroMetric
                hint={`página ${formatInteger(currentPage)} de ${formatInteger(totalPages)}`}
                icon="players"
                label="Mostrando"
                value={`${formatInteger(currentRangeStart)}-${formatInteger(currentRangeEnd)}`}
              />
              <PlayersHeroMetric
                hint="nesta página"
                icon="assist"
                label="G+A"
                value={formatInteger(pageSummary.goalInvolvements)}
              />
              <PlayersHeroMetric
                hint="média da página"
                icon="star"
                label="Nota"
                value={formatDecimal(pageSummary.averageRating)}
              />
              <PlayersHeroMetric
                hint={comparisonHint}
                icon="compare"
                label="Comparar"
                value={`${selectedIds.length}/2`}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <PlayersLinkButton href={rankingsHref} icon="ranking" label="Ranking de gols" />
              <PlayersLinkButton href={teamsHref} icon="shield" label="Times" />
              <PlayersLinkButton href={seasonHubHref} icon="star" label={seasonLinkLabel} />
            </div>
          </div>

          <aside className="grid content-start gap-3 xl:pt-14">
            {featuredPlayer && featuredPlayerMetric ? (
              <Link
                className="group flex min-h-[12rem] flex-col justify-between rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/16"
                href={getPlayerHref(featuredPlayer.playerId)}
                onFocus={() => {
                  prefetchPlayerDetail(featuredPlayer.playerId);
                }}
                onMouseEnter={() => {
                  prefetchPlayerDetail(featuredPlayer.playerId);
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <ProfileMedia
                      alt={featuredPlayer.playerName}
                      assetId={featuredPlayer.playerId}
                      category="players"
                      className="h-16 w-16 border border-white/18 bg-white/12"
                      fallback={getInitials(featuredPlayer.playerName)}
                      imageClassName="p-1"
                      shape="circle"
                      linkBehavior="none"
                    />
                    <div className="min-w-0">
                      <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                        Destaque da lista
                      </p>
                      <h2 className="mt-1 truncate font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                        {featuredPlayer.playerName}
                      </h2>
                    </div>
                  </div>
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/12 text-white transition-transform group-hover:scale-105">
                    <PlayersPageIcon className="h-4 w-4" icon="star" />
                  </span>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-2">
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">
                      {featuredPlayerMetric.label}
                    </p>
                    <p className="mt-1 text-2xl font-extrabold">{featuredPlayerMetric.value}</p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Jogos</p>
                    <p className="mt-1 text-2xl font-extrabold">
                      {formatInteger(featuredPlayer.matchesPlayed)}
                    </p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Time</p>
                    <p className="mt-1 truncate text-sm font-bold">
                      {featuredPlayer.teamName ?? "Sem time"}
                    </p>
                  </div>
                </div>
              </Link>
            ) : (
              <div className="rounded-[1.55rem] border border-white/12 bg-white/10 p-5 text-white/70">
                Sem jogadores para destacar neste recorte.
              </div>
            )}

            {featuredPlayers.length > 1 ? (
              <div className="grid gap-2">
                {featuredPlayers.slice(1).map((player, index) => {
                  const playerMetric = resolveFeaturedPlayerMetric(player, sortBy);

                  return (
                    <Link
                      className="flex items-center gap-3 rounded-[1.15rem] border border-white/10 bg-white/8 px-3 py-3 text-white transition-colors hover:bg-white/14"
                      href={getPlayerHref(player.playerId)}
                      key={player.playerId}
                      onFocus={() => {
                        prefetchPlayerDetail(player.playerId);
                      }}
                      onMouseEnter={() => {
                        prefetchPlayerDetail(player.playerId);
                      }}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/12 text-xs font-bold text-white/72">
                        {index + 2}
                      </span>
                      <ProfileMedia
                        alt={player.playerName}
                        assetId={player.playerId}
                        category="players"
                        className="h-10 w-10 border-0 bg-white/12"
                        fallback={getInitials(player.playerName)}
                        imageClassName="p-1"
                        shape="circle"
                        linkBehavior="none"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold">{player.playerName}</p>
                        <p className="truncate text-xs text-white/56">
                          {player.teamName ?? formatPosition(player.position)}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-extrabold">{playerMetric.value}</p>
                        <p className="text-[0.58rem] uppercase tracking-[0.16em] text-white/48">
                          {playerMetric.label}
                        </p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            ) : null}
          </aside>
        </div>
      </ProfilePanel>

      {playersQuery.isError ? (
        <ProfileAlert title="Dados carregados com alerta" tone="warning">
          <p>{playersQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {shouldShowCoverageNotice(playersQuery.coverage.status, playersQuery.coverage.percentage) ? (
        <PartialDataBanner
          coverage={playersQuery.coverage}
          message={resolveCoverageMessage(playersQuery.coverage.percentage)}
        />
      ) : null}

      <ProfilePanel className="space-y-4 border-white/80 bg-white/84">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#e9f2ff] text-[#003526]">
              <PlayersPageIcon className="h-5 w-5" icon="search" />
            </span>
            <div>
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
                Filtros
              </p>
              <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
                Refinar lista
              </h2>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{describeVenue(venue)}</ProfileTag>
            <ProfileTag>{sortLabel}</ProfileTag>
            {selectedStageId || selectedStageFormat ? <ProfileTag>Fase filtrada</ProfileTag> : null}
            <ProfileTag>{localMinMinutesLabel}</ProfileTag>
            {selectedIds.length > 0 ? (
              <ProfileTag>{selectedIds.length}/2 comparação</ProfileTag>
            ) : null}
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.35fr)_220px_220px_220px]">
          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Busca
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[#003526]">
                <PlayersPageIcon className="h-4 w-4" icon="search" />
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none placeholder:text-[#707974]"
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
                placeholder="Ex.: Arrascaeta"
                type="text"
                value={search}
              />
            </div>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Ordenar
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[#003526]">
                <PlayersPageIcon className="h-4 w-4" icon="ranking" />
              </span>
              <select
                className="w-full border-0 bg-transparent text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none ring-0"
                onChange={(event) => {
                  setSortBy(event.target.value as PlayersSortBy);
                }}
                value={sortBy}
              >
                <option value="goals">Gols</option>
                <option value="assists">Assists</option>
                <option value="minutesPlayed">Minutos</option>
                <option value="rating">Nota</option>
                <option value="playerName">Nome</option>
              </select>
            </div>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Direção
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[#003526]">
                <PlayersPageIcon className="h-4 w-4" icon="assist" />
              </span>
              <select
                className="w-full border-0 bg-transparent text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none ring-0"
                onChange={(event) => {
                  setSortDirection(event.target.value as PlayersSortDirection);
                }}
                value={sortDirection}
              >
                <option value="desc">Maior para menor</option>
                <option value="asc">Menor para maior</option>
              </select>
            </div>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Minutos
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[#003526]">
                <PlayersPageIcon className="h-4 w-4" icon="star" />
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none placeholder:text-[#707974]"
                min={0}
                onChange={(event) => {
                  setMinMinutesInput(event.target.value);
                }}
                placeholder="Opcional"
                type="number"
                value={minMinutesInput}
              />
            </div>
          </label>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="soft">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Lista de jogadores
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Jogadores encontrados
            </h2>
            <p className="mt-2 text-sm/6 text-[#57657a]">
              Mostrando {formatInteger(currentRangeStart)}-{formatInteger(currentRangeEnd)} de{" "}
              {formatInteger(totalCount)} jogadores.
              {deferredSearch.trim().length > 0 ? ` Busca: "${deferredSearch.trim()}".` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{formatInteger(pageSummary.goalInvolvements)} G+A na página</ProfileTag>
            <ProfileTag>{formatDecimal(pageSummary.averageRating)} nota média</ProfileTag>
            <ProfileTag>{formatInteger(pageSummary.totalMinutes)} minutos na página</ProfileTag>
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState
            description={
              deferredSearch.trim().length > 0
                ? `Nenhum jogador encontrado para "${deferredSearch.trim()}" no recorte atual.`
                : "Não há jogadores suficientes para os filtros atuais."
            }
            title="Lista vazia"
          />
        ) : (
          <div className="overflow-hidden rounded-[1.4rem] border border-[rgba(191,201,195,0.52)] bg-white/92">
            <div className="overflow-x-auto">
              <table className="w-full table-fixed border-collapse text-left text-sm text-[#1f2d40]">
                <thead className="bg-[rgba(240,243,255,0.82)] text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                  <tr>
                    <th className="w-14 px-2 py-3 text-center font-semibold">#</th>
                    <th className="w-[23%] px-3 py-3 font-semibold">Jogador</th>
                    <th className="w-[16%] px-3 py-3 text-center font-semibold">Times</th>
                    <th className="w-[10%] px-2 py-3 text-center font-semibold">Pos.</th>
                    <th className="w-[7%] px-2 py-3 text-center font-semibold">Jogos</th>
                    <th className="w-[9%] px-2 py-3 text-center font-semibold">Min</th>
                    <th className="w-[6%] px-2 py-3 text-center font-semibold">Gols</th>
                    <th className="w-[9%] px-2 py-3 text-center font-semibold">Assists</th>
                    <th className="w-[8%] px-2 py-3 text-center font-semibold">Nota</th>
                    <th className="w-[10%] px-2 py-3 text-center font-semibold">Comp.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgba(191,201,195,0.38)]">
                  {rows.map((player, index) => {
                    const teamHref = getTeamHref(player);
                    const teamSummary =
                      player.teamName ?? player.teamContextLabel ?? "Sem time";
                    const recentTeams =
                      player.recentTeams && player.recentTeams.length > 0
                        ? player.recentTeams.slice(0, 3)
                        : player.teamId
                          ? [{ teamId: player.teamId, teamName: player.teamName ?? null }]
                          : [];
                    const isSelected = selectedIdsSet.has(player.playerId);
                    const canAddMore = selectedIds.length < 2;
                    const isDisabled = !isSelected && !canAddMore;

                    return (
                      <tr className="align-middle hover:bg-[rgba(240,243,255,0.42)]" key={player.playerId}>
                        <td className="px-2 py-3 text-center">
                          <span className="inline-flex min-w-10 items-center justify-center rounded-full bg-[rgba(216,227,251,0.72)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#003526]">
                            {formatInteger(currentRangeStart + index)}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2.5">
                            <ProfileMedia
                              alt={player.playerName}
                              assetId={player.playerId}
                              category="players"
                              className="h-10 w-10 border-0 bg-[rgba(216,227,251,0.82)]"
                              fallback={getInitials(player.playerName)}
                              imageClassName="p-1.5"
                              shape="circle"
                            />
                            <div className="min-w-0">
                              <Link
                                className="block truncate font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
                                href={getPlayerHref(player.playerId)}
                                onFocus={() => {
                                  prefetchPlayerDetail(player.playerId);
                                }}
                                onMouseEnter={() => {
                                  prefetchPlayerDetail(player.playerId);
                                }}
                              >
                                {player.playerName}
                              </Link>
                              <p className="mt-1 text-xs text-[#57657a]">
                                {player.nationality ?? "Nacionalidade não informada"}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-center">
                          {recentTeams.length > 0 ? (
                            <div className="mb-1.5 flex items-center justify-center">
                              {recentTeams.map((team, teamIndex) => {
                                const teamHrefForAsset = getTeamAssetHref(team.teamId);
                                const asset = (
                                  <ProfileMedia
                                    alt={team.teamName ?? "Time"}
                                    assetId={team.teamId}
                                    category="clubs"
                                    className={`h-8 w-8 border border-white bg-white ${
                                      teamIndex > 0 ? "-ml-2" : ""
                                    }`}
                                    fallback={getInitials(team.teamName ?? "Time")}
                                    fallbackClassName="text-[0.64rem]"
                                    imageClassName="p-1"
                                    linkBehavior="none"
                                    shape="circle"
                                  />
                                );

                                return teamHrefForAsset ? (
                                  <Link href={teamHrefForAsset} key={team.teamId}>
                                    {asset}
                                  </Link>
                                ) : (
                                  <div key={team.teamId}>{asset}</div>
                                );
                              })}
                            </div>
                          ) : null}
                          {teamHref ? (
                            <Link
                              className="block truncate text-xs font-semibold text-[#1f2d40] transition-colors hover:text-[#003526]"
                              href={teamHref}
                            >
                              {teamSummary}
                            </Link>
                          ) : (
                            <p className="truncate text-xs font-semibold text-[#111c2d]">
                              {teamSummary}
                            </p>
                          )}
                        </td>
                        <td className="px-2 py-3 text-center">
                          <span className="inline-flex max-w-full items-center justify-center rounded-full bg-[rgba(240,243,255,0.96)] px-2 py-1 text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                            {formatPosition(player.position)}
                          </span>
                        </td>
                        <td className="px-2 py-3 text-center font-medium tabular-nums text-[#1f2d40]">
                          {formatInteger(player.matchesPlayed)}
                        </td>
                        <td className="px-2 py-3 text-center font-medium tabular-nums text-[#1f2d40]">
                          {formatMinutesCell(player.minutesPlayed)}
                        </td>
                        <td className="px-2 py-3 text-center font-medium tabular-nums text-[#1f2d40]">
                          {formatMetricValue("goals", player.goals)}
                        </td>
                        <td className="px-2 py-3 text-center font-medium tabular-nums text-[#1f2d40]">
                          {formatMetricValue("assists", player.assists)}
                        </td>
                        <td className="px-2 py-3 text-center">
                          <span
                            className={`inline-flex min-w-14 justify-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                              typeof player.rating === "number"
                                ? "bg-[#003526] text-white"
                                : "bg-[rgba(240,243,255,0.96)] text-[#57657a]"
                            }`}
                          >
                            {formatMetricValue("player_rating", player.rating)}
                          </span>
                        </td>
                        <td className="px-2 py-3 text-center">
                          <button
                            aria-pressed={isSelected}
                            className={`rounded-full px-2.5 py-1.5 text-[0.7rem] font-semibold transition-colors ${
                              isSelected
                                ? "bg-[#003526] text-white"
                                : "border border-[rgba(112,121,116,0.28)] bg-white/90 text-[#1f2d40]"
                            } disabled:cursor-not-allowed disabled:opacity-50`}
                            disabled={isDisabled}
                            onClick={() => {
                              handleCompareAction(player.playerId);
                            }}
                            type="button"
                          >
                            {isSelected ? "Remover" : "Comp."}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 border-t border-[rgba(191,201,195,0.4)] bg-[rgba(240,243,255,0.52)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-[#57657a]">
                Página {formatInteger(currentPage)} de {formatInteger(totalPages)}.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-[#57657a]">
                  Linhas
                  <select
                    className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/88 px-3 py-1.5 text-[#1f2d40]"
                    onChange={(event) => {
                      setPageSize(Number(event.target.value));
                    }}
                    value={pageSize}
                  >
                    {[20, 40, 60, 100].map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-1.5 font-medium text-[#1f2d40] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage <= 1}
                  onClick={() => {
                    setPage((currentValue) => Math.max(currentValue - 1, 1));
                  }}
                  type="button"
                >
                  Anterior
                </button>
                <button
                  className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-1.5 font-medium text-[#1f2d40] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage >= totalPages}
                  onClick={() => {
                    setPage((currentValue) => Math.min(currentValue + 1, totalPages));
                  }}
                  type="button"
                >
                  Próxima
                </button>
              </div>
            </div>
          </div>
        )}
      </ProfilePanel>
    </ProfileShell>
  );
}
