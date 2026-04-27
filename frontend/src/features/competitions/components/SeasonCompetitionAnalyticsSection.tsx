"use client";

import { useMemo } from "react";

import Link from "next/link";

import { useQueries } from "@tanstack/react-query";

import { fetchStageTies } from "@/features/competitions/services/competition-hub.service";
import { competitionStructureQueryKeys } from "@/features/competitions/queryKeys";
import { useCompetitionAnalytics } from "@/features/competitions/hooks";
import type { CompetitionStructureData } from "@/features/competitions/types";
import {
  getStageFormatLabel,
  isKnockoutStageFormat,
  localizeCompetitionStageName,
} from "@/features/competitions/utils/competition-structure";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import { buildRankingPath } from "@/shared/utils/context-routing";

type SeasonCompetitionAnalyticsSectionProps = {
  context: CompetitionSeasonContext;
  structure: CompetitionStructureData;
};

function formatAverage(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }

  return value.toFixed(2);
}

function formatOutcomeLabel(stageResult: string): string {
  switch (stageResult) {
    case "champion":
      return "Campeão";
    case "runner_up":
      return "Vice";
    case "qualified":
      return "Classificado";
    case "repechage":
      return "Repescagem";
    case "eliminated":
      return "Eliminado";
    default:
      return "Participação";
  }
}

export function SeasonCompetitionAnalyticsSection({
  context,
  structure,
}: SeasonCompetitionAnalyticsSectionProps) {
  const analyticsQuery = useCompetitionAnalytics({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
  });
  const knockoutStages = useMemo(
    () => structure.stages.filter((stage) => isKnockoutStageFormat(stage.stageFormat)),
    [structure.stages],
  );
  const tieQueries = useQueries({
    queries: knockoutStages.map((stage) => ({
      queryKey: competitionStructureQueryKeys.ties({
        competitionKey: context.competitionKey,
        seasonLabel: context.seasonLabel,
        stageId: stage.stageId,
      }),
      queryFn: () =>
        fetchStageTies({
          competitionKey: context.competitionKey,
          seasonLabel: context.seasonLabel,
          stageId: stage.stageId,
        }),
      staleTime: 5 * 60 * 1000,
      gcTime: 20 * 60 * 1000,
      enabled: Boolean(context.competitionKey && context.seasonLabel && stage.stageId),
    })),
  });

  const bracketStages = useMemo(
    () =>
      knockoutStages.map((stage, index) => ({
        stage,
        isLoading: tieQueries[index]?.isLoading ?? false,
        isError: tieQueries[index]?.isError ?? false,
        coverage: tieQueries[index]?.data?.meta?.coverage,
        ties: tieQueries[index]?.data?.data?.ties ?? [],
      })),
    [knockoutStages, tieQueries],
  );

  const hasPartialBracketCoverage = bracketStages.some(
    (stage) => stage.coverage?.status === "partial",
  );
  const seasonSummary = analyticsQuery.data?.seasonSummary;
  const stageAnalytics = analyticsQuery.data?.stageAnalytics ?? [];
  const seasonComparisons = analyticsQuery.data?.seasonComparisons ?? [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-4">
        <ProfileKpi
          hint="Recorte estrutural da temporada"
          label="Fases"
          value={analyticsQuery.isLoading ? "..." : seasonSummary?.totalStages ?? 0}
        />
        <ProfileKpi
          hint="Fases orientadas a tabela"
          label="Tabela"
          value={analyticsQuery.isLoading ? "..." : seasonSummary?.tableStages ?? 0}
        />
        <ProfileKpi
          hint="Fases eliminatórias"
          label="Mata-mata"
          value={analyticsQuery.isLoading ? "..." : seasonSummary?.knockoutStages ?? 0}
        />
        <ProfileKpi
          hint="Média de gols por jogo"
          label="Gols/jogo"
          value={analyticsQuery.isLoading ? "..." : formatAverage(seasonSummary?.averageGoals)}
        />
      </div>

      {analyticsQuery.isError ? (
        <ProfileAlert title="Não foi possível carregar as análises da competição" tone="critical">
          <p>{analyticsQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {analyticsQuery.isPartial ? (
        <PartialDataBanner
          className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
          coverage={analyticsQuery.coverage}
          message="As análises seguem disponíveis, mas parte da temporada tem cobertura parcial."
        />
      ) : null}

      <ProfilePanel className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Análises por fase
            </p>
            <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Desempenho segmentado pela estrutura da edição
            </h3>
            <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
              Cada fase expõe o formato esportivo, o volume de partidas e links para leituras analíticas já filtradas no mesmo contexto.
            </p>
          </div>
          {analyticsQuery.coverage.status !== "complete" ? (
            <ProfileCoveragePill coverage={analyticsQuery.coverage} />
          ) : null}
        </div>

        {analyticsQuery.isLoading ? (
          <div className="grid gap-3 md:grid-cols-2">
            {Array.from({ length: 4 }, (_, index) => (
              <LoadingSkeleton height={180} key={`analytics-stage-loading-${index}`} />
            ))}
          </div>
        ) : null}

        {!analyticsQuery.isLoading && stageAnalytics.length === 0 ? (
          <EmptyState
            className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
            description="Ainda não há fases suficientes para exibir análises estruturais desta temporada."
            title="Sem análises por fase"
          />
        ) : null}

        {!analyticsQuery.isLoading && stageAnalytics.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {stageAnalytics.map((stage) => (
              <ProfilePanel className="space-y-4" key={stage.stageId} tone={stage.isCurrent ? "soft" : "base"}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <ProfileTag>{localizeCompetitionStageName(stage.stageName ?? stage.stageId)}</ProfileTag>
                    {stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stage.stageFormat)}</ProfileTag> : null}
                    {stage.isCurrent ? <ProfileTag>Atual</ProfileTag> : null}
                  </div>
                  <div className="text-right text-xs uppercase tracking-[0.16em] text-[#57657a]">
                    {stage.matchCount} jogos
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <ProfileKpi hint="Times com presença na fase" label="Times" value={stage.teamCount} />
                  <ProfileKpi hint="Confrontos agregados" label="Chaves" value={stage.tieCount} />
                  <ProfileKpi hint="Média por partida" label="Gols/jogo" value={formatAverage(stage.averageGoals)} />
                </div>

                <div className="grid gap-2 text-sm text-[#57657a] sm:grid-cols-3">
                  <div className="rounded-[1rem] bg-[rgba(240,243,255,0.88)] px-3 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em]">Mandante</p>
                    <p className="mt-1 font-semibold text-[#111c2d]">{stage.homeWins}</p>
                  </div>
                  <div className="rounded-[1rem] bg-[rgba(240,243,255,0.88)] px-3 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em]">Empates</p>
                    <p className="mt-1 font-semibold text-[#111c2d]">{stage.draws}</p>
                  </div>
                  <div className="rounded-[1rem] bg-[rgba(240,243,255,0.88)] px-3 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em]">Visitante</p>
                    <p className="mt-1 font-semibold text-[#111c2d]">{stage.awayWins}</p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Link
                    className="button-pill button-pill-soft"
                    href={buildRankingPath("player-goals", {
                      competitionId: context.competitionId,
                      seasonId: context.seasonId,
                      stageId: stage.stageId,
                      stageFormat: stage.stageFormat ?? null,
                    })}
                  >
                    Artilharia da fase
                  </Link>
                  <Link
                    className="button-pill button-pill-secondary"
                    href={buildRankingPath("team-possession", {
                      competitionId: context.competitionId,
                      seasonId: context.seasonId,
                      stageId: stage.stageId,
                      stageFormat: stage.stageFormat ?? null,
                    })}
                  >
                    Posse da fase
                  </Link>
                </div>
              </ProfilePanel>
            ))}
          </div>
        ) : null}
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="soft">
        <div>
          <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
            Comparativo histórico
          </p>
          <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            Comparação entre temporadas da mesma competição
          </h3>
          <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
            O comparativo mantém a mesma identidade de competição e destaca quando o formato macro da edição muda entre temporadas.
          </p>
        </div>

        {analyticsQuery.isLoading ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <LoadingSkeleton height={148} key={`analytics-comparison-loading-${index}`} />
            ))}
          </div>
        ) : null}

        {!analyticsQuery.isLoading && seasonComparisons.length === 0 ? (
          <EmptyState
            className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-white/80"
            description="Ainda não há temporadas suficientes para comparar a estrutura desta competição."
            title="Sem comparativo histórico"
          />
        ) : null}

        {!analyticsQuery.isLoading && seasonComparisons.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-3">
            {seasonComparisons.map((season) => (
              <ProfilePanel className="space-y-4" key={season.seasonLabel}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <ProfileTag>{season.seasonLabel}</ProfileTag>
                  <ProfileTag>{season.formatFamily ?? "formato"}</ProfileTag>
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#111c2d]">{season.seasonFormatCode ?? "-"}</p>
                  <p className="mt-1 text-sm text-[#57657a]">
                    {season.matchCount} jogos, {season.stageCount} fases, {season.tieCount} chaves.
                  </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-[1rem] bg-[rgba(240,243,255,0.88)] px-3 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Tabela</p>
                    <p className="mt-1 font-semibold text-[#111c2d]">{season.tableStageCount}</p>
                  </div>
                  <div className="rounded-[1rem] bg-[rgba(240,243,255,0.88)] px-3 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Mata-mata</p>
                    <p className="mt-1 font-semibold text-[#111c2d]">{season.knockoutStageCount}</p>
                  </div>
                </div>
              </ProfilePanel>
            ))}
          </div>
        ) : null}
      </ProfilePanel>

      <ProfilePanel className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Chaveamento estrutural
            </p>
            <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Visão completa das fases eliminatórias
            </h3>
            <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
              As colunas abaixo seguem a ordem estrutural das fases eliminatórias da edição, sem depender de nome de competição.
            </p>
          </div>
        </div>

        {hasPartialBracketCoverage ? (
          <PartialDataBanner
            className="rounded-[1.2rem] border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-[#6e3900]"
            coverage={{ status: "partial", label: "Cobertura do chaveamento" }}
            message="Parte do chaveamento desta temporada ainda está com cobertura parcial."
          />
        ) : null}

        {bracketStages.length === 0 ? (
          <EmptyState
            className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
            description="Esta temporada não tem fases eliminatórias suficientes para montar um chaveamento."
            title="Sem chaveamento"
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-4">
            {bracketStages.map(({ stage, ties, isLoading, isError }) => (
              <ProfilePanel className="space-y-4" key={stage.stageId} tone={stage.isCurrent ? "soft" : "base"}>
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <ProfileTag>{localizeCompetitionStageName(stage.stageName ?? stage.stageId)}</ProfileTag>
                    {stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stage.stageFormat)}</ProfileTag> : null}
                  </div>
                </div>

                {isError ? (
                  <ProfileAlert title="Falha ao carregar esta fase" tone="warning">
                    <p>Os confrontos desta etapa não puderam ser carregados agora.</p>
                  </ProfileAlert>
                ) : null}

                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 2 }, (_, index) => (
                      <LoadingSkeleton height={110} key={`${stage.stageId}-loading-${index}`} />
                    ))}
                  </div>
                ) : null}

                {!isLoading && !isError && ties.length === 0 ? (
                  <EmptyState
                    className="rounded-[1rem] border-[rgba(191,201,195,0.55)] bg-white/80"
                    description="Nenhum confronto agregado está disponível para esta fase."
                    title="Sem confrontos"
                  />
                ) : null}

                {!isLoading && ties.length > 0 ? (
                  <div className="grid gap-3">
                    {ties.map((tie) => (
                      <div
                        className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4"
                        key={tie.tieId}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <ProfileTag>Confronto {tie.tieOrder}</ProfileTag>
                          {tie.resolutionType ? <ProfileTag>{tie.resolutionType}</ProfileTag> : null}
                        </div>
                        <div className="mt-3 space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-semibold text-[#111c2d]">
                              {tie.homeTeamName ?? tie.homeTeamId ?? "Mandante"}
                            </span>
                            <span className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                              {tie.homeGoals}
                            </span>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-semibold text-[#111c2d]">
                              {tie.awayTeamName ?? tie.awayTeamId ?? "Visitante"}
                            </span>
                            <span className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                              {tie.awayGoals}
                            </span>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-[#57657a]">
                          <span>{tie.matchCount} jogos</span>
                          {tie.winnerTeamName ? <span>• {formatOutcomeLabel("qualified")}: {tie.winnerTeamName}</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </ProfilePanel>
            ))}
          </div>
        )}
      </ProfilePanel>
    </div>
  );
}
