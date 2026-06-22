"use client";

import { useAnalyticsOverview } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
} from "@/features/analytics/components/AnalyticsPrimitives";
import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return INTEGER_FORMATTER.format(value);
}

function formatAvgGoals(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return DECIMAL_FORMATTER.format(value);
}

function formatRate(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${DECIMAL_FORMATTER.format(value)}%`;
}

export function AnalyticsOverviewTab() {
  const query = useAnalyticsOverview();

  if (query.isLoading && !query.data) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton height={32} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <LoadingSkeleton height={96} />
          <LoadingSkeleton height={96} />
          <LoadingSkeleton height={96} />
          <LoadingSkeleton height={96} />
          <LoadingSkeleton height={96} />
          <LoadingSkeleton height={96} />
        </div>
      </div>
    );
  }

  if (query.isError && !query.data) {
    return (
      <EmptyState
        title="Falha ao carregar visão geral"
        description={query.error?.message ?? "Erro desconhecido"}
      />
    );
  }

  if (!query.data || query.isEmpty) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="Nenhum dado disponível"
          description="Selecione um escopo com dados para visualizar a visão geral."
        />
        {query.coverage ? (
          <CoverageBadge coverage={query.coverage} />
        ) : null}
      </div>
    );
  }

  const overview = query.data;
  const summary = overview.summary;

  return (
    <div className="space-y-6">
      <AnalyticsPanel className="space-y-5">
        <AnalyticsSectionHeader
          eyebrow="Visão geral"
          title="Resumo executivo do recorte"
          description="Indicadores consolidados para validar rapidamente volume, resultado e entidades disponíveis."
          aside={query.coverage ? <CoverageBadge coverage={query.coverage} /> : null}
        />

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <AnalyticsKpi label="Partidas" value={formatInteger(summary.totalMatches)} tone="accent" />
          <AnalyticsKpi label="Gols" value={formatInteger(summary.totalGoals)} />
          <AnalyticsKpi label="Média" value={formatAvgGoals(summary.avgGoalsPerMatch)} hint="gols por partida" />
          <AnalyticsKpi label="Times" value={formatInteger(summary.totalTeams)} tone="soft" />
          <AnalyticsKpi label="Técnicos" value={formatInteger(summary.totalCoaches)} tone="soft" />
          <AnalyticsKpi label="Jogadores" value={formatInteger(summary.totalPlayers)} tone="soft" />
        </div>
      </AnalyticsPanel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <AnalyticsPanel className="space-y-4">
          <AnalyticsSectionHeader
            eyebrow="Resultado"
            title="Distribuição mandante/visitante"
            description="Leitura agregada do comportamento de resultado no escopo filtrado."
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <AnalyticsKpi label="Mandante" value={formatInteger(summary.homeWins)} hint={formatRate(summary.homeWinRate)} />
            <AnalyticsKpi label="Empates" value={formatInteger(summary.draws)} hint={formatRate(summary.drawRate)} />
            <AnalyticsKpi label="Visitante" value={formatInteger(summary.awayWins)} hint={formatRate(summary.awayWinRate)} />
          </div>
        </AnalyticsPanel>

        <AnalyticsPanel className="space-y-4">
          <AnalyticsSectionHeader
            eyebrow="Derivados"
            title="Destaques do agregado"
            description="Superlativos simples calculados sobre o mesmo recorte analítico."
          />
          <div className="grid gap-3 md:grid-cols-2">
            {overview.topScorerTeam ? (
              <AnalyticsKpi
                label="Melhor ataque"
                value={overview.topScorerTeam.teamName}
                hint={`${formatInteger(overview.topScorerTeam.goalsFor)} gols`}
              />
            ) : null}
            {overview.bestDefenseTeam ? (
              <AnalyticsKpi
                label="Melhor defesa"
                value={overview.bestDefenseTeam.teamName}
                hint={`${formatInteger(overview.bestDefenseTeam.goalsAgainst)} gols sofridos`}
              />
            ) : null}
            {overview.bestPpmCoach ? (
              <AnalyticsKpi
                label="Técnico PPM"
                value={overview.bestPpmCoach.coachName}
                hint={`${formatAvgGoals(overview.bestPpmCoach.pointsPerMatch)} PPM em ${formatInteger(overview.bestPpmCoach.matches)} jogos`}
              />
            ) : null}
          </div>
        </AnalyticsPanel>
      </div>

      {query.isError ? (
        <p className="text-sm text-red-600">
          {query.error?.message ?? "Erro ao carregar dados adicionais."}
        </p>
      ) : null}
    </div>
  );
}
