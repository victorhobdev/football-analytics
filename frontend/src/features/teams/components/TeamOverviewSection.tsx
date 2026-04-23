"use client";

import Link from "next/link";

import type { TeamProfile } from "@/features/teams/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import {
  ProfileCoveragePill,
  ProfileKpi,
  ProfileMetricTile,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CoverageState } from "@/shared/types/coverage.types";
import { formatDate } from "@/shared/utils/formatters";

function formatPercentage(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return `${Math.round(value)}%`;
}

function formatGoalDiff(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value > 0 ? `+${value}` : String(value);
}

function formatResultLabel(result: string | null | undefined): string {
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

function getFormTone(result: string) {
  if (result === "V") {
    return "bg-[#003526] text-white";
  }

  if (result === "E") {
    return "bg-[#d8e3fb] text-[#003526]";
  }

  if (result === "D") {
    return "bg-[#ba1a1a] text-white";
  }

  return "bg-[#d8e3fb] text-[#404944]";
}

type TeamOverviewSectionProps = {
  coverage: CoverageState;
  matchesHref: string;
  profile: TeamProfile;
  rankingsHref: string | null;
  seasonHubHref: string | null;
};

export function TeamOverviewSection({
  coverage,
  matchesHref,
  profile,
  rankingsHref,
  seasonHubHref,
}: TeamOverviewSectionProps) {
  const { team, summary, standing, form, recentMatches } = profile;
  const latestMatch = recentMatches?.[0] ?? null;
  const winRate =
    summary.matchesPlayed && summary.matchesPlayed > 0 && typeof summary.wins === "number"
      ? (summary.wins / summary.matchesPlayed) * 100
      : null;
  const pointsPerMatch =
    summary.matchesPlayed && summary.matchesPlayed > 0 && typeof summary.points === "number"
      ? (summary.points / summary.matchesPlayed).toFixed(2)
      : "-";

  return (
    <div className="space-y-6">
      {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <ProfilePanel className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ProfileCoveragePill coverage={coverage} />
                <ProfileTag>{team.competitionName ?? "Competição"}</ProfileTag>
                <ProfileTag>{team.seasonLabel ?? "Temporada"}</ProfileTag>
              </div>
              <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
                Resumo competitivo
              </h2>
              <p className="text-sm leading-6 text-[#57657a]">
                Posição, forma recente e produção agregada do time nesta temporada.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {seasonHubHref ? (
                <Link
                  className="button-pill button-pill-soft"
                  href={seasonHubHref}
                >
                  Temporada
                </Link>
              ) : null}
              {rankingsHref ? (
                <Link
                  className="button-pill button-pill-soft"
                  href={rankingsHref}
                >
                  Rankings
                </Link>
              ) : null}
              <Link
                className="button-pill button-pill-primary"
                href={matchesHref}
              >
                Ver partidas do time
              </Link>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ProfileKpi label="Posição" value={standing?.position ? `${standing.position}º` : "-"} hint={standing?.totalTeams ? `de ${standing.totalTeams}` : "Sem tabela"} />
            <ProfileKpi label="Pontos" value={summary.points ?? "-"} hint={`Pontos por jogo ${pointsPerMatch}`} />
            <ProfileKpi label="Vitórias" value={summary.wins ?? "-"} hint={`Taxa ${formatPercentage(winRate)}`} />
            <ProfileKpi label="Saldo" value={formatGoalDiff(summary.goalDiff)} hint={`${summary.goalsFor ?? "-"} pró / ${summary.goalsAgainst ?? "-"} contra`} />
          </div>

          <div className="space-y-3">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Forma recente
            </p>
            <div className="flex flex-wrap gap-3">
              {(form ?? []).length > 0 ? (
                form!.map((result, index) => {
                  const label = formatResultLabel(result);
                  return (
                    <span
                      className={`inline-flex h-11 w-11 items-center justify-center rounded-full text-sm font-bold ${getFormTone(label)}`}
                      key={`${result}-${index}`}
                    >
                      {label}
                    </span>
                  );
                })
              ) : (
                <p className="text-sm text-[#57657a]">Ainda não há sequência recente suficiente para este time.</p>
              )}
            </div>
          </div>
        </ProfilePanel>

        <ProfilePanel className="space-y-5" tone="accent">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
              Última partida consolidada
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-white">
              {latestMatch?.opponentName ?? "Sem adversário"}
            </h2>
            <p className="text-sm leading-6 text-white/75">
              {latestMatch
                ? `${formatDate(latestMatch.playedAt)} · ${latestMatch.venue === "home" ? "Casa" : "Fora"}`
                : "A última partida consolidada ainda não está disponível."}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <ProfileMetricTile label="Jogos" value={summary.matchesPlayed ?? "-"} />
            <ProfileMetricTile label="Empates" value={summary.draws ?? "-"} />
            <ProfileMetricTile label="Derrotas" value={summary.losses ?? "-"} />
            <ProfileMetricTile label="Resultado" value={latestMatch ? `${latestMatch.goalsFor ?? "-"} - ${latestMatch.goalsAgainst ?? "-"}` : "-"} />
          </div>
        </ProfilePanel>
      </section>
    </div>
  );
}
