"use client";

import Link from "next/link";

import { usePathname, useSearchParams } from "next/navigation";

import { useTeamMatches } from "@/features/teams/hooks/useTeamMatches";
import { useTeamProfile } from "@/features/teams/hooks/useTeamProfile";
import { TeamJourneySection } from "@/features/teams/components/TeamJourneySection";
import { TeamMatchesSection } from "@/features/teams/components/TeamMatchesSection";
import { TeamOverviewSection } from "@/features/teams/components/TeamOverviewSection";
import { TeamSquadSection } from "@/features/teams/components/TeamSquadSection";
import { TeamStatsSection } from "@/features/teams/components/TeamStatsSection";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
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
  buildMatchesPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type TeamProfileContentProps = {
  teamId: string;
  contextOverride: CompetitionSeasonContext;
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

export function TeamProfileContent({ teamId, contextOverride }: TeamProfileContentProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { roundId, venue, lastN, dateRangeStart, dateRangeEnd } = useGlobalFiltersState();
  const activeTab = resolveTeamProfileTab(searchParams.get("tab"));
  const profileQuery = useTeamProfile(
    teamId,
    { includeRecentMatches: true, includeSquad: true, includeStats: true },
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
  const matchesHref = buildMatchesPath(sharedFilters);
  const headToHeadHref = buildHeadToHeadPath({
    ...sharedFilters,
    teamA: teamId,
  });

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

  const { team, sectionCoverage, squad, stats } = profileQuery.data;
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

      <ProfilePanel className="space-y-6" tone="accent">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex items-start gap-5">
            <ProfileMedia
              alt={`Escudo de ${team.teamName}`}
              assetId={team.teamId}
              category="clubs"
              className="h-20 w-20"
              fallback={getTeamMonogram(team.teamName)}
              tone="contrast"
            />
            <div className="space-y-2">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-white/65">
                Time
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <ProfileCoveragePill coverage={profileQuery.coverage} className="bg-white/16 text-white" />
                <ProfileTag className="bg-white/12 text-white/82">
                  {team.competitionName ?? contextOverride.competitionName}
                </ProfileTag>
                <ProfileTag className="bg-white/12 text-white/82">
                  {team.seasonLabel ?? contextOverride.seasonLabel}
                </ProfileTag>
              </div>
              <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-white md:text-5xl">
                {team.teamName}
              </h1>
              <p className="max-w-3xl text-sm leading-6 text-white/74">
                Campanha, elenco, partidas e métricas do time no mesmo contexto da temporada.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              className="button-pill button-pill-on-dark"
              href={headToHeadHref}
            >
              Confronto direto
            </Link>
            <Link
              className="button-pill button-pill-on-dark"
              href={playersHref}
            >
              Jogadores
            </Link>
            <Link
              className="button-pill button-pill-on-dark"
              href={rankingsHref}
            >
              Rankings
            </Link>
            <Link
              className="button-pill button-pill-inverse"
              href={matchesHref}
            >
              Abrir partidas
            </Link>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <ProfileKpi
            hint="Classificação atual"
            invert
            label="Posição"
            value={profileQuery.data.standing?.position ? `${profileQuery.data.standing.position}º` : "-"}
          />
          <ProfileKpi
            hint="Na temporada ativa"
            invert
            label="Pontos"
            value={profileQuery.data.summary.points ?? "-"}
          />
          <ProfileKpi hint="Jogadores identificados" invert label="Elenco" value={squad?.length ?? 0} />
          <ProfileKpi hint="Leitura mensal" invert label="Estatísticas" value={stats?.trend?.length ?? 0} />
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
          coverage={overviewCoverage}
          matchesHref={matchesHref}
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
