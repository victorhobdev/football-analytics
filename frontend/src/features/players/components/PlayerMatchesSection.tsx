"use client";

import Link from "next/link";

import { formatMetricValue } from "@/config/metrics.registry";
import type { PlayerMatchStatsPoint, PlayerProfileMeta } from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileCoveragePill,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  buildCanonicalTeamPath,
  buildFilterQueryString,
  buildMatchCenterPath,
  buildMatchesPath,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type PlayerMatchesSectionProps = {
  competitionContext: CompetitionSeasonContext | null;
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
  matches: PlayerMatchStatsPoint[] | undefined;
  profileMeta?: PlayerProfileMeta | null;
};

function formatResultLabel(result: PlayerMatchStatsPoint["result"]): string {
  if (result === "win") {
    return "V";
  }

  if (result === "draw") {
    return "E";
  }

  if (result === "loss") {
    return "D";
  }

  return "-";
}

function getResultTone(result: PlayerMatchStatsPoint["result"]): string {
  if (result === "win") {
    return "bg-[#003526] text-white";
  }

  if (result === "draw") {
    return "bg-[#d8e3fb] text-[#003526]";
  }

  if (result === "loss") {
    return "bg-[#ba1a1a] text-white";
  }

  return "bg-[rgba(240,243,255,0.88)] text-[#57657a]";
}

export function PlayerMatchesSection({
  competitionContext,
  coverage,
  filters,
  matches,
  profileMeta,
}: PlayerMatchesSectionProps) {
  const items = matches ?? [];
  const canonicalExtraQuery = buildFilterQueryString(filters, ["competitionId", "seasonId"]);

  if (items.length === 0) {
    return (
      <div className="space-y-4">
        {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}
        <EmptyState
          title={profileMeta && !profileMeta.hasHistoricalStats ? "Sem partidas consolidadas" : "Partidas indisponíveis"}
          description={
            profileMeta && !profileMeta.hasHistoricalStats
              ? "Este perfil não possui histórico de partidas consolidado para navegação detalhada."
              : "Não há partidas suficientes para montar esta leitura do jogador agora."
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}

      <ProfilePanel className="space-y-4" tone="soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Partidas
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Registro de partidas do jogador
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
              Cada linha mantém a mesma competição e temporada desta visão e abre a central do
              jogo.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={coverage} />
            <Link
              className="button-pill button-pill-primary"
              href={buildMatchesPath(filters)}
            >
              Abrir calendário
            </Link>
          </div>
        </div>
      </ProfilePanel>

      <section className="space-y-3">
        {items.map((match) => {
          const matchId = match.matchId ?? match.fixtureId;
          const opponentHref =
            competitionContext && match.opponentTeamId
              ? `${buildCanonicalTeamPath(competitionContext, match.opponentTeamId)}${canonicalExtraQuery}`
              : null;

          return (
            <ProfilePanel
              className="grid gap-4 xl:grid-cols-[170px_minmax(0,1fr)_auto]"
              key={`${match.fixtureId}-${match.playedAt ?? "nd"}`}
            >
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[#111c2d]">{formatDate(match.playedAt)}</p>
                <p className="text-xs uppercase tracking-[0.16em] text-[#57657a]">
                  {match.competitionName ?? "Competição"} · Rodada {match.roundId ?? "-"}
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold ${getResultTone(match.result)}`}
                  >
                    {formatResultLabel(match.result)}
                  </span>
                  <ProfileTag>
                    {match.venue === "home" ? "Casa" : match.venue === "away" ? "Fora" : "Mando não definido"}
                  </ProfileTag>
                  {match.teamName ? <ProfileTag>{match.teamName}</ProfileTag> : null}
                  {opponentHref ? (
                    <Link
                      className="text-sm font-semibold text-[#003526] transition-colors hover:text-[#00513b] hover:underline"
                      href={opponentHref}
                    >
                      {match.opponentName ?? "Adversário"}
                    </Link>
                  ) : (
                    <ProfileTag>{match.opponentName ?? "Adversário"}</ProfileTag>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-5">
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Min</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {formatMetricValue("minutes_played", match.minutesPlayed)}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Gols</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {formatMetricValue("goals", match.goals)}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Assistências</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {formatMetricValue("assists", match.assists)}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Finalizações</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {formatMetricValue("shots_total", match.shotsTotal)}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Nota</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {formatMetricValue("player_rating", match.rating)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end">
                <Link
                  aria-label={`Abrir central da partida de ${match.teamName ?? "Time"} contra ${match.opponentName ?? "adversário"}`}
                  className="button-pill button-pill-primary"
                  href={buildMatchCenterPath(matchId, {
                    ...filters,
                    competitionId:
                      match.competitionId ?? competitionContext?.competitionId ?? filters.competitionId,
                    seasonId: match.seasonId ?? competitionContext?.seasonId ?? filters.seasonId,
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
    </div>
  );
}
