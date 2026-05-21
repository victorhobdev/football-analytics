"use client";

import Link from "next/link";

import { usePathname, useSearchParams } from "next/navigation";

import { useTeamMatches } from "@/features/teams/hooks/useTeamMatches";
import { useTeamProfile } from "@/features/teams/hooks/useTeamProfile";
import { TeamJourneySection } from "@/features/teams/components/TeamJourneySection";
import { TeamHonorsSection } from "@/features/teams/components/TeamHonorsSection";
import { TeamMatchesSection } from "@/features/teams/components/TeamMatchesSection";
import { TeamOverviewSection } from "@/features/teams/components/TeamOverviewSection";
import { TeamSquadSection } from "@/features/teams/components/TeamSquadSection";
import { TeamStatsSection } from "@/features/teams/components/TeamStatsSection";
import type { TeamHonorsPreview } from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
  ProfileTabs,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  buildHeadToHeadPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type TeamProfileContentProps = {
  teamId: string;
  contextOverride: CompetitionSeasonContext;
  honorsPreview?: TeamHonorsPreview | null;
};

const TEAM_PROFILE_TABS = ["overview", "journey", "squad", "matches", "stats"] as const;
type TeamProfileTab = (typeof TEAM_PROFILE_TABS)[number];

function isTeamProfileTab(value: string | null | undefined): value is TeamProfileTab {
  return typeof value === "string" && TEAM_PROFILE_TABS.includes(value as TeamProfileTab);
}

function resolveTeamProfileTab(value: string | null | undefined): TeamProfileTab {
  return isTeamProfileTab(value) ? value : "overview";
}

function buildTeamProfileTabHref(
  pathname: string,
  searchParams: URLSearchParams | Readonly<Pick<URLSearchParams, "toString">>,
  tab: TeamProfileTab,
): string {
  const nextSearchParams = new URLSearchParams(searchParams.toString());

  if (tab === "overview") {
    nextSearchParams.delete("tab");
  } else {
    nextSearchParams.set("tab", tab);
  }

  const serialized = nextSearchParams.toString();
  return serialized.length > 0 ? `${pathname}?${serialized}` : pathname;
}

function resolveSectionCoverage(
  coverage: CoverageState | undefined,
  fallback: CoverageState,
): CoverageState {
  if (coverage) {
    return coverage;
  }

  return fallback;
}

function getTeamMonogram(teamName: string): string {
  const initials = teamName
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "CLB";
}

function formatInteger(value: number | null | undefined): string {
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
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value);
}

function formatPercentage(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return `${Math.round(value)}%`;
}

function formatGoalDiff(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "-";
  }

  return value > 0 ? `+${value}` : String(value);
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

function getResultTone(result: string | null | undefined): string {
  if (result === "win" || result === "V") {
    return "bg-[#a6f2d1] text-[#003526]";
  }

  if (result === "draw" || result === "E") {
    return "bg-[#d8e3fb] text-[#0d2240]";
  }

  if (result === "loss" || result === "D") {
    return "bg-[#ffdad6] text-[#93000a]";
  }

  return "bg-white/14 text-white/70";
}

type TeamProfileIconName =
  | "arrow"
  | "chart"
  | "match"
  | "players"
  | "shield"
  | "star"
  | "table";

function TeamProfileIcon({
  className,
  icon,
}: {
  className?: string;
  icon: TeamProfileIconName;
}) {
  const sharedClassName = className ?? "h-4 w-4";

  if (icon === "shield") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 18 7v5.4c0 3.3-2 5.8-6 7.1-4-1.3-6-3.8-6-7.1V7l6-2.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "chart") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M5 18V10h4v8M10 18V5h4v13M15 18v-6h4v6" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4 18.5h16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (icon === "players") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M8.5 11.2a3.1 3.1 0 1 0 0-6.2 3.1 3.1 0 0 0 0 6.2ZM15.5 11.2a3.1 3.1 0 1 0 0-6.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
        <path
          d="M3.8 19c.6-3.1 2.3-4.8 4.7-4.8s4.1 1.7 4.7 4.8M12.7 16c.8-1.2 1.9-1.8 3.2-1.8 2.2 0 3.7 1.6 4.3 4.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "table") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M6 6.5h12M6 11.5h12M6 16.5h12"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "match") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="m12 8.2 2.6 1.9-1 3.1h-3.2l-1-3.1L12 8.2Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.5"
        />
      </svg>
    );
  }

  if (icon === "arrow") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M6.5 12h11m0 0-4.5-4.5M17.5 12l-4.5 4.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
      <path
        d="m12 4.6 1.9 4 4.4.6-3.2 3.1.8 4.4-3.9-2.1-3.9 2.1.8-4.4-3.2-3.1 4.4-.6 1.9-4Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function TeamProfileMetric({
  hint,
  icon,
  label,
  value,
}: {
  hint: string;
  icon: TeamProfileIconName;
  label: string;
  value: string;
}) {
  return (
    <article className="flex min-h-[9.2rem] flex-col justify-between rounded-[1.35rem] border border-white/12 bg-white/10 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/14">
      <div className="flex items-center justify-between gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/12 text-white">
          <TeamProfileIcon className="h-5 w-5" icon={icon} />
        </span>
        <p className="text-right text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/58">
          {label}
        </p>
      </div>
      <p className="mt-4 font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-none tracking-[-0.03em]">
        {value}
      </p>
      <p className="mt-2 text-sm text-white/62">{hint}</p>
    </article>
  );
}

function TeamProfileLinkButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: TeamProfileIconName;
  label: string;
}) {
  return (
    <Link
      className="group inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-4 py-2 text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/86 transition-colors hover:border-white/28 hover:bg-white/18"
      href={href}
    >
      <TeamProfileIcon className="h-4 w-4 transition-transform group-hover:scale-110" icon={icon} />
      {label}
    </Link>
  );
}

export function TeamProfileContent({
  teamId,
  contextOverride,
  honorsPreview,
}: TeamProfileContentProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { roundId, venue, lastN, dateRangeStart, dateRangeEnd } = useGlobalFiltersState();
  const activeTab = resolveTeamProfileTab(searchParams.get("tab"));
  const profileQuery = useTeamProfile(
    teamId,
    { includeRecentMatches: false, includeSquad: true, includeStats: true },
    contextOverride,
  );
  const teamMatchesQuery = useTeamMatches(teamId, contextOverride, {
    pageSize: 10,
    sortBy: "kickoffAt",
    sortDirection: "desc",
  });
  const sharedFilters = {
    competitionId: contextOverride.competitionId,
    seasonId: contextOverride.seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  };
  const seasonHubHref = buildSeasonHubTabPath(contextOverride, "standings", sharedFilters);
  const rankingsHref = buildSeasonHubTabPath(contextOverride, "rankings", sharedFilters);
  const playersHref = buildPlayersPath(sharedFilters);
  const teamsHref = buildTeamsPath(sharedFilters);
  const headToHeadHref = buildHeadToHeadPath({
    ...sharedFilters,
    teamA: teamId,
  });
  const matchesTabHref = buildTeamProfileTabHref(pathname, searchParams, "matches");

  if (profileQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Perfil de time
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando perfil do time
          </h1>
        </header>
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={110} />
        <LoadingSkeleton height={280} />
      </ProfileShell>
    );
  }

  if (profileQuery.isError && !profileQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Perfil de time
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar perfil do time
          </h1>
        </header>
        <ProfileAlert title="Erro no carregamento" tone="critical">
          <p>{profileQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (profileQuery.isEmpty || !profileQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Perfil de time
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Perfil de time indisponível
          </h1>
        </header>
        <EmptyState
          title="Perfil indisponível"
          description="A base retornou dados insuficientes para o time no contexto atual."
        />
      </ProfileShell>
    );
  }

  const { form, sectionCoverage, squad, standing, stats, summary, team } = profileQuery.data;
  const overviewCoverage = resolveSectionCoverage(
    sectionCoverage?.overview,
    {
      ...profileQuery.coverage,
      label: sectionCoverage?.overview?.label ?? "Cobertura do resumo do time",
    },
  );
  const squadCoverage = resolveSectionCoverage(sectionCoverage?.squad, {
    status: squad && squad.length > 0 ? "complete" : "unknown",
    label: "Cobertura do elenco",
  });
  const statsCoverage = resolveSectionCoverage(sectionCoverage?.stats, {
    status: stats ? "complete" : "unknown",
    label: "Cobertura das estatísticas do time",
  });
  const matchesCoverage = teamMatchesQuery.coverage;
  const tabLinks = [
    { key: "overview" as const, label: "Resumo", coverage: overviewCoverage, badge: "Resumo" },
    { key: "journey" as const, label: "Jornada", coverage: overviewCoverage, badge: "Histórico" },
    { key: "squad" as const, label: "Elenco", coverage: squadCoverage, badge: `${squad?.length ?? 0} jogadores` },
    { key: "matches" as const, label: "Partidas", coverage: matchesCoverage, badge: `${teamMatchesQuery.data?.items.length ?? 0} jogos` },
    { key: "stats" as const, label: "Estatísticas", coverage: statsCoverage, badge: `${stats?.trend?.length ?? 0} períodos` },
  ];
  const activeTabLabel = tabLinks.find((tabLink) => tabLink.key === activeTab)?.label ?? "Resumo";
  const topSquadPlayers = [...(squad ?? [])]
    .filter((player) => typeof player.minutesPlayed === "number" && player.minutesPlayed > 0)
    .sort((left, right) => (right.minutesPlayed ?? 0) - (left.minutesPlayed ?? 0))
    .slice(0, 3);
  const bestTrendPeriod = [...(stats?.trend ?? [])].sort((left, right) => {
    const rightPoints = right.points ?? -1;
    const leftPoints = left.points ?? -1;

    if (rightPoints !== leftPoints) {
      return rightPoints - leftPoints;
    }

    return (right.goalDiff ?? -999) - (left.goalDiff ?? -999);
  })[0];
  const pointsPerMatch =
    stats?.pointsPerMatch ??
    (summary.matchesPlayed && summary.matchesPlayed > 0 && typeof summary.points === "number"
      ? summary.points / summary.matchesPlayed
      : null);
  const winRate =
    stats?.winRatePct ??
    (summary.matchesPlayed && summary.matchesPlayed > 0 && typeof summary.wins === "number"
      ? (summary.wins / summary.matchesPlayed) * 100
      : null);
  const cleanSheetRate =
    summary.matchesPlayed && summary.matchesPlayed > 0 && typeof stats?.cleanSheets === "number"
      ? (stats.cleanSheets / summary.matchesPlayed) * 100
      : null;

  return (
    <ProfileShell className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#00513b]" href="/competitions">
          Competições
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#00513b]" href={seasonHubHref}>
          {contextOverride.competitionName}
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#00513b]" href={teamsHref}>
          Times
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{team.teamName}</span>
      </div>

      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(166,242,209,0.24),transparent_30%),radial-gradient(circle_at_88%_0%,rgba(216,227,251,0.2),transparent_34%)]" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-52 w-52 rounded-full bg-white/5 blur-3xl" />

        <div className="relative grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(390px,0.42fr)] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="bg-white/10 text-white/82">
                {team.competitionName ?? contextOverride.competitionName}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">
                {team.seasonLabel ?? contextOverride.seasonLabel}
              </ProfileTag>
              <ProfileTag className="bg-white/10 text-white/82">
                {standing?.position && standing.totalTeams
                  ? `${standing.position}º de ${standing.totalTeams}`
                  : "Sem posição oficial"}
              </ProfileTag>
            </div>

            <div className="flex min-w-0 flex-col items-start gap-5 sm:flex-row">
              <ProfileMedia
                alt={`Escudo de ${team.teamName}`}
                assetId={team.teamId}
                category="clubs"
                className="h-24 w-24 shrink-0 border border-white/18 bg-white/12"
                fallback={getTeamMonogram(team.teamName)}
                imageClassName="p-3"
                tone="contrast"
              />
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                  <TeamProfileIcon className="h-4 w-4" icon="shield" />
                  Perfil do clube
                </p>
                <h1 className="mt-3 max-w-2xl break-words font-[family:var(--font-profile-headline)] text-4xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-5xl">
                  {team.teamName}
                </h1>
              </div>
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <TeamProfileMetric
                hint={`${formatInteger(summary.matchesPlayed)} jogos`}
                icon="shield"
                label="Campanha"
                value={`${formatInteger(summary.wins)}-${formatInteger(summary.draws)}-${formatInteger(summary.losses)}`}
              />
              <TeamProfileMetric
                hint="classificação"
                icon="table"
                label="Posição"
                value={standing?.position ? `${standing.position}º` : "-"}
              />
              <TeamProfileMetric
                hint={`${formatDecimal(pointsPerMatch)} por jogo`}
                icon="star"
                label="Pontos"
                value={formatInteger(summary.points)}
              />
              <TeamProfileMetric
                hint="taxa de vitória"
                icon="chart"
                label="Aproveit."
                value={formatPercentage(winRate)}
              />
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <TeamProfileMetric
                hint={`${formatInteger(summary.goalsFor)} pró / ${formatInteger(summary.goalsAgainst)} contra`}
                icon="shield"
                label="Saldo"
                value={formatGoalDiff(summary.goalDiff)}
              />
              <TeamProfileMetric
                hint="gols por jogo"
                icon="match"
                label="Ataque"
                value={formatDecimal(stats?.goalsForPerMatch)}
              />
              <TeamProfileMetric
                hint="gols sofridos/jogo"
                icon="shield"
                label="Defesa"
                value={formatDecimal(stats?.goalsAgainstPerMatch)}
              />
              <TeamProfileMetric
                hint={`${formatPercentage(cleanSheetRate)} dos jogos`}
                icon="star"
                label="Clean sheets"
                value={formatInteger(stats?.cleanSheets)}
              />
              <TeamProfileMetric
                hint="jogadores usados"
                icon="players"
                label="Elenco"
                value={formatInteger(squad?.length)}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <TeamProfileLinkButton href={headToHeadHref} icon="match" label="Confronto direto" />
              <TeamProfileLinkButton href={playersHref} icon="players" label="Jogadores" />
              <TeamProfileLinkButton href={rankingsHref} icon="chart" label="Rankings" />
              <TeamProfileLinkButton href={matchesTabHref} icon="table" label="Partidas" />
            </div>

            {honorsPreview ? <TeamHonorsSection honors={honorsPreview} /> : null}
          </div>

          <aside className="grid content-start gap-3 xl:pt-14">
            <div className="flex min-h-[12rem] flex-col justify-between rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                    Pico do recorte
                  </p>
                  <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                    {bestTrendPeriod?.label ?? "Sem série mensal"}
                  </h2>
                  <p className="mt-1 text-sm text-white/60">
                    {bestTrendPeriod
                      ? `${formatInteger(bestTrendPeriod.matches)} jogos · ${formatInteger(bestTrendPeriod.wins)}-${formatInteger(bestTrendPeriod.draws)}-${formatInteger(bestTrendPeriod.losses)}`
                      : "Ainda sem série mensal consolidada neste recorte."}
                  </p>
                </div>
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white/12 text-white">
                  <TeamProfileIcon className="h-5 w-5" icon="star" />
                </span>
              </div>

              <div className="mt-5 grid grid-cols-3 gap-2">
                <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                  <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Pontos</p>
                  <p className="mt-1 text-2xl font-extrabold">
                    {formatInteger(bestTrendPeriod?.points)}
                  </p>
                </div>
                <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                  <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Saldo</p>
                  <p className="mt-1 text-2xl font-extrabold">
                    {formatGoalDiff(bestTrendPeriod?.goalDiff)}
                  </p>
                </div>
                <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                  <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Gols pró</p>
                  <p className="mt-1 text-2xl font-extrabold">
                    {formatInteger(bestTrendPeriod?.goalsFor)}
                  </p>
                </div>
              </div>
            </div>

            <div className="min-h-[5.9rem] rounded-[1.3rem] border border-white/10 bg-white/8 p-4 text-white">
              <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                Forma consolidada
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(form ?? []).length > 0 ? (
                  form!.map((result, index) => (
                    <span
                      className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-extrabold ${getResultTone(result)}`}
                      key={`${result}-${index}`}
                    >
                      {formatResultLabel(result)}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-white/62">Sem sequência suficiente no recorte.</span>
                )}
              </div>
            </div>

            {topSquadPlayers.length > 0 ? (
              <div className="grid gap-2">
                {topSquadPlayers.map((player, index) => (
                  <div
                    className="flex items-center gap-3 rounded-[1.15rem] border border-white/10 bg-white/8 px-3 py-3 text-white"
                    key={player.playerId ?? `${player.playerName}-${index}`}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/12 text-xs font-bold text-white/72">
                      {index + 1}
                    </span>
                    <ProfileMedia
                      alt={player.playerName ?? "Jogador"}
                      assetId={player.playerId ?? undefined}
                      category="players"
                      className="h-10 w-10 border-0 bg-white/12"
                      fallback={(player.playerName ?? "J").slice(0, 2)}
                      imageClassName="p-1"
                      shape="circle"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold">{player.playerName ?? "Jogador"}</p>
                      <p className="truncate text-xs text-white/56">
                        {player.positionName ?? "Posição não informada"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-extrabold">{formatInteger(player.minutesPlayed)}</p>
                      <p className="text-[0.58rem] uppercase tracking-[0.16em] text-white/48">min</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </aside>
        </div>
      </ProfilePanel>

      {profileQuery.isError ? (
        <ProfileAlert title="Perfil carregado com alerta" tone="warning">
          <p>{profileQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      <ProfileTabs
        ariaLabel="Abas do perfil do time"
        aside={<ProfileTag>{activeTabLabel}</ProfileTag>}
        items={tabLinks.map((tabLink) => ({
          key: tabLink.key,
          label: tabLink.label,
          href: buildTeamProfileTabHref(pathname, searchParams, tabLink.key),
          isActive: activeTab === tabLink.key,
          badge: tabLink.badge,
        }))}
      />

      {activeTab === "overview" ? (
        <TeamOverviewSection
          matchesHref={matchesTabHref}
          profile={profileQuery.data}
          rankingsHref={rankingsHref}
          seasonHubHref={seasonHubHref}
        />
      ) : null}

      {activeTab === "journey" ? (
        <TeamJourneySection competitionContext={contextOverride} teamId={teamId} />
      ) : null}

      {activeTab === "squad" ? (
        <TeamSquadSection
          competitionContext={contextOverride}
          coverage={squadCoverage}
          filters={sharedFilters}
          squad={squad}
        />
      ) : null}

      {activeTab === "matches" ? (
        <TeamMatchesSection
          competitionContext={contextOverride}
          coverage={matchesCoverage}
          errorMessage={teamMatchesQuery.error?.message}
          filters={sharedFilters}
          isError={teamMatchesQuery.isError}
          isLoading={teamMatchesQuery.isLoading}
          matches={teamMatchesQuery.data?.items ?? []}
          teamId={teamId}
        />
      ) : null}

      {activeTab === "stats" ? (
        <TeamStatsSection coverage={statsCoverage} stats={stats} />
      ) : null}
    </ProfileShell>
  );
}
