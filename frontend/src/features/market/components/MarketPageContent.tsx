"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useMarketTransfers } from "@/features/market/hooks";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildMatchesPath,
  buildPlayerResolverPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
  buildTeamsPath,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

const MARKET_PAGE_SIZE = 24;

const TRANSFER_TYPE_LABELS: Record<number, string> = {
  219: "Transferência definitiva",
  218: "Empréstimo",
  9688: "Livre / fim de contrato",
  220: "Retorno de empréstimo",
};

const TRANSFER_TYPE_FILTERS: Array<{ label: string; value: number | null }> = [
  { label: "Todas", value: null },
  { label: "Definitiva", value: 219 },
  { label: "Empréstimo", value: 218 },
  { label: "Livre", value: 9688 },
  { label: "Retorno", value: 220 },
];

const MARKET_SORT_OPTIONS = [
  { key: "amountDesc", label: "Maior valor", sortBy: "amount", sortDirection: "desc" },
  { key: "dateDesc", label: "Mais recentes", sortBy: "transferDate", sortDirection: "desc" },
  { key: "playerNameAsc", label: "Jogador A-Z", sortBy: "playerName", sortDirection: "asc" },
] as const;

const TEAM_DIRECTION_FILTERS = [
  { label: "Todas", value: "all" },
  { label: "Chegadas", value: "arrivals" },
  { label: "Saídas", value: "departures" },
] as const;

function describeTransferWindow(params: {
  roundId: string | null;
  lastN: number | null;
  dateRangeStart: string | null;
  dateRangeEnd: string | null;
}): string {
  if (typeof params.lastN === "number" && params.lastN > 0) {
    return `Últimas ${params.lastN} movimentações`;
  }

  if (params.dateRangeStart || params.dateRangeEnd) {
    return `${params.dateRangeStart ?? "..."} até ${params.dateRangeEnd ?? "..."}`;
  }

  if (params.roundId) {
    return `Times da rodada ${params.roundId}`;
  }

  return "Base completa";
}

function formatTransferDate(value: string | null | undefined): string {
  if (!value) {
    return "Data não informada";
  }

  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(parsedDate);
}

function parseAmount(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }

  const normalized = Number(value);

  if (!Number.isFinite(normalized)) {
    return null;
  }

  return normalized;
}

function parseMillionsInput(value: string): number | undefined {
  if (value.trim().length === 0) {
    return undefined;
  }

  const normalized = Number(value.replace(",", "."));

  if (!Number.isFinite(normalized) || normalized < 0) {
    return undefined;
  }

  return Math.round(normalized * 1_000_000);
}

function getAmountValue(item: {
  amount?: string | null;
  amountValue?: number | null;
}): number | null {
  if (typeof item.amountValue === "number" && Number.isFinite(item.amountValue)) {
    return item.amountValue;
  }

  return parseAmount(item.amount);
}

function formatAmountInMillions(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Valor não divulgado";
  }

  const millions = value / 1_000_000;
  const formattedValue = new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: millions >= 10 ? 1 : 2,
    minimumFractionDigits: 0,
  }).format(millions);
  const unit = Math.abs(millions - 1) < 0.005 ? "milhão" : "milhões";

  return `€ ${formattedValue} ${unit}`;
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

function getTransferTypeLabel(typeId: number | null | undefined, typeName: string | null | undefined): string {
  if (typeName && typeName.trim().length > 0) {
    return typeName;
  }

  if (typeof typeId === "number") {
    return TRANSFER_TYPE_LABELS[typeId] ?? "Tipo desconhecido";
  }

  return "Tipo desconhecido";
}

function formatMovement(item: {
  fromTeamName?: string | null;
  toTeamName?: string | null;
  careerEnded: boolean;
}): string {
  const fromTeam = item.fromTeamName ?? "Origem não informada";
  const toTeam = item.careerEnded ? "Fim de carreira" : item.toTeamName ?? "Destino não informado";

  return `${fromTeam} -> ${toTeam}`;
}

function getPlayerMonogram(playerName: string): string {
  const initials = playerName
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "TRF";
}

function getTeamFallback(teamName: string | null | undefined, teamId: string | null | undefined): string {
  if (teamName && !teamName.startsWith("Team #")) {
    const initials = teamName
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean)
      .map((token) => token[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 3);

    return initials.length > 0 ? initials : "CLB";
  }

  return teamId ? `#${teamId.slice(-3)}` : "CLB";
}

export function MarketPageContent() {
  const [search, setSearch] = useState("");
  const [clubSearch, setClubSearch] = useState("");
  const [teamDirection, setTeamDirection] = useState<(typeof TEAM_DIRECTION_FILTERS)[number]["value"]>("all");
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<(typeof MARKET_SORT_OPTIONS)[number]["key"]>("amountDesc");
  const [onlyValuedTransfers, setOnlyValuedTransfers] = useState(false);
  const [minAmountMillions, setMinAmountMillions] = useState("");
  const [maxAmountMillions, setMaxAmountMillions] = useState("");
  const deferredSearch = useDeferredValue(search);
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const selectedSort =
    MARKET_SORT_OPTIONS.find((option) => option.key === sortKey) ?? MARKET_SORT_OPTIONS[0];
  const minAmount = useMemo(() => parseMillionsInput(minAmountMillions), [minAmountMillions]);
  const maxAmount = useMemo(() => parseMillionsInput(maxAmountMillions), [maxAmountMillions]);

  useEffect(() => {
    setPage(1);
  }, [
    clubSearch,
    competitionId,
    dateRangeEnd,
    dateRangeStart,
    deferredSearch,
    lastN,
    maxAmount,
    minAmount,
    onlyValuedTransfers,
    roundId,
    seasonId,
    selectedTypeId,
    sortKey,
    teamDirection,
    venue,
  ]);

  const marketQuery = useMarketTransfers(
    {
      search: deferredSearch,
      clubSearch,
      teamDirection,
      typeId: selectedTypeId,
      hasAmount: onlyValuedTransfers ? true : undefined,
      minAmount,
      maxAmount,
      page,
      pageSize: MARKET_PAGE_SIZE,
      sortBy: selectedSort.sortBy,
      sortDirection: selectedSort.sortDirection,
    },
    resolvedContext,
  );
  const sharedFilters = useMemo(
    () => ({
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
    }),
    [competitionId, dateRangeEnd, dateRangeStart, lastN, roundId, seasonId, venue],
  );
  const seasonHubHref = resolvedContext
    ? buildSeasonHubTabPath(resolvedContext, "calendar", sharedFilters)
    : "/competitions";
  const playersHref = buildPlayersPath(sharedFilters);
  const teamsHref = buildTeamsPath(sharedFilters);
  const matchesHref = buildMatchesPath(sharedFilters);
  const activeWindowLabel = describeTransferWindow({
    roundId,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });

  if (marketQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mercado
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando transferências
          </h1>
        </header>
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
      </ProfileShell>
    );
  }

  if (marketQuery.isError && !marketQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mercado
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar transferências
          </h1>
        </header>
        <ProfileAlert title="Erro no carregamento" tone="critical">
          <p>{marketQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  const items = marketQuery.data?.items ?? [];
  const pagination = marketQuery.meta?.pagination;
  const totalCount = pagination?.totalCount ?? items.length;
  const totalPages = Math.max(pagination?.totalPages ?? Math.ceil(totalCount / MARKET_PAGE_SIZE), 1);
  const currentPage = pagination?.page ?? page;
  const resolvedPageSize = pagination?.pageSize ?? MARKET_PAGE_SIZE;
  const currentRangeStart = totalCount === 0 ? 0 : (currentPage - 1) * resolvedPageSize + 1;
  const currentRangeEnd = totalCount === 0 ? 0 : currentRangeStart + items.length - 1;
  const hasPreviousPage = pagination?.hasPreviousPage ?? currentPage > 1;
  const hasNextPage = pagination?.hasNextPage ?? currentPage < totalPages;
  const valuedTransfers = items.filter((item) => getAmountValue(item) !== null).length;
  const topAmount = items.reduce<number | null>((currentTop, item) => {
    const amountValue = getAmountValue(item);

    if (amountValue === null) {
      return currentTop;
    }

    return currentTop === null ? amountValue : Math.max(currentTop, amountValue);
  }, null);

  return (
    <ProfileShell className="space-y-6">
      <section className="space-y-4">
        <ProfilePanel className="p-0" tone="accent">
          <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(460px,0.9fr)] lg:items-center">
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <ProfileCoveragePill coverage={marketQuery.coverage} className="bg-white/16 text-white" />
                <ProfileTag className="bg-white/12 text-white/82">
                  {resolvedContext ? "Contexto fechado" : "Entrada direta"}
                </ProfileTag>
                <ProfileTag className="bg-white/12 text-white/82">EUR</ProfileTag>
                <ProfileTag className="bg-white/12 text-white/82">{activeWindowLabel}</ProfileTag>
              </div>
              <div>
                <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
                  Mercado
                </p>
                <h1 className="mt-1 font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-tight text-white md:text-4xl">
                  {resolvedContext
                    ? `${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
                    : "Transferências por valor, jogador e clube"}
                </h1>
                <p className="mt-2 max-w-3xl text-sm/6 text-white/74">
                  Priorize grandes movimentações, filtre por clube e acompanhe origem, destino e valor.
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/8 px-4 py-3 text-white">
                <p className="text-[0.66rem] font-semibold uppercase tracking-[0.16em] text-white/64">
                  Transferências
                </p>
                <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold">
                  {formatInteger(totalCount)}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/8 px-4 py-3 text-white">
                <p className="text-[0.66rem] font-semibold uppercase tracking-[0.16em] text-white/64">
                  Com valor página
                </p>
                <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold">
                  {formatInteger(valuedTransfers)}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/8 px-4 py-3 text-white">
                <p className="text-[0.66rem] font-semibold uppercase tracking-[0.16em] text-white/64">
                  Maior valor
                </p>
                <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold">
                  {formatAmountInMillions(topAmount)}
                </p>
              </div>
            </div>
          </div>
        </ProfilePanel>

        <ProfilePanel className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(190px,1fr)_minmax(190px,1fr)_minmax(150px,0.65fr)_minmax(130px,0.5fr)_minmax(130px,0.5fr)_auto] lg:items-end">
            <label className="space-y-1.5">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Jogador ou valor
              </span>
              <input
                className="w-full rounded-xl border border-[rgba(191,201,195,0.65)] bg-white/92 px-3 py-2.5 text-sm text-[#111c2d] outline-none transition-colors placeholder:text-[#7f8b99] focus:border-[#8bd6b6]"
                onChange={(event) => {
                  setPage(1);
                  setSearch(event.target.value);
                }}
                placeholder="Neymar, 25M..."
                value={search}
              />
            </label>

            <label className="space-y-1.5">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Clube
              </span>
              <input
                className="w-full rounded-xl border border-[rgba(191,201,195,0.65)] bg-white/92 px-3 py-2.5 text-sm text-[#111c2d] outline-none transition-colors placeholder:text-[#7f8b99] focus:border-[#8bd6b6]"
                onChange={(event) => {
                  setPage(1);
                  setClubSearch(event.target.value);
                }}
                placeholder="Barcelona, Santos..."
                value={clubSearch}
              />
            </label>

            <label className="space-y-1.5">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Ordenar
              </span>
              <select
                className="w-full rounded-xl border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-2.5 text-sm font-medium text-[#1f2d40] outline-none focus:border-[#8bd6b6]"
                onChange={(event) => {
                  setPage(1);
                  setSortKey(event.target.value as (typeof MARKET_SORT_OPTIONS)[number]["key"]);
                }}
                value={sortKey}
              >
                {MARKET_SORT_OPTIONS.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Mínimo mi €
              </span>
              <input
                className="w-full rounded-xl border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-2.5 text-sm text-[#1f2d40] outline-none focus:border-[#8bd6b6]"
                min="0"
                onChange={(event) => {
                  setPage(1);
                  setMinAmountMillions(event.target.value);
                }}
                placeholder="25"
                step="0.1"
                type="number"
                value={minAmountMillions}
              />
            </label>

            <label className="space-y-1.5">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Máximo mi €
              </span>
              <input
                className="w-full rounded-xl border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-2.5 text-sm text-[#1f2d40] outline-none focus:border-[#8bd6b6]"
                min="0"
                onChange={(event) => {
                  setPage(1);
                  setMaxAmountMillions(event.target.value);
                }}
                placeholder="100"
                step="0.1"
                type="number"
                value={maxAmountMillions}
              />
            </label>

            <label className="flex min-h-[42px] items-center gap-3 rounded-xl border border-[rgba(112,121,116,0.18)] bg-white/72 px-3 py-2.5 text-sm font-semibold text-[#1f2d40]">
              <input
                checked={onlyValuedTransfers}
                className="h-4 w-4 accent-[#003526]"
                onChange={(event) => {
                  setPage(1);
                  setOnlyValuedTransfers(event.target.checked);
                }}
                type="checkbox"
              />
              Só com valor
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Tipo
              </span>
              {TRANSFER_TYPE_FILTERS.map((option) => {
                const isActive = selectedTypeId === option.value;

                return (
                  <button
                    aria-pressed={isActive}
                    className={`rounded-full border px-3 py-2 text-xs font-semibold transition-colors ${
                      isActive
                        ? "border-[#003526] bg-[#003526] text-white"
                        : "border-[rgba(112,121,116,0.24)] bg-white/88 text-[#1f2d40] hover:border-[#8bd6b6]"
                    }`}
                    key={option.label}
                    onClick={() => {
                      setPage(1);
                      setSelectedTypeId(option.value);
                    }}
                    type="button"
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
                Clube
              </span>
              {TEAM_DIRECTION_FILTERS.map((option) => {
                const isActive = teamDirection === option.value;

                return (
                  <button
                    aria-pressed={isActive}
                    className={`rounded-full border px-3 py-2 text-xs font-semibold transition-colors ${
                      isActive
                        ? "border-[#003526] bg-[#003526] text-white"
                        : "border-[rgba(112,121,116,0.24)] bg-white/88 text-[#1f2d40] hover:border-[#8bd6b6]"
                    }`}
                    key={option.value}
                    onClick={() => {
                      setPage(1);
                      setTeamDirection(option.value);
                    }}
                    type="button"
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>

            <div className="ml-auto flex flex-wrap gap-2">
              <Link className="button-pill button-pill-secondary" href={seasonHubHref}>
                Temporada
              </Link>
              <Link className="button-pill button-pill-secondary" href={playersHref}>
                Jogadores
              </Link>
              <Link className="button-pill button-pill-secondary" href={teamsHref}>
                Times
              </Link>
              <Link className="button-pill button-pill-secondary" href={matchesHref}>
                Partidas
              </Link>
            </div>
          </div>
        </ProfilePanel>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {items.length === 0 ? (
          <div className="lg:col-span-2">
            <EmptyState
              title="Nenhuma transferência encontrada"
              description="Ajuste a busca, o clube, a direção ou a faixa de valor para ampliar o recorte."
            />
          </div>
        ) : items.map((item) => {
          const playerHref = item.playerId ? buildPlayerResolverPath(item.playerId, sharedFilters) : null;
          const fromTeamHref = item.fromTeamId ? buildTeamResolverPath(item.fromTeamId, sharedFilters) : null;
          const toTeamHref = item.toTeamId ? buildTeamResolverPath(item.toTeamId, sharedFilters) : null;
          const amountValue = getAmountValue(item);
          const amountLabel = formatAmountInMillions(amountValue);

          return (
            <article
              className="overflow-hidden rounded-xl border border-[rgba(191,201,195,0.58)] bg-white shadow-[0_22px_55px_-42px_rgba(17,28,45,0.34)]"
              key={item.transferId}
            >
              <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 gap-4">
                  <ProfileMedia
                    alt={item.playerName}
                    assetId={item.playerId}
                    category="players"
                    className="h-14 w-14 rounded-xl shadow-[0_16px_32px_-24px_rgba(0,53,38,0.74)]"
                    fallback={getPlayerMonogram(item.playerName)}
                    href={playerHref}
                    shape="rounded"
                  />

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <ProfileTag>{getTransferTypeLabel(item.typeId, item.typeName)}</ProfileTag>
                      {item.careerEnded ? <ProfileTag>Fim de carreira</ProfileTag> : null}
                    </div>
                    <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-tight text-[#111c2d]">
                      {item.playerName}
                    </h2>
                    <p className="mt-2 text-sm/6 text-[#57657a]">
                      {formatMovement(item)}
                    </p>
                  </div>
                </div>

                <div className="flex min-h-24 flex-col items-center justify-center rounded-xl border border-[rgba(199,159,78,0.28)] bg-[rgba(255,248,230,0.82)] px-4 py-3 text-center sm:min-w-44">
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#8c6a1f]">
                    Valor
                  </p>
                  <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {amountLabel}
                  </p>
                  {amountValue !== null ? (
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#8c6a1f]">
                      EUR
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="grid border-y border-[rgba(191,201,195,0.38)] bg-[rgba(246,248,252,0.74)] sm:grid-cols-3">
                <div className="border-b border-[rgba(191,201,195,0.28)] px-5 py-4 sm:border-b-0 sm:border-r">
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#69778d]">
                    Origem
                  </p>
                  <div className="mt-2 flex min-w-0 items-center gap-2">
                    <ProfileMedia
                      alt={item.fromTeamName ?? "Origem"}
                      assetId={item.fromTeamId}
                      category="clubs"
                      className="h-9 w-9 rounded-lg border-[rgba(191,201,195,0.6)] bg-white"
                      fallback={getTeamFallback(item.fromTeamName, item.fromTeamId)}
                      href={fromTeamHref}
                      shape="rounded"
                    />
                    <p className="truncate text-sm font-extrabold text-[#111c2d]">
                      {item.fromTeamName ?? "Não informada"}
                    </p>
                  </div>
                </div>
                <div className="border-b border-[rgba(191,201,195,0.28)] px-5 py-4 sm:border-b-0 sm:border-r">
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#69778d]">
                    Destino
                  </p>
                  <div className="mt-2 flex min-w-0 items-center gap-2">
                    <ProfileMedia
                      alt={item.toTeamName ?? "Destino"}
                      assetId={item.toTeamId}
                      category="clubs"
                      className="h-9 w-9 rounded-lg border-[rgba(191,201,195,0.6)] bg-white"
                      fallback={getTeamFallback(item.toTeamName, item.toTeamId)}
                      href={toTeamHref}
                      shape="rounded"
                    />
                    <p className="truncate text-sm font-extrabold text-[#111c2d]">
                      {item.careerEnded ? "Fim de carreira" : item.toTeamName ?? "Não informado"}
                    </p>
                  </div>
                </div>
                <div className="px-5 py-4">
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#69778d]">
                    Data
                  </p>
                  <p className="mt-1 text-sm font-extrabold text-[#111c2d]">
                    {formatTransferDate(item.transferDate)}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 px-5 py-4">
                {playerHref ? (
                  <Link
                    className="button-pill button-pill-primary"
                    href={playerHref}
                  >
                    Abrir jogador
                  </Link>
                ) : null}
                {fromTeamHref ? (
                  <Link
                    className="button-pill button-pill-secondary"
                    href={fromTeamHref}
                  >
                    Time de origem
                  </Link>
                ) : null}
                {toTeamHref ? (
                  <Link
                    className="button-pill button-pill-secondary"
                    href={toTeamHref}
                  >
                    Time de destino
                  </Link>
                ) : null}
              </div>
            </article>
          );
        })}
      </section>

      {items.length > 0 ? (
        <ProfilePanel className="flex flex-col gap-3 border-white/80 bg-white/84 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium text-[#57657a]">
            Mostrando {formatInteger(currentRangeStart)}-{formatInteger(currentRangeEnd)} de{" "}
            {formatInteger(totalCount)} transferências. Página {formatInteger(currentPage)} de{" "}
            {formatInteger(totalPages)}.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="button-pill disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!hasPreviousPage}
              onClick={() => setPage((value) => Math.max(value - 1, 1))}
              type="button"
            >
              Anterior
            </button>
            <button
              className="button-pill button-pill-primary disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!hasNextPage}
              onClick={() => setPage((value) => Math.min(value + 1, totalPages))}
              type="button"
            >
              Próxima
            </button>
          </div>
        </ProfilePanel>
      ) : null}

    </ProfileShell>
  );
}
