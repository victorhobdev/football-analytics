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
  ProfileCoveragePill,
  ProfileKpi,
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
  buildMatchesPath,
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

function PlayersLinkButton({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  return (
    <Link
      className="button-pill button-pill-secondary hover:-translate-y-0.5"
      href={href}
    >
      {label}
    </Link>
  );
}

function ContextFact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[1.05rem] border border-[rgba(191,201,195,0.44)] bg-white/86 px-3 py-3">
      <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-[#111c2d]">{value}</p>
    </div>
  );
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

  const selectedPlayersPreview = useMemo(
    () =>
      selectedIds.map((playerId) => {
        const player = rows.find((candidate) => candidate.playerId === playerId);

        return {
          playerId,
          label: player?.playerName ?? playerId,
        };
      }),
    [rows, selectedIds],
  );

  const compareStatusCopy =
    selectedPlayersPreview.length === 0
      ? "Selecione até dois jogadores para comparar sem sair desta lista."
      : selectedPlayersPreview.length === 1
        ? "Um jogador selecionado. Escolha mais um para liberar a comparação."
        : "Dois jogadores selecionados. A comparação já está pronta.";

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
  const matchesHref = buildMatchesPath({
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

  const contextFacts = [
    { label: "Competição", value: competitionName ?? "Todas as competições" },
    { label: "Temporada", value: seasonLabel ?? "Todas as temporadas" },
    { label: "Mando", value: describeVenue(venue) },
    { label: "Janela", value: activeWindowLabel },
    { label: "Ordenação", value: sortLabel },
    { label: "Mín. mínimo", value: localMinMinutesLabel },
  ];

  if (selectedStageId || selectedStageFormat) {
    contextFacts.push({
      label: "Fase",
      value: selectedStageFormat ?? "Recorte de fase aplicado",
    });
  }

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

      <ProfilePanel className="space-y-5" tone="accent">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileCoveragePill
                className="bg-white/14 text-white"
                coverage={playersQuery.coverage}
              />
              <ProfileTag className="bg-white/10 text-white/85">
                {competitionName ?? "Todas as competições"}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/85">
                {seasonLabel ?? "Todas as temporadas"}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/85">{activeWindowLabel}</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/85">{localMinMinutesLabel}</ProfileTag>
            </div>

            <div className="space-y-3">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-white/64">
                Lista de jogadores
              </p>
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-white md:text-5xl">
                Jogadores
              </h1>
              <p className="max-w-3xl text-sm/6 text-white/76">
                Veja os jogadores do filtro atual.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {contextFacts.map((fact) => (
                <ContextFact key={`${fact.label}-${fact.value}`} label={fact.label} value={fact.value} />
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <ProfileKpi
              hint="Na lista"
              invert
              label="Jogadores"
              value={formatInteger(totalCount)}
            />
            <ProfileKpi
              hint={`${formatInteger(currentRangeStart)}-${formatInteger(currentRangeEnd)}`}
              invert
              label="Página"
              value={`${formatInteger(currentPage)}/${formatInteger(totalPages)}`}
            />
            <ProfileKpi
              hint="Nesta página"
              invert
              label="Minutos na página"
              value={formatInteger(pageSummary.totalMinutes)}
            />
            <ProfileKpi
              hint={compareStatusCopy}
              invert
              label="Comparação"
              value={`${selectedIds.length}/2`}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <PlayersLinkButton href={seasonHubHref} label="Temporada" />
          <PlayersLinkButton href={rankingsHref} label="Ranking de gols" />
          <PlayersLinkButton href={teamsHref} label="Times" />
          <PlayersLinkButton href={matchesHref} label="Partidas" />
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

      <ProfilePanel className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Filtros
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Ajuste a lista
            </h2>
            <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
              Busque por nome e ajuste minutos e ordenação.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{describeVenue(venue)}</ProfileTag>
            <ProfileTag>{sortLabel}</ProfileTag>
            {selectedStageId || selectedStageFormat ? <ProfileTag>Fase filtrada</ProfileTag> : null}
            <ProfileTag>{localMinMinutesLabel}</ProfileTag>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.35fr)_220px_220px_220px]">
          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Buscar jogador
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-xs font-semibold text-[#003526]">
                Q
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none placeholder:text-[#707974]"
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
                placeholder="Ex.: Arrascaeta"
                type="text"
                value={search}
              />
            </div>
          </label>

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Ordenar por
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
                Ord
              </span>
              <select
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none ring-0"
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

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Direção
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
                Dir
              </span>
              <select
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none ring-0"
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

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Mínimo de minutos
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
                Min
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm text-[#111c2d] outline-none placeholder:text-[#707974]"
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

        <div className="flex flex-col gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.5)] bg-[rgba(240,243,255,0.52)] px-4 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              Comparação
            </p>
            <p className="mt-1 text-sm text-[#57657a]">{compareStatusCopy}</p>
          </div>
          {selectedPlayersPreview.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selectedPlayersPreview.map((player) => (
                <span
                  className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#1f2d40]"
                  key={player.playerId}
                >
                  {player.label}
                </span>
              ))}
            </div>
          ) : null}
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
                      <tr className="align-top hover:bg-[rgba(240,243,255,0.42)]" key={player.playerId}>
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
