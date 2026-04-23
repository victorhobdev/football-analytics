"use client";

import Link from "next/link";

import type { TeamMatchListItem } from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  buildCanonicalTeamPath,
  buildMatchCenterPath,
  buildMatchesPath,
  buildFilterQueryString,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

function resolveOpponent(match: TeamMatchListItem, teamId: string) {
  if (match.homeTeamId === teamId) {
    return {
      opponentTeamId: match.awayTeamId,
      opponentName: match.awayTeamName ?? "Visitante",
      venue: "home" as const,
    };
  }

  if (match.awayTeamId === teamId) {
    return {
      opponentTeamId: match.homeTeamId,
      opponentName: match.homeTeamName ?? "Mandante",
      venue: "away" as const,
    };
  }

  return {
    opponentTeamId: null,
    opponentName: `${match.homeTeamName ?? "Mandante"} x ${match.awayTeamName ?? "Visitante"}`,
    venue: null,
  };
}

function formatScore(match: TeamMatchListItem): string {
  const leftScore = typeof match.homeScore === "number" ? String(match.homeScore) : "-";
  const rightScore = typeof match.awayScore === "number" ? String(match.awayScore) : "-";
  return `${leftScore} - ${rightScore}`;
}

type TeamMatchesSectionProps = {
  competitionContext: CompetitionSeasonContext;
  coverage: CoverageState;
  filters: {
    competitionId?: string | null;
    seasonId?: string | null;
    roundId?: string | null;
    venue?: string | null;
    lastN?: number | null;
    dateRangeStart?: string | null;
    dateRangeEnd?: string | null;
  };
  isError: boolean;
  isLoading: boolean;
  matches: TeamMatchListItem[];
  teamId: string;
  errorMessage?: string | null;
};

export function TeamMatchesSection({
  competitionContext,
  coverage,
  filters,
  isError,
  isLoading,
  matches,
  teamId,
  errorMessage,
}: TeamMatchesSectionProps) {
  const canonicalExtraQuery = buildFilterQueryString(filters, ["competitionId", "seasonId"]);

  return (
    <div className="space-y-5">
      <ProfilePanel className="flex flex-wrap items-start justify-between gap-3" tone="soft">
        <div className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Partidas
          </p>
          <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
            Calendário e resultados do clube
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
            Use a aba para seguir da campanha do time até a central do jogo sem perder o contexto
            da temporada.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ProfileCoveragePill coverage={coverage} />
          <Link
            className="button-pill button-pill-primary"
            href={buildMatchesPath({
              ...filters,
              competitionId: competitionContext.competitionId,
              seasonId: competitionContext.seasonId,
            })}
          >
            Abrir lista completa
          </Link>
        </div>
      </ProfilePanel>

      {isLoading ? (
        <div className="space-y-3">
          <LoadingSkeleton height={104} />
          <LoadingSkeleton height={104} />
          <LoadingSkeleton height={104} />
        </div>
      ) : null}

      {isError && matches.length === 0 ? (
        <ProfileAlert title="Falha ao carregar partidas do time" tone="critical">
          <p>{errorMessage ?? "Sem mensagem adicional."}</p>
        </ProfileAlert>
      ) : null}

      {!isLoading && !isError && matches.length === 0 ? (
        <EmptyState
          title="Sem partidas do time"
          description="Ainda não há jogos disponíveis para este time no contexto atual."
        />
      ) : null}

      {matches.length > 0 ? (
        <section className="space-y-3">
          {matches.map((match) => {
            const opponent = resolveOpponent(match, teamId);
            const opponentHref =
              opponent.opponentTeamId && opponent.opponentTeamId.trim().length > 0
                ? `${buildCanonicalTeamPath(competitionContext, opponent.opponentTeamId)}${canonicalExtraQuery}`
                : null;

            return (
              <ProfilePanel
                className="grid gap-4 xl:grid-cols-[170px_minmax(0,1fr)_auto]"
                key={match.matchId}
              >
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-[#111c2d]">{formatDate(match.kickoffAt)}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#57657a]">
                    {match.status ?? "Sem status"} · Rodada {match.roundId ?? "-"}
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <ProfileTag>{match.competitionName ?? competitionContext.competitionName}</ProfileTag>
                    <ProfileTag>{opponent.venue === "home" ? "Casa" : opponent.venue === "away" ? "Fora" : "Mando não definido"}</ProfileTag>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                      {match.homeTeamName ?? "Mandante"} {formatScore(match)} {match.awayTeamName ?? "Visitante"}
                    </h3>
                    {opponentHref ? (
                      <Link
                        className="text-sm font-semibold text-[#003526] transition-colors hover:text-[#00513b] hover:underline"
                        href={opponentHref}
                      >
                        {opponent.opponentName}
                      </Link>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center justify-end">
                  <Link
                    aria-label={`Abrir central da partida de ${match.homeTeamName ?? "Mandante"} x ${match.awayTeamName ?? "Visitante"}`}
                    className="button-pill button-pill-primary"
                    href={buildMatchCenterPath(match.matchId, {
                      ...filters,
                      competitionId: match.competitionId ?? competitionContext.competitionId,
                      seasonId: match.seasonId ?? competitionContext.seasonId,
                      roundId: match.roundId ?? filters.roundId,
                    })}
                  >
                    Abrir central da partida
                  </Link>
                </div>
              </ProfilePanel>
            );
          })}
        </section>
      ) : null}

      {isError && matches.length > 0 ? (
        <ProfileAlert title="Partidas carregadas com alerta" tone="warning">
          <p>{errorMessage ?? "Sem mensagem adicional."}</p>
        </ProfileAlert>
      ) : null}
    </div>
  );
}
