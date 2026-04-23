"use client";

import { useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useTeamsList } from "@/features/teams/hooks/useTeamsList";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfileMetricTile,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileRouteCard } from "@/shared/components/profile/ProfileRouteCard";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildCanonicalTeamPath,
  buildFilterQueryString,
  buildMatchesPath,
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

export function TeamsPageContent() {
  const [search, setSearch] = useState("");
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const teamsQuery = useTeamsList(
    {
      search,
      pageSize: 40,
      sortBy: "points",
      sortDirection: "desc",
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
  const matchesHref = buildMatchesPath(sharedFilterInput);
  const playersHref = buildPlayersPath(sharedFilterInput);
  const rankingsHref = buildRankingPath("team-possession", sharedFilterInput);
  const activeWindowLabel = describeTimeWindow({
    roundId,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });

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

  if (teamsQuery.isEmpty || !teamsQuery.data) {
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

  const items = teamsQuery.data.items;

  return (
    <ProfileShell className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.95fr)]">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={teamsQuery.coverage} className="bg-white/16 text-white" />
            <ProfileTag className="bg-white/12 text-white/82">
              {resolvedContext ? "Contexto fechado" : "Entrada direta"}
            </ProfileTag>
            <ProfileTag className="bg-white/12 text-white/82">{items.length} times</ProfileTag>
          </div>
          <div className="space-y-3">
            <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
              Lista de times
            </p>
            <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {resolvedContext
                ? `Times em ${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
                : "Descoberta de times"}
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/74">
              Veja quem puxa a campanha da temporada, abra o perfil do time e siga para elenco,
              partidas e métricas sem sair do mesmo contexto.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <ProfileKpi hint="Na visão atual" invert label="Times" value={items.length} />
            <ProfileKpi hint={describeVenue(venue)} invert label="Mando" value={describeVenue(venue)} />
            <ProfileKpi hint="Janela aplicada" invert label="Janela" value={activeWindowLabel} />
          </div>
        </ProfilePanel>

        <div className="grid gap-4">
          <ProfilePanel className="space-y-4">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Leitura atual
            </p>
            <dl className="space-y-3 text-sm text-[#1f2d40]">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Competição</dt>
                <dd className="text-right font-medium">{resolvedContext?.competitionName ?? "Todas"}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Temporada</dt>
                <dd className="text-right font-medium">{resolvedContext?.seasonLabel ?? "Todas"}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Mando</dt>
                <dd className="text-right font-medium">{describeVenue(venue)}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Janela</dt>
                <dd className="text-right font-medium">{activeWindowLabel}</dd>
              </div>
            </dl>
          </ProfilePanel>

          <ProfilePanel className="space-y-3" tone="soft">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Atalhos
            </p>
            <div className="flex flex-wrap gap-2">
              <Link
                className="button-pill button-pill-primary"
                href={seasonHubHref}
              >
                Voltar para temporada
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href={matchesHref}
              >
                Abrir partidas
              </Link>
            </div>
          </ProfilePanel>
        </div>
      </section>

      {teamsQuery.isError ? (
        <ProfileAlert title="Lista carregada com alerta" tone="warning">
          <p>{teamsQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-4">
        <ProfileRouteCard
          description="Volte para a temporada quando quiser reler tabela e fases sem perder o recorte."
          href={seasonHubHref}
          label="Contexto canônico"
          title="Temporada"
        />
        <ProfileRouteCard
          description="Abra o calendário completo e siga do time para a lista de jogos da mesma leitura."
          href={matchesHref}
          label="Saída canônica"
          title="Partidas"
        />
        <ProfileRouteCard
          description="Cruze o elenco com o catálogo de atletas mantendo competição, temporada e janela."
          href={playersHref}
          label="Descoberta"
          title="Jogadores"
        />
        <ProfileRouteCard
          description="Compare posse e outros destaques coletivos sem sair do mesmo produto."
          href={rankingsHref}
          label="Leitura comparativa"
          title="Rankings"
        />
      </section>

      {teamsQuery.isPartial ? <PartialDataBanner coverage={teamsQuery.coverage} /> : null}

      <ProfilePanel className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between" tone="soft">
        <div className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Filtro local
          </p>
          <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            Encontrar time nesta temporada
          </h2>
        </div>
        <label className="flex min-w-[260px] flex-col gap-2 text-sm font-medium text-[#1f2d40]">
          Busca por nome
          <input
            className="rounded-[1rem] border border-[rgba(191,201,195,0.55)] bg-white/92 px-4 py-3 text-sm text-[#111c2d] outline-none transition-colors focus:border-[#003526] focus:ring-2 focus:ring-[#003526]"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Ex: Palmeiras, Liverpool, Flamengo"
            type="search"
            value={search}
          />
        </label>
      </ProfilePanel>

      <section className="grid gap-4 xl:grid-cols-2">
        {items.map((team) => {
          const profileHref = resolvedContext
            ? `${buildCanonicalTeamPath(resolvedContext, team.teamId)}${canonicalExtraQuery}`
            : buildTeamResolverPath(team.teamId, sharedFilterInput);

          return (
            <ProfilePanel className="space-y-5" key={team.teamId}>
              <div className="flex flex-wrap items-start gap-4">
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
                    <p className="text-sm text-[#57657a]">
                      {resolvedContext
                        ? `${resolvedContext.competitionName} · ${resolvedContext.seasonLabel}`
                        : "Catálogo guiado pelos filtros atuais"}
                    </p>
                    <Link
                      className="button-pill button-pill-primary"
                      href={profileHref}
                    >
                      Abrir perfil de {team.teamName}
                    </Link>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-4">
                <ProfileMetricTile label="Jogos" value={team.matchesPlayed ?? "-"} />
                <ProfileMetricTile label="Vitórias" value={team.wins ?? "-"} />
                <ProfileMetricTile label="Saldo" value={formatGoalDiff(team.goalDiff)} />
                <ProfileMetricTile label="Gols pró" value={team.goalsFor ?? "-"} />
              </div>

              <div className="grid gap-3 sm:grid-cols-4">
                <ProfileMetricTile label="Empates" value={team.draws ?? "-"} tone="soft" />
                <ProfileMetricTile label="Derrotas" value={team.losses ?? "-"} tone="soft" />
                <ProfileMetricTile label="Gols contra" value={team.goalsAgainst ?? "-"} tone="soft" />
                <ProfileMetricTile label="Pontos" value={team.points ?? "-"} tone="soft" />
              </div>
            </ProfilePanel>
          );
        })}
      </section>
    </ProfileShell>
  );
}
