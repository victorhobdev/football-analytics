"use client";

import type { ReactNode } from "react";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { usePlayerProfile } from "@/features/players/hooks";
import type { Player, PlayerProfileMeta, PlayerWorldCupSummary } from "@/features/players/types";
import { PlayerHistorySection } from "@/features/players/components/PlayerHistorySection";
import { PlayerMatchesSection } from "@/features/players/components/PlayerMatchesSection";
import { PlayerOverviewSection } from "@/features/players/components/PlayerOverviewSection";
import { PlayerStatsSection } from "@/features/players/components/PlayerStatsSection";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { useInsights } from "@/shared/hooks/useInsights";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
  ProfileTabs,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  appendFilterQueryString,
  buildCanonicalTeamPath,
  buildMatchCenterPath,
  buildMatchesPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type PlayerProfileContentProps = {
  playerId: string;
  contextOverride?: CompetitionSeasonContext | null;
  notice?: ReactNode;
};

const PLAYER_PROFILE_TABS = ["overview", "history", "matches", "stats"] as const;
type PlayerProfileTab = (typeof PLAYER_PROFILE_TABS)[number];

function isPlayerProfileTab(value: string | null | undefined): value is PlayerProfileTab {
  return typeof value === "string" && PLAYER_PROFILE_TABS.includes(value as PlayerProfileTab);
}

function resolvePlayerProfileTab(value: string | null | undefined): PlayerProfileTab {
  return isPlayerProfileTab(value) ? value : "overview";
}

function buildPlayerProfileTabHref(
  pathname: string,
  searchParams: URLSearchParams | Readonly<Pick<URLSearchParams, "toString">>,
  tab: PlayerProfileTab,
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

function getPlayerMonogram(playerName: string): string {
  const initials = playerName
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "PLY";
}

function getProfileTypeLabel(profileType: string): string {
  if (profileType === "world_cup_local") {
    return "Perfil da Copa";
  }

  if (profileType === "sportmonks_without_history") {
    return "Perfil básico";
  }

  return "Perfil com histórico";
}

function getProfileDescription(
  hasHistoricalStats: boolean,
  playerName: string,
  worldCup: PlayerWorldCupSummary | null,
): string {
  if (hasHistoricalStats) {
    return "Resumo, histórico, partidas e tendência do atleta em uma leitura única dentro da temporada selecionada.";
  }

  if (worldCup?.editionCount) {
    const editionLabel = worldCup.editionCount === 1 ? "Copa" : "Copas";
    const teamLabel =
      worldCup.teamNames.length === 1
        ? `pela seleção ${worldCup.teamNames[0]}`
        : `por ${worldCup.teamCount} seleções`;
    const goalsLabel =
      typeof worldCup.goalCount === "number"
        ? `, com ${formatInteger(worldCup.goalCount)} ${worldCup.goalCount === 1 ? "gol" : "gols"}`
        : "";

    return `${playerName} tem registro em ${worldCup.editionCount} ${editionLabel} ${teamLabel}${goalsLabel}.`;
  }

  return "Informações básicas disponíveis para consulta neste perfil.";
}

const POSITION_LABELS: Record<string, string> = {
  goalkeeper: "Goleiro",
  defender: "Defensor",
  midfielder: "Meio-campista",
  forward: "Atacante",
  "center forward": "Centroavante",
  "right winger": "Ponta direita",
  "left winger": "Ponta esquerda",
  "attacking midfielder": "Meia ofensivo",
  "defensive midfielder": "Volante",
  "left back": "Lateral esquerdo",
  "right back": "Lateral direito",
};

function formatPositionLabel(position: string | null | undefined): string | null {
  const normalizedPosition = position?.trim();

  if (!normalizedPosition) {
    return null;
  }

  return POSITION_LABELS[normalizedPosition.toLowerCase()] ?? normalizedPosition;
}

function normalizeTagKey(value: string): string {
  return value.trim().toLocaleLowerCase("pt-BR");
}

function buildProfileTagLabels({
  contextOverride,
  displayPosition,
  hasHistoricalStats,
  player,
  profileMeta,
}: {
  contextOverride: CompetitionSeasonContext | null;
  displayPosition: string | null;
  hasHistoricalStats: boolean;
  player: Player;
  profileMeta: PlayerProfileMeta;
}): string[] {
  const labels = [
    hasHistoricalStats
      ? getProfileTypeLabel(profileMeta.profileType)
      : profileMeta.isWorldCupLinked
        ? "Copa do Mundo"
        : "Perfil básico",
    contextOverride?.competitionName,
    contextOverride?.seasonLabel,
    displayPosition,
    player.teamName,
    player.nationality,
  ];
  const seenLabels = new Set<string>();

  return labels.filter((label): label is string => {
    if (!label) {
      return false;
    }

    const key = normalizeTagKey(label);
    if (seenLabels.has(key)) {
      return false;
    }

    seenLabels.add(key);
    return true;
  });
}

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});

const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
});

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return INTEGER_FORMATTER.format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return DECIMAL_FORMATTER.format(value);
}

function formatPercentage(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return `${Math.round(value)}%`;
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
  if (result === "win") {
    return "bg-[#a6f2d1] text-[#003526]";
  }

  if (result === "draw") {
    return "bg-[#d8e3fb] text-[#0d2240]";
  }

  if (result === "loss") {
    return "bg-[#ffdad6] text-[#93000a]";
  }

  return "bg-white/14 text-white/70";
}

type PlayerProfileIconName =
  | "assist"
  | "chart"
  | "clock"
  | "match"
  | "player"
  | "ranking"
  | "shield"
  | "star"
  | "target"
  | "timeline";

function PlayerProfileIcon({
  className,
  icon,
}: {
  className?: string;
  icon: PlayerProfileIconName;
}) {
  const sharedClassName = className ?? "h-4 w-4";

  if (icon === "player") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 11.2a3.35 3.35 0 1 0 0-6.7 3.35 3.35 0 0 0 0 6.7Z"
          stroke="currentColor"
          strokeWidth="1.8"
        />
        <path
          d="M5.2 19.4c.8-3.5 3.2-5.2 6.8-5.2s6 1.7 6.8 5.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "assist") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M5 12h9" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        <path
          d="m11 8 4 4-4 4M18.5 6.5v11"
          stroke="currentColor"
          strokeLinecap="round"
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

  if (icon === "clock") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 8v4.4l2.8 1.7" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
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

  if (icon === "ranking") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M6 18V11h4v7M10 18V6h4v12M14 18v-5h4v5" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4.5 18.5h15" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

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

  if (icon === "target") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="7" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 2.8v3M21.2 12h-3M12 21.2v-3M2.8 12h3" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" />
      </svg>
    );
  }

  if (icon === "timeline") {
    return (
      <svg aria-hidden="true" className={sharedClassName} fill="none" viewBox="0 0 24 24">
        <path d="M6 7h12M6 12h8M6 17h11" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        <path d="M4 7h.01M4 12h.01M4 17h.01" stroke="currentColor" strokeLinecap="round" strokeWidth="2.4" />
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

function PlayerProfileMetric({
  hint,
  icon,
  label,
  value,
}: {
  hint: string;
  icon: PlayerProfileIconName;
  label: string;
  value: string;
}) {
  return (
    <article className="flex min-h-[9.2rem] flex-col justify-between rounded-[1.35rem] border border-white/12 bg-white/10 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-colors hover:bg-white/14">
      <div className="flex items-center justify-between gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/12 text-white">
          <PlayerProfileIcon className="h-5 w-5" icon={icon} />
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

function PlayerProfileLinkButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: PlayerProfileIconName;
  label: string;
}) {
  return (
    <Link
      className="group inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-4 py-2 text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/86 transition-colors hover:border-white/28 hover:bg-white/18"
      href={href}
    >
      <PlayerProfileIcon className="h-4 w-4 transition-transform group-hover:scale-110" icon={icon} />
      {label}
    </Link>
  );
}

export function PlayerProfileContent({
  playerId,
  contextOverride = null,
  notice = null,
}: PlayerProfileContentProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const stageId = searchParams.get("stageId")?.trim() || null;
  const stageFormat = searchParams.get("stageFormat")?.trim() || null;
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const activeTab = resolvePlayerProfileTab(searchParams.get("tab"));
  const profileQuery = usePlayerProfile(
    playerId,
    {
      includeRecentMatches: true,
      includeHistory: true,
      includeStats: true,
      stageId,
      stageFormat,
    },
    contextOverride,
  );
  const insightsQuery = useInsights({
    entityType: "player",
    entityId: playerId,
    filters: contextOverride
      ? {
          competitionId: contextOverride.competitionId,
          seasonId: contextOverride.seasonId,
        }
      : undefined,
  });
  const sharedFilters = {
    competitionId: contextOverride?.competitionId ?? competitionId,
    seasonId: contextOverride?.seasonId ?? seasonId,
    roundId,
    stageId,
    stageFormat,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  };
  const seasonHubHref = contextOverride
    ? buildSeasonHubTabPath(contextOverride, "calendar", sharedFilters)
    : null;
  const rankingsHref = contextOverride
    ? buildSeasonHubTabPath(contextOverride, "rankings", sharedFilters)
    : null;
  const playersHref = buildPlayersPath(sharedFilters);
  const matchesHref = buildMatchesPath(sharedFilters);

  if (profileQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        {notice}
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Jogador
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando perfil do jogador
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
        {notice}
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Jogador
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar perfil do jogador
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
        {notice}
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Jogador
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Perfil de jogador indisponível
          </h1>
        </header>
        <EmptyState
          title="Perfil indisponível"
          description="Não há dados suficientes para montar este perfil agora."
        />
      </ProfileShell>
    );
  }

  const { history, player, profileMeta, recentMatches, sectionCoverage, stats, summary } = profileQuery.data;
  const hasHistoricalStats = profileMeta.hasHistoricalStats;
  const worldCup = profileMeta.worldCup ?? null;
  const displayPosition = formatPositionLabel(worldCup?.primaryPosition ?? player.position);
  const profileImageAssetId = worldCup?.imageAssetId ?? player.playerId;
  const profileTagLabels = buildProfileTagLabels({
    contextOverride,
    displayPosition,
    hasHistoricalStats,
    player,
    profileMeta,
  });
  const teamHref = player.teamId
    ? contextOverride
      ? appendFilterQueryString(
          buildCanonicalTeamPath(contextOverride, player.teamId),
          sharedFilters,
          ["competitionId", "seasonId"],
        )
      : buildTeamResolverPath(player.teamId, sharedFilters)
    : null;
  const overviewCoverage = resolveSectionCoverage(sectionCoverage?.overview, {
    ...profileQuery.coverage,
    label: sectionCoverage?.overview?.label ?? "Cobertura do resumo do jogador",
  });
  const historyCoverage = resolveSectionCoverage(sectionCoverage?.history, {
    status: history && history.length > 0 ? "complete" : "unknown",
    label: "Cobertura do histórico do jogador",
  });
  const matchesCoverage = resolveSectionCoverage(sectionCoverage?.matches, {
    ...profileQuery.coverage,
    label: sectionCoverage?.matches?.label ?? "Cobertura das partidas do jogador",
  });
  const statsCoverage = resolveSectionCoverage(sectionCoverage?.stats, {
    status: stats ? "complete" : "unknown",
    label: "Cobertura das estatísticas do jogador",
  });
  const tabLinks = [
    { key: "overview" as const, label: "Resumo", coverage: overviewCoverage, badge: "Resumo" },
    {
      key: "history" as const,
      label: "Histórico",
      coverage: historyCoverage,
      badge: `${history?.length ?? 0} contextos`,
    },
    {
      key: "matches" as const,
      label: "Partidas",
      coverage: matchesCoverage,
      badge: `${recentMatches?.length ?? 0} jogos`,
    },
    {
      key: "stats" as const,
      label: "Estatísticas",
      coverage: statsCoverage,
      badge: `${stats?.trend?.length ?? 0} períodos`,
    },
  ];
  const visibleTabLinks = hasHistoricalStats
    ? tabLinks
    : tabLinks.filter((tabLink) => tabLink.key === "overview");
  const effectiveActiveTab: PlayerProfileTab = hasHistoricalStats ? activeTab : "overview";
  const activeTabLabel =
    visibleTabLinks.find((tabLink) => tabLink.key === effectiveActiveTab)?.label ?? "Resumo";
  const historyItems = history ?? [];
  const recentMatchItems = recentMatches ?? [];
  const goalContribution = (summary.goals ?? 0) + (summary.assists ?? 0);
  const minutesPerMatch =
    stats?.minutesPerMatch ??
    (summary.matchesPlayed && summary.matchesPlayed > 0
      ? (summary.minutesPlayed ?? 0) / summary.matchesPlayed
      : null);
  const shotsOnTargetPct =
    stats?.shotsOnTargetPct ??
    (summary.shotsTotal && summary.shotsTotal > 0
      ? ((summary.shotsOnTarget ?? 0) / summary.shotsTotal) * 100
      : null);
  const bestRecentMatch =
    [...recentMatchItems].sort((left, right) => {
      const rightScore =
        (right.rating ?? -1) * 100 +
        (right.goals ?? 0) * 10 +
        (right.assists ?? 0) * 8 +
        (right.minutesPlayed ?? 0) / 100;
      const leftScore =
        (left.rating ?? -1) * 100 +
        (left.goals ?? 0) * 10 +
        (left.assists ?? 0) * 8 +
        (left.minutesPlayed ?? 0) / 100;

      return rightScore - leftScore;
    })[0] ?? null;
  const bestTrendPeriod =
    [...(stats?.trend ?? [])].sort((left, right) => {
      const rightContribution = (right.goals ?? 0) + (right.assists ?? 0);
      const leftContribution = (left.goals ?? 0) + (left.assists ?? 0);

      if (rightContribution !== leftContribution) {
        return rightContribution - leftContribution;
      }

      if ((right.rating ?? -1) !== (left.rating ?? -1)) {
        return (right.rating ?? -1) - (left.rating ?? -1);
      }

      return (right.minutesPlayed ?? 0) - (left.minutesPlayed ?? 0);
    })[0] ?? null;
  const bestTrendContribution = (bestTrendPeriod?.goals ?? 0) + (bestTrendPeriod?.assists ?? 0);
  const recentForm = recentMatchItems.slice(0, 5);
  const teamHistoryLabels = Array.from(
    new Set(historyItems.map((entry) => entry.teamName).filter((teamName): teamName is string => Boolean(teamName))),
  ).slice(0, 4);
  const contextHistoryLabels = Array.from(
    new Set(
      historyItems
        .map((entry) =>
          entry.competitionName && entry.seasonLabel
            ? `${entry.competitionName} ${entry.seasonLabel}`
            : entry.competitionName ?? entry.seasonLabel ?? null,
        )
        .filter((label): label is string => Boolean(label)),
    ),
  ).slice(0, 3);
  const matchesTabHref = buildPlayerProfileTabHref(pathname, searchParams, "matches");
  const historyTabHref = buildPlayerProfileTabHref(pathname, searchParams, "history");
  const statsTabHref = buildPlayerProfileTabHref(pathname, searchParams, "stats");
  const bestRecentMatchId = bestRecentMatch?.matchId ?? bestRecentMatch?.fixtureId ?? null;
  const bestRecentMatchHref = bestRecentMatchId
    ? buildMatchCenterPath(bestRecentMatchId, {
        ...sharedFilters,
        competitionId: bestRecentMatch?.competitionId ?? sharedFilters.competitionId,
        seasonId: bestRecentMatch?.seasonId ?? sharedFilters.seasonId,
        roundId: bestRecentMatch?.roundId ?? sharedFilters.roundId,
      })
    : null;

  return (
    <ProfileShell className="space-y-6">
      {notice}

      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#00513b]" href="/competitions">
          Competições
        </Link>
        {contextOverride ? (
          <>
            <span className="text-[#8fa097]">/</span>
            <Link className="transition-colors hover:text-[#00513b]" href={seasonHubHref ?? "/competitions"}>
              {contextOverride.competitionName}
            </Link>
            <span className="text-[#8fa097]">/</span>
          </>
        ) : (
          <>
            <span className="text-[#8fa097]">/</span>
          </>
        )}
        <Link className="transition-colors hover:text-[#00513b]" href={playersHref}>
          Jogadores
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{player.playerName}</span>
      </div>

      <ProfilePanel className="profile-hero-clean relative overflow-hidden p-0" tone="accent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(166,242,209,0.24),transparent_30%),radial-gradient(circle_at_88%_0%,rgba(216,227,251,0.2),transparent_34%)]" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-52 w-52 rounded-full bg-white/5 blur-3xl" />

        <div className="relative grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.42fr)] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5">
            <div className="flex flex-wrap items-center gap-2">
              {hasHistoricalStats ? (
                <ProfileCoveragePill coverage={profileQuery.coverage} className="bg-white/16 text-white" />
              ) : null}
              {profileTagLabels.map((label) => (
                <ProfileTag className="bg-white/10 text-white/82" key={label}>
                  {label}
                </ProfileTag>
              ))}
            </div>

            <div className="flex min-w-0 flex-col items-start gap-5 sm:flex-row">
              <ProfileMedia
                alt={player.playerName}
                assetId={profileImageAssetId}
                category="players"
                className="h-24 w-24 shrink-0 border border-white/18 bg-white/12"
                fallback={getPlayerMonogram(player.playerName)}
                fallbackClassName="text-xl tracking-[0.08em] text-white"
                href={pathname}
                imageClassName="p-2"
                shape="circle"
                tone="contrast"
              />
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                  <PlayerProfileIcon className="h-4 w-4" icon="player" />
                  Perfil do jogador
                </p>
                <h1 className="mt-3 max-w-3xl break-words font-[family:var(--font-profile-headline)] text-5xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-6xl">
                  {player.playerName}
                </h1>
                <p className="mt-4 max-w-3xl text-sm leading-6 text-white/70">
                  {getProfileDescription(hasHistoricalStats, player.playerName, worldCup)}
                </p>
              </div>
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {hasHistoricalStats ? (
                <>
                  <PlayerProfileMetric
                    hint={`${formatInteger(summary.minutesPlayed)} minutos`}
                    icon="match"
                    label="Jogos"
                    value={formatInteger(summary.matchesPlayed)}
                  />
                  <PlayerProfileMetric
                    hint={`${formatInteger(summary.goals)} gols · ${formatInteger(summary.assists)} assists`}
                    icon="assist"
                    label="G+A"
                    value={formatInteger(goalContribution)}
                  />
                  <PlayerProfileMetric
                    hint="nota média do recorte"
                    icon="star"
                    label="Nota"
                    value={formatDecimal(summary.rating)}
                  />
                  <PlayerProfileMetric
                    hint={`assistências/90 ${formatDecimal(stats?.assistsPer90)}`}
                    icon="ranking"
                    label="Gols/90"
                    value={formatDecimal(stats?.goalsPer90)}
                  />
                  <PlayerProfileMetric
                    hint={`${formatDecimal(minutesPerMatch)} por jogo`}
                    icon="clock"
                    label="Minutos"
                    value={formatInteger(summary.minutesPlayed)}
                  />
                  <PlayerProfileMetric
                    hint={`${formatInteger(summary.shotsOnTarget)} no alvo`}
                    icon="target"
                    label="Finaliz."
                    value={formatInteger(summary.shotsTotal)}
                  />
                  <PlayerProfileMetric
                    hint="precisão nas finalizações"
                    icon="chart"
                    label="No alvo"
                    value={formatPercentage(shotsOnTargetPct)}
                  />
                  <PlayerProfileMetric
                    hint="contextos mapeados"
                    icon="timeline"
                    label="Histórico"
                    value={formatInteger(historyItems.length)}
                  />
                </>
              ) : (
                <>
                  <PlayerProfileMetric
                    hint={worldCup?.editionLabels?.length ? worldCup.editionLabels.join(" · ") : "Sem edições registradas"}
                    icon="timeline"
                    label="Edições"
                    value={formatInteger(worldCup?.editionCount)}
                  />
                  <PlayerProfileMetric
                    hint={worldCup?.teamNames?.length ? worldCup.teamNames.join(" · ") : "Seleção não informada"}
                    icon="shield"
                    label={worldCup?.teamCount === 1 ? "Seleção" : "Seleções"}
                    value={formatInteger(worldCup?.teamCount)}
                  />
                  <PlayerProfileMetric
                    hint="Total registrado em Copas"
                    icon="match"
                    label="Gols"
                    value={formatInteger(worldCup?.goalCount)}
                  />
                  <PlayerProfileMetric
                    hint="Posição registrada"
                    icon="player"
                    label="Posição"
                    value={displayPosition ?? "-"}
                  />
                </>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <PlayerProfileLinkButton href={playersHref} icon="player" label="Lista de jogadores" />
              {teamHref && hasHistoricalStats ? (
                <PlayerProfileLinkButton href={teamHref} icon="shield" label="Time" />
              ) : null}
              {rankingsHref && hasHistoricalStats ? (
                <PlayerProfileLinkButton href={rankingsHref} icon="ranking" label="Rankings" />
              ) : null}
              {hasHistoricalStats ? (
                <>
                  <PlayerProfileLinkButton href={matchesTabHref} icon="match" label="Partidas" />
                  <PlayerProfileLinkButton href={statsTabHref} icon="chart" label="Estatísticas" />
                </>
              ) : null}
              {seasonHubHref ? (
                <PlayerProfileLinkButton href={seasonHubHref} icon="timeline" label="Contexto" />
              ) : null}
            </div>
          </div>

          <aside className="grid content-start gap-3 xl:pt-14">
            {hasHistoricalStats ? (
              <>
                <div className="flex min-h-[12rem] flex-col justify-between rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                        Melhor partida recente
                      </p>
                      <h2 className="mt-1 truncate font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                        {bestRecentMatch?.opponentName ?? "Sem partida destacada"}
                      </h2>
                      <p className="mt-1 text-sm text-white/60">
                        {bestRecentMatch
                          ? `${formatDate(bestRecentMatch.playedAt)} · ${bestRecentMatch.teamName ?? player.teamName ?? "Time"}`
                          : "Ainda sem partidas suficientes para destacar."}
                      </p>
                    </div>
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/12 text-white">
                      <PlayerProfileIcon className="h-5 w-5" icon="star" />
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-2">
                    <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                      <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Nota</p>
                      <p className="mt-1 text-2xl font-extrabold">
                        {formatDecimal(bestRecentMatch?.rating)}
                      </p>
                    </div>
                    <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                      <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">G+A</p>
                      <p className="mt-1 text-2xl font-extrabold">
                        {bestRecentMatch
                          ? formatInteger((bestRecentMatch.goals ?? 0) + (bestRecentMatch.assists ?? 0))
                          : "-"}
                      </p>
                    </div>
                    <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                      <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Min</p>
                      <p className="mt-1 text-2xl font-extrabold">
                        {formatInteger(bestRecentMatch?.minutesPlayed)}
                      </p>
                    </div>
                  </div>

                  {bestRecentMatchHref ? (
                    <Link className="button-pill button-pill-on-dark mt-4 w-full" href={bestRecentMatchHref}>
                      Abrir central da partida
                    </Link>
                  ) : null}
                </div>

                <div className="min-h-[5.9rem] rounded-[1.3rem] border border-white/10 bg-white/8 p-4 text-white">
                  <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                    Forma recente
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {recentForm.length > 0 ? (
                      recentForm.map((match, index) => (
                        <span
                          className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-extrabold ${getResultTone(match.result)}`}
                          key={`${match.fixtureId}-${index}`}
                          title={match.opponentName ?? undefined}
                        >
                          {formatResultLabel(match.result)}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-white/62">Sem sequência suficiente no recorte.</span>
                    )}
                  </div>
                </div>

                {bestTrendPeriod ? (
                  <div className="rounded-[1.3rem] border border-white/10 bg-white/8 p-4 text-white">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                          Pico mensal
                        </p>
                        <h3 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                          {bestTrendPeriod.label ?? bestTrendPeriod.periodKey ?? "Período"}
                        </h3>
                      </div>
                      <Link className="button-pill button-pill-on-dark" href={statsTabHref}>
                        Ver série
                      </Link>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-2">
                      <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                        <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">G+A</p>
                        <p className="mt-1 text-2xl font-extrabold">{formatInteger(bestTrendContribution)}</p>
                      </div>
                      <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                        <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Jogos</p>
                        <p className="mt-1 text-2xl font-extrabold">
                          {formatInteger(bestTrendPeriod.matchesPlayed)}
                        </p>
                      </div>
                      <div className="rounded-[1rem] bg-white/10 px-3 py-3">
                        <p className="text-[0.6rem] uppercase tracking-[0.16em] text-white/52">Nota</p>
                        <p className="mt-1 text-2xl font-extrabold">
                          {formatDecimal(bestTrendPeriod.rating)}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {contextHistoryLabels.length > 0 || teamHistoryLabels.length > 0 ? (
                  <div className="rounded-[1.3rem] border border-white/10 bg-white/8 p-4 text-white">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                        Contextos mapeados
                      </p>
                      <Link className="button-pill button-pill-on-dark" href={historyTabHref}>
                        Histórico
                      </Link>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {[...contextHistoryLabels, ...teamHistoryLabels].map((label) => (
                        <ProfileTag className="bg-white/10 text-white/82" key={label}>
                          {label}
                        </ProfileTag>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="rounded-[1.55rem] border border-white/12 bg-white/12 p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/52">
                      Recorte disponível
                    </p>
                    <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-white">
                      {worldCup?.goalCount ? `${formatInteger(worldCup.goalCount)} gols em Copas` : "Dados básicos"}
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-white/68">
                      {worldCup?.editionCount
                        ? `Participações registradas em ${formatInteger(worldCup.editionCount)} ${worldCup.editionCount === 1 ? "edição" : "edições"} da Copa do Mundo.`
                        : "Informações principais do jogador reunidas em uma visão simples."}
                    </p>
                  </div>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/12 text-white">
                    <PlayerProfileIcon className="h-5 w-5" icon="shield" />
                  </span>
                </div>

                {worldCup?.teamNames?.length ? (
                  <div className="mt-5 space-y-2">
                    <p className="text-[0.6rem] font-bold uppercase tracking-[0.16em] text-white/52">
                      Seleções
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {worldCup.teamNames.map((teamName) => (
                        <ProfileTag className="bg-white/10 text-white/82" key={teamName}>
                          {teamName}
                        </ProfileTag>
                      ))}
                    </div>
                  </div>
                ) : null}

                {worldCup?.editionLabels?.length ? (
                  <div className="mt-5 space-y-2">
                    <p className="text-[0.6rem] font-bold uppercase tracking-[0.16em] text-white/52">
                      Edições
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {worldCup.editionLabels.map((editionLabel) => (
                        <ProfileTag className="bg-white/10 text-white/82" key={editionLabel}>
                          {editionLabel}
                        </ProfileTag>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </aside>
        </div>
      </ProfilePanel>

      {profileQuery.isError ? (
        <ProfileAlert title="Perfil carregado com alerta" tone="warning">
          <p>{profileQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {visibleTabLinks.length > 1 ? (
        <ProfileTabs
          ariaLabel="Abas do perfil do jogador"
          aside={<ProfileTag>{activeTabLabel}</ProfileTag>}
          items={visibleTabLinks.map((tabLink) => ({
            key: tabLink.key,
            label: tabLink.label,
            href: buildPlayerProfileTabHref(pathname, searchParams, tabLink.key),
            isActive: effectiveActiveTab === tabLink.key,
            badge: tabLink.badge,
          }))}
        />
      ) : null}

      {effectiveActiveTab === "overview" ? (
        <PlayerOverviewSection
          coverage={overviewCoverage}
          insights={{
            coverage: insightsQuery.coverage,
            errorMessage: insightsQuery.error?.message,
            isError: insightsQuery.isError,
            isLoading: insightsQuery.isLoading,
            isPartial: insightsQuery.isPartial,
            items: insightsQuery.data ?? [],
          }}
          matchesHref={hasHistoricalStats ? matchesHref : null}
          profile={profileQuery.data}
          rankingsHref={hasHistoricalStats ? rankingsHref : null}
          seasonHubHref={seasonHubHref}
          teamHref={hasHistoricalStats ? teamHref : null}
        />
      ) : null}

      {effectiveActiveTab === "history" ? (
        <PlayerHistorySection
          coverage={historyCoverage}
          filters={sharedFilters}
          history={history}
          profileMeta={profileMeta}
        />
      ) : null}

      {effectiveActiveTab === "matches" ? (
        <PlayerMatchesSection
          competitionContext={contextOverride}
          coverage={matchesCoverage}
          filters={sharedFilters}
          matches={recentMatches}
          profileMeta={profileMeta}
        />
      ) : null}

      {effectiveActiveTab === "stats" ? (
        <PlayerStatsSection
          coverage={statsCoverage}
          profileMeta={profileMeta}
          stats={stats}
          summary={summary}
        />
      ) : null}
    </ProfileShell>
  );
}
