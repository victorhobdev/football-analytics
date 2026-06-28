"use client";

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { useAnalyticsSuperlatives } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
  AnalyticsSelect,
} from "@/features/analytics/components/AnalyticsPrimitives";
import type { AnalyticsSuperlativeCategory, SuperlativeRecord } from "@/features/analytics/types";
import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";
import { DataTable } from "@/shared/components/data-display/DataTable";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";

const CATEGORY_OPTIONS: Array<{ label: string; value: AnalyticsSuperlativeCategory }> = [
  { label: "Partida com mais gols", value: "most_goals_match" },
  { label: "Maior goleada", value: "biggest_win" },
  { label: "Melhor ataque", value: "best_attack" },
  { label: "Melhor defesa", value: "best_defense" },
  { label: "Melhor saldo de gols", value: "best_goal_diff" },
  { label: "Rodada com mais gols", value: "most_goals_round" },
  { label: "Rodada com maior média", value: "highest_avg_goals_round" },
  { label: "Melhor PPG (time)", value: "best_team_ppg" },
  { label: "Melhor PPM (técnico)", value: "coach_best_ppm" },
  { label: "Técnico com mais jogos", value: "coach_most_matches" },
];

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatValue(value: number, category: string): string {
  if (category === "best_team_ppg" || category === "coach_best_ppm" || category === "highest_avg_goals_round") {
    return DECIMAL_FORMATTER.format(value);
  }
  return INTEGER_FORMATTER.format(value);
}

type SuperlativeRow = SuperlativeRecord & { formattedValue: string };

export function AnalyticsSuperlativesTab() {
  const [category, setCategory] = useState<AnalyticsSuperlativeCategory>("most_goals_match");
  const [limit, setLimit] = useState(10);

  const query = useAnalyticsSuperlatives({ category, limit });

  const columns = useMemo<Array<ColumnDef<SuperlativeRow>>>(
    () => [
      {
        id: "position",
        header: "Posição",
        cell: ({ row }) => (
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#003526] text-xs font-bold text-white">
            {row.original.position}
          </span>
        ),
      },
      { accessorKey: "entityLabel", header: "Entidade" },
      { accessorKey: "formattedValue", header: "Valor" },
      { accessorKey: "scope", header: "Escopo" },
      { accessorKey: "sampleSize", header: "Amostra" },
    ],
    [],
  );

  const tableData = useMemo<SuperlativeRow[]>(
    () =>
      query.data?.records.map((record) => ({
        ...record,
        formattedValue: formatValue(record.value, query.data!.category),
      })) ?? [],
    [query.data],
  );

  return (
    <div className="space-y-6">
      <AnalyticsPanel className="space-y-4">
        <AnalyticsSectionHeader
          eyebrow="Recordes e extremos"
          title="Superlativos derivados das agregações"
          description="Cada linha representa um extremo calculado dentro do escopo e condicionado pela cobertura da categoria."
          aside={query.coverage ? <CoverageBadge coverage={query.coverage} /> : null}
        />
        <div className="flex flex-wrap gap-3">
          <AnalyticsSelect
            label="Categoria"
            onChange={(value) => setCategory(value as AnalyticsSuperlativeCategory)}
            options={CATEGORY_OPTIONS.map((option) => ({ ...option }))}
            value={category}
          />
          <AnalyticsSelect
            label="Limite"
            onChange={(value) => setLimit(Number(value))}
            options={[5, 10, 20, 50].map((value) => ({ label: String(value), value: String(value) }))}
            value={String(limit)}
          />
        </div>
      </AnalyticsPanel>

      {query.isLoading && !query.data ? (
        <AnalyticsPanel className="space-y-2">
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
        </AnalyticsPanel>
      ) : query.isError && !query.data ? (
        <EmptyState
          title="Falha ao carregar recordes"
          description={query.error?.message ?? "Erro desconhecido"}
        />
      ) : !query.data || query.isEmpty ? (
        <EmptyState
          title="Nenhum recorde disponível"
          description="Selecione um escopo com dados ou altere a categoria."
        />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            {query.data.categoryLabel ? (
              <AnalyticsKpi label="Categoria" value={query.data.categoryLabel} />
            ) : null}
            <AnalyticsKpi label="Registros" value={INTEGER_FORMATTER.format(query.data.records.length)} tone="soft" />
          </div>

          <AnalyticsPanel>
            <DataTable
              columns={columns}
              data={tableData}
              emptyTitle="Nenhum recorde encontrado"
              emptyDescription="Nenhum recorde encontrado para esta categoria."
            />
          </AnalyticsPanel>
        </div>
      )}
    </div>
  );
}
