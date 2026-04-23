"use client";

import { useDeferredValue, useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useCoachesList } from "@/features/coaches/hooks";
import { CoachAvatar } from "@/features/coaches/components/CoachAvatar";
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

function formatPointsPerMatch(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value.toFixed(2);
}

function formatDateRange(startDate: string | null | undefined, endDate: string | null | undefined): string {
  const normalizedStart = startDate?.trim() ?? "";
  const normalizedEnd = endDate?.trim() ?? "";

  if (normalizedStart && normalizedEnd) {
    return `${normalizedStart} -> ${normalizedEnd}`;
  }

  if (normalizedStart) {
    return `${normalizedStart} -> atual`;
  }

  if (normalizedEnd) {
    return `Até ${normalizedEnd}`;
  }

  return "Janela não informada";
}

function formatRecord(wins: number, draws: number, losses: number): string {
  return `${wins}-${draws}-${losses}`;
}

export function CoachesPageContent() {
  const [search, setSearch] = useState("");
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
      pageSize: 24,
      sortBy: "adjustedPpm",
      sortDirection: "desc",
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

  if (coachesQuery.isLoading) {
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
        <LoadingSkeleton height={140} />
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

  if (coachesQuery.isEmpty || !coachesQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnicos
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Nenhum técnico encontrado
          </h1>
        </header>
        <EmptyState
          title="Sem técnicos neste recorte"
          description="Não encontramos técnicos com os filtros atuais."
        />
      </ProfileShell>
    );
  }

  const items = coachesQuery.data.items;

  return (
    <ProfileShell className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.95fr)]">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={coachesQuery.coverage} className="bg-white/16 text-white" />
            <ProfileTag className="bg-white/12 text-white/82">
              {resolvedContext ? "Contexto fechado" : "Entrada direta"}
            </ProfileTag>
            <ProfileTag className="bg-white/12 text-white/82">{items.length} técnicos</ProfileTag>
          </div>

            <div className="space-y-3">
              <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
                Catálogo de técnicos
              </p>
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {resolvedContext
                ? `Técnicos em ${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
                : "Leitura de técnicos por passagem e rendimento"}
              </h1>
              <p className="max-w-3xl text-sm/6 text-white/74">
                O domínio agora usa identidade canônica de técnicos materializada na base de dados.
                A ordenação prioriza técnicos em atividade e rendimento sustentado, reduzindo o
                viés de amostras curtas.
              </p>
            </div>

          <div className="grid gap-3 md:grid-cols-3">
            <ProfileKpi hint="Linhas nesta visão" invert label="Técnicos" value={items.length} />
            <ProfileKpi hint={describeVenue(venue)} invert label="Mando" value={describeVenue(venue)} />
            <ProfileKpi hint="Janela aplicada" invert label="Janela" value={activeWindowLabel} />
          </div>
        </ProfilePanel>

        <div className="grid gap-4">
          <ProfilePanel className="space-y-4">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Busca
            </p>
            <label className="block">
              <span className="sr-only">Buscar técnico ou time</span>
              <input
                className="w-full rounded-[1.1rem] border border-[rgba(191,201,195,0.65)] bg-white/92 px-4 py-3 text-sm text-[#111c2d] outline-none transition-colors placeholder:text-[#7f8b99] focus:border-[#8bd6b6]"
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
                placeholder="Buscar técnico ou time"
                value={search}
              />
            </label>
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
                <dt className="text-[#57657a]">Janela</dt>
                <dd className="text-right font-medium">{activeWindowLabel}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Ranking</dt>
                <dd className="text-right font-medium">Ativo → rendimento sustentado</dd>
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
              <Link
                className="button-pill button-pill-secondary"
                href={playersHref}
              >
                Abrir jogadores
              </Link>
            </div>
          </ProfilePanel>
        </div>
      </section>

      <PartialDataBanner
        coverage={coachesQuery.coverage}
        message="Parte das passagens pode não ter partidas materializadas neste recorte."
      />

      <section className="grid gap-4 lg:grid-cols-2">
        {items.map((item) => {
          const teamContext = item.context ?? resolvedContext;
          const teamHref = item.teamId
            ? teamContext
              ? appendFilterQueryString(
                  buildCanonicalTeamPath(teamContext, item.teamId),
                  sharedFilters,
                  ["competitionId", "seasonId"],
                )
              : buildTeamResolverPath(item.teamId, sharedFilters)
            : null;
          const coachHref = appendFilterQueryString(`/coaches/${item.coachId}`, sharedFilters);

          return (
            <div
              className="rounded-[1.45rem] border border-[rgba(191,201,195,0.6)] bg-white/90 p-5 shadow-[0_24px_70px_-54px_rgba(17,28,45,0.28)]"
              key={item.coachId}
            >
                <div className="flex items-start gap-4">
                <CoachAvatar
                  coachName={item.coachName}
                  photoUrl={item.photoUrl}
                  hasRealPhoto={item.hasRealPhoto}
                />

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                      {item.coachName}
                    </h2>
                    <ProfileTag>{item.active ? "Ativo" : "Histórico"}</ProfileTag>
                    {item.temporary ? <ProfileTag>Interino</ProfileTag> : null}
                    {item.matches > 0 && item.matches < 5 ? <ProfileTag>Amostra curta</ProfileTag> : null}
                  </div>
                  <p className="mt-1 text-sm/6 text-[#57657a]">
                    {item.teamName ?? "Sem time principal"} • {formatDateRange(item.startDate, item.endDate)}
                  </p>
                  <p className="mt-1 text-xs font-medium uppercase tracking-[0.14em] text-[#57657a]">
                    PPM bruto {formatPointsPerMatch(item.pointsPerMatch)}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Jogos</p>
                  <p className="text-xl font-extrabold text-[#111c2d]">{item.matches}</p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Rendimento</p>
                  <p className="text-xl font-extrabold text-[#111c2d]">
                    {formatPointsPerMatch(item.adjustedPpm)}
                  </p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Campanha</p>
                  <p className="text-xl font-extrabold text-[#111c2d]">
                    {formatRecord(item.wins, item.draws, item.losses)}
                  </p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Passagens</p>
                  <p className="text-xl font-extrabold text-[#111c2d]">{item.tenureCount}</p>
                </ProfilePanel>
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                <Link
                  className="button-pill button-pill-primary"
                  href={coachHref}
                >
                  Abrir perfil
                </Link>
                {teamHref ? (
                  <Link
                    className="button-pill button-pill-secondary"
                    href={teamHref}
                  >
                    Abrir time
                  </Link>
                ) : null}
              </div>
            </div>
          );
        })}
      </section>
    </ProfileShell>
  );
}
