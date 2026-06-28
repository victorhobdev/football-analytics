"use client";

import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { useAnalyticsCoverage } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
} from "@/features/analytics/components/AnalyticsPrimitives";
import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { DataTable } from "@/shared/components/data-display/DataTable";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const METRIC_LABELS: Record<string, string> = {
  scores: "Placar",
  events: "Eventos",
  lineups: "Escalações",
  playerStats: "Estatísticas Individuais",
  teamStats: "Estatísticas por Time",
  coachAssignment: "Atribuição Técnico",
};

const STATUS_LABELS: Record<string, string> = {
  complete: "Completo",
  partial: "Parcial",
  insufficient: "Insuficiente",
  not_available: "Indisponível",
};

const STATUS_BADGE_CLASSES: Record<string, string> = {
  complete: "border-emerald-300 bg-emerald-50 text-emerald-700",
  partial: "border-amber-300 bg-amber-50 text-amber-700",
  insufficient: "border-red-300 bg-red-50 text-red-700",
  not_available: "border-slate-300 bg-slate-50 text-slate-600",
};

type CoverageMetricRow = {
  metricKey: string;
  metricLabel: string;
  count: number;
  percentage: number | null;
  status: string;
};

export function AnalyticsCoverageTab() {
  const query = useAnalyticsCoverage();

  const metricEntries = useMemo(
    () => Object.entries(query.data?.metrics ?? {}),
    [query.data?.metrics],
  );

  const columns = useMemo<Array<ColumnDef<CoverageMetricRow>>>(
    () => [
      { accessorKey: "metricLabel", header: "Métrica" },
      { accessorKey: "count", header: "Registros" },
      {
        id: "percentage",
        header: "%",
        cell: ({ row }) =>
          typeof row.original.percentage === "number" ? `${DECIMAL_FORMATTER.format(row.original.percentage)}%` : "-",
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${STATUS_BADGE_CLASSES[row.original.status] ?? "border-slate-300 bg-slate-50 text-slate-600"}`}>
            {STATUS_LABELS[row.original.status] ?? row.original.status}
          </span>
        ),
      },
    ],
    [],
  );

  const tableData = useMemo<CoverageMetricRow[]>(
    () =>
      metricEntries.map(([key, metric]) => ({
        metricKey: key,
        metricLabel: METRIC_LABELS[key] ?? key,
        count: metric.count,
        percentage: metric.percentage,
        status: metric.status,
      })),
    [metricEntries],
  );

  if (query.isLoading && !query.data) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton height={96} />
        <LoadingSkeleton height={24} />
        <LoadingSkeleton height={24} />
        <LoadingSkeleton height={24} />
      </div>
    );
  }

  if (query.isError && !query.data) {
    return (
      <EmptyState
        title="Falha ao carregar cobertura"
        description={query.error?.message ?? "Erro desconhecido"}
      />
    );
  }

  if (!query.data || query.isEmpty) {
    return (
      <EmptyState
        title="Nenhum dado de cobertura"
        description="Selecione um escopo para ver o relatório de cobertura."
      />
    );
  }

  const coverage = query.data;

  return (
    <div className="space-y-6">
      {query.coverage ? (
        <PartialDataBanner coverage={query.coverage} />
      ) : null}

      <AnalyticsPanel className="space-y-4">
        <AnalyticsSectionHeader
          eyebrow="Cobertura"
          title="Confiabilidade por camada de dado"
          description="Mostra quais famílias de métricas podem ser usadas no recorte atual e quais devem permanecer ocultas."
          aside={query.coverage ? <CoverageBadge coverage={query.coverage} /> : null}
        />
        <div className="grid gap-3 sm:grid-cols-3">
          <AnalyticsKpi label="Partidas" value={INTEGER_FORMATTER.format(coverage.totalMatches)} tone="accent" />
          <AnalyticsKpi label="Ativadas" value={coverage.enabledMetrics.length} />
          <AnalyticsKpi label="Ocultas" value={coverage.hiddenMetrics.length} tone="soft" />
        </div>
      </AnalyticsPanel>

      <AnalyticsPanel>
        <DataTable
          columns={columns}
          data={tableData}
          emptyTitle="Nenhuma métrica de cobertura"
          emptyDescription="Nenhuma métrica de cobertura disponível."
        />
      </AnalyticsPanel>

      {coverage.hiddenMetrics.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-[#57657a]">Métricas ocultas</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {coverage.hiddenMetrics.map((hm) => (
              <div key={hm.metric} className="rounded-[1rem] border border-[rgba(191,201,195,0.46)] bg-white/82 p-3">
                <p className="text-sm font-medium text-slate-900">{hm.metric}</p>
                <p className="text-xs text-slate-500">{hm.reason}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {coverage.enabledMetrics.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-[#57657a]">
            Métricas disponíveis ({coverage.enabledMetrics.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {coverage.enabledMetrics.map((metric) => (
              <span
                key={metric}
                className="inline-flex items-center rounded-full border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
              >
                {metric}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
