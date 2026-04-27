"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { CoachAvatar } from "@/features/coaches/components/CoachAvatar";
import { useCoachesList } from "@/features/coaches/hooks";
import type {
  CoachListItem,
  CoachesListSortBy,
  CoachesListSortDirection,
} from "@/features/coaches/types";
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
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  appendFilterQueryString,
  buildCanonicalTeamPath,
  buildMatchesPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const PERCENT_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

const PAGE_SIZE_OPTIONS = [12, 24, 48, 96] as const;
const MIN_MATCH_OPTIONS = [0, 1, 5, 10, 20] as const;
const DEFAULT_PAGE_SIZE: (typeof PAGE_SIZE_OPTIONS)[number] = 24;
const DEFAULT_MIN_MATCHES: (typeof MIN_MATCH_OPTIONS)[number] = 1;
const CAMPAIGN_INDEX_EXPLANATION =
  "Pontos/Jogo = pontos por jogo ponderado pela amostra do recorte, para não premiar passagens muito curtas.";

const SORT_OPTIONS: Array<{ label: string; value: CoachesListSortBy }> = [
  { label: "Pontos/Jogo", value: "adjustedPpm" },
  { label: "Jogos", value: "matches" },
  { label: "Vitórias", value: "wins" },
  { label: "Pontos/Jogo bruto", value: "pointsPerMatch" },
  { label: "Nome", value: "coachName" },
  { label: "Início da passagem", value: "startDate" },
];

function describeVenue(venue: string | null | undefined): string {
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
  if (typeof params.lastN === "number" && params.lastN > 0) {
    return `Últimas ${params.lastN} partidas`;
  }

  if (params.dateRangeStart || params.dateRangeEnd) {
    return `${params.dateRangeStart ?? "..."} até ${params.dateRangeEnd ?? "..."}`;
  }

  if (params.roundId) {
    return `Rodada ${params.roundId}`;
  }

  return "Temporada inteira";
}

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return INTEGER_FORMATTER.format(value);
}

function formatSignedInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return value > 0 ? `+${INTEGER_FORMATTER.format(value)}` : INTEGER_FORMATTER.format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return DECIMAL_FORMATTER.format(value);
}

function formatPercent(value: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return `${PERCENT_FORMATTER.format(value)}%`;
}

function formatShortDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const [year, month, day] = value.split("-");

  if (!year || !month || !day) {
    return value;
  }

  return `${day}/${month}/${year}`;
}

function formatDateRange(startDate: string | null | undefined, endDate: string | null | undefined): string {
  if (startDate && endDate) {
    return `${formatShortDate(startDate)} até ${formatShortDate(endDate)}`;
  }

  if (startDate) {
    return `${formatShortDate(startDate)} até atual`;
  }

  if (endDate) {
    return `Até ${formatShortDate(endDate)}`;
  }

  return "Janela não informada";
}

function formatRecord(wins: number, draws: number, losses: number): string {
  return `${wins}V ${draws}E ${losses}D`;
}

function calculateWinRate(item: CoachListItem): number | null {
  if (item.matches <= 0) {
    return null;
  }

  return (item.wins / item.matches) * 100;
}

function isUnknownCoachName(coachName: string): boolean {
  return /^(Unknown Coach|Nome pendente) #/i.test(coachName.trim());
}

function getCoachDisplayName(item: CoachListItem): string {
  return isUnknownCoachName(item.coachName) ? "Nome pendente de ingestão" : item.coachName;
}

function getCoachSecondaryName(item: CoachListItem): string | null {
  return isUnknownCoachName(item.coachName) ? `ID ${item.coachId}` : null;
}

function getContextLabel(item: CoachListItem): string {
  if (!item.context) {
    return "Contexto não resolvido";
  }

  return `${item.context.competitionName} ${item.context.seasonLabel}`;
}

function getSortLabel(sortBy: CoachesListSortBy): string {
  return SORT_OPTIONS.find((option) => option.value === sortBy)?.label ?? "Critério";
}

function getDirectionLabel(sortDirection: CoachesListSortDirection): string {
  return sortDirection === "asc" ? "Menor para maior" : "Maior para menor";
}

function getMinMatchesLabel(minMatches: number): string {
  return minMatches === 0 ? "Todas as passagens" : `${minMatches}+ jogos`;
}

function StatTile({
  label,
  tone = "base",
  value,
}: {
  label: string;
  tone?: "base" | "soft";
  value: string;
}) {
  return (
    <article
      className={
        tone === "soft"
          ? "rounded-[1rem] border border-[rgba(216,227,251,0.74)] bg-[rgba(240,243,255,0.78)] px-3 py-2.5"
          : "rounded-[1rem] border border-white/76 bg-white/78 px-3 py-2.5"
      }
    >
      <p className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-[#69778d]">{label}</p>
      <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-xl font-extrabold leading-none tracking-[-0.03em] text-[#111c2d]">
        {value}
      </p>
    </article>
  );
}

function FilterSelect<TValue extends string | number>({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: TValue }>;
  value: TValue;
}) {
  return (
    <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
      {label}
      <select
        className="h-[58px] rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={String(option.value)} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function CoachesPageContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(DEFAULT_PAGE_SIZE);
  const [sortBy, setSortBy] = useState<CoachesListSortBy>("adjustedPpm");
  const [sortDirection, setSortDirection] = useState<CoachesListSortDirection>("desc");
  const [minMatches, setMinMatches] = useState<(typeof MIN_MATCH_OPTIONS)[number]>(DEFAULT_MIN_MATCHES);
  const [includeUnknown, setIncludeUnknown] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const coachesQuery = useCoachesList(
    {
      search: deferredSearch,
      page,
      pageSize,
      sortBy,
      sortDirection,
      minMatches,
      includeUnknown,
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
    ? buildSeasonHubTabPath(resolvedContext, "standings", sharedFilters)
    : "/competitions";
  const matchesHref = buildMatchesPath(sharedFilters);
  const playersHref = buildPlayersPath(sharedFilters);
  const activeWindowLabel = describeTimeWindow({
    roundId,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });

  useEffect(() => {
    setPage(1);
  }, [
    dateRangeEnd,
    dateRangeStart,
    deferredSearch,
    includeUnknown,
    lastN,
    minMatches,
    resolvedContext?.competitionId,
    resolvedContext?.seasonId,
    roundId,
    sortBy,
    sortDirection,
    venue,
  ]);

  if (coachesQuery.isLoading && !coachesQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnicos
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando técnicos
          </h1>
        </header>
        <LoadingSkeleton height={220} />
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
      </ProfileShell>
    );
  }

  if (coachesQuery.isError && !coachesQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnicos
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar técnicos
          </h1>
        </header>
        <ProfileAlert title="Erro no carregamento" tone="critical">
          <p>{coachesQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (!coachesQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <EmptyState
          title="Sem técnicos disponíveis"
          description="Não foi possível montar a lista de técnicos neste momento."
        />
      </ProfileShell>
    );
  }

  const items = coachesQuery.data.items;
  const pagination = coachesQuery.meta?.pagination;
  const totalCount = pagination?.totalCount ?? items.length;
  const totalPages = Math.max(pagination?.totalPages ?? 1, 1);
  const currentPage = pagination?.page ?? page;
  const resolvedPageSize = pagination?.pageSize ?? pageSize;
  const currentRangeStart = totalCount === 0 ? 0 : (currentPage - 1) * resolvedPageSize + 1;
  const currentRangeEnd = totalCount === 0 ? 0 : currentRangeStart + items.length - 1;
  const featuredCoaches = items.slice(0, 3);
  const featuredCoach = featuredCoaches[0] ?? null;
  const pageMatches = items.reduce((total, item) => total + item.matches, 0);
  const activeItemsCount = items.filter((item) => item.active).length;
  const contextLabel = resolvedContext
    ? `${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
    : "Todos os contextos";
  const hasLocalFilters =
    search.trim().length > 0 ||
    includeUnknown ||
    minMatches !== DEFAULT_MIN_MATCHES ||
    pageSize !== DEFAULT_PAGE_SIZE ||
    sortBy !== "adjustedPpm" ||
    sortDirection !== "desc";

  const getCoachHref = (coachId: string) => appendFilterQueryString(`/coaches/${coachId}`, sharedFilters);
  const getTeamHref = (item: CoachListItem) => {
    const teamContext = item.context ?? resolvedContext;

    if (!item.teamId) {
      return null;
    }

    return teamContext
      ? appendFilterQueryString(
          buildCanonicalTeamPath(teamContext, item.teamId),
          sharedFilters,
          ["competitionId", "seasonId"],
        )
      : buildTeamResolverPath(item.teamId, sharedFilters);
  };
  const resetLocalFilters = () => {
    setSearch("");
    setSortBy("adjustedPpm");
    setSortDirection("desc");
    setMinMatches(DEFAULT_MIN_MATCHES);
    setIncludeUnknown(false);
    setPageSize(DEFAULT_PAGE_SIZE);
    setPage(1);
  };

  return (
    <ProfileShell className="space-y-6">
      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_12%,rgba(166,242,209,0.26),transparent_32%),radial-gradient(circle_at_84%_2%,rgba(216,227,251,0.22),transparent_34%)]" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-28 left-12 h-56 w-56 rounded-full bg-white/5 blur-3xl" />

        <div className="relative grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.42fr)] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5 xl:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileCoveragePill coverage={coachesQuery.coverage} className="bg-white/12 text-white/82" />
              <ProfileTag className="bg-white/10 text-white/82">{contextLabel}</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">Dados até 31/12/2025</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">{activeWindowLabel}</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">{describeVenue(venue)}</ProfileTag>
            </div>

            <div className="max-w-3xl">
              <p className="text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                Técnicos
              </p>
              <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-5xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-6xl">
                Ranking limpo de comando técnico
              </h1>
  
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <ProfileKpi
                hint={`de ${formatInteger(totalCount)} técnicos filtrados`}
                invert
                label="Mostrando"
                value={`${formatInteger(currentRangeStart)}-${formatInteger(currentRangeEnd)}`}
              />
              <ProfileKpi hint="Somados nesta página" invert label="Jogos" value={formatInteger(pageMatches)} />
              <ProfileKpi hint="Em 31/12/2025" invert label="Ativos no corte" value={formatInteger(activeItemsCount)} />
              <ProfileKpi hint={getDirectionLabel(sortDirection)} invert label="Critério" value={getSortLabel(sortBy)} />
            </div>

            <div className="flex flex-wrap gap-2">
              <Link className="button-pill button-pill-on-dark" href={seasonHubHref}>
                Temporada
              </Link>
              <Link className="button-pill button-pill-on-dark" href={matchesHref}>
                Partidas
              </Link>
              <Link className="button-pill button-pill-on-dark" href={playersHref}>
                Jogadores
              </Link>
            </div>
          </div>

          <aside className="grid content-start gap-3 xl:pt-14">
            {featuredCoach ? (
              <Link
                className="group flex min-h-[12rem] flex-col justify-between rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/16"
                href={getCoachHref(featuredCoach.coachId)}
              >
                <div className="flex items-start gap-3">
                  <CoachAvatar
                    coachName={featuredCoach.coachName}
                    hasRealPhoto={featuredCoach.hasRealPhoto}
                    photoUrl={featuredCoach.photoUrl}
                  />
                  <div className="min-w-0">
                    <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                      Destaque #{currentRangeStart || 1}
                    </p>
                    <h2 className="mt-1 line-clamp-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold leading-tight tracking-[-0.035em] text-white">
                      {getCoachDisplayName(featuredCoach)}
                    </h2>
                    <p className="mt-1 truncate text-sm text-white/58">
                      {featuredCoach.teamName ?? "Sem clube resolvido"}
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-2">
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Pontos/Jogo</p>
                    <p className="mt-1 text-2xl font-extrabold">{formatDecimal(featuredCoach.adjustedPpm)}</p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Jogos</p>
                    <p className="mt-1 text-2xl font-extrabold">{formatInteger(featuredCoach.matches)}</p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Saldo</p>
                    <p className="mt-1 text-2xl font-extrabold">{formatSignedInteger(featuredCoach.goalDiff)}</p>
                  </div>
                </div>
              </Link>
            ) : (
              <div className="rounded-[1.55rem] border border-white/12 bg-white/10 p-5 text-white/70">
                Sem técnicos para destacar neste recorte.
              </div>
            )}

            {featuredCoaches.length > 1 ? (
              <div className="grid gap-2">
                {featuredCoaches.slice(1).map((coach, index) => (
                  <Link
                    className="flex items-center gap-3 rounded-[1.15rem] border border-white/10 bg-white/8 px-3 py-3 text-white transition-colors hover:bg-white/14"
                    href={getCoachHref(coach.coachId)}
                    key={coach.coachId}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/12 text-xs font-bold text-white/72">
                      {currentRangeStart + index + 1}
                    </span>
                    <CoachAvatar coachName={coach.coachName} hasRealPhoto={coach.hasRealPhoto} photoUrl={coach.photoUrl} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold">{getCoachDisplayName(coach)}</p>
                      <p className="truncate text-xs text-white/56">{coach.teamName ?? "Sem clube resolvido"}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-extrabold">{formatDecimal(coach.adjustedPpm)}</p>
                      <p className="text-[0.58rem] uppercase tracking-[0.16em] text-white/48">índice</p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
          </aside>
        </div>
      </ProfilePanel>

      {coachesQuery.isError ? (
        <ProfileAlert title="Lista carregada com alerta" tone="warning">
          <p>{coachesQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      <ProfilePanel className="space-y-4 border-white/80 bg-white/84">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
              Filtros
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
              Encontrar técnico relevante
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-[#57657a]">
              Busque por técnico ou clube. Ex.: Flamengo retorna os técnicos que tiveram passagem pelo clube no recorte atual.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{formatInteger(totalCount)} técnicos</ProfileTag>
            <ProfileTag>{getMinMatchesLabel(minMatches)}</ProfileTag>
            <ProfileTag>{includeUnknown ? "Inclui pendentes" : "Nomes resolvidos"}</ProfileTag>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_220px_190px_160px]">
          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Busca
            <input
              className="h-[58px] rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] placeholder:text-[#707974]"
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Ex.: Abel Ferreira, Palmeiras"
              type="search"
              value={search}
            />
          </label>

          <FilterSelect
            label="Ordenar"
            onChange={(value) => {
              setSortBy(value as CoachesListSortBy);
              setPage(1);
            }}
            options={SORT_OPTIONS}
            value={sortBy}
          />

          <FilterSelect
            label="Direção"
            onChange={(value) => {
              setSortDirection(value as CoachesListSortDirection);
              setPage(1);
            }}
            options={[
              { label: "Maior para menor", value: "desc" },
              { label: "Menor para maior", value: "asc" },
            ]}
            value={sortDirection}
          />

          <FilterSelect
            label="Linhas"
            onChange={(value) => {
              setPageSize(Number(value) as (typeof PAGE_SIZE_OPTIONS)[number]);
              setPage(1);
            }}
            options={PAGE_SIZE_OPTIONS.map((option) => ({ label: String(option), value: option }))}
            value={pageSize}
          />
        </div>

        <div className="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:items-end">
          <FilterSelect
            label="Amostra mínima"
            onChange={(value) => {
              setMinMatches(Number(value) as (typeof MIN_MATCH_OPTIONS)[number]);
              setPage(1);
            }}
            options={MIN_MATCH_OPTIONS.map((option) => ({ label: getMinMatchesLabel(option), value: option }))}
            value={minMatches}
          />

          <label className="flex min-h-[58px] items-center gap-3 rounded-[1.15rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-semibold text-[#1f2d40] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
            <input
              checked={includeUnknown}
              className="h-4 w-4 accent-[#003526]"
              onChange={(event) => {
                setIncludeUnknown(event.target.checked);
                setPage(1);
              }}
              type="checkbox"
            />
            Incluir nomes pendentes de ingestão
          </label>

          <button
            className={hasLocalFilters ? "button-pill button-pill-primary" : "button-pill button-pill-secondary"}
            disabled={!hasLocalFilters}
            onClick={resetLocalFilters}
            type="button"
          >
            Limpar filtros
          </button>
        </div>
      </ProfilePanel>

      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
              Lista atual
            </p>
            <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.045em] text-[#111c2d]">
              Técnicos no recorte
            </h2>
          </div>
          <p className="text-sm text-[#57657a]">
            Página {formatInteger(currentPage)} de {formatInteger(totalPages)}
          </p>
        </div>

        {items.length > 0 ? (
          <div className="grid gap-3">
            {items.map((item, index) => {
              const rank = currentRangeStart + index;
              const coachHref = getCoachHref(item.coachId);
              const teamHref = getTeamHref(item);
              const secondaryName = getCoachSecondaryName(item);

              return (
                <ProfilePanel className="overflow-hidden border-white/78 bg-white/84 p-0" key={item.coachId}>
                  <div className="grid gap-3 p-4 md:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.58fr)] lg:items-center">
                    <div className="flex min-w-0 gap-3">
                      <div className="flex flex-col items-center gap-2">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#003526] font-[family:var(--font-profile-headline)] text-xs font-extrabold text-white shadow-[0_16px_34px_-26px_rgba(0,53,38,0.7)]">
                          {formatInteger(rank)}
                        </span>
                        <span className="h-full w-px bg-[linear-gradient(180deg,rgba(0,53,38,0.18),transparent)]" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex min-w-0 items-start gap-3">
                          <CoachAvatar
                            coachName={item.coachName}
                            hasRealPhoto={item.hasRealPhoto}
                            photoUrl={item.photoUrl}
                          />
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <ProfileTag>{item.active ? "Ativo no corte" : "Histórico"}</ProfileTag>
                              {item.temporary ? <ProfileTag>Interino</ProfileTag> : null}
                              {item.matches < 5 ? <ProfileTag>Amostra curta</ProfileTag> : null}
                            </div>
                            <h3 className="mt-1.5 font-[family:var(--font-profile-headline)] text-2xl font-extrabold leading-tight tracking-[-0.04em] text-[#111c2d]">
                              {getCoachDisplayName(item)}
                            </h3>
                            {secondaryName ? <p className="mt-1 text-xs font-semibold text-[#7d889e]">{secondaryName}</p> : null}
                            <p className="mt-1.5 text-sm/6 text-[#57657a]">
                              {item.teamName ?? "Sem clube resolvido"} • {formatDateRange(item.startDate, item.endDate)}
                            </p>
                            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#69778d]">
                              {getContextLabel(item)} • Último jogo {formatShortDate(item.lastMatchDate)}
                            </p>
                          </div>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2">
                          <Link className="button-pill button-pill-primary" href={coachHref}>
                            Abrir perfil
                          </Link>
                          {teamHref ? (
                            <Link className="button-pill button-pill-secondary" href={teamHref}>
                              Abrir clube
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-2">
                      <StatTile label="Pontos/Jogo" value={formatDecimal(item.adjustedPpm)} />
                      <StatTile label="Jogos" value={formatInteger(item.matches)} />
                      <StatTile label="Aproveitamento" tone="soft" value={formatPercent(calculateWinRate(item))} />
                      <StatTile label="Campanha" tone="soft" value={formatRecord(item.wins, item.draws, item.losses)} />
                      <StatTile label="Gols" value={`${formatInteger(item.goalsFor)}-${formatInteger(item.goalsAgainst)}`} />
                      <StatTile label="Saldo" value={formatSignedInteger(item.goalDiff)} />
                    </div>
                  </div>
                </ProfilePanel>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="Nenhum técnico encontrado"
            description="Ajuste busca, amostra mínima ou a opção de nomes pendentes para ampliar o recorte."
          />
        )}
      </section>

      <ProfilePanel className="flex flex-col gap-3 border-white/80 bg-white/84 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-medium text-[#57657a]">
          Mostrando {formatInteger(currentRangeStart)}-{formatInteger(currentRangeEnd)} de {formatInteger(totalCount)} técnicos
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            className="button-pill disabled:cursor-not-allowed disabled:opacity-45"
            disabled={currentPage <= 1}
            onClick={() => setPage((value) => Math.max(value - 1, 1))}
            type="button"
          >
            Anterior
          </button>
          <button
            className="button-pill button-pill-primary disabled:cursor-not-allowed disabled:opacity-45"
            disabled={currentPage >= totalPages}
            onClick={() => setPage((value) => Math.min(value + 1, totalPages))}
            type="button"
          >
            Próxima
          </button>
        </div>
      </ProfilePanel>
    </ProfileShell>
  );
}
