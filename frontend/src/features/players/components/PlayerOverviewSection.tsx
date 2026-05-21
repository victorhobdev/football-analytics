"use client";

import Link from "next/link";

import type { PlayerProfile, PlayerProfileMeta } from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfileMetricTile,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { InsightObject } from "@/shared/types/insight.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import { formatDate } from "@/shared/utils/formatters";

type PlayerOverviewSectionProps = {
  coverage: CoverageState;
  matchesHref?: string | null;
  profile: PlayerProfile;
  rankingsHref?: string | null;
  seasonHubHref?: string | null;
  teamHref?: string | null;
  insights: {
    coverage: CoverageState;
    errorMessage?: string | null;
    isError: boolean;
    isLoading: boolean;
    isPartial: boolean;
    items: InsightObject[];
  };
};

function formatPercentage(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return `${Math.round(value)}%`;
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value.toFixed(2);
}

function formatResultLabel(result: string | null | undefined): string {
  if (result === "win") {
    return "V";
  }

  if (result === "draw") {
    return "E";
  }

  if (result === "loss") {
    return "D";
  }

  return "-";
}

function formatInsightSeverity(severity: InsightObject["severity"]): string {
  if (severity === "critical") {
    return "Crítico";
  }

  if (severity === "warning") {
    return "Atenção";
  }

  return "Informativo";
}

function getUnavailableHistoryTitle(profileMeta: PlayerProfileMeta): string {
  if (profileMeta.profileType === "world_cup_local") {
    return "Perfil local da Copa";
  }

  return "Perfil sem histórico consolidado";
}

function getUnavailableHistoryDescription(profileMeta: PlayerProfileMeta): string {
  if (profileMeta.profileType === "world_cup_local") {
    return "Este jogador segue disponível como perfil local da Copa, com identidade preservada mesmo sem histórico estatístico carregado.";
  }

  return "Este jogador possui identidade consolidada na plataforma, mas ainda não tem histórico estatístico disponível para navegação.";
}

export function PlayerOverviewSection({
  coverage,
  matchesHref,
  profile,
  rankingsHref,
  seasonHubHref,
  teamHref,
  insights,
}: PlayerOverviewSectionProps) {
  const { player, profileMeta, recentMatches, summary } = profile;
  const latestMatch = recentMatches?.[0] ?? null;
  const goalContribution =
    (typeof summary.goals === "number" ? summary.goals : 0) +
    (typeof summary.assists === "number" ? summary.assists : 0);
  const shotsOnTargetPct =
    typeof summary.shotsOnTarget === "number" &&
    typeof summary.shotsTotal === "number" &&
    summary.shotsTotal > 0
      ? (summary.shotsOnTarget / summary.shotsTotal) * 100
      : null;
  const worldCup = profileMeta.worldCup ?? null;

  if (!profileMeta.hasHistoricalStats) {
    return (
      <div className="space-y-6">
        {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}

        <ProfileAlert title={getUnavailableHistoryTitle(profileMeta)} tone="info">
          <p>{getUnavailableHistoryDescription(profileMeta)}</p>
        </ProfileAlert>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <ProfilePanel className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileCoveragePill coverage={coverage} />
                  {player.position ? <ProfileTag>{player.position}</ProfileTag> : null}
                  {worldCup?.teamCount === 1 && worldCup.teamNames[0] ? (
                    <ProfileTag>{worldCup.teamNames[0]}</ProfileTag>
                  ) : null}
                </div>
                <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
                  Identidade e contexto preservados
                </h2>
                <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
                  O perfil continua navegável com os dados de identidade disponíveis, sem tratar a
                  ausência de histórico como erro de produto.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {teamHref ? (
                  <Link className="button-pill button-pill-soft" href={teamHref}>
                    {player.teamName ?? "Time"}
                  </Link>
                ) : null}
                {seasonHubHref ? (
                  <Link className="button-pill button-pill-soft" href={seasonHubHref}>
                    Temporada
                  </Link>
                ) : null}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <ProfileKpi
                label="Edições"
                value={worldCup?.editionCount ?? "-"}
                hint={
                  worldCup?.editionLabels?.length
                    ? worldCup.editionLabels.join(" · ")
                    : "Sem edições detalhadas"
                }
              />
              <ProfileKpi
                label="Seleções"
                value={worldCup?.teamCount ?? "-"}
                hint={
                  worldCup?.teamNames?.length
                    ? worldCup.teamNames.join(" · ")
                    : "Sem seleção detalhada"
                }
              />
              <ProfileKpi
                label="Gols em Copas"
                value={worldCup?.goalCount ?? "-"}
                hint="Total consolidado no contexto da Copa"
              />
              <ProfileKpi
                label="Posição"
                value={worldCup?.primaryPosition ?? player.position ?? "-"}
                hint="Melhor posição disponível no contexto da Copa"
              />
            </div>
          </ProfilePanel>

          <ProfilePanel className="space-y-5" tone="accent">
            <div className="space-y-2">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
                Contexto Copa
              </p>
              <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-white">
                {worldCup?.editionCount
                  ? `${worldCup.editionCount} edições registradas`
                  : "Contexto preservado"}
              </h2>
              <p className="text-sm leading-6 text-white/75">
                {worldCup?.teamNames?.length
                  ? "Seleções, edições e gols seguem disponíveis para leitura rápida neste perfil."
                  : "A plataforma mantém a identidade deste jogador mesmo sem histórico consolidado."}
              </p>
            </div>

            {worldCup?.teamNames?.length ? (
              <div className="space-y-2">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
                  Seleções
                </p>
                <div className="flex flex-wrap gap-2">
                  {worldCup.teamNames.map((teamName) => (
                    <ProfileTag className="bg-white/12 text-white/84" key={teamName}>
                      {teamName}
                    </ProfileTag>
                  ))}
                </div>
              </div>
            ) : null}

            {worldCup?.editionLabels?.length ? (
              <div className="space-y-2">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
                  Edições
                </p>
                <div className="flex flex-wrap gap-2">
                  {worldCup.editionLabels.map((editionLabel) => (
                    <ProfileTag className="bg-white/12 text-white/84" key={editionLabel}>
                      {editionLabel}
                    </ProfileTag>
                  ))}
                </div>
              </div>
            ) : null}
          </ProfilePanel>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <ProfilePanel className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ProfileCoveragePill coverage={coverage} />
                {player.teamName ? <ProfileTag>{player.teamName}</ProfileTag> : null}
                {player.position ? <ProfileTag>{player.position}</ProfileTag> : null}
              </div>
              <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
                Resumo competitivo
              </h2>
              <p className="text-sm leading-6 text-[#57657a]">
                Leitura principal do jogador nesta temporada, com atalhos para time, rankings e
                calendário.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {teamHref ? (
                <Link
                  className="button-pill button-pill-soft"
                  href={teamHref}
                >
                  {player.teamName ?? "Time"}
                </Link>
              ) : null}
              {seasonHubHref ? (
                <Link
                  className="button-pill button-pill-soft"
                  href={seasonHubHref}
                >
                  Temporada
                </Link>
              ) : null}
              {rankingsHref ? (
                <Link
                  className="button-pill button-pill-soft"
                  href={rankingsHref}
                >
                  Rankings
                </Link>
              ) : null}
              {matchesHref ? (
                <Link
                  className="button-pill button-pill-primary"
                  href={matchesHref}
                >
                  Ver partidas
                </Link>
              ) : null}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ProfileKpi label="Jogos" value={summary.matchesPlayed ?? "-"} hint={`Minutos ${summary.minutesPlayed ?? "-"}`} />
            <ProfileKpi label="Gols + assistências" value={goalContribution} hint={`${summary.goals ?? 0} gols · ${summary.assists ?? 0} assistências`} />
            <ProfileKpi label="Nota" value={formatDecimal(summary.rating)} hint={`No alvo ${formatPercentage(shotsOnTargetPct)}`} />
            <ProfileKpi label="Finalizações" value={summary.shotsTotal ?? "-"} hint={`${summary.shotsOnTarget ?? 0} no alvo`} />
          </div>
        </ProfilePanel>

        <ProfilePanel className="space-y-5" tone="accent">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
              Última participação consolidada
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-white">
              {latestMatch?.opponentName ?? "Sem adversário"}
            </h2>
            <p className="text-sm leading-6 text-white/75">
              {latestMatch
                ? `${formatDate(latestMatch.playedAt)} · ${latestMatch.venue === "home" ? "Casa" : "Fora"}`
                : "Ainda não há última partida consolidada para este jogador."}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <ProfileMetricTile label="Resultado" value={latestMatch ? formatResultLabel(latestMatch.result) : "-"} />
            <ProfileMetricTile label="Placar" value={latestMatch ? `${latestMatch.goalsFor ?? "-"} - ${latestMatch.goalsAgainst ?? "-"}` : "-"} />
            <ProfileMetricTile label="Minutos" value={latestMatch?.minutesPlayed ?? "-"} />
            <ProfileMetricTile label="Nota" value={formatDecimal(latestMatch?.rating)} />
          </div>

          <div className="rounded-[1.3rem] bg-white/10 p-4">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
              Navegação conectada
            </p>
            <p className="mt-2 text-sm leading-6 text-white/78">
              Os atalhos mantêm a mesma competição e temporada ao abrir time, rankings e
              partidas.
            </p>
          </div>
        </ProfilePanel>
      </section>

      <ProfilePanel className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Leituras
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Leituras do jogador
            </h2>
          </div>
          <ProfileCoveragePill coverage={insights.coverage} />
        </div>

        {insights.isLoading ? (
          <p className="text-sm text-[#57657a]">Carregando leituras do jogador...</p>
        ) : null}

        {!insights.isLoading && insights.isError && insights.items.length === 0 ? (
          <ProfileAlert title="Falha ao carregar leituras do jogador" tone="critical">
            <p>{insights.errorMessage ?? "Sem mensagem adicional."}</p>
          </ProfileAlert>
        ) : null}

        {!insights.isLoading && insights.isPartial ? <PartialDataBanner coverage={insights.coverage} /> : null}

        {!insights.isLoading && !insights.isError && insights.items.length === 0 ? (
          <EmptyState
            title="Sem leituras"
            description="Não há leituras adicionais disponíveis para este jogador."
          />
        ) : null}

        {!insights.isLoading && insights.items.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {insights.items.slice(0, 4).map((insight) => (
              <article
                className="rounded-[1.35rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.88)] p-4"
                key={insight.insight_id}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <ProfileTag>{formatInsightSeverity(insight.severity)}</ProfileTag>
                  <span className="text-xs text-[#57657a]">{insight.reference_period}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#111c2d]">{insight.explanation}</p>
              </article>
            ))}
          </div>
        ) : null}

        {!insights.isLoading && insights.isError && insights.items.length > 0 ? (
          <ProfileAlert title="Leituras carregadas com alerta" tone="warning">
            <p>{insights.errorMessage ?? "Sem mensagem adicional."}</p>
          </ProfileAlert>
        ) : null}
      </ProfilePanel>
    </div>
  );
}
