"use client";

import { useEffect, useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { useAnalyticsOlap } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
  AnalyticsSelect,
} from "@/features/analytics/components/AnalyticsPrimitives";
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
  { label: "Pontos/Jogo", value: "points_per_match" },
  { label: "Aproveitamento", value: "win_rate" },
  { label: "PPG", value: "ppg" },
] as const;

const DIMENSION_OPTIONS = [
  { label: "Rodada", value: "round" },
  { label: "Time", value: "team" },
  { label: "Técnico", value: "coach" },
  { label: "Mando", value: "venue" },
  { label: "Período", value: "period" },
] as const;

const GRAIN_OPTIONS = [
  { label: "Competição/Temporada", value: "competition_season" },
  { label: "Competição/Temporada/Rodada", value: "competition_season_round" },
  { label: "Competição/Temporada/Time", value: "competition_season_team" },
  { label: "Competição/Temporada/Time/Rodada", value: "competition_season_team_round" },
  { label: "Competição/Temporada/Técnico", value: "competition_season_coach" },
] as const;

const OPERATION_OPTIONS = [
  { label: "Slice", value: "slice" },
  { label: "Dice", value: "dice" },
  { label: "Drill Down", value: "drill_down" },
  { label: "Roll Up", value: "roll_up" },
  { label: "Pivot", value: "pivot" },
  { label: "Drill Through", value: "drill_through" },
] as const;

const BREAKDOWN_OPTIONS = [
  { label: "Nenhum", value: "none" },
  { label: "Mando", value: "venue" },
  { label: "Rodada", value: "round" },
  { label: "Time", value: "team" },
] as const;

const DIMENSION_GRAINS: Record<string, string[]> = {
  round: ["competition_season_round", "competition_season_team_round"],
  team: ["competition_season_team", "competition_season_team_round"],
  coach: ["competition_season_coach"],
  venue: ["competition_season_team"],
  period: ["competition_season", "competition_season_team"],
};

const DIMENSION_BREAKDOWNS: Record<string, string[]> = {
  round: ["none", "venue", "team"],
  team: ["none", "venue", "round"],
  coach: ["none", "round", "team"],
  venue: ["none", "round", "team"],
  period: ["none", "venue", "round", "team"],
};

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatValue(metric: string, value: number): string {
  if (metric === "avg_goals" || metric === "points_per_match" || metric === "ppg" || metric === "win_rate") {
    return DECIMAL_FORMATTER.format(value);
  }
  return INTEGER_FORMATTER.format(value);
}

type OlapRowWithFormatted = {
  dimensionKey: string;
  dimensionLabel: string;
  formattedValue: string;
  sampleSize: number;
  breakdown: string | null;
};

export function AnalyticsOlapTab() {
  const [metric, setMetric] = useState("goals");
  const [dimension, setDimension] = useState("round");
  const [grain, setGrain] = useState("competition_season_round");
  const [operation, setOperation] = useState("slice");
  const [breakdown, setBreakdown] = useState("none");
  const availableGrains = DIMENSION_GRAINS[dimension] ?? GRAIN_OPTIONS.map((option) => option.value);
  const availableBreakdowns = DIMENSION_BREAKDOWNS[dimension] ?? ["none"];
  const grainOptions = GRAIN_OPTIONS.filter((option) => availableGrains.includes(option.value));
  const breakdownOptions = BREAKDOWN_OPTIONS.filter((option) => availableBreakdowns.includes(option.value));

  useEffect(() => {
    if (!availableGrains.includes(grain)) {
      setGrain(availableGrains[0] ?? "competition_season_round");
    }
    if (!availableBreakdowns.includes(breakdown)) {
      setBreakdown("none");
    }
  }, [availableBreakdowns, availableGrains, breakdown, grain]);

  const query = useAnalyticsOlap({
    metric,
    dimension,
    grain,
    operation: operation !== "slice" ? operation : undefined,
    breakdown: breakdown !== "none" ? breakdown : undefined,
  });

  const columns = useMemo<Array<ColumnDef<OlapRowWithFormatted>>>(
    () => [
      { accessorKey: "dimensionLabel", header: query.data?.dimension ?? "Dimensão" },
      { accessorKey: "formattedValue", header: query.data?.metric ?? "Valor" },
      { accessorKey: "sampleSize", header: "Amostra" },
      ...(query.data?.rows[0]?.breakdown
        ? [{ accessorKey: "breakdown" as const, header: "Breakdown" }]
        : []),
    ],
    [query.data],
  );

  const tableData = useMemo<OlapRowWithFormatted[]>(
    () =>
      query.data?.rows.map((row) => ({
        ...row,
        formattedValue: formatValue(query.data!.metric, row.value),
        breakdown: row.breakdown?.label ?? null,
      })) ?? [],
    [query.data],
  );

  return (
    <div className="space-y-6">
      <AnalyticsPanel className="space-y-4">
        <AnalyticsSectionHeader
          eyebrow="Consultas OLAP"
          title="Exploração por métrica, dimensão e grain"
          description="Use a consulta como cubo analítico: filtre, troque a dimensão, altere o nível de detalhe e abra a composição quando disponível."
          aside={query.coverage ? <CoverageBadge coverage={query.coverage} /> : null}
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <AnalyticsSelect
            label="Métrica"
            onChange={setMetric}
            options={METRIC_OPTIONS.map((option) => ({ ...option }))}
            value={metric}
          />
          <AnalyticsSelect
            label="Dimensão"
            onChange={setDimension}
            options={DIMENSION_OPTIONS.map((option) => ({ ...option }))}
            value={dimension}
          />
          <AnalyticsSelect
            label="Grain"
            onChange={setGrain}
            options={grainOptions.map((option) => ({ ...option }))}
            value={grain}
          />
          <AnalyticsSelect
            label="Operação"
            onChange={setOperation}
            options={OPERATION_OPTIONS.map((option) => ({ ...option }))}
            value={operation}
          />
          <AnalyticsSelect
            label="Breakdown"
            onChange={setBreakdown}
            options={breakdownOptions.map((option) => ({ ...option }))}
            value={breakdown}
          />
        </div>
      </AnalyticsPanel>

      {query.isLoading && !query.data ? (
        <AnalyticsPanel className="space-y-2">
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
          <LoadingSkeleton height={24} />
        </AnalyticsPanel>
      ) : query.isError && !query.data ? (
        <EmptyState
          title="Falha na consulta OLAP"
          description={query.error?.message ?? "Erro desconhecido"}
        />
      ) : !query.data || query.isEmpty ? (
        <EmptyState
          title="Nenhum resultado OLAP"
          description="Altere os parâmetros da consulta ou selecione um escopo com dados."
        />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <AnalyticsKpi label="Linhas" value={INTEGER_FORMATTER.format(query.data.rows.length)} />
            <AnalyticsKpi label="Amostra" value={INTEGER_FORMATTER.format(query.data.total)} tone="soft" />
            <AnalyticsKpi
              label="Drill-through"
              value={query.data.drillThroughAvailable ? "Disponível" : "Indisponível"}
              tone={query.data.drillThroughAvailable ? "soft" : "base"}
            />
          </div>

          <AnalyticsPanel>
            <DataTable
              columns={columns}
              data={tableData}
              emptyTitle="Nenhuma linha retornada"
              emptyDescription="Tente alterar os parâmetros da consulta."
              enableVirtualization
              virtualizerMaxHeight={480}
            />
          </AnalyticsPanel>
        </div>
      )}
    </div>
  );
}
