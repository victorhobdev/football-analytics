"use client";

import { useEffect, useMemo, useState } from "react";

import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useTeamsList } from "@/features/teams/hooks/useTeamsList";
import { teamsQueryKeys } from "@/features/teams/queryKeys";
import { fetchTeamsList } from "@/features/teams/services/teams.service";
import type {
  TeamListItem,
  TeamsListFilters,
  TeamsListSortBy,
  TeamsListSortDirection,
} from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileMetricTile,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildCanonicalTeamPath,
  buildFilterQueryString,
  buildPlayersPath,
  buildRankingPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

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

function formatGoalDiff(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value > 0 ? `+${value}` : String(value);
}

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

type TeamsPageIconName =
  | "arrow"
  | "chart"
  | "players"
  | "search"
  | "shield"
  | "star"
  | "table";

function TeamsPageIcon({
  className,
  icon,
}: {
  className?: string;
  icon: TeamsPageIconName;
}) {
  const sharedClassName = className ?? "h-4 w-4";

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

  if (icon === "chart") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M5 18V10h4v8M10 18V5h4v13M15 18v-6h4v6" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4 18.5h16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

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

  if (icon === "search") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="10.8" cy="10.8" r="5.8" stroke="currentColor" strokeWidth="1.8" />
        <path d="m15.4 15.4 4.1 4.1" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (icon === "table") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M6 6.5h12M6 11.5h12M6 16.5h12"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "arrow") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M6.5 12h11m0 0-4.5-4.5M17.5 12l-4.5 4.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
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

function TeamsHeroMetric({
  hint,
  icon,
  label,
  value,
}: {
  hint: string;
  icon: TeamsPageIconName;
  label: string;
  value: string;
}) {
  return (
    <article className="flex min-h-[9.2rem] flex-col justify-between rounded-[1.35rem] border border-white/12 bg-white/10 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/14">
      <div className="flex items-center justify-between gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/12 text-white">
          <TeamsPageIcon className="h-5 w-5" icon={icon} />
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

function TeamsLinkButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: TeamsPageIconName;
  label: string;
}) {
  return (
    <Link
      className="group inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-4 py-2 text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/86 transition-colors hover:border-white/28 hover:bg-white/18"
      href={href}
    >
      <TeamsPageIcon className="h-4 w-4 transition-transform group-hover:scale-110" icon={icon} />
      {label}
    </Link>
  );
}

function resolveFeaturedTeamMetric(team: TeamListItem) {
  if (typeof team.points === "number") {
    return { label: "Pontos", value: formatInteger(team.points) };
  }

  if (typeof team.wins === "number") {
    return { label: "Vitórias", value: formatInteger(team.wins) };
  }

  return { label: "Saldo", value: formatGoalDiff(team.goalDiff) };
}

function calculateTotals(items: TeamListItem[]) {
  return items.reduce(
    (acc, team) => ({
      goalsFor: acc.goalsFor + (team.goalsFor ?? 0),
      matchesPlayed: acc.matchesPlayed + (team.matchesPlayed ?? 0),
      wins: acc.wins + (team.wins ?? 0),
    }),
    { goalsFor: 0, matchesPlayed: 0, wins: 0 },
  );
}

const TEAM_PAGE_SIZE_OPTIONS = [10, 20, 40, 100] as const;
type TeamPageSizeSelection = (typeof TEAM_PAGE_SIZE_OPTIONS)[number] | "all";

const TEAM_SORT_OPTIONS: Array<{ label: string; value: TeamsListSortBy }> = [
  { label: "Pontos", value: "points" },
  { label: "Vitórias", value: "wins" },
  { label: "Saldo", value: "goalDiff" },
  { label: "Posição", value: "position" },
  { label: "Nome", value: "teamName" },
];

export function TeamsPageContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<TeamPageSizeSelection>(40);
  const [sortBy, setSortBy] = useState<TeamsListSortBy>("points");
  const [sortDirection, setSortDirection] = useState<TeamsListSortDirection>("desc");
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const isAllRowsMode = pageSize === "all";
  const requestPage = isAllRowsMode ? 1 : page;
  const requestPageSize = isAllRowsMode ? 100 : pageSize;
  const teamsQuery = useTeamsList(
    {
      page: requestPage,
      pageSize: requestPageSize,
      search,
      sortBy,
      sortDirection,
    },
    resolvedContext,
  );
  const sharedFilterInput = useMemo(
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
  const canonicalExtraQuery = useMemo(
    () => buildFilterQueryString(sharedFilterInput, ["competitionId", "seasonId"]),
    [sharedFilterInput],
  );
  const seasonHubHref = resolvedContext
    ? buildSeasonHubTabPath(resolvedContext, "standings", sharedFilterInput)
    : "/competitions";
  const seasonLinkLabel = resolvedContext ? "Temporada" : "Temporadas";
  const playersHref = buildPlayersPath(sharedFilterInput);
  const rankingsHref = buildRankingPath("team-possession", sharedFilterInput);
  const activeWindowLabel = describeTimeWindow({
    roundId,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });
  const allRowsBaseFilters = useMemo<TeamsListFilters>(() => {
    const normalizedSearch = search.trim();

    return {
      competitionId: resolvedContext?.competitionId ?? competitionId,
      seasonId: resolvedContext?.seasonId ?? seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
      search: normalizedSearch.length > 0 ? normalizedSearch : undefined,
      pageSize: requestPageSize,
      sortBy,
      sortDirection,
    };
  }, [
    competitionId,
    dateRangeEnd,
    dateRangeStart,
    lastN,
    requestPageSize,
    resolvedContext?.competitionId,
    resolvedContext?.seasonId,
    roundId,
    search,
    seasonId,
    sortBy,
    sortDirection,
    venue,
  ]);
  const allRowsPageNumbers = useMemo(() => {
    if (!isAllRowsMode || !teamsQuery.data || teamsQuery.isError) {
      return [];
    }

    const totalPages = teamsQuery.meta?.pagination?.totalPages ?? 1;
    return Array.from({ length: Math.max(totalPages - 1, 0) }, (_, index) => index + 2);
  }, [
    isAllRowsMode,
    teamsQuery.data,
    teamsQuery.isError,
    teamsQuery.meta?.pagination?.totalPages,
  ]);
  const allRowsQueries = useQueries({
    queries: allRowsPageNumbers.map((allPage) => {
      const filters = { ...allRowsBaseFilters, page: allPage };

      return {
        queryKey: teamsQueryKeys.list(filters),
        queryFn: () => fetchTeamsList(filters),
        staleTime: 10 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
      };
    }),
  });
  const isLoadingAllRows = isAllRowsMode && allRowsQueries.some((query) => query.isLoading);
  const allRowsError = allRowsQueries.find((query) => query.isError)?.error;

  useEffect(() => {
    setPage(1);
  }, [
    dateRangeEnd,
    dateRangeStart,
    lastN,
    resolvedContext?.competitionId,
    resolvedContext?.seasonId,
    roundId,
    venue,
  ]);

  if (teamsQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Times
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando times
          </h1>
        </header>
        <LoadingSkeleton height={120} />
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
      </ProfileShell>
    );
  }

  if (teamsQuery.isError && !teamsQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Times
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar times
          </h1>
        </header>
        <ProfileAlert title="Erro no carregamento" tone="critical">
          <p>{teamsQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (!teamsQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Times
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Nenhum time encontrado
          </h1>
        </header>
        <EmptyState
          title="Sem times disponíveis"
          description="Não há times disponíveis com os filtros atuais."
        />
      </ProfileShell>
    );
  }

  const items = isAllRowsMode
    ? [
        ...teamsQuery.data.items,
        ...allRowsQueries.flatMap((query) => query.data?.data.items ?? []),
      ]
    : teamsQuery.data.items;
  const pagination = teamsQuery.meta?.pagination;
  const totalCount = pagination?.totalCount ?? items.length;
  const currentPage = isAllRowsMode ? 1 : pagination?.page ?? page;
  const resolvedPageSize = isAllRowsMode
    ? Math.max(totalCount, items.length, 1)
    : pagination?.pageSize ?? requestPageSize;
  const totalPages = isAllRowsMode
    ? 1
    : Math.max(pagination?.totalPages ?? Math.ceil(totalCount / resolvedPageSize), 1);
  const currentRangeStart = totalCount === 0 ? 0 : (currentPage - 1) * resolvedPageSize + 1;
  const currentRangeEnd = isAllRowsMode
    ? items.length
    : totalCount === 0
      ? 0
      : currentRangeStart + items.length - 1;
  const featuredTeams = items.slice(0, 3);
  const featuredTeam = featuredTeams[0] ?? null;
  const featuredTeamMetric = featuredTeam ? resolveFeaturedTeamMetric(featuredTeam) : null;
  const totals = calculateTotals(items);
  const contextLabel = resolvedContext
    ? `${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
    : "times do acervo";

  return (
    <ProfileShell className="space-y-6">
      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(166,242,209,0.24),transparent_30%),radial-gradient(circle_at_88%_0%,rgba(216,227,251,0.2),transparent_34%)]" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-52 w-52 rounded-full bg-white/5 blur-3xl" />

        <div className="relative grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.42fr)] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5 xl:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/10 text-white/82">{contextLabel}</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">{describeVenue(venue)}</ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">{activeWindowLabel}</ProfileTag>
            </div>

            <div className="max-w-3xl">
              <p className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                <TeamsPageIcon className="h-4 w-4" icon="shield" />
                Times
              </p>
              <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-5xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-6xl">
                Resumo rápido dos clubes
              </h1>
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <TeamsHeroMetric
                hint={`de ${formatInteger(totalCount)} no recorte`}
                icon="shield"
                label="Mostrando"
                value={`${formatInteger(currentRangeStart)}-${formatInteger(currentRangeEnd)}`}
              />
              <TeamsHeroMetric
                hint="somados"
                icon="table"
                label="Jogos"
                value={formatInteger(totals.matchesPlayed)}
              />
              <TeamsHeroMetric
                hint="somadas"
                icon="star"
                label="Vitórias"
                value={formatInteger(totals.wins)}
              />
              <TeamsHeroMetric
                hint="gols pró"
                icon="chart"
                label="Ataque"
                value={formatInteger(totals.goalsFor)}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <TeamsLinkButton href={rankingsHref} icon="chart" label="Rankings" />
              <TeamsLinkButton href={playersHref} icon="players" label="Jogadores" />
              <TeamsLinkButton href={seasonHubHref} icon="table" label={seasonLinkLabel} />
            </div>
          </div>

          <aside className="grid content-start gap-3 xl:pt-14">
            {featuredTeam && featuredTeamMetric ? (
              <Link
                className="group flex min-h-[12rem] flex-col justify-between rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/16"
                href={
                  resolvedContext
                    ? `${buildCanonicalTeamPath(resolvedContext, featuredTeam.teamId)}${canonicalExtraQuery}`
                    : buildTeamResolverPath(featuredTeam.teamId, sharedFilterInput)
                }
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <ProfileMedia
                      alt={`Escudo de ${featuredTeam.teamName}`}
                      assetId={featuredTeam.teamId}
                      category="clubs"
                      className="h-16 w-16 border border-white/18 bg-white/12"
                      fallback={featuredTeam.teamName.slice(0, 3)}
                      imageClassName="p-2"
                      linkBehavior="none"
                    />
                    <div className="min-w-0">
                      <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                        Destaque da lista
                      </p>
                      <h2 className="mt-1 truncate font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                        {featuredTeam.teamName}
                      </h2>
                    </div>
                  </div>
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/12 text-white transition-transform group-hover:scale-105">
                    <TeamsPageIcon className="h-4 w-4" icon="star" />
                  </span>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-2">
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">
                      {featuredTeamMetric.label}
                    </p>
                    <p className="mt-1 text-2xl font-extrabold">{featuredTeamMetric.value}</p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Saldo</p>
                    <p className="mt-1 text-2xl font-extrabold">
                      {formatGoalDiff(featuredTeam.goalDiff)}
                    </p>
                  </div>
                  <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                    <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Pos.</p>
                    <p className="mt-1 text-2xl font-extrabold">
                      {featuredTeam.position ? `${featuredTeam.position}º` : "-"}
                    </p>
                  </div>
                </div>
              </Link>
            ) : (
              <div className="rounded-[1.55rem] border border-white/12 bg-white/10 p-5 text-white/70">
                Sem times para destacar neste recorte.
              </div>
            )}

            {featuredTeams.length > 1 ? (
              <div className="grid gap-2">
                {featuredTeams.slice(1).map((team, index) => (
                  <Link
                    className="flex items-center gap-3 rounded-[1.15rem] border border-white/10 bg-white/8 px-3 py-3 text-white transition-colors hover:bg-white/14"
                    href={
                      resolvedContext
                        ? `${buildCanonicalTeamPath(resolvedContext, team.teamId)}${canonicalExtraQuery}`
                        : buildTeamResolverPath(team.teamId, sharedFilterInput)
                    }
                    key={team.teamId}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/12 text-xs font-bold text-white/72">
                      {index + 2}
                    </span>
                    <ProfileMedia
                      alt={`Escudo de ${team.teamName}`}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-10 w-10 border-0 bg-white/12"
                      fallback={team.teamName.slice(0, 3)}
                      imageClassName="p-1.5"
                      linkBehavior="none"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold">{team.teamName}</p>
                      <p className="truncate text-xs text-white/56">
                        {team.position && team.totalTeams
                          ? `${team.position}º de ${team.totalTeams}`
                          : "Sem posição oficial"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-extrabold">{formatInteger(team.points)}</p>
                      <p className="text-[0.58rem] uppercase tracking-[0.16em] text-white/48">
                        pts
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
          </aside>
        </div>
      </ProfilePanel>

      {teamsQuery.isError ? (
        <ProfileAlert title="Lista carregada com alerta" tone="warning">
          <p>{teamsQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {allRowsError ? (
        <ProfileAlert title="Lista completa incompleta" tone="warning">
          <p>
            Algumas páginas adicionais não carregaram. A lista segue disponível com o recorte
            carregado até agora.
          </p>
        </ProfileAlert>
      ) : null}

      <ProfilePanel className="space-y-4 border-white/80 bg-white/84">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#e9f2ff] text-[#003526]">
              <TeamsPageIcon className="h-5 w-5" icon="search" />
            </span>
            <div>
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
                Filtros
              </p>
              <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
                Encontrar clube
              </h2>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{describeVenue(venue)}</ProfileTag>
            <ProfileTag>{activeWindowLabel}</ProfileTag>
            <ProfileTag>{formatInteger(totalCount)} times</ProfileTag>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_220px_220px_160px]">
          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Busca
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(216,227,251,0.82)] text-[#003526]">
                <TeamsPageIcon className="h-4 w-4" icon="search" />
              </span>
              <input
                className="w-full border-0 bg-transparent text-sm font-medium normal-case tracking-normal text-[#111c2d] outline-none placeholder:text-[#707974]"
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder="Ex.: Palmeiras, Liverpool, Flamengo"
                type="search"
                value={search}
              />
            </div>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Ordenar
            <select
              className="h-[58px] rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
              onChange={(event) => {
                setSortBy(event.target.value as TeamsListSortBy);
                setPage(1);
              }}
              value={sortBy}
            >
              {TEAM_SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Direção
            <select
              className="h-[58px] rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
              onChange={(event) => {
                setSortDirection(event.target.value as TeamsListSortDirection);
                setPage(1);
              }}
              value={sortDirection}
            >
              <option value="desc">Maior para menor</option>
              <option value="asc">Menor para maior</option>
            </select>
          </label>

          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
            Linhas
            <select
              className="h-[58px] rounded-[1.2rem] border border-[rgba(191,201,195,0.48)] bg-[#f9f9ff] px-4 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
              onChange={(event) => {
                const nextPageSize =
                  event.target.value === "all"
                    ? "all"
                    : (Number(event.target.value) as (typeof TEAM_PAGE_SIZE_OPTIONS)[number]);

                setPageSize(nextPageSize);
                setPage(1);
              }}
              value={pageSize}
            >
              {TEAM_PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
              <option value="all">Todos</option>
            </select>
          </label>
        </div>
      </ProfilePanel>

      <section className="grid gap-4 xl:grid-cols-2">
        {items.length > 0 ? (
          items.map((team) => {
            const profileHref = resolvedContext
              ? `${buildCanonicalTeamPath(resolvedContext, team.teamId)}${canonicalExtraQuery}`
              : buildTeamResolverPath(team.teamId, sharedFilterInput);

            return (
              <ProfilePanel className="space-y-5 overflow-hidden border-white/78 bg-white/84" key={team.teamId}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex min-w-0 items-start gap-4">
                    <ProfileMedia
                      alt={`Escudo de ${team.teamName}`}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-16 w-16"
                      fallback={team.teamName.slice(0, 3)}
                    />
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <ProfileTag>
                          {team.position && team.totalTeams
                            ? `${team.position}º de ${team.totalTeams}`
                            : "Sem posição oficial"}
                        </ProfileTag>
                        <ProfileTag>{team.points ?? "-"} pts</ProfileTag>
                      </div>
                      <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
                        {team.teamName}
                      </h2>
                    </div>
                  </div>
                  <Link
                    className="button-pill button-pill-primary gap-2"
                    href={profileHref}
                  >
                    <span>Abrir perfil</span>
                    <TeamsPageIcon className="h-4 w-4" icon="arrow" />
                  </Link>
                </div>

                <div className="grid gap-3 sm:grid-cols-4">
                  <ProfileMetricTile label="Jogos" value={team.matchesPlayed ?? "-"} />
                  <ProfileMetricTile label="Vitórias" value={team.wins ?? "-"} />
                  <ProfileMetricTile label="Saldo" value={formatGoalDiff(team.goalDiff)} tone="soft" />
                  <ProfileMetricTile label="Pontos" value={team.points ?? "-"} tone="soft" />
                </div>
              </ProfilePanel>
            );
          })
        ) : (
          <div className="xl:col-span-2">
            <EmptyState
              title="Nenhum clube encontrado"
              description="Ajuste a busca, o tamanho da lista ou a ordenação para continuar explorando o recorte."
            />
          </div>
        )}
      </section>

      <ProfilePanel className="flex flex-col gap-3 border-white/80 bg-white/84 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-medium text-[#57657a]">
          {isAllRowsMode ? (
            isLoadingAllRows ? (
              <>Carregando todos os clubes · {formatInteger(currentRangeEnd)} de {formatInteger(totalCount)}</>
            ) : (
              <>Todos os {formatInteger(currentRangeEnd)} clubes carregados</>
            )
          ) : (
            <>
              Página {formatInteger(currentPage)} de {formatInteger(totalPages)} · mostrando{" "}
              {formatInteger(currentRangeStart)}-{formatInteger(currentRangeEnd)} de{" "}
              {formatInteger(totalCount)} clubes
            </>
          )}
        </p>
        {!isAllRowsMode ? (
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
        ) : null}
      </ProfilePanel>
    </ProfileShell>
  );
}
