"use client";

import Link from "next/link";
import { useMemo } from "react";

import { useSearchParams } from "next/navigation";

import { useCoachProfile } from "@/features/coaches/hooks";
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
  buildCoachesPath,
  buildMatchesPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

type CoachProfileContentProps = {
  coachId: string;
};

function formatPointsPerMatch(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value.toFixed(2);
}

function formatRecord(wins: number, draws: number, losses: number): string {
  return `${wins}-${draws}-${losses}`;
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

export function CoachProfileContent({ coachId }: CoachProfileContentProps) {
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const profileQuery = useCoachProfile(coachId, {}, resolvedContext);
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
  const coachesHref = buildCoachesPath(sharedFilters);
  const matchesHref = buildMatchesPath(sharedFilters);
  const playersHref = buildPlayersPath(sharedFilters);

  if (profileQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnico
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando perfil do técnico
          </h1>
        </header>
        <LoadingSkeleton height={150} />
        <LoadingSkeleton height={120} />
        <LoadingSkeleton height={240} />
      </ProfileShell>
    );
  }

  if (profileQuery.isError && !profileQuery.data) {
    const isNotFound = profileQuery.error?.status === 404;

    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnico
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            {isNotFound ? "Técnico indisponível" : "Falha ao carregar técnico"}
          </h1>
        </header>
        {isNotFound ? (
          <EmptyState
            title="Técnico indisponível"
            description="Não encontramos este técnico no produto agora."
          />
        ) : (
          <ProfileAlert title="Erro no carregamento" tone="critical">
            <p>{profileQuery.error?.message}</p>
          </ProfileAlert>
        )}
      </ProfileShell>
    );
  }

  if (profileQuery.isEmpty || !profileQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Técnico
          </p>
          <h1
            aria-label="Perfil de técnico indisponível"
            className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]"
          >
            Perfil de técnico indisponível
          </h1>
        </header>
        <EmptyState
          title="Perfil indisponível"
          description="Não há dados suficientes para montar este perfil agora."
        />
      </ProfileShell>
    );
  }

  const { coach, sectionCoverage, summary, tenures } = profileQuery.data;
  const fallbackContext = tenures.find((tenure) => tenure.context)?.context ?? resolvedContext;
  const teamHref = coach.teamId
    ? fallbackContext
      ? appendFilterQueryString(
          buildCanonicalTeamPath(fallbackContext, coach.teamId),
          sharedFilters,
          ["competitionId", "seasonId"],
        )
      : buildTeamResolverPath(coach.teamId, sharedFilters)
    : null;
  const seasonHubHref = fallbackContext
    ? buildSeasonHubTabPath(fallbackContext, "standings", sharedFilters)
    : null;

  return (
    <ProfileShell className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#00513b]" href={coachesHref}>
          Técnicos
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{coach.coachName}</span>
      </div>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.95fr)]">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={profileQuery.coverage} className="bg-white/16 text-white" />
            <ProfileTag className="bg-white/12 text-white/82">Técnico</ProfileTag>
            {coach.active ? <ProfileTag className="bg-white/12 text-white/82">Ativo</ProfileTag> : null}
            {coach.temporary ? <ProfileTag className="bg-white/12 text-white/82">Interino</ProfileTag> : null}
          </div>

          <div className="flex items-start gap-5">
            <CoachAvatar
              coachName={coach.coachName}
              photoUrl={coach.photoUrl}
              hasRealPhoto={coach.hasRealPhoto}
              size="profile"
            />

            <div className="space-y-3">
              <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
                Perfil do técnico
              </p>
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
                {coach.coachName}
              </h1>
              <p className="max-w-3xl text-sm/6 text-white/74">
                {coach.teamName
                  ? `${coach.teamName} • ${formatDateRange(coach.startDate, coach.endDate)}`
                  : "Sem time principal resolvido neste recorte."}
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <ProfileKpi hint="Campanha agregada" invert label="Jogos" value={summary.matches} />
            <ProfileKpi
              hint="Ranking do domínio de técnicos"
              invert
              label="Rendimento"
              value={formatPointsPerMatch(summary.adjustedPpm)}
            />
            <ProfileKpi hint="Passagens no recorte" invert label="Passagens" value={summary.tenureCount} />
            <ProfileKpi hint="Clubes no recorte" invert label="Times" value={summary.teamsCount} />
          </div>
        </ProfilePanel>

        <div className="grid gap-4">
          <ProfilePanel className="space-y-4">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Leitura atual
            </p>
            <dl className="space-y-3 text-sm text-[#1f2d40]">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Campanha</dt>
                <dd className="text-right font-medium">
                  {formatRecord(summary.wins, summary.draws, summary.losses)}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Pontos</dt>
                <dd className="text-right font-medium">{summary.points}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">PPM bruto</dt>
                <dd className="text-right font-medium">{formatPointsPerMatch(summary.pointsPerMatch)}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Passagens ativas</dt>
                <dd className="text-right font-medium">{summary.activeTenures}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Último jogo</dt>
                <dd className="text-right font-medium">{coach.lastMatchDate ?? "-"}</dd>
              </div>
            </dl>
          </ProfilePanel>

          <ProfilePanel className="space-y-3" tone="soft">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Atalhos
            </p>
            <div className="flex flex-wrap gap-2">
              {seasonHubHref ? (
                <Link
                  className="button-pill button-pill-primary"
                  href={seasonHubHref}
                >
                  Abrir temporada
                </Link>
              ) : null}
              {teamHref ? (
                <Link
                  className="button-pill button-pill-secondary"
                  href={teamHref}
                >
                  Abrir time
                </Link>
              ) : null}
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
        coverage={profileQuery.coverage}
        message="Este técnico existe no produto, mas o recorte atual não tem todas as partidas materializadas."
      />

      {summary.matches === 0 ? (
        <ProfileAlert title="Sem partidas no recorte atual" tone="warning">
          O técnico foi encontrado, mas não há partidas materializadas neste contexto para montar
          campanha agregada agora.
        </ProfileAlert>
      ) : null}

      <section className="grid gap-4">
        <ProfilePanel className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                Passagens
              </p>
              <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                Histórico de passagens no recorte
              </h2>
            </div>
            <ProfileCoveragePill coverage={sectionCoverage.tenures} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {tenures.map((tenure) => {
              const tenureContext = tenure.context ?? fallbackContext;
              const tenureTeamHref = tenure.teamId
                ? tenureContext
                  ? appendFilterQueryString(
                      buildCanonicalTeamPath(tenureContext, tenure.teamId),
                      sharedFilters,
                      ["competitionId", "seasonId"],
                    )
                  : buildTeamResolverPath(tenure.teamId, sharedFilters)
                : null;

              return (
                <div
                  className="rounded-[1.35rem] border border-[rgba(191,201,195,0.58)] bg-[rgba(255,255,255,0.78)] p-5"
                  key={tenure.coachTenureId}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                      {tenure.teamName ?? "Time não resolvido"}
                    </h3>
                    {tenure.active ? <ProfileTag>Ativo</ProfileTag> : null}
                    {tenure.temporary ? <ProfileTag>Interino</ProfileTag> : null}
                  </div>

                  <p className="mt-2 text-sm/6 text-[#57657a]">
                    {formatDateRange(tenure.startDate, tenure.endDate)}
                  </p>
                  <p className="mt-1 text-sm/6 text-[#57657a]">
                    {tenure.context
                      ? `${tenure.context.competitionName} ${tenure.context.seasonLabel}`
                      : "Sem contexto canônico resolvido"}
                  </p>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <ProfilePanel className="space-y-1" tone="soft">
                      <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Jogos</p>
                      <p className="text-xl font-extrabold text-[#111c2d]">{tenure.matches}</p>
                    </ProfilePanel>
                    <ProfilePanel className="space-y-1" tone="soft">
                      <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">PPM</p>
                      <p className="text-xl font-extrabold text-[#111c2d]">
                        {formatPointsPerMatch(tenure.pointsPerMatch)}
                      </p>
                    </ProfilePanel>
                    <ProfilePanel className="space-y-1" tone="soft">
                      <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Campanha</p>
                      <p className="text-xl font-extrabold text-[#111c2d]">
                        {formatRecord(tenure.wins, tenure.draws, tenure.losses)}
                      </p>
                    </ProfilePanel>
                    <ProfilePanel className="space-y-1" tone="soft">
                      <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Último jogo</p>
                      <p className="text-xl font-extrabold text-[#111c2d]">
                        {tenure.lastMatchDate ?? "-"}
                      </p>
                    </ProfilePanel>
                  </div>

                  {tenureTeamHref ? (
                    <div className="mt-4">
                      <Link
                        className="button-pill button-pill-primary"
                        href={tenureTeamHref}
                      >
                        Abrir time
                      </Link>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </ProfilePanel>
      </section>
    </ProfileShell>
  );
}
