"use client";

import { useState } from "react";

import { useAnalyticsComparisons } from "@/features/analytics/hooks/useAnalytics";
import {
  AnalyticsKpi,
  AnalyticsPanel,
  AnalyticsSectionHeader,
  AnalyticsSelect,
} from "@/features/analytics/components/AnalyticsPrimitives";
import type { AnalyticsComparisonType } from "@/features/analytics/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";

const TYPE_OPTIONS: Array<{ label: string; value: AnalyticsComparisonType }> = [
  { label: "Time vs Time", value: "team_vs_team" },
  { label: "Temporada vs Temporada", value: "season_vs_season" },
  { label: "Casa vs Fora", value: "home_vs_away" },
  { label: "Período vs Período", value: "period_vs_period" },
] as const;

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return INTEGER_FORMATTER.format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return DECIMAL_FORMATTER.format(value);
}

function formatSigned(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value > 0 ? `+${INTEGER_FORMATTER.format(value)}` : INTEGER_FORMATTER.format(value);
}

function EntityCard({
  entity,
  label,
}: {
  entity: {
    label: string;
    matches: number;
    wins: number;
    draws: number;
    losses: number;
    points: number;
    goalsFor: number;
    goalsAgainst: number;
    goalDiff: number;
    avgGoalsPerMatch: number | null;
  };
  label: string;
}) {
  return (
    <AnalyticsPanel>
      <p className="text-[0.68rem] font-bold uppercase tracking-[0.14em] text-[#57657a]">{label}</p>
      <p className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">{entity.label}</p>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm text-slate-600">
        <div>Jogos: <span className="font-medium text-slate-900">{formatInteger(entity.matches)}</span></div>
        <div>Pontos: <span className="font-medium text-slate-900">{formatInteger(entity.points)}</span></div>
        <div>Vitórias: <span className="font-medium text-slate-900">{formatInteger(entity.wins)}</span></div>
        <div>Empates: <span className="font-medium text-slate-900">{formatInteger(entity.draws)}</span></div>
        <div>Derrotas: <span className="font-medium text-slate-900">{formatInteger(entity.losses)}</span></div>
        <div>Saldo: <span className="font-medium text-slate-900">{formatSigned(entity.goalDiff)}</span></div>
        <div>GP: <span className="font-medium text-slate-900">{formatInteger(entity.goalsFor)}</span></div>
        <div>GC: <span className="font-medium text-slate-900">{formatInteger(entity.goalsAgainst)}</span></div>
        <div className="col-span-2">Média: <span className="font-medium text-slate-900">{formatDecimal(entity.avgGoalsPerMatch)}</span></div>
      </div>
    </AnalyticsPanel>
  );
}

const COVERAGE_STATUS_LABEL: Record<string, string> = {
  complete: "Completo",
  partial: "Parcial",
  insufficient: "Insuficiente",
  not_available: "Indisponível",
};

export function AnalyticsComparisonsTab() {
  const [type, setType] = useState<AnalyticsComparisonType>("team_vs_team");
  const [entityA, setEntityA] = useState("");
  const [entityB, setEntityB] = useState("");
  const requiresEntityB = type === "team_vs_team" || type === "season_vs_season";
  const entityAValue = entityA.trim();
  const entityBValue = requiresEntityB ? entityB.trim() : entityAValue;

  const canSearch = entityAValue.length > 0 && (!requiresEntityB || entityBValue.length > 0);

  const query = useAnalyticsComparisons(
    { type, entityA: entityAValue, entityB: entityBValue },
    canSearch,
  );

  return (
    <div className="space-y-6">
      <AnalyticsPanel className="space-y-4">
        <AnalyticsSectionHeader
          eyebrow="Comparações"
          title="Comparar entidades e períodos"
          description="Informe os identificadores compatíveis com o tipo de comparação para avaliar diferenças no mesmo escopo filtrado."
        />
        <div className="flex flex-wrap items-end gap-3">
          <AnalyticsSelect
            label="Tipo"
            onChange={(value) => setType(value as AnalyticsComparisonType)}
            options={TYPE_OPTIONS.map((option) => ({ ...option }))}
            value={type}
          />

          <label className="flex min-w-[12rem] flex-1 flex-col gap-2 text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[#57657a] sm:flex-none">
            {requiresEntityB ? "Entidade A" : "Entidade"}
            <input
              className="h-10 rounded-lg border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-3 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none transition-colors focus:border-[#0f513c]"
              placeholder={type === "season_vs_season" ? "Temporada" : "ID do time"}
              value={entityA}
              onChange={(e) => setEntityA(e.target.value)}
            />
          </label>

          {requiresEntityB ? (
            <label className="flex min-w-[12rem] flex-1 flex-col gap-2 text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[#57657a] sm:flex-none">
              Entidade B
              <input
                className="h-10 rounded-lg border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-3 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none transition-colors focus:border-[#0f513c]"
                placeholder={type === "season_vs_season" ? "Temporada" : "ID do time"}
                value={entityB}
                onChange={(e) => setEntityB(e.target.value)}
              />
            </label>
          ) : null}
        </div>
      </AnalyticsPanel>

      {!canSearch ? (
        <AnalyticsPanel>
          <p className="text-sm text-[#57657a]">
            {requiresEntityB ? "Preencha as duas entidades para comparar." : "Informe a entidade para comparar casa/fora ou períodos."}
          </p>
        </AnalyticsPanel>
      ) : query.isLoading && !query.data ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <LoadingSkeleton height={240} />
          <LoadingSkeleton height={240} />
        </div>
      ) : query.isError && !query.data ? (
        <EmptyState
          title="Falha na comparação"
          description={query.error?.message ?? "Erro desconhecido"}
        />
      ) : !query.data || query.isEmpty ? (
        <EmptyState
          title="Nenhum resultado de comparação"
          description="Verifique os identificadores informados ou selecione outro tipo."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <EntityCard entity={query.data.entityA} label="Entidade A" />
            <EntityCard entity={query.data.entityB} label="Entidade B" />
          </div>

          {query.data.difference ? (
            <AnalyticsPanel className="space-y-4">
              <AnalyticsSectionHeader eyebrow="Diferença" title="A - B" />
              <div className="grid gap-3 sm:grid-cols-5">
                <AnalyticsKpi label="Pontos" value={formatSigned(query.data.difference.points)} />
                <AnalyticsKpi label="Saldo" value={formatSigned(query.data.difference.goalDiff)} />
                <AnalyticsKpi label="Vitórias" value={formatSigned(query.data.difference.wins)} tone="soft" />
                <AnalyticsKpi label="Empates" value={formatSigned(query.data.difference.draws)} tone="soft" />
                <AnalyticsKpi label="Derrotas" value={formatSigned(query.data.difference.losses)} tone="soft" />
              </div>
            </AnalyticsPanel>
          ) : null}

          {query.data.coverage ? (
            <div className="flex flex-wrap gap-3">
              <span className="inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium text-slate-600">
                Cobertura A: {COVERAGE_STATUS_LABEL[query.data.coverage.entityA.status] ?? query.data.coverage.entityA.status} ({INTEGER_FORMATTER.format(query.data.coverage.entityA.sampleSize)}/{INTEGER_FORMATTER.format(query.data.coverage.entityA.expectedSize)})
              </span>
              <span className="inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium text-slate-600">
                Cobertura B: {COVERAGE_STATUS_LABEL[query.data.coverage.entityB.status] ?? query.data.coverage.entityB.status} ({INTEGER_FORMATTER.format(query.data.coverage.entityB.sampleSize)}/{INTEGER_FORMATTER.format(query.data.coverage.entityB.expectedSize)})
              </span>
            </div>
          ) : null}

          {query.isError ? (
            <p className="text-sm text-red-600">{query.error?.message}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
