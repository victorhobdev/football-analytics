"use client";

import type { PlayerProfileMeta, PlayerProfileStats, PlayerStatsSummary } from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileCoveragePill,
  ProfileMetricTile,
  ProfilePanel,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CoverageState } from "@/shared/types/coverage.types";

type PlayerStatsSectionProps = {
  coverage: CoverageState;
  profileMeta?: PlayerProfileMeta | null;
  stats: PlayerProfileStats | null | undefined;
  summary: PlayerStatsSummary;
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

export function PlayerStatsSection({
  coverage,
  profileMeta,
  stats,
  summary,
}: PlayerStatsSectionProps) {
  const trend = stats?.trend ?? [];
  const hasStats =
    typeof stats?.goalsPer90 === "number" ||
    typeof stats?.assistsPer90 === "number" ||
    typeof stats?.goalContributionsPer90 === "number" ||
    typeof summary.rating === "number" ||
    trend.length > 0;

  if (!hasStats) {
    return (
      <div className="space-y-4">
        {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}
        <EmptyState
          title={profileMeta && !profileMeta.hasHistoricalStats ? "Sem histórico estatístico" : "Estatísticas indisponíveis"}
          description={
            profileMeta && !profileMeta.hasHistoricalStats
              ? "Este perfil segue válido, mas não possui histórico estatístico consolidado para esta seção."
              : "Não há métricas suficientes para montar esta leitura do jogador agora."
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
              Estatísticas
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Produção agregada e tendência
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
              Métricas por 90 minutos e leitura mensal consolidada da temporada selecionada.
            </p>
          </div>
          <ProfileCoveragePill coverage={coverage} />
        </div>

        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <ProfileMetricTile label="Gols/90" value={formatDecimal(stats?.goalsPer90)} />
          <ProfileMetricTile label="Assistências/90" value={formatDecimal(stats?.assistsPer90)} />
          <ProfileMetricTile
            label="Contribuições/90"
            value={formatDecimal(stats?.goalContributionsPer90)}
          />
          <ProfileMetricTile label="Finalizações/90" value={formatDecimal(stats?.shotsPer90)} />
          <ProfileMetricTile label="No alvo (%)" value={formatPercentage(stats?.shotsOnTargetPct)} />
          <ProfileMetricTile
            label="Nota"
            value={typeof summary.rating === "number" ? summary.rating.toFixed(2) : "-"}
          />
        </div>
      </ProfilePanel>

      <section className="space-y-3">
        {trend.map((point) => (
          <ProfilePanel
            className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)]"
            key={point.periodKey ?? point.label}
          >
            <div className="space-y-2">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                Janela mensal
              </p>
              <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                {point.label ?? point.periodKey ?? "Período"}
              </h3>
              <p className="text-sm text-[#57657a]">{point.matchesPlayed ?? 0} partidas consolidadas</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-4">
              <ProfileMetricTile label="Minutos" value={point.minutesPlayed ?? "-"} tone="soft" />
              <ProfileMetricTile label="Gols + assistências" value={`${point.goals ?? 0} + ${point.assists ?? 0}`} tone="soft" />
              <ProfileMetricTile label="Finalizações" value={point.shotsTotal ?? "-"} tone="soft" />
              <ProfileMetricTile
                label="Nota"
                value={typeof point.rating === "number" ? point.rating.toFixed(2) : "-"}
                tone="soft"
              />
            </div>
          </ProfilePanel>
        ))}
      </section>
    </div>
  );
}
