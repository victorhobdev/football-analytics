"use client";

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { useAnalyticsTrends } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
  AnalyticsSelect,
} from "@/features/analytics/components/AnalyticsPrimitives";
import { LineChart } from "@/shared/components/charts/LineChart";
import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";
import { DataTable } from "@/shared/components/data-display/DataTable";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";

const METRIC_OPTIONS = [
  { label: "Partidas", value: "matches" },
  { label: "Gols", value: "goals" },
  { label: "Média de Gols", value: "avg_goals" },
  { label: "Vitórias Casa", value: "home_wins" },
  { label: "Vitórias Fora", value: "away_wins" },
  { label: "Empates", value: "draws" },
  { label: "Pontos", value: "points" },
  { label: "Gols Pró", value: "goals_for" },
  { label: "Gols Contra", value: "goals_against" },
  { label: "Saldo de Gols", value: "goal_diff" },
] as const;

const PERIOD_OPTIONS = [
  { label: "Rodada", value: "round" },
  { label: "Mês", value: "month" },
] as const;

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DIRECTION_LABEL: Record<string, string> = {
  up: "Alta",
  down: "Queda",
  stable: "Estável",
};

export function AnalyticsTrendsTab() {
  const [metric, setMetric] = useState("goals");
  const [periodType, setPeriodType] = useState<"round" | "month">("round");

  const query = useAnalyticsTrends({ metric, periodType });

  const columns = useMemo<Array<ColumnDef<{ periodLabel: string; value: number; sampleSize: number }>>>(
    () => [
      { accessorKey: "periodLabel", header: "Período" },
      { accessorKey: "value", header: "Valor" },
      { accessorKey: "sampleSize", header: "Amostra" },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <AnalyticsPanel className="space-y-4">
        <AnalyticsSectionHeader
          eyebrow="Tendências"
          title="Série temporal do recorte"
          description="Escolha uma métrica e uma granularidade para observar evolução, amostra e direção geral."
          aside={query.coverage ? <CoverageBadge coverage={query.coverage} /> : null}
        />
        <div className="flex flex-wrap gap-3">
          <AnalyticsSelect
            label="Métrica"
            onChange={setMetric}
            options={METRIC_OPTIONS.map((option) => ({ ...option }))}
            value={metric}
          />
          <AnalyticsSelect
            label="Período"
            onChange={(value) => setPeriodType(value as "round" | "month")}
            options={PERIOD_OPTIONS.map((option) => ({ ...option }))}
            value={periodType}
          />
        </div>
      </AnalyticsPanel>

      {query.isLoading && !query.data ? (
        <AnalyticsPanel className="space-y-2">
          <LoadingSkeleton height={200} />
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
        </AnalyticsPanel>
      ) : query.isError && !query.data ? (
        <EmptyState
          title="Falha ao carregar tendências"
          description={query.error?.message ?? "Erro desconhecido"}
        />
      ) : !query.data || query.isEmpty ? (
        <EmptyState
          title="Nenhuma tendência disponível"
          description="Selecione um escopo com dados ou altere a métrica/período."
        />
      ) : (() => {
        const trends = query.data!;
        const chartData = trends.series.map((point) => ({
          periodLabel: point.periodLabel,
          value: point.value,
        }));

        return (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <AnalyticsKpi label="Períodos" value={INTEGER_FORMATTER.format(trends.series.length)} />
              <AnalyticsKpi
                label="Amostra"
                value={INTEGER_FORMATTER.format(trends.series.reduce((total, point) => total + point.sampleSize, 0))}
                tone="soft"
              />
              <AnalyticsKpi
                label="Direção"
                value={trends.trendDirection ? DIRECTION_LABEL[trends.trendDirection] ?? trends.trendDirection : "-"}
                hint={`mínimo ${trends.minPeriodsRequired} períodos`}
                tone="soft"
              />
            </div>

            {chartData.length > 0 ? (
              <AnalyticsPanel>
                <LineChart
                  data={chartData}
                  xKey="periodLabel"
                  lines={[{ dataKey: "value", label: METRIC_OPTIONS.find((o) => o.value === trends.metric)?.label ?? trends.metric }]}
                />
              </AnalyticsPanel>
            ) : null}

            <AnalyticsPanel>
              <DataTable
                columns={columns}
                data={trends.series}
                emptyTitle="Nenhum ponto de dados"
                emptyDescription="Nenhum ponto de dados disponível para esta série."
              />
            </AnalyticsPanel>
          </div>
        );
      })()}
    </div>
  );
}
