"use client";

import { startTransition, useMemo } from "react";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useTeamMatches } from "@/features/teams/hooks/useTeamMatches";
import { useTeamsList } from "@/features/teams/hooks/useTeamsList";
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
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildCanonicalTeamPath,
  buildFilterQueryString,
  buildMatchCenterPath,
  buildMatchesPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

function getTeamMonogram(teamName: string): string {
  const initials = teamName
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "TIM";
}

function resolveMatchTimestamp(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }

  const parsedDate = new Date(value);
  return Number.isNaN(parsedDate.getTime()) ? 0 : parsedDate.getTime();
}

function normalizeTeamId(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const normalizedValue = value.trim();
  return normalizedValue.length > 0 ? normalizedValue : null;
}

function resolveScore(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

type ComparisonMatch = {
  awayTeamName: string;
  awayTeamId: string | null;
  homeTeamName: string;
  homeTeamId: string | null;
  kickoffAt?: string | null;
  matchId: string;
  resultForTeamA: "win" | "draw" | "loss";
  scoreLine: string;
  teamAGoals: number;
  teamBGoals: number;
  venueForTeamA: "home" | "away";
};

function buildComparisonMatches(
  teamAId: string,
  teamBId: string,
  matches: Array<{
    awayScore?: number | null;
    awayTeamId?: string | null;
    awayTeamName?: string | null;
    homeScore?: number | null;
    homeTeamId?: string | null;
    homeTeamName?: string | null;
    kickoffAt?: string | null;
    matchId: string;
  }>,
): ComparisonMatch[] {
  return matches
    .filter(
      (match) =>
        (match.homeTeamId === teamAId && match.awayTeamId === teamBId) ||
        (match.homeTeamId === teamBId && match.awayTeamId === teamAId),
    )
    .map((match) => {
      const teamAIsHome = match.homeTeamId === teamAId;
      const teamAGoals = teamAIsHome ? resolveScore(match.homeScore) : resolveScore(match.awayScore);
      const teamBGoals = teamAIsHome ? resolveScore(match.awayScore) : resolveScore(match.homeScore);
      const resultForTeamA: ComparisonMatch["resultForTeamA"] =
        teamAGoals > teamBGoals ? "win" : teamAGoals < teamBGoals ? "loss" : "draw";
      const venueForTeamA: ComparisonMatch["venueForTeamA"] = teamAIsHome ? "home" : "away";

      return {
        awayTeamName: match.awayTeamName ?? "Visitante",
        awayTeamId: normalizeTeamId(match.awayTeamId),
        homeTeamName: match.homeTeamName ?? "Mandante",
        homeTeamId: normalizeTeamId(match.homeTeamId),
        kickoffAt: match.kickoffAt,
        matchId: match.matchId,
        resultForTeamA,
        scoreLine: `${resolveScore(match.homeScore)} - ${resolveScore(match.awayScore)}`,
        teamAGoals,
        teamBGoals,
        venueForTeamA,
      };
    })
    .sort((left, right) => resolveMatchTimestamp(right.kickoffAt) - resolveMatchTimestamp(left.kickoffAt));
}

function formatResultPill(result: ComparisonMatch["resultForTeamA"]): string {
  if (result === "win") {
    return "V";
  }

  if (result === "loss") {
    return "D";
  }

  return "E";
}

function getResultClasses(result: ComparisonMatch["resultForTeamA"]): string {
  if (result === "win") {
    return "bg-[#003526] text-white";
  }

  if (result === "loss") {
    return "bg-[#ba1a1a] text-white";
  }

  return "bg-[rgba(216,227,251,0.82)] text-[#1f2d40]";
}

export function HeadToHeadPageContent() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const resolvedContext = useResolvedCompetitionContext();
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const selectedTeamAId = normalizeTeamId(searchParams.get("teamA"));
  const selectedTeamBId = normalizeTeamId(searchParams.get("teamB"));
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
  const canonicalExtraQuery = useMemo(
    () => buildFilterQueryString(sharedFilters, ["competitionId", "seasonId"]),
    [sharedFilters],
  );
  const teamsQuery = useTeamsList(
    {
      pageSize: 64,
      sortBy: "points",
      sortDirection: "desc",
    },
    resolvedContext,
  );
  const matchesQuery = useTeamMatches(selectedTeamAId, resolvedContext, {
    pageSize: 100,
    sortBy: "kickoffAt",
    sortDirection: "desc",
  });

  const selectedTeamA = useMemo(
    () => teamsQuery.data?.items.find((team) => team.teamId === selectedTeamAId) ?? null,
    [selectedTeamAId, teamsQuery.data?.items],
  );
  const selectedTeamB = useMemo(
    () => teamsQuery.data?.items.find((team) => team.teamId === selectedTeamBId) ?? null,
    [selectedTeamBId, teamsQuery.data?.items],
  );
  const comparisonMatches = useMemo(
    () =>
      selectedTeamAId && selectedTeamBId
        ? buildComparisonMatches(selectedTeamAId, selectedTeamBId, matchesQuery.data?.items ?? [])
        : [],
    [matchesQuery.data?.items, selectedTeamAId, selectedTeamBId],
  );

  const comparisonSummary = useMemo(() => {
    return comparisonMatches.reduce(
      (summary, match) => {
        summary.total += 1;
        summary.teamAGoals += match.teamAGoals;
        summary.teamBGoals += match.teamBGoals;

        if (match.resultForTeamA === "win") {
          summary.teamAWins += 1;
        } else if (match.resultForTeamA === "loss") {
          summary.teamBWins += 1;
        } else {
          summary.draws += 1;
        }

        if (match.venueForTeamA === "home") {
          summary.homeMatches += 1;
        } else {
          summary.awayMatches += 1;
        }

        return summary;
      },
      {
        awayMatches: 0,
        draws: 0,
        homeMatches: 0,
        teamAGoals: 0,
        teamAWins: 0,
        teamBGoals: 0,
        teamBWins: 0,
        total: 0,
      },
    );
  }, [comparisonMatches]);

  const updateSelection = (nextTeamA: string | null, nextTeamB: string | null) => {
    const nextSearchParams = new URLSearchParams(searchParams.toString());

    if (nextTeamA) {
      nextSearchParams.set("teamA", nextTeamA);
    } else {
      nextSearchParams.delete("teamA");
    }

    if (nextTeamB) {
      nextSearchParams.set("teamB", nextTeamB);
    } else {
      nextSearchParams.delete("teamB");
    }

    const serialized = nextSearchParams.toString();

    startTransition(() => {
      router.replace(serialized.length > 0 ? `${pathname}?${serialized}` : pathname, {
        scroll: false,
      });
    });
  };

  if (!resolvedContext) {
    return (
      <ProfileShell className="space-y-6">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/12 text-white/82">Confronto direto</ProfileTag>
              <ProfileTag className="bg-white/12 text-white/82">Contexto obrigatório</ProfileTag>
            </div>
            <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              Selecione competição e temporada antes de comparar
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/74">
              O comparativo direto opera no mesmo recorte canônico usado por partidas, rankings e
              perfis de time. Defina primeiro a temporada para montar o confronto com segurança.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              className="button-pill button-pill-inverse"
              href="/competitions"
            >
              Abrir competições
            </Link>
            <Link
              className="button-pill button-pill-on-dark"
              href={buildTeamsPath(sharedFilters)}
            >
              Abrir times
            </Link>
          </div>
        </ProfilePanel>
      </ProfileShell>
    );
  }

  const teams = teamsQuery.data?.items ?? [];
  const hasComparisonSelection = Boolean(selectedTeamAId && selectedTeamBId);
  const isSameTeamSelected = selectedTeamAId !== null && selectedTeamAId === selectedTeamBId;

  return (
    <ProfileShell className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.95fr)]">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileTag className="bg-white/12 text-white/82">Confronto direto</ProfileTag>
            <ProfileTag className="bg-white/12 text-white/82">{resolvedContext.competitionName}</ProfileTag>
            <ProfileTag className="bg-white/12 text-white/82">{resolvedContext.seasonLabel}</ProfileTag>
            <ProfileCoveragePill
              className="bg-white/12 text-white"
              coverage={matchesQuery.coverage}
            />
          </div>

          <div className="space-y-3">
            <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
              Comparativo direto
            </p>
            <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {selectedTeamA?.teamName && selectedTeamB?.teamName
                ? `${selectedTeamA.teamName} x ${selectedTeamB.teamName}`
                : "Compare dois times no mesmo recorte"}
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/74">
              A leitura usa os confrontos já disponíveis no calendário do recorte atual e leva
              direto para a central da partida e os perfis canônicos de cada time.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <ProfileKpi
              hint="Confrontos encontrados"
              invert
              label="Partidas"
              value={comparisonSummary.total}
            />
            <ProfileKpi
              hint={selectedTeamA?.teamName ?? "Time A"}
              invert
              label="Vitórias A"
              value={comparisonSummary.teamAWins}
            />
            <ProfileKpi
              hint={selectedTeamB?.teamName ?? "Time B"}
              invert
              label="Vitórias B"
              value={comparisonSummary.teamBWins}
            />
            <ProfileKpi hint="Sem vencedor" invert label="Empates" value={comparisonSummary.draws} />
          </div>
        </ProfilePanel>

        <ProfilePanel className="space-y-4">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Seleção do confronto
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Escolha os dois times
            </h2>
          </div>

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Time A
            <select
              className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-white/92 px-4 py-3 text-sm text-[#111c2d] outline-none transition-colors focus:border-[#003526] focus:ring-2 focus:ring-[#003526]"
              onChange={(event) => {
                updateSelection(normalizeTeamId(event.target.value), selectedTeamBId);
              }}
              value={selectedTeamAId ?? ""}
            >
              <option value="">Selecione o primeiro time</option>
              {teams.map((team) => (
                <option key={`team-a-${team.teamId}`} value={team.teamId}>
                  {team.teamName}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 text-sm text-[#1f2d40]">
            Time B
            <select
              className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-white/92 px-4 py-3 text-sm text-[#111c2d] outline-none transition-colors focus:border-[#003526] focus:ring-2 focus:ring-[#003526]"
              onChange={(event) => {
                updateSelection(selectedTeamAId, normalizeTeamId(event.target.value));
              }}
              value={selectedTeamBId ?? ""}
            >
              <option value="">Selecione o segundo time</option>
              {teams.map((team) => (
                <option key={`team-b-${team.teamId}`} value={team.teamId}>
                  {team.teamName}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-wrap gap-2">
            <Link
              className="button-pill button-pill-soft"
              href={buildTeamsPath(sharedFilters)}
            >
              Abrir times
            </Link>
            <Link
              className="button-pill button-pill-soft"
              href={buildMatchesPath(sharedFilters)}
            >
              Abrir partidas
            </Link>
          </div>
        </ProfilePanel>
      </section>

      {teamsQuery.isLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={104} />
          <LoadingSkeleton height={104} />
        </div>
      ) : null}

      {teamsQuery.isError ? (
        <ProfileAlert title="Falha ao carregar times para comparação" tone="critical">
          <p>{teamsQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {!teamsQuery.isLoading && !teamsQuery.isError && teams.length === 0 ? (
        <EmptyState
          title="Sem times para comparar"
          description="O recorte atual não retornou times suficientes para montar o comparativo."
        />
      ) : null}

      {isSameTeamSelected ? (
        <ProfileAlert title="Seleção inválida" tone="warning">
          <p>Escolha dois times diferentes para montar o comparativo direto.</p>
        </ProfileAlert>
      ) : null}

      {!hasComparisonSelection ? (
        <EmptyState
          title="Selecione dois times"
          description="Use os seletores acima para comparar confrontos diretos no contexto atual."
        />
      ) : null}

      {hasComparisonSelection && matchesQuery.isLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={140} />
          <LoadingSkeleton height={140} />
          <LoadingSkeleton height={140} />
        </div>
      ) : null}

      {hasComparisonSelection && !isSameTeamSelected && matchesQuery.isError ? (
        <ProfileAlert title="Falha ao carregar confrontos" tone="critical">
          <p>{matchesQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {hasComparisonSelection &&
      !isSameTeamSelected &&
      !matchesQuery.isLoading &&
      !matchesQuery.isError &&
      comparisonMatches.length === 0 ? (
        <EmptyState
          title="Sem confrontos no recorte atual"
          description="Nenhuma partida entre esses dois times foi encontrada na competição, temporada e janela selecionadas."
        />
      ) : null}

      {comparisonMatches.length > 0 ? (
        <>
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <ProfilePanel className="space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                    Leitura consolidada
                  </p>
                  <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    Saldo do confronto
                  </h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedTeamA ? (
                    <Link
                      className="button-pill button-pill-soft gap-2"
                      href={`${buildCanonicalTeamPath(resolvedContext, selectedTeamA.teamId)}${canonicalExtraQuery}`}
                    >
                      <ProfileMedia
                        alt={selectedTeamA.teamName}
                        assetId={selectedTeamA.teamId}
                        category="clubs"
                        className="h-7 w-7 border-0 bg-transparent"
                        fallback={getTeamMonogram(selectedTeamA.teamName)}
                        fallbackClassName="text-[0.62rem]"
                        imageClassName="p-1"
                        shape="circle"
                      />
                      {selectedTeamA.teamName}
                    </Link>
                  ) : null}
                  {selectedTeamB ? (
                    <Link
                      className="button-pill button-pill-soft gap-2"
                      href={`${buildCanonicalTeamPath(resolvedContext, selectedTeamB.teamId)}${canonicalExtraQuery}`}
                    >
                      <ProfileMedia
                        alt={selectedTeamB.teamName}
                        assetId={selectedTeamB.teamId}
                        category="clubs"
                        className="h-7 w-7 border-0 bg-transparent"
                        fallback={getTeamMonogram(selectedTeamB.teamName)}
                        fallbackClassName="text-[0.62rem]"
                        imageClassName="p-1"
                        shape="circle"
                      />
                      {selectedTeamB.teamName}
                    </Link>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-4">
                <ProfileMetricTile
                  label={`${selectedTeamA?.teamName ?? "Time A"} gols`}
                  value={comparisonSummary.teamAGoals}
                />
                <ProfileMetricTile
                  label={`${selectedTeamB?.teamName ?? "Time B"} gols`}
                  value={comparisonSummary.teamBGoals}
                />
                <ProfileMetricTile label="Casa do time A" value={comparisonSummary.homeMatches} />
                <ProfileMetricTile label="Fora do time A" value={comparisonSummary.awayMatches} />
              </div>

              <div className="space-y-3">
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                  Sequência recente do time A
                </p>
                <div className="flex flex-wrap gap-2">
                  {comparisonMatches.slice(0, 6).map((match) => (
                    <span
                      className={`inline-flex h-11 w-11 items-center justify-center rounded-full text-sm font-bold ${getResultClasses(match.resultForTeamA)}`}
                      key={`h2h-result-${match.matchId}`}
                    >
                      {formatResultPill(match.resultForTeamA)}
                    </span>
                  ))}
                </div>
              </div>
            </ProfilePanel>

            <ProfilePanel className="space-y-5" tone="soft">
              <div>
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                  Contexto ativo
                </p>
                <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                  Como ler este comparativo
                </h2>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <ProfileMetricTile label="Competição" value={resolvedContext.competitionName} tone="soft" />
                <ProfileMetricTile label="Temporada" value={resolvedContext.seasonLabel} tone="soft" />
                <ProfileMetricTile label="Mando" value={venue === "all" ? "Todos" : venue === "home" ? "Casa" : "Fora"} tone="soft" />
                <ProfileMetricTile
                  label="Janela"
                  value={typeof lastN === "number" ? `Últimas ${lastN}` : dateRangeStart || dateRangeEnd ? "Personalizada" : roundId ? `Rodada ${roundId}` : "Temporada"}
                  tone="soft"
                />
              </div>

              <p className="text-sm/6 text-[#57657a]">
                O comparativo usa as partidas já disponíveis neste recorte. Se você trocar competição,
                temporada ou janela global, o confronto é recalculado com a mesma política do produto.
              </p>
            </ProfilePanel>
          </section>

          <section className="space-y-3">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
                  Partidas do confronto
                </p>
                <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                  Histórico dentro do recorte atual
                </h2>
              </div>
              <Link
                className="button-pill button-pill-primary"
                href={buildMatchesPath({
                  ...sharedFilters,
                  competitionId: resolvedContext.competitionId,
                  seasonId: resolvedContext.seasonId,
                })}
              >
                Abrir calendário
              </Link>
            </div>

            {comparisonMatches.map((match) => (
              <ProfilePanel
                className="grid gap-4 xl:grid-cols-[180px_minmax(0,1fr)_auto]"
                key={match.matchId}
              >
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-[#111c2d]">{formatDate(match.kickoffAt)}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#57657a]">
                    {match.venueForTeamA === "home" ? "Time A em casa" : "Time A fora"}
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] ${getResultClasses(match.resultForTeamA)}`}
                    >
                      {formatResultPill(match.resultForTeamA)}
                    </span>
                    <ProfileTag>{resolvedContext.competitionName}</ProfileTag>
                    <ProfileTag>{resolvedContext.seasonLabel}</ProfileTag>
                  </div>
                  <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {match.homeTeamName} {match.scoreLine} {match.awayTeamName}
                  </h3>
                </div>

                <div className="flex items-center justify-end">
                  <Link
                    className="button-pill button-pill-primary"
                    href={buildMatchCenterPath(match.matchId, {
                      ...sharedFilters,
                      competitionId: resolvedContext.competitionId,
                      seasonId: resolvedContext.seasonId,
                    })}
                  >
                    Abrir central da partida
                  </Link>
                </div>
              </ProfilePanel>
            ))}
          </section>
        </>
      ) : null}
    </ProfileShell>
  );
}
