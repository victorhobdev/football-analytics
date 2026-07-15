"use client";

import { useTeamJourneyHistory } from "@/features/teams/hooks/useTeamJourneyHistory";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";

type TeamJourneySectionProps = {
  competitionContext: CompetitionSeasonContext;
  teamId: string;
};

function getStageFormatLabel(stageFormat: string | null | undefined): string {
  switch (stageFormat) {
    case "league_table":
      return "Fase de liga";
    case "group_table":
      return "Fase de grupos";
    case "knockout":
      return "Mata-mata";
    case "qualification_knockout":
      return "Eliminatória preliminar";
    case "placement_match":
      return "Disputa de colocação";
    default:
      return "Estrutura";
  }
}

function formatJourneyOutcomeLabel(value: string): string {
  switch (value) {
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
    case "unknown":
      return "Indeterminado";
    default:
      return "Participação";
  }
}

export function TeamJourneySection({
  competitionContext,
  teamId,
}: TeamJourneySectionProps) {
  const teamJourneyQuery = useTeamJourneyHistory({
    competitionKey: competitionContext.competitionKey,
    teamId,
  });
  const seasons = teamJourneyQuery.data?.seasons ?? [];
  const latestSeason = seasons[0] ?? null;

  if (teamJourneyQuery.isLoading) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton height={150} />
        <LoadingSkeleton height={280} />
      </div>
    );
  }

  if (teamJourneyQuery.isError) {
    return (
      <ProfileAlert title="Não foi possível carregar a jornada histórica" tone="critical">
        <p>{teamJourneyQuery.error?.message}</p>
      </ProfileAlert>
    );
  }

  if (seasons.length === 0) {
    return (
      <EmptyState
        className="rounded-[1.2rem] border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)]"
        description="Não há temporadas suficientes para montar a jornada histórica deste time nesta competição."
        title="Sem jornada histórica"
      />
    );
  }

  return (
    <div className="space-y-5">
      <ProfilePanel className="space-y-4" tone="soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Jornada histórica
            </p>
            <h3 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              Todas as fases disputadas nesta competição
            </h3>
            <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">
              A linha do tempo abaixo combina fases de tabela e mata-mata sob o mesmo contrato estrutural da competição.
            </p>
          </div>
        </div>

        {latestSeason ? (
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-[1rem] bg-white/80 px-4 py-4">
              <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Temporada mais recente</p>
              <p className="mt-2 font-semibold text-[#111c2d]">{latestSeason.seasonLabel}</p>
            </div>
            <div className="rounded-[1rem] bg-white/80 px-4 py-4">
              <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Situação</p>
              <p className="mt-2 font-semibold text-[#111c2d]">
                {formatJourneyOutcomeLabel(latestSeason.summary.finalOutcome)}
              </p>
            </div>
            <div className="rounded-[1rem] bg-white/80 px-4 py-4">
              <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Jogos</p>
              <p className="mt-2 font-semibold text-[#111c2d]">{latestSeason.summary.matchesPlayed}</p>
            </div>
            <div className="rounded-[1rem] bg-white/80 px-4 py-4">
              <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Formato</p>
              <p className="mt-2 font-semibold text-[#111c2d]">{latestSeason.seasonFormatCode ?? "-"}</p>
            </div>
          </div>
        ) : null}
      </ProfilePanel>

      <div className="grid gap-4">
        {seasons.map((season) => (
          <ProfilePanel className="space-y-4" key={season.seasonLabel}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{season.seasonLabel}</ProfileTag>
                  {season.formatFamily ? <ProfileTag>{season.formatFamily}</ProfileTag> : null}
                  {season.seasonFormatCode ? <ProfileTag>{season.seasonFormatCode}</ProfileTag> : null}
                </div>
                <p className="text-sm text-[#57657a]">
                  {season.summary.matchesPlayed} jogos, {season.summary.goalsFor} gols marcados e{" "}
                  {season.summary.goalsAgainst} sofridos.
                </p>
              </div>
              <div className="text-right">
                <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Situação</p>
                <p className="mt-2 font-semibold text-[#111c2d]">
                  {formatJourneyOutcomeLabel(season.summary.finalOutcome)}
                </p>
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              {season.stages.map((stage) => (
                <div
                  className="rounded-[1.1rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] px-4 py-4"
                  key={`${season.seasonLabel}-${stage.stageId}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <ProfileTag>{stage.stageName ?? stage.stageId}</ProfileTag>
                      {stage.stageFormat ? <ProfileTag>{getStageFormatLabel(stage.stageFormat)}</ProfileTag> : null}
                    </div>
                    <ProfileTag>{formatJourneyOutcomeLabel(stage.stageResult)}</ProfileTag>
                  </div>

                  <div className="mt-4 grid gap-2 text-sm text-[#57657a] sm:grid-cols-3">
                    <div>
                      <p className="text-[0.68rem] uppercase tracking-[0.16em]">Campanha</p>
                      <p className="mt-1 font-semibold text-[#111c2d]">
                        {stage.wins}V {stage.draws}E {stage.losses}D
                      </p>
                    </div>
                    <div>
                      <p className="text-[0.68rem] uppercase tracking-[0.16em]">Gols</p>
                      <p className="mt-1 font-semibold text-[#111c2d]">
                        {stage.goalsFor} / {stage.goalsAgainst}
                      </p>
                    </div>
                    <div>
                      <p className="text-[0.68rem] uppercase tracking-[0.16em]">Jogos</p>
                      <p className="mt-1 font-semibold text-[#111c2d]">{stage.matchesPlayed}</p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {stage.groupName ? <ProfileTag>{stage.groupName}</ProfileTag> : null}
                    {typeof stage.sourcePosition === "number" ? (
                      <ProfileTag>{stage.sourcePosition}º lugar</ProfileTag>
                    ) : null}
                    {stage.tieOutcome ? <ProfileTag>{stage.tieOutcome}</ProfileTag> : null}
                  </div>
                </div>
              ))}
            </div>
          </ProfilePanel>
        ))}
      </div>
    </div>
  );
}
