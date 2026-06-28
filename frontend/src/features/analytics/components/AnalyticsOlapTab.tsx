"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

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
  rawValue: number;
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

  const [showDrillPanel, setShowDrillPanel] = useState(false);

  const drillQuery = useAnalyticsOlap(
    { metric, dimension, grain, operation: "drill_through", breakdown: "none" },
  );

  const handleDrillThrough = useCallback(() => {
    if (query.data?.drillThroughAvailable) {
      setShowDrillPanel((prev) => !prev);
    }
  }, [query.data?.drillThroughAvailable]);

  const columns = useMemo<Array<ColumnDef<OlapRowWithFormatted>>>(
    () => [
      {
        accessorKey: "dimensionLabel",
        header: query.data?.dimension ?? "Dimensão",
        enableSorting: true,
      },
      {
        accessorKey: "rawValue",
        header: query.data?.metric ?? "Valor",
        enableSorting: true,
        cell: ({ row }) => <span>{row.original.formattedValue}</span>,
      },
      { accessorKey: "sampleSize", header: "Amostra", enableSorting: true },
      ...(query.data?.rows[0]?.breakdown
        ? [{ accessorKey: "breakdown" as const, header: "Breakdown", enableSorting: false }]
        : []),
    ],
    [query.data],
  );

  const tableData = useMemo<OlapRowWithFormatted[]>(
    () =>
      query.data?.rows.map((row) => ({
        ...row,
        formattedValue: formatValue(query.data!.metric, row.value),
        rawValue: row.value,
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
            {query.data.drillThroughAvailable ? (
              <button
                className="rounded-lg border border-[#003526]/10 bg-[rgba(240,243,255,0.82)] px-4 py-3 text-left transition-colors hover:bg-[#003526] hover:text-white"
                onClick={handleDrillThrough}
                type="button"
              >
                <p className="text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[#57657a] group-hover:text-white/68">
                  Drill-through
                </p>
                <p className="mt-1.5 text-sm font-semibold">
                  {showDrillPanel ? "Ocultar partidas" : "Ver partidas"}
                </p>
              </button>
            ) : (
              <AnalyticsKpi label="Drill-through" value="Indisponível" tone="base" />
            )}
          </div>

          {showDrillPanel && drillQuery.data ? (
            <AnalyticsPanel className="space-y-3">
              <p className="text-sm font-semibold text-[#111c2d]">
                Partidas no escopo ({drillQuery.data.rows.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {drillQuery.data.rows.slice(0, 20).map((row) => (
                  <a
                    className="inline-flex items-center rounded-full border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-3 py-1 text-xs font-medium text-[#111c2d] transition-colors hover:border-[#0f513c] hover:bg-white"
                    href={`/matches/${row.matchId ?? row.dimensionKey}`}
                    key={row.dimensionKey ?? row.matchId}
                  >
                    Match {row.dimensionKey ?? row.matchId}
                  </a>
                ))}
                {drillQuery.data.rows.length > 20 ? (
                  <span className="inline-flex items-center text-xs text-[#57657a]">
                    +{drillQuery.data.rows.length - 20} mais
                  </span>
                ) : null}
              </div>
            </AnalyticsPanel>
          ) : null}

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
