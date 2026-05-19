import Link from "next/link";

import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";
import { ProfileAlert, ProfileKpi, ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";
import { formatDate, formatNumber } from "@/shared/utils/formatters";
import type { ApiResponseMeta } from "@/shared/types/api-response.types";

import type {
  WorldCup2022CompetitionHubData,
  WorldCup2022Fixture,
  WorldCup2022MatchEvent,
  WorldCup2022MatchViewData,
  WorldCup2022TeamFixture,
  WorldCup2022TeamViewData,
} from "@/features/world-cup-2022/types/world-cup-2022.types";

function buildWorldCupHubPath() {
  return "/competitions/world-cup-2022";
}

function buildWorldCupMatchPath(fixtureId: string) {
  return `/competitions/world-cup-2022/matches/${fixtureId}`;
}

function buildWorldCupTeamPath(teamId: string) {
  return `/competitions/world-cup-2022/teams/${teamId}`;
}

function resolveVenueCityLabel(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed.startsWith("{")) {
    return trimmed;
  }

  try {
    const parsed = JSON.parse(trimmed) as { name?: unknown };
    return typeof parsed.name === "string" && parsed.name.trim().length > 0 ? parsed.name.trim() : trimmed;
  } catch {
    return trimmed;
  }
}

function resolveScoreLabel(fixture: Pick<WorldCup2022Fixture, "homeGoals" | "awayGoals">): string {
  const homeGoals = typeof fixture.homeGoals === "number" ? fixture.homeGoals : "-";
  const awayGoals = typeof fixture.awayGoals === "number" ? fixture.awayGoals : "-";
  return `${homeGoals} x ${awayGoals}`;
}

function resolveEventClockLabel(event: WorldCup2022MatchEvent): string {
  if (typeof event.minute !== "number") {
    return "--";
  }

  const secondValue =
    typeof event.second === "number" && Number.isFinite(event.second)
      ? String(Math.floor(event.second)).padStart(2, "0")
      : "00";

  return `${event.minute}' ${secondValue}s`;
}

function SectionHeading({
  eyebrow,
  title,
  description,
  aside,
}: {
  eyebrow: string;
  title: string;
  description: string;
  aside?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
          {eyebrow}
        </p>
        <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
          {title}
        </h2>
        <p className="max-w-3xl text-sm leading-7 text-[#57657a]">{description}</p>
      </div>
      {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
    </div>
  );
}

function Breadcrumbs({ items }: { items: Array<{ href?: string; label: string }> }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
      {items.map((item, index) => (
        <div className="contents" key={`${item.label}-${index}`}>
          {index > 0 ? <span className="text-[#8fa097]">/</span> : null}
          {item.href ? (
            <Link className="transition-colors hover:text-[#00513b]" href={item.href}>
              {item.label}
            </Link>
          ) : (
            <span>{item.label}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function FixtureListItem({
  fixture,
  showOpponentContext = false,
}: {
  fixture: WorldCup2022Fixture | WorldCup2022TeamFixture;
  showOpponentContext?: boolean;
}) {
  const venueCity = resolveVenueCityLabel(fixture.venueCity);
  const opponentFixture = fixture as WorldCup2022TeamFixture;

  return (
    <article className="rounded-[1.25rem] border border-white/70 bg-white/76 p-4 shadow-[0_24px_54px_-44px_rgba(17,28,45,0.22)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileTag>{fixture.stageName ?? "Stage"}</ProfileTag>
            {fixture.groupName ? (
              <ProfileTag className="bg-[rgba(166,242,209,0.5)] text-[#00513b]">{fixture.groupName}</ProfileTag>
            ) : null}
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              {formatDate(fixture.kickoffAt)}
            </span>
          </div>
          <Link
            className="inline-flex items-center gap-2 font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d] hover:text-[#00513b]"
            href={buildWorldCupMatchPath(fixture.fixtureId)}
          >
            <span>{fixture.homeTeamName ?? "Mandante"}</span>
            <span className="text-[#57657a]">{resolveScoreLabel(fixture)}</span>
            <span>{fixture.awayTeamName ?? "Visitante"}</span>
          </Link>
          {showOpponentContext ? (
            <p className="text-sm text-[#57657a]">
              {opponentFixture.venueRole === "home" ? "Mandante" : "Visitante"} contra{" "}
              <Link
                className="font-semibold text-[#00513b] hover:underline"
                href={buildWorldCupTeamPath(opponentFixture.opponentTeamId)}
              >
                {opponentFixture.opponentTeamName ?? "Adversário"}
              </Link>
            </p>
          ) : null}
        </div>
        <div className="space-y-1 text-right text-sm text-[#57657a]">
          <p>{fixture.venueName ?? "Sem estádio"}</p>
          {venueCity ? <p>{venueCity}</p> : null}
          {fixture.referee ? <p>Árbitro: {fixture.referee}</p> : null}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <Link className="font-semibold text-[#00513b] hover:underline" href={buildWorldCupTeamPath(fixture.homeTeamId)}>
          {fixture.homeTeamName ?? "Mandante"}
        </Link>
        <span className="text-[#8fa097]">vs</span>
        <Link className="font-semibold text-[#00513b] hover:underline" href={buildWorldCupTeamPath(fixture.awayTeamId)}>
          {fixture.awayTeamName ?? "Visitante"}
        </Link>
      </div>
    </article>
  );
}

function EventRow({ event }: { event: WorldCup2022MatchEvent }) {
  return (
    <tr className="border-b border-[rgba(191,201,195,0.35)] align-top last:border-b-0">
      <td className="px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-[#57657a]">
        {resolveEventClockLabel(event)}
      </td>
      <td className="px-3 py-3 text-sm font-semibold text-[#111c2d]">{event.eventType ?? "-"}</td>
      <td className="px-3 py-3 text-sm text-[#404944]">{event.team.teamName ?? "-"}</td>
      <td className="px-3 py-3 text-sm text-[#404944]">{event.player.playerName ?? "-"}</td>
      <td className="px-3 py-3 text-sm text-[#57657a]">
        <div className="space-y-1">
          {event.outcomeLabel ? <p>Resultado: {event.outcomeLabel}</p> : null}
          {event.playPatternLabel ? <p>Padrão: {event.playPatternLabel}</p> : null}
          <p>Fonte: {event.sourceName ?? "-"}</p>
        </div>
      </td>
    </tr>
  );
}

export function WorldCup2022ErrorState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <ProfileShell className="space-y-6">
      <Breadcrumbs
        items={[
          { href: "/competitions", label: "Competições" },
          { href: buildWorldCupHubPath(), label: "World Cup 2022" },
          { label: "Indisponível" },
        ]}
      />
      <ProfileAlert title={title} tone="critical">
        {description}
      </ProfileAlert>
    </ProfileShell>
  );
}

export function WorldCup2022CompetitionHubView({
  data,
  meta,
}: {
  data: WorldCup2022CompetitionHubData;
  meta?: ApiResponseMeta;
}) {
  return (
    <ProfileShell className="space-y-6">
      <Breadcrumbs
        items={[
          { href: "/competitions", label: "Competições" },
          { label: "World Cup 2022" },
        ]}
      />

      <ProfilePanel tone="accent">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.8fr)_minmax(18rem,0.95fr)]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/12 text-white">Copa 2022</ProfileTag>
              {meta?.coverage ? (
                <CoverageBadge className="border-white/10 bg-white/10 text-white" coverage={meta.coverage} />
              ) : null}
            </div>
            <div className="space-y-3">
              <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.05em] text-white md:text-5xl">
                {data.competition.seasonName}
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-white/78">
                Hub inicial da Copa 2022 consumindo o BFF dedicado. Fixtures e grupos publicados sem depender de estatísticas derivadas.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <ProfileKpi hint="Partidas publicadas no recorte." invert label="Fixtures" value={formatNumber(data.fixtures.length)} />
            <ProfileKpi hint="Grupos finais publicados." invert label="Grupos" value={formatNumber(data.standings.groupCount)} />
            <ProfileKpi hint="Linhas finais de classificação." invert label="Standings" value={formatNumber(data.standings.rowCount)} />
          </div>
        </div>
      </ProfilePanel>
 
      <ProfilePanel tone="base" className="space-y-4">
        <SectionHeading
          aside={<ProfileTag>{data.fixtures.length} partidas</ProfileTag>}
          description="Calendário completo do recorte 2022. Cada card leva para a visão detalhada da partida e para as páginas das seleções."
          eyebrow="Competition hub"
          title="Fixtures"
        />
        <div className="grid gap-3">
          {data.fixtures.map((fixture) => (
            <FixtureListItem fixture={fixture} key={fixture.fixtureId} />
          ))}
        </div>
      </ProfilePanel>

      <ProfilePanel tone="soft" className="space-y-4">
        <SectionHeading
          aside={<ProfileTag>{data.standings.groupCount} grupos</ProfileTag>}
          description="Classificação final por grupo, preservando o grão próprio de standings sem misturar com fixtures."
          eyebrow="Standings"
          title="Tabela por grupo"
        />
        <div className="grid gap-4 xl:grid-cols-2">
          {data.standings.groups.map((group) => (
            <article className="rounded-[1.35rem] border border-white/70 bg-white/78 p-4" key={group.groupKey}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                    {group.stageKey ?? "group_stage_1"}
                  </p>
                  <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                    {group.groupName}
                  </h3>
                </div>
                <ProfileTag>{group.rows.length} seleções</ProfileTag>
              </div>
              <div className="overflow-hidden rounded-[1rem] border border-[rgba(191,201,195,0.34)]">
                <table className="min-w-full border-collapse">
                  <thead className="bg-[rgba(240,243,255,0.82)] text-left text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                    <tr>
                      <th className="px-3 py-3">Pos</th>
                      <th className="px-3 py-3">Seleção</th>
                      <th className="px-3 py-3">Pts</th>
                      <th className="px-3 py-3">J</th>
                      <th className="px-3 py-3">SG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.rows.map((row) => (
                      <tr className="border-t border-[rgba(191,201,195,0.34)] text-sm text-[#404944]" key={`${group.groupKey}-${row.teamId}`}>
                        <td className="px-3 py-3 font-semibold text-[#111c2d]">{row.position}</td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <Link className="font-semibold text-[#00513b] hover:underline" href={buildWorldCupTeamPath(row.teamId)}>
                              {row.teamName ?? row.teamCode ?? row.teamId}
                            </Link>
                            {row.advanced ? (
                              <span className="rounded-full bg-[#a6f2d1] px-2 py-0.5 text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#00513b]">
                                Qualificada
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-3">{row.points}</td>
                        <td className="px-3 py-3">{row.matchesPlayed}</td>
                        <td className="px-3 py-3">{row.goalDiff}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ))}
        </div>
      </ProfilePanel>
    </ProfileShell>
  );
}

export function WorldCup2022MatchView({
  data,
  meta,
}: {
  data: WorldCup2022MatchViewData;
  meta?: ApiResponseMeta;
}) {
  const fixture = data.fixture;
  const venueCity = resolveVenueCityLabel(fixture.venueCity);

  return (
    <ProfileShell className="space-y-6">
      <Breadcrumbs
        items={[
          { href: "/competitions", label: "Competições" },
          { href: buildWorldCupHubPath(), label: "World Cup 2022" },
          { label: fixture.fixtureId },
        ]}
      />

      <ProfilePanel tone="accent">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.8fr)_minmax(18rem,0.95fr)]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/12 text-white">{fixture.stageName ?? "Stage"}</ProfileTag>
              {fixture.groupName ? <ProfileTag className="bg-white/12 text-white">{fixture.groupName}</ProfileTag> : null}
              {meta?.coverage ? (
                <CoverageBadge className="border-white/10 bg-white/10 text-white" coverage={meta.coverage} />
              ) : null}
            </div>
            <div className="space-y-3">
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.05em] text-white md:text-5xl">
                {fixture.homeTeamName} <span className="text-white/72">{resolveScoreLabel(fixture)}</span> {fixture.awayTeamName}
              </h1>
              <p className="text-sm leading-7 text-white/78">
                {formatDate(fixture.kickoffAt)} · {fixture.venueName ?? "Sem estádio"}
                {venueCity ? ` · ${venueCity}` : ""}
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <ProfileKpi hint="Grupos de lineup retornados pela BFF." invert label="Times em lineup" value={formatNumber(data.lineups.length)} />
            <ProfileKpi hint="Eventos observacionais publicados na Copa." invert label="Eventos" value={formatNumber(data.events.length)} />
            <ProfileKpi hint="Fonte estrutural do fixture." invert label="Provider" value={fixture.sourceProvider ?? "-"} />
          </div>
        </div>
      </ProfilePanel>
 
      <ProfilePanel tone="base" className="space-y-4">
        <SectionHeading
          aside={
            <div className="flex flex-wrap items-center gap-2">
              <CoverageBadge coverage={data.sectionCoverage.lineups} />
              <ProfileTag>{data.lineups.length} times</ProfileTag>
            </div>
          }
          description="Escalações consumidas diretamente do BFF da Copa, separando titulares e banco sem derivação adicional."
          eyebrow="Match view"
          title="Lineups"
        />
        <div className="grid gap-4 xl:grid-cols-2">
          {data.lineups.map((teamLineup) => (
            <article className="rounded-[1.35rem] border border-white/70 bg-white/76 p-4" key={teamLineup.teamId}>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Seleção</p>
                  <Link className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#111c2d] hover:text-[#00513b]" href={buildWorldCupTeamPath(teamLineup.teamId)}>
                    {teamLineup.teamName ?? teamLineup.teamId}
                  </Link>
                </div>
                <ProfileTag>{teamLineup.starters.length} titulares</ProfileTag>
              </div>
              <div className="grid gap-4">
                <div>
                  <p className="mb-2 text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Titulares</p>
                  <ul className="space-y-2">
                    {teamLineup.starters.map((player) => (
                      <li className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] px-3 py-2 text-sm" key={player.lineupId}>
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold text-[#111c2d]">{player.playerName ?? player.playerInternalId ?? player.playerId}</p>
                            <p className="text-xs text-[#57657a]">{player.positionName ?? "Sem posição"}</p>
                          </div>
                          <div className="text-right text-xs text-[#57657a]">
                            {player.jerseyNumber ? <p>#{player.jerseyNumber}</p> : null}
                            {player.formationPosition ? <p>Pos. {player.formationPosition}</p> : null}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-2 text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Banco</p>
                  <div className="flex flex-wrap gap-2">
                    {teamLineup.bench.map((player) => (
                      <span className="rounded-full border border-[rgba(191,201,195,0.34)] bg-[rgba(240,243,255,0.76)] px-3 py-1 text-sm text-[#404944]" key={player.lineupId}>
                        {player.playerName ?? player.playerInternalId ?? player.playerId}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </ProfilePanel>

      <ProfilePanel tone="soft" className="space-y-4">
        <SectionHeading
          aside={
            <div className="flex flex-wrap items-center gap-2">
              <CoverageBadge coverage={data.sectionCoverage.events} />
              <ProfileTag>{formatNumber(data.events.length)} eventos</ProfileTag>
            </div>
          }
          description="Eventos publicados no contrato da Copa, navegáveis por fixture e sem depender de `raw.match_events`."
          eyebrow="Event stream"
          title="Eventos"
        />
        <div className="overflow-hidden rounded-[1.25rem] border border-[rgba(191,201,195,0.34)] bg-white/76">
          <div className="max-h-[42rem] overflow-auto">
            <table className="min-w-full border-collapse">
              <thead className="sticky top-0 bg-[rgba(240,243,255,0.96)] text-left text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                <tr>
                  <th className="px-3 py-3">Relógio</th>
                  <th className="px-3 py-3">Evento</th>
                  <th className="px-3 py-3">Seleção</th>
                  <th className="px-3 py-3">Jogador</th>
                  <th className="px-3 py-3">Contexto</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <EventRow event={event} key={event.sourceEventId ?? `${event.fixtureId}-${event.eventIndex}`} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </ProfilePanel>
    </ProfileShell>
  );
}

export function WorldCup2022TeamView({
  data,
  meta,
}: {
  data: WorldCup2022TeamViewData;
  meta?: ApiResponseMeta;
}) {
  return (
    <ProfileShell className="space-y-6">
      <Breadcrumbs
        items={[
          { href: "/competitions", label: "Competições" },
          { href: buildWorldCupHubPath(), label: "World Cup 2022" },
          { label: data.team.teamName ?? data.team.teamId },
        ]}
      />

      <ProfilePanel tone="accent">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.8fr)_minmax(18rem,0.95fr)]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/12 text-white">Seleção</ProfileTag>
              {meta?.coverage ? (
                <CoverageBadge className="border-white/10 bg-white/10 text-white" coverage={meta.coverage} />
              ) : null}
            </div>
            <div className="space-y-3">
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.05em] text-white md:text-5xl">
                {data.team.teamName ?? data.team.teamId}
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-white/78">
                Visão da seleção no recorte da Copa 2022, com coach source-scoped e calendário completo publicado.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <ProfileKpi hint="Partidas retornadas no recorte 2022." invert label="Partidas" value={formatNumber(data.team.matchesPlayed)} />
            <ProfileKpi hint="Cobertura da seção de coach." invert label="Coach" value={data.coach ? "Sim" : "Não"} />
            <ProfileKpi hint="Fixtures publicadas para a seleção." invert label="Fixtures" value={formatNumber(data.fixtures.length)} />
          </div>
        </div>
      </ProfilePanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1.8fr)]">
        <ProfilePanel tone="base" className="space-y-4">
          <SectionHeading
            aside={<CoverageBadge coverage={data.sectionCoverage.coach} />}
            description="Coach publicado apenas no escopo da nomeação da Copa 2022. Não há identidade global de coach nesta superfície."
            eyebrow="Coach"
            title="Comando técnico"
          />
          {data.coach ? (
            <div className="space-y-3 rounded-[1.25rem] border border-white/70 bg-white/76 p-4">
              <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
                {data.coach.fullName ?? data.coach.coachSourceScopedId ?? "Coach"}
              </p>
              <div className="grid gap-2 text-sm text-[#404944]">
                {data.coach.countryName ? <p>País: {data.coach.countryName}</p> : null}
                {data.coach.coachSourceScopedId ? <p>ID source-scoped: {data.coach.coachSourceScopedId}</p> : null}
                {data.coach.identityScope ? <p>Escopo de identidade: {data.coach.identityScope}</p> : null}
                {data.coach.tenureScope ? <p>Escopo de tenure: {data.coach.tenureScope}</p> : null}
              </div>
            </div>
          ) : (
            <ProfileAlert title="Coach indisponível" tone="warning">
              Nenhum coach publicado para esta seleção no recorte 2022.
            </ProfileAlert>
          )}
        </ProfilePanel>

        <ProfilePanel tone="soft" className="space-y-4">
          <SectionHeading
            aside={<CoverageBadge coverage={data.sectionCoverage.fixtures} />}
            description="Calendário da seleção no torneio, usando o mesmo `teamId` publicado no raw da wave da Copa."
            eyebrow="Fixtures"
            title="Campanha no torneio"
          />
          <div className="grid gap-3">
            {data.fixtures.map((fixture) => (
              <FixtureListItem fixture={fixture} key={fixture.fixtureId} showOpponentContext />
            ))}
          </div>
        </ProfilePanel>
      </div>
    </ProfileShell>
  );
}
