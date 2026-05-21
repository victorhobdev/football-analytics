"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileKpi, ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { useWorldCupRankings } from "@/features/world-cup/hooks/useWorldCupRankings";
import {
  buildWorldCupEditionPath,
  buildWorldCupHubPath,
  buildWorldCupTeamPath,
} from "@/features/world-cup/routes";

const PLAYER_CARD_PAGE_SIZE = 12;
const SECTION_CARD_LIMIT = 8;
const MATCH_RECORDS_LIMIT = 6;

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function RankingCard({
  title,
  metricLabel,
  children,
  footer,
}: {
  title: string;
  metricLabel: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <article className="rounded-[1.4rem] border border-[rgba(191,201,195,0.42)] bg-white/82 p-4">
      <header className="space-y-1">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{metricLabel}</p>
        <h3 className="font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
          {title}
        </h3>
      </header>

      <div className="mt-4 space-y-3">{children}</div>
      {footer ? <div className="mt-4">{footer}</div> : null}
    </article>
  );
}

function RankingListRow({
  rank,
  title,
  href,
  subtitle,
  meta,
  metricLabel,
  metricValue,
}: {
  rank: number;
  title: ReactNode;
  href?: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  metricLabel: string;
  metricValue: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">#{rank}</p>
        {href ? (
          <Link
            className="block truncate font-[family:var(--font-profile-headline)] text-[1.2rem] font-extrabold tracking-[-0.03em] text-[#111c2d] transition-colors hover:text-[#003526]"
            href={href}
          >
            {title}
          </Link>
        ) : (
          <p className="truncate font-[family:var(--font-profile-headline)] text-[1.2rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
            {title}
          </p>
        )}
        {subtitle ? <div className="text-sm/6 text-[#57657a]">{subtitle}</div> : null}
        {meta ? <div className="flex flex-wrap gap-2">{meta}</div> : null}
      </div>

      <div className="shrink-0 rounded-[0.95rem] border border-[rgba(191,201,195,0.34)] bg-white px-3 py-2 text-right">
        <p className="text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">{metricLabel}</p>
        <p className="mt-1 font-[family:var(--font-profile-headline)] text-[1.5rem] font-extrabold leading-none text-[#111c2d]">
          {metricValue}
        </p>
      </div>
    </div>
  );
}

function ChipLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      className="inline-flex items-center rounded-full border border-[rgba(191,201,195,0.42)] bg-white px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[#455468] transition-colors hover:border-[#8bd6b6] hover:text-[#003526]"
      href={href}
    >
      {children}
    </Link>
  );
}

function LoadMoreButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="inline-flex items-center rounded-full bg-[#003526] px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-white transition-colors hover:bg-[#00513b]"
      onClick={onClick}
      type="button"
    >
      Mostrar mais
    </button>
  );
}

function TeamLink({ teamId, teamName }: { teamId: string | null | undefined; teamName: string | null | undefined }) {
  if (teamId && teamName) {
    return (
      <Link className="font-semibold text-[#003526] transition-colors hover:text-[#00513b]" href={buildWorldCupTeamPath(teamId)}>
        {teamName}
      </Link>
    );
  }

  return <span>{teamName ?? "Seleção não identificada"}</span>;
}

export function WorldCupRankingsContent() {
  const rankingsQuery = useWorldCupRankings();
  const [visibleScorers, setVisibleScorers] = useState(PLAYER_CARD_PAGE_SIZE);
  const [visibleSquadAppearances, setVisibleSquadAppearances] = useState(PLAYER_CARD_PAGE_SIZE);

  if (rankingsQuery.isLoading && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando os rankings históricos da Copa do Mundo."
        kicker="Copa do Mundo"
        loading
        title="Carregando rankings históricos"
      />
    );
  }

  if (rankingsQuery.isError && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="Não foi possível carregar os rankings históricos agora."
        kicker="Copa do Mundo"
        title="Falha ao abrir rankings"
        tone="critical"
      />
    );
  }

  if (!rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="A vertical não retornou dados suficientes para montar os rankings."
        kicker="Copa do Mundo"
        title="Rankings indisponíveis"
        tone="warning"
      />
    );
  }

  const { editionRankings, matchRankings, playerRankings, teamRankings } = rankingsQuery.data;
  const scorersToRender = playerRankings.scorers.items.slice(0, visibleScorers);
  const squadAppearancesToRender = playerRankings.squadAppearances.items.slice(0, visibleSquadAppearances);
  const squadAppearancesLabel = `${playerRankings.squadAppearances.minimumAppearancesCount}+ Copas`;

  return (
    <ProfileShell className="world-cup-theme space-y-6" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Início
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupHubPath()}>
          Copa do Mundo
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>Rankings</span>
      </div>

      <ProfilePanel className="world-cup-hero space-y-6" tone="accent">
        <div className="flex flex-wrap items-center gap-2">
          <ProfileTag className="world-cup-hero-tag">Seleções</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Edições</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Jogadores</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Recordes</ProfileTag>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)] xl:items-end">
          <div className="space-y-4">
            <h1 className="font-[family:var(--font-profile-headline)] text-[2.8rem] font-extrabold leading-none tracking-[-0.07em] text-white md:text-[3.5rem]">
              Rankings históricos
            </h1>
            <p className="max-w-2xl text-sm/6 text-white/78 md:text-[0.96rem]/7">
              Seleções, edições, jogadores e recordes em um só recorte.
            </p>
          </div>

          <aside className="grid gap-3 sm:grid-cols-2">
            <ProfileKpi invert label="Seleções" value={formatWholeNumber(teamRankings.wins.items.length)} />
            <ProfileKpi invert label="Edições" value={formatWholeNumber(editionRankings.goals.items.length)} />
            <ProfileKpi invert label="Artilheiros" value={formatWholeNumber(playerRankings.scorers.items.length)} />
            <ProfileKpi invert label={squadAppearancesLabel} value={formatWholeNumber(playerRankings.squadAppearances.items.length)} />
          </aside>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Seleções</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            Lideranças históricas
          </h2>
          <p className="max-w-3xl text-sm/6 text-[#57657a]">
            Vitórias, jogos, gols e top 4. Alemanha já sai agregada com Germany + West Germany.
          </p>
        </header>

        <div className="grid gap-4 xl:grid-cols-2">
          <RankingCard metricLabel={teamRankings.titles.metricLabel} title={teamRankings.titles.label}>
            {teamRankings.titles.items.slice(0, SECTION_CARD_LIMIT).map((team) => (
              <RankingListRow
                href={buildWorldCupTeamPath(team.teamId)}
                key={`${teamRankings.titles.label}-${team.teamId}`}
                metricLabel="Títulos"
                metricValue={formatWholeNumber(team.titlesCount)}
                rank={team.rank}
                subtitle={`${formatWholeNumber(team.finalsCount)} finais · ${formatWholeNumber(team.participationsCount)} Copas`}
                title={team.teamName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <RankingCard metricLabel={teamRankings.wins.metricLabel} title={teamRankings.wins.label}>
            {teamRankings.wins.items.slice(0, SECTION_CARD_LIMIT).map((team) => (
              <RankingListRow
                href={buildWorldCupTeamPath(team.teamId)}
                key={`${teamRankings.wins.label}-${team.teamId}`}
                metricLabel="Vitórias"
                metricValue={formatWholeNumber(team.wins)}
                rank={team.rank}
                subtitle={`${formatWholeNumber(team.matches)} jogos`}
                title={team.teamName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <RankingCard metricLabel={teamRankings.matches.metricLabel} title={teamRankings.matches.label}>
            {teamRankings.matches.items.slice(0, SECTION_CARD_LIMIT).map((team) => (
              <RankingListRow
                href={buildWorldCupTeamPath(team.teamId)}
                key={`${teamRankings.matches.label}-${team.teamId}`}
                metricLabel="Jogos"
                metricValue={formatWholeNumber(team.matches)}
                rank={team.rank}
                subtitle={`${formatWholeNumber(team.wins)} vitórias`}
                title={team.teamName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <RankingCard metricLabel={teamRankings.goalsScored.metricLabel} title={teamRankings.goalsScored.label}>
            {teamRankings.goalsScored.items.slice(0, SECTION_CARD_LIMIT).map((team) => (
              <RankingListRow
                href={buildWorldCupTeamPath(team.teamId)}
                key={`${teamRankings.goalsScored.label}-${team.teamId}`}
                metricLabel="Gols"
                metricValue={formatWholeNumber(team.goalsScored)}
                rank={team.rank}
                subtitle={`${formatWholeNumber(team.matches)} jogos`}
                title={team.teamName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <div className="xl:col-span-2">
            <RankingCard metricLabel={teamRankings.topFourAppearances.metricLabel} title={teamRankings.topFourAppearances.label}>
              {teamRankings.topFourAppearances.items.slice(0, SECTION_CARD_LIMIT).map((team) => (
                <RankingListRow
                  href={buildWorldCupTeamPath(team.teamId)}
                  key={`${teamRankings.topFourAppearances.label}-${team.teamId}`}
                  metricLabel="Top 4"
                  metricValue={formatWholeNumber(team.topFourCount)}
                  rank={team.rank}
                  subtitle={`${formatWholeNumber(team.titlesCount)} títulos`}
                  title={team.teamName ?? "Não identificado"}
                />
              ))}
            </RankingCard>
          </div>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Edições</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            Gols por Copa
          </h2>
          <p className="max-w-3xl text-sm/6 text-[#57657a]">Duas leituras diretas: volume total e média por jogo.</p>
        </header>

        <div className="grid gap-4 xl:grid-cols-2">
          <RankingCard metricLabel={editionRankings.goalsPerMatch.metricLabel} title={editionRankings.goalsPerMatch.label}>
            {editionRankings.goalsPerMatch.items.slice(0, SECTION_CARD_LIMIT).map((edition) => (
              <RankingListRow
                href={buildWorldCupEditionPath(edition.seasonLabel)}
                key={`${editionRankings.goalsPerMatch.label}-${edition.seasonLabel}`}
                metricLabel="Média"
                metricValue={formatDecimal(edition.goalsPerMatch)}
                rank={edition.rank}
                subtitle={`${formatWholeNumber(edition.goalsCount)} gols em ${formatWholeNumber(edition.matchesCount)} jogos`}
                title={edition.year}
              />
            ))}
          </RankingCard>

          <RankingCard metricLabel={editionRankings.goals.metricLabel} title={editionRankings.goals.label}>
            {editionRankings.goals.items.slice(0, SECTION_CARD_LIMIT).map((edition) => (
              <RankingListRow
                href={buildWorldCupEditionPath(edition.seasonLabel)}
                key={`${editionRankings.goals.label}-${edition.seasonLabel}`}
                metricLabel="Gols"
                metricValue={formatWholeNumber(edition.goalsCount)}
                rank={edition.rank}
                subtitle={`${formatDecimal(edition.goalsCount / edition.matchesCount)} por jogo`}
                title={edition.year}
              />
            ))}
          </RankingCard>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Jogadores</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            Artilharia e longevidade
          </h2>
          <p className="max-w-3xl text-sm/6 text-[#57657a]">Dois recortes fortes: gols e presença recorrente em elencos.</p>
        </header>

        <div className="grid gap-4 xl:grid-cols-2">
          <RankingCard
            footer={
              visibleScorers < playerRankings.scorers.items.length ? (
                <LoadMoreButton onClick={() => setVisibleScorers((current) => current + PLAYER_CARD_PAGE_SIZE)} />
              ) : null
            }
            metricLabel={playerRankings.scorers.metricLabel}
            title="Jogadores com 3+ gols"
          >
            {scorersToRender.map((scorer) => (
              <RankingListRow
                key={`${scorer.playerId ?? scorer.playerName ?? "scorer"}-${scorer.rank}`}
                metricLabel="Gols"
                metricValue={formatWholeNumber(scorer.goals)}
                meta={scorer.editions.map((edition) => (
                  <ChipLink href={buildWorldCupEditionPath(edition.seasonLabel)} key={`${scorer.playerId ?? scorer.playerName ?? "scorer"}-${edition.seasonLabel}`}>
                    {edition.year} · {edition.goals}
                  </ChipLink>
                ))}
                rank={scorer.rank}
                subtitle={<TeamLink teamId={scorer.teamId} teamName={scorer.teamName} />}
                title={scorer.playerName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <RankingCard
            footer={
              visibleSquadAppearances < playerRankings.squadAppearances.items.length ? (
                <LoadMoreButton onClick={() => setVisibleSquadAppearances((current) => current + PLAYER_CARD_PAGE_SIZE)} />
              ) : null
            }
            metricLabel={playerRankings.squadAppearances.metricLabel}
            title={`Jogadores com ${squadAppearancesLabel.toLowerCase()} no elenco`}
          >
            {squadAppearancesToRender.map((player) => (
              <RankingListRow
                key={`${player.playerId}-${player.rank}`}
                metricLabel="Copas"
                metricValue={formatWholeNumber(player.appearancesCount)}
                meta={player.editions.map((edition) => (
                  <ChipLink href={buildWorldCupEditionPath(edition.seasonLabel)} key={`${player.playerId}-${edition.seasonLabel}`}>
                    {edition.year}
                  </ChipLink>
                ))}
                rank={player.rank}
                subtitle={<TeamLink teamId={player.teamId} teamName={player.teamName} />}
                title={player.playerName ?? "Não identificado"}
              />
            ))}
          </RankingCard>
        </div>
      </ProfilePanel>

      {matchRankings.highestScoringFinals.items.length > 0 || matchRankings.biggestWins.items.length > 0 ? (
        <ProfilePanel className="space-y-5" tone="base">
          <header className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Recordes de partidas</p>
            <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
              Jogos que mais marcaram a história
            </h2>
            <p className="max-w-3xl text-sm/6 text-[#57657a]">Finais mais abertas e placares mais largos do torneio.</p>
          </header>

          <div className="grid gap-4 xl:grid-cols-2">
            <RankingCard metricLabel={matchRankings.highestScoringFinals.metricLabel} title={matchRankings.highestScoringFinals.label}>
              {matchRankings.highestScoringFinals.items.slice(0, MATCH_RECORDS_LIMIT).map((match) => (
                <RankingListRow
                  href={buildWorldCupEditionPath(match.seasonLabel)}
                  key={`${match.seasonLabel}-final`}
                  metricLabel="Gols"
                  metricValue={formatWholeNumber(match.totalGoals)}
                  rank={match.rank}
                  subtitle={
                    <>
                      {match.homeTeam?.teamName ?? "Não identificado"} {formatWholeNumber(match.homeScore)} x{" "}
                      {formatWholeNumber(match.awayScore)} {match.awayTeam?.teamName ?? "Não identificado"}
                    </>
                  }
                  title={match.year}
                />
              ))}
            </RankingCard>

            <RankingCard metricLabel={matchRankings.biggestWins.metricLabel} title={matchRankings.biggestWins.label}>
              {matchRankings.biggestWins.items.slice(0, MATCH_RECORDS_LIMIT).map((match) => (
                <RankingListRow
                  href={buildWorldCupEditionPath(match.seasonLabel)}
                  key={match.fixtureId}
                  metricLabel="Saldo"
                  metricValue={formatWholeNumber(match.goalDiff)}
                  rank={match.rank}
                  subtitle={
                    <>
                      {match.homeTeam?.teamName ?? "Não identificado"} {formatWholeNumber(match.homeScore)} x{" "}
                      {formatWholeNumber(match.awayScore)} {match.awayTeam?.teamName ?? "Não identificado"}
                    </>
                  }
                  title={match.year}
                />
              ))}
            </RankingCard>
          </div>
        </ProfilePanel>
      ) : null}
    </ProfileShell>
  );
}
