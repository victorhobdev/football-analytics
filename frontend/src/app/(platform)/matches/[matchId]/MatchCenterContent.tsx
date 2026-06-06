"use client";

import Link from "next/link";

import { usePathname, useSearchParams } from "next/navigation";

import { useMatchCenter } from "@/features/matches/hooks";
import type {
  MatchCenterSectionCoverage,
  MatchPlayerStat,
  MatchTimelineEvent,
} from "@/features/matches/types";
import {
  MatchCenterHeader,
  MatchLineupsPlaceholder,
  MatchPlayerStatsPlaceholder,
  MatchTeamStatsPlaceholder,
  MatchTimelinePlaceholder,
} from "@/features/matches/components";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfileMetricTile,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
  ProfileTabs,
} from "@/shared/components/profile/ProfilePrimitives";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  buildCompetitionHubPath,
  buildMatchesPath,
  buildSeasonHubTabPath,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type MatchCenterContentProps = {
  matchId: string;
};

const MATCH_CENTER_TABS = ["summary", "timeline", "lineups", "team-stats", "player-stats"] as const;

type MatchCenterTab = (typeof MATCH_CENTER_TABS)[number];

function resolveMinuteLabel(event: MatchTimelineEvent): string {
  if (typeof event.minute === "number" && Number.isFinite(event.minute)) {
    return `${event.minute}'`;
  }

  return "Sem minuto";
}

function resolveEventTitle(event: MatchTimelineEvent): string {
  const playerName = event.playerName?.trim();
  const detail = event.detail?.trim();
  const type = event.type?.trim();

  if (playerName && detail) {
    return `${playerName} · ${detail}`;
  }

  if (playerName) {
    return playerName;
  }

  if (detail) {
    return detail;
  }

  return type?.length ? type : "Incidente sem detalhe";
}

function resolvePreviewPlayers(playerStats: MatchPlayerStat[]) {
  return [...playerStats]
    .sort((left, right) => {
      const rightRating = right.rating ?? Number.NEGATIVE_INFINITY;
      const leftRating = left.rating ?? Number.NEGATIVE_INFINITY;

      if (rightRating !== leftRating) {
        return rightRating - leftRating;
      }

      const rightGoals = right.goals ?? Number.NEGATIVE_INFINITY;
      const leftGoals = left.goals ?? Number.NEGATIVE_INFINITY;
      return rightGoals - leftGoals;
    })
    .slice(0, 3);
}

function resolveScoreSummary(
  homeScore: number | null | undefined,
  awayScore: number | null | undefined,
): string {
  const left =
    typeof homeScore === "number" && Number.isFinite(homeScore) ? String(homeScore) : "-";
  const right =
    typeof awayScore === "number" && Number.isFinite(awayScore) ? String(awayScore) : "-";
  return `${left} x ${right}`;
}

function isMatchCenterTab(value: string | null | undefined): value is MatchCenterTab {
  return typeof value === "string" && MATCH_CENTER_TABS.includes(value as MatchCenterTab);
}

function resolveMatchCenterTab(value: string | null | undefined): MatchCenterTab {
  return isMatchCenterTab(value) ? value : "summary";
}

function buildMatchCenterTabHref(
  pathname: string,
  searchParams: URLSearchParams | Readonly<Pick<URLSearchParams, "toString">>,
  tab: MatchCenterTab,
): string {
  const nextSearchParams = new URLSearchParams(searchParams.toString());

  if (tab === "summary") {
    nextSearchParams.delete("tab");
  } else {
    nextSearchParams.set("tab", tab);
  }

  const serialized = nextSearchParams.toString();
  return serialized.length > 0 ? `${pathname}?${serialized}` : pathname;
}

function resolveSectionCoverage(
  coverage: CoverageState | undefined,
  label: string,
): CoverageState {
  if (coverage) {
    return coverage;
  }

  return {
    status: "unknown",
    label,
  };
}

function resolveSectionDescription(tab: MatchCenterTab): string {
  if (tab === "timeline") {
    return "Lance a lance da partida, com atalhos para o jogador e o time quando houver contexto resolvido.";
  }

  if (tab === "lineups") {
    return "Escalações por time, com titulares, banco, posição e camisa quando esses dados estiverem disponíveis.";
  }

  if (tab === "team-stats") {
    return "Comparativo dos dois times com os principais números do jogo.";
  }

  if (tab === "player-stats") {
    return "Atuação individual dos jogadores nesta partida.";
  }

  return "Resumo do jogo com os principais lances, personagens e atalhos para aprofundar a análise.";
}

export function MatchCenterContent({ matchId }: MatchCenterContentProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { roundId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const activeTab = resolveMatchCenterTab(searchParams.get("tab"));
  const matchCenterQuery = useMatchCenter(matchId, {
    includeTimeline: true,
    includeLineups: true,
    includeTeamStats: true,
    includePlayerStats: true,
  });

  if (matchCenterQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Partida
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando partida
          </h1>
          <p className="text-sm text-[#57657a]">Os detalhes do jogo estão sendo preparados.</p>
        </header>
        <LoadingSkeleton height={120} />
        <LoadingSkeleton height={220} />
        <LoadingSkeleton height={220} />
        <LoadingSkeleton height={160} />
      </ProfileShell>
    );
  }

  if (matchCenterQuery.isError && !matchCenterQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Partida
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Partida indisponível
          </h1>
        </header>
        <ProfileAlert title="Não foi possível abrir esta partida" tone="critical">
          <p>Tente novamente em instantes ou volte para a lista de partidas.</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (matchCenterQuery.isEmpty || !matchCenterQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Partida
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Partida indisponível
          </h1>
        </header>
        <EmptyState
          description="Não foi possível encontrar dados suficientes para esta partida agora."
          title="Partida indisponível"
        />
      </ProfileShell>
    );
  }

  const { match, timeline, lineups, teamStats, playerStats, sectionCoverage } = matchCenterQuery.data;
  const competitionContext = resolveCompetitionSeasonContext({
    competitionId: match.competitionId,
    seasonId: match.seasonId,
  });
  const sharedContextInput = {
    competitionId: match.competitionId,
    seasonId: match.seasonId,
    roundId,
    venue,
    lastN: timeRangeParams.lastN,
    dateRangeStart: timeRangeParams.dateRangeStart,
    dateRangeEnd: timeRangeParams.dateRangeEnd,
  };
  const timelineEvents = timeline ?? [];
  const lineupPlayers = lineups ?? [];
  const teamStatsRows = teamStats ?? [];
  const playerStatsRows = playerStats ?? [];
  const incidentsPreview = timelineEvents.slice(0, 5);
  const previewPlayers = resolvePreviewPlayers(playerStatsRows);
  const startersCount = lineupPlayers.filter((player) => player.isStarter).length;
  const kickoffLabel = formatDate(match.kickoffAt);
  const seasonLabel = competitionContext?.seasonLabel ?? match.seasonId ?? "Temporada";
  const matchesHref = buildMatchesPath(sharedContextInput);
  const competitionHubHref = competitionContext
    ? buildCompetitionHubPath(competitionContext.competitionKey)
    : "/competitions";
  const seasonHubHref = competitionContext
    ? buildSeasonHubTabPath(competitionContext, "calendar", sharedContextInput)
    : null;
  const rankingsHref = competitionContext
    ? buildSeasonHubTabPath(competitionContext, "rankings", sharedContextInput)
    : null;
  const sectionStates: MatchCenterSectionCoverage = {
    timeline: resolveSectionCoverage(sectionCoverage?.timeline, "Linha do tempo"),
    lineups: resolveSectionCoverage(sectionCoverage?.lineups, "Escalações"),
    teamStats: resolveSectionCoverage(sectionCoverage?.teamStats, "Estatísticas dos times"),
    playerStats: resolveSectionCoverage(sectionCoverage?.playerStats, "Estatísticas dos jogadores"),
  };
  const tabLinks = [
    {
      key: "summary" as const,
      label: "Resumo",
      badge: "4 blocos",
    },
    {
      key: "timeline" as const,
      label: "Linha do tempo",
      badge: `${timelineEvents.length} eventos`,
    },
    {
      key: "lineups" as const,
      label: "Escalações",
      badge: `${lineupPlayers.length} atletas`,
    },
    {
      key: "team-stats" as const,
      label: "Times",
      badge: `${teamStatsRows.length} linhas`,
    },
    {
      key: "player-stats" as const,
      label: "Jogadores",
      badge: `${playerStatsRows.length} linhas`,
    },
  ];

  return (
    <ProfileShell className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#00513b]" href="/competitions">
          Competições
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#00513b]" href={competitionHubHref}>
          {match.competitionName ?? "Competição"}
        </Link>
        {seasonHubHref ? (
          <>
            <span className="text-[#8fa097]">/</span>
            <Link className="transition-colors hover:text-[#00513b]" href={seasonHubHref}>
              {seasonLabel}
            </Link>
          </>
        ) : null}
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#00513b]" href={matchesHref}>
          Partidas
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{match.homeTeamName ?? "Mandante"} x {match.awayTeamName ?? "Visitante"}</span>
      </div>

      <ProfilePanel className="space-y-6" tone="accent">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-white/65">
              Partida
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {match.competitionName ? (
                <ProfileTag className="bg-white/12 text-white/82">{match.competitionName}</ProfileTag>
              ) : null}
              {seasonLabel ? (
                <ProfileTag className="bg-white/12 text-white/82">{seasonLabel}</ProfileTag>
              ) : null}
            </div>
            <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-white md:text-5xl">
              {match.homeTeamName ?? "Mandante"} x {match.awayTeamName ?? "Visitante"}
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-white/74">
              Placar, principais lances, escalações e números do jogo em uma leitura única.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              className="button-pill button-pill-on-dark"
              href={matchesHref}
            >
              Voltar para partidas
            </Link>
            {seasonHubHref ? (
              <Link
                className="button-pill button-pill-on-dark"
                href={seasonHubHref}
              >
                Voltar para temporada
              </Link>
            ) : null}
            {rankingsHref ? (
              <Link
                className="button-pill button-pill-inverse"
                href={rankingsHref}
              >
                Rankings
              </Link>
            ) : null}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-5">
          <ProfileKpi hint={kickoffLabel} invert label="Placar" value={resolveScoreSummary(match.homeScore, match.awayScore)} />
          <ProfileKpi hint={kickoffLabel} invert label="Status" value={match.status?.trim() || "Sem status"} />
          <ProfileKpi hint={match.venueName?.trim() || "Local indisponível"} invert label="Local" value={match.venueName?.trim() || "Indisponível"} />
          <ProfileKpi hint={sectionStates.timeline?.label} invert label="Eventos" value={timelineEvents.length} />
          <ProfileKpi hint={sectionStates.playerStats?.label} invert label="Atletas" value={playerStatsRows.length} />
        </div>
      </ProfilePanel>

      <MatchCenterHeader contextInput={sharedContextInput} match={match} />

      {matchCenterQuery.isError ? (
        <ProfileAlert title="Alguns dados chegaram incompletos" tone="warning">
          <p>Parte da leitura da partida pode aparecer reduzida neste momento.</p>
        </ProfileAlert>
      ) : null}

      {matchCenterQuery.isPartial ? (
        <ProfileAlert title="Algumas áreas ainda estão incompletas" tone="warning">
          <p>Parte do detalhamento da partida ainda não está disponível.</p>
        </ProfileAlert>
      ) : null}

      <ProfileTabs
        ariaLabel="Abas da central da partida"
        items={tabLinks.map((tabLink) => ({
          key: tabLink.key,
          label: tabLink.label,
          href: buildMatchCenterTabHref(pathname, searchParams, tabLink.key),
          isActive: activeTab === tabLink.key,
          badge: tabLink.badge,
        }))}
      />

      <ProfilePanel className="flex flex-wrap items-center justify-between gap-3" tone="soft">
        <div className="space-y-1">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Seção ativa
          </p>
          <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            {tabLinks.find((tabLink) => tabLink.key === activeTab)?.label ?? "Resumo"}
          </h2>
        </div>
        <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
          {resolveSectionDescription(activeTab)}
        </p>
      </ProfilePanel>

      {activeTab === "summary" ? (
        <>
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <ProfilePanel className="space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    Principais lances
                  </p>
                  <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    O que marcou o jogo
                  </h2>
                </div>
                <ProfileTag>{timelineEvents.length} eventos</ProfileTag>
              </div>

              {incidentsPreview.length > 0 ? (
                <ol className="space-y-3">
                  {incidentsPreview.map((event, index) => (
                    <li
                      className="grid gap-3 rounded-[1.2rem] bg-[rgba(240,243,255,0.88)] px-4 py-3 md:grid-cols-[auto_1fr]"
                      key={event.eventId ?? `${event.type ?? "event"}-${index}`}
                    >
                      <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#003526] text-sm font-bold text-white">
                        {resolveMinuteLabel(event)}
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-[#111c2d]">
                          {resolveEventTitle(event)}
                        </p>
                        <p className="text-xs uppercase tracking-[0.16em] text-[#57657a]">
                          {[event.teamName, event.type].filter(Boolean).join(" · ") ||
                            "Sem detalhe adicional"}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="rounded-[1.2rem] bg-[rgba(240,243,255,0.88)] px-4 py-5 text-sm text-[#57657a]">
                  Nenhum incidente disponível para esta partida.
                </div>
              )}
            </ProfilePanel>

            <div className="grid gap-6">
              <ProfilePanel className="grid gap-4 md:grid-cols-2">
                <ProfileKpi
                  hint={kickoffLabel}
                  label="Placar atual"
                  value={resolveScoreSummary(match.homeScore, match.awayScore)}
                />
                <ProfileKpi
                  hint={match.venueName?.trim() || "Local indisponível"}
                  label="Status"
                  value={match.status?.trim() || "Sem status"}
                />
                <ProfileMetricTile label="Jogadores nas escalações" value={lineupPlayers.length} />
                <ProfileMetricTile label="Titulares detectados" value={startersCount || "-"} />
                <ProfileMetricTile label="Linhas de estatísticas" value={playerStatsRows.length} />
                <ProfileMetricTile label="Competição" value={match.competitionName?.trim() || "-"} />
              </ProfilePanel>

              <ProfilePanel className="space-y-4" tone="accent">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
                      Panorama da partida
                    </p>
                    <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-white">
                      Números disponíveis agora
                    </h2>
                  </div>
                  {matchCenterQuery.isPartial ? (
                    <ProfileCoveragePill coverage={matchCenterQuery.coverage} className="self-start" />
                  ) : null}
                </div>

                <div className="grid gap-3 md:grid-cols-4">
                  <ProfileKpi
                    hint={sectionStates.timeline?.label}
                    invert
                    label="Linha do tempo"
                    value={timelineEvents.length}
                  />
                  <ProfileKpi
                    hint={sectionStates.lineups?.label}
                    invert
                    label="Escalações"
                    value={lineupPlayers.length}
                  />
                  <ProfileKpi
                    hint={sectionStates.teamStats?.label}
                    invert
                    label="Times"
                    value={teamStatsRows.length}
                  />
                  <ProfileKpi
                    hint={sectionStates.playerStats?.label}
                    invert
                    label="Jogadores"
                    value={playerStatsRows.length}
                  />
                </div>

                <div className="space-y-3">
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/65">
                    Destaques do jogo
                  </p>
                  {previewPlayers.length > 0 ? (
                    <div className="grid gap-3">
                      {previewPlayers.map((player, index) => (
                        <div
                          className="flex flex-col gap-2 rounded-[1.2rem] bg-white/10 px-4 py-3 md:flex-row md:items-center md:justify-between"
                          key={player.playerId ?? `${player.playerName ?? "player"}-${index}`}
                        >
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {player.playerName?.trim() || "Atleta sem nome"}
                            </p>
                            <p className="text-xs uppercase tracking-[0.16em] text-white/60">
                              {[
                                player.teamName,
                                player.minutesPlayed ? `${player.minutesPlayed} min` : null,
                              ]
                                .filter(Boolean)
                                .join(" · ") || "Sem identificação complementar"}
                            </p>
                          </div>
                          <div className="flex items-center gap-5 text-sm text-white/85">
                            <span>Nota {player.rating?.toFixed(2) ?? "-"}</span>
                            <span>Gols {player.goals ?? 0}</span>
                            <span>Passes-chave {player.keyPasses ?? 0}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm leading-6 text-white/75">
                      Nenhum destaque adicional disponível para esta partida.
                    </p>
                  )}
                </div>
              </ProfilePanel>
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-4">
            <ProfilePanel className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    Lances
                  </p>
                  <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    Eventos e incidentes
                  </h2>
                </div>
                <ProfileCoveragePill coverage={sectionStates.timeline!} />
              </div>
              <p className="text-sm leading-6 text-[#57657a]">
                Lance a lance da partida, em ordem cronológica.
              </p>
              <Link
                className="button-pill button-pill-primary"
                href={buildMatchCenterTabHref(pathname, searchParams, "timeline")}
              >
                Ver linha do tempo
              </Link>
            </ProfilePanel>

            <ProfilePanel className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    Escalações
                  </p>
                  <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    Titulares e banco
                  </h2>
                </div>
                <ProfileCoveragePill coverage={sectionStates.lineups!} />
              </div>
              <p className="text-sm leading-6 text-[#57657a]">
                Escalações por time, com titulares e banco quando esses dados estiverem disponíveis.
              </p>
              <Link
                className="button-pill button-pill-primary"
                href={buildMatchCenterTabHref(pathname, searchParams, "lineups")}
              >
                Ver escalações
              </Link>
            </ProfilePanel>

            <ProfilePanel className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    Times
                  </p>
                  <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    Comparativo dos times
                  </h2>
                </div>
                <ProfileCoveragePill coverage={sectionStates.teamStats!} />
              </div>
              <p className="text-sm leading-6 text-[#57657a]">
                Posse, volume ofensivo, passe e disciplina lado a lado.
              </p>
              <Link
                className="button-pill button-pill-primary"
                href={buildMatchCenterTabHref(pathname, searchParams, "team-stats")}
              >
                Ver comparativo
              </Link>
            </ProfilePanel>

            <ProfilePanel className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    Jogadores
                  </p>
                  <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                    Atuação individual
                  </h2>
                </div>
                <ProfileCoveragePill coverage={sectionStates.playerStats!} />
              </div>
              <p className="text-sm leading-6 text-[#57657a]">
                Nomes, minutos, participações e nota dos jogadores no jogo.
              </p>
              <Link
                className="button-pill button-pill-primary"
                href={buildMatchCenterTabHref(pathname, searchParams, "player-stats")}
              >
                Ver jogadores
              </Link>
            </ProfilePanel>
          </section>
        </>
      ) : null}

      {activeTab === "timeline" ? (
        <MatchTimelinePlaceholder
          awayTeamId={match.awayTeamId}
          awayTeamName={match.awayTeamName}
          competitionContext={competitionContext}
          contextInput={sharedContextInput}
          coverage={sectionStates.timeline}
          events={timeline}
          homeTeamId={match.homeTeamId}
          homeTeamName={match.homeTeamName}
        />
      ) : null}

      {activeTab === "lineups" ? (
        <MatchLineupsPlaceholder
          awayTeamId={match.awayTeamId}
          awayTeamName={match.awayTeamName}
          competitionContext={competitionContext}
          contextInput={sharedContextInput}
          coverage={sectionStates.lineups}
          homeTeamId={match.homeTeamId}
          homeTeamName={match.homeTeamName}
          lineups={lineups}
        />
      ) : null}

      {activeTab === "player-stats" ? (
        <MatchPlayerStatsPlaceholder
          competitionContext={competitionContext}
          contextInput={sharedContextInput}
          coverage={sectionStates.playerStats}
          playerStats={playerStats}
        />
      ) : null}

      {activeTab === "team-stats" ? (
        <MatchTeamStatsPlaceholder
          awayTeamId={match.awayTeamId}
          awayTeamName={match.awayTeamName}
          coverage={sectionStates.teamStats}
          homeTeamId={match.homeTeamId}
          homeTeamName={match.homeTeamName}
          teamStats={teamStats}
        />
      ) : null}
    </ProfileShell>
  );
}
