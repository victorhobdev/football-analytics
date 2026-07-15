"use client";

import type { TeamProfileStats } from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileMetricTile,
  ProfilePanel,
} from "@/shared/components/profile/ProfilePrimitives";

type TeamStatsSectionProps = {
  stats: TeamProfileStats | null | undefined;
};

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value.toFixed(2);
}

function formatPercentage(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return `${Math.round(value)}%`;
}

export function TeamStatsSection({ stats }: TeamStatsSectionProps) {
  const trend = stats?.trend ?? [];
  const hasStats =
    stats &&
    (typeof stats.pointsPerMatch === "number" ||
      typeof stats.winRatePct === "number" ||
      typeof stats.goalsForPerMatch === "number" ||
      typeof stats.goalsAgainstPerMatch === "number" ||
      trend.length > 0);

  if (!hasStats) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="Estatísticas indisponíveis"
          description="As métricas agregadas do time ainda não estão disponíveis neste contexto."
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <ProfilePanel className="space-y-4" tone="soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Estatísticas
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Tendência e métricas agregadas
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
              A seção resume produção por jogo e a evolução mensal da campanha.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <ProfileMetricTile label="Pontos por jogo" value={formatDecimal(stats?.pointsPerMatch)} />
          <ProfileMetricTile label="Taxa de vitórias" value={formatPercentage(stats?.winRatePct)} />
          <ProfileMetricTile label="Gols pró / jogo" value={formatDecimal(stats?.goalsForPerMatch)} />
          <ProfileMetricTile label="Gols contra / jogo" value={formatDecimal(stats?.goalsAgainstPerMatch)} />
          <ProfileMetricTile label="Jogos sem sofrer gol" value={stats?.cleanSheets ?? "-"} />
          <ProfileMetricTile label="Sem marcar" value={stats?.failedToScore ?? "-"} />
        </div>
      </ProfilePanel>

      <section className="space-y-3">
        {trend.map((point) => (
          <ProfilePanel className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)]" key={point.periodKey ?? point.label}>
            <div className="space-y-2">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                Janela mensal
              </p>
              <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                {point.label ?? point.periodKey ?? "Período"}
              </h3>
              <p className="text-sm text-[#57657a]">{point.matches ?? 0} partidas consolidadas</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-4">
              <ProfileMetricTile label="Pontos" value={point.points ?? "-"} tone="soft" />
              <ProfileMetricTile label="V-E-D" value={`${point.wins ?? 0}-${point.draws ?? 0}-${point.losses ?? 0}`} tone="soft" />
              <ProfileMetricTile label="Gols" value={`${point.goalsFor ?? 0} / ${point.goalsAgainst ?? 0}`} tone="soft" />
              <ProfileMetricTile label="Saldo" value={point.goalDiff ?? "-"} tone="soft" />
            </div>
          </ProfilePanel>
        ))}
      </section>
    </div>
  );
}
