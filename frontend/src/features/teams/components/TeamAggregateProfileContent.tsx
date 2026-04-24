"use client";

import type { ReactNode } from "react";

import Link from "next/link";

import { TeamHonorsSection } from "@/features/teams/components/TeamHonorsSection";
import { useTeamContexts } from "@/features/teams/hooks/useTeamContexts";
import { useTeamProfile } from "@/features/teams/hooks/useTeamProfile";
import { useTeamsList } from "@/features/teams/hooks/useTeamsList";
import type { TeamHonorsPreview } from "@/features/teams/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { getCompetitionById } from "@/config/competitions.registry";
import { getSeasonById, getSeasonByQueryId } from "@/config/seasons.registry";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import {
  buildCanonicalTeamPath,
  buildRankingsHubPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type TeamAggregateProfileContentProps = {
  teamId: string;
  honorsPreview?: TeamHonorsPreview | null;
};

type AggregateMetricIconName = "calendar" | "chart" | "form" | "goal" | "grid" | "shield" | "trend";

type AggregateHeroKpiProps = {
  compactValue?: boolean;
  hint?: ReactNode;
  icon: AggregateMetricIconName;
  label: string;
  value: ReactNode;
};

type AggregateMetricTileProps = {
  icon: AggregateMetricIconName;
  label: string;
  value: string | number;
};

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

function AggregateMetricIcon({
  className,
  name,
}: {
  className?: string;
  name: AggregateMetricIconName;
}) {
  const path =
    name === "calendar"
      ? "M7 3v3M17 3v3M4.5 9h15M6 5h12a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 18 19H6a1.5 1.5 0 0 1-1.5-1.5v-11A1.5 1.5 0 0 1 6 5Z"
      : name === "chart"
        ? "M6 19v-7M12 19V5M18 19v-9"
      : name === "form"
        ? "M5 7h14M5 12h14M5 17h8"
      : name === "goal"
        ? "M4.5 7.5h15v9h-15v-9ZM8 7.5v9M16 7.5v9M4.5 12h15"
      : name === "grid"
        ? "M5 5h5v5H5V5Zm9 0h5v5h-5V5ZM5 14h5v5H5v-5Zm9 0h5v5h-5v-5Z"
      : name === "trend"
        ? "M4 16.5 9 11l4 4 7-8M15 7h5v5"
      : "M12 3.5 18.5 6v5.2c0 3.9-2.5 7.2-6.5 9.3-4-2.1-6.5-5.4-6.5-9.3V6L12 3.5Z";

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d={path} />
    </svg>
  );
}

function AggregateHeroKpi({
  compactValue = false,
  hint,
  icon,
  label,
  value,
}: AggregateHeroKpiProps) {
  return (
    <article className="rounded-[1.35rem] border border-white/72 bg-white/72 px-4 py-4 text-[#111c2d] shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
          {label}
        </p>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#e4f6ee] text-[#00513b]">
          <AggregateMetricIcon className="h-4 w-4" name={icon} />
        </span>
      </div>
      <p
        className={
          compactValue
            ? "mt-2 whitespace-nowrap font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-none tracking-[-0.055em]"
            : "mt-2 break-words font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-none tracking-[-0.04em]"
        }
      >
        {value}
      </p>
      {hint ? <p className="mt-3 text-sm text-[#515f74]">{hint}</p> : null}
    </article>
  );
}

function AggregateMetricTile({ icon, label, value }: AggregateMetricTileProps) {
  return (
    <article className="group flex min-h-[8.9rem] flex-col justify-between rounded-[1.1rem] border border-[rgba(216,227,251,0.78)] bg-[rgba(240,243,255,0.72)] p-4 text-[#111c2d] shadow-[inset_0_1px_0_rgba(255,255,255,0.68)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.62rem] font-semibold uppercase tracking-[0.15em] text-[#57657a]">
          {label}
        </p>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/78 text-[#00513b] shadow-[0_12px_28px_-24px_rgba(0,53,38,0.55)]">
          <AggregateMetricIcon className="h-4 w-4" name={icon} />
        </span>
      </div>
      <p className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold leading-none tracking-[-0.04em]">
        {value}
      </p>
    </article>
  );
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

function resolveSeasonLabel(competitionId: string | null, seasonId: string | null): string | null {
  if (!seasonId) {
    return null;
  }

  const competition = getCompetitionById(competitionId);
  const season = competition
    ? getSeasonByQueryId(seasonId, competition.seasonCalendar)
    : getSeasonById(seasonId);

  return season?.label ?? seasonId;
}

function resolveScopeLabel(competitionId: string | null, seasonId: string | null): string {
  const competition = getCompetitionById(competitionId);
  const seasonLabel = resolveSeasonLabel(competitionId, seasonId);

  if (competition && seasonLabel) {
    return `${competition.name} · ${seasonLabel}`;
  }

  if (competition) {
    return `${competition.name} · todas as temporadas`;
  }

  if (seasonLabel) {
    return `Todas as competições · ${seasonLabel}`;
  }

  return "Todas as competições · todas as temporadas";
}

export function TeamAggregateProfileContent({
  teamId,
  honorsPreview,
}: TeamAggregateProfileContentProps) {
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const contextsQuery = useTeamContexts(teamId, { competitionId, seasonId });
  const defaultContext = contextsQuery.data?.defaultContext ?? null;
  const defaultProfileQuery = useTeamProfile(
    teamId,
    { includeRecentMatches: false, includeSquad: false, includeStats: false },
    defaultContext,
  );
  const resolvedTeamName = defaultProfileQuery.data?.team.teamName ?? null;
  const teamsQuery = useTeamsList({
    pageSize: 100,
    search: resolvedTeamName ?? undefined,
    sortBy: "points",
    sortDirection: "desc",
  });
  const aggregateTeam =
    teamsQuery.data?.items.find((item) => item.teamId === teamId) ??
    teamsQuery.data?.items.find((item) => item.teamName === resolvedTeamName) ??
    null;
  const isLoading =
    contextsQuery.isLoading ||
    defaultProfileQuery.isLoading ||
    (resolvedTeamName !== null && teamsQuery.isLoading);

  if (isLoading && !aggregateTeam) {
    return (
      <ProfileShell className="space-y-6">
        <LoadingSkeleton height={160} />
        <LoadingSkeleton height={260} />
      </ProfileShell>
    );
  }

  if (!aggregateTeam) {
    return (
      <ProfileShell className="space-y-6">
        <EmptyState
          title="Recorte do clube indisponível"
          description="Não encontramos métricas agregadas para este clube nos filtros atuais."
        />
      </ProfileShell>
    );
  }

  const sharedFilters = {
    competitionId,
    seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  };
  const availableContexts = contextsQuery.data?.availableContexts ?? [];
  const competitionCount = new Set(
    availableContexts.map((context) => context.competitionId).filter(Boolean),
  ).size;
  const seasonCount = new Set(
    availableContexts.map((context) => context.seasonId).filter(Boolean),
  ).size;
  const winRate =
    aggregateTeam.matchesPlayed && aggregateTeam.matchesPlayed > 0
      ? ((aggregateTeam.wins ?? 0) / aggregateTeam.matchesPlayed) * 100
      : null;
  const pointsPerMatch =
    aggregateTeam.matchesPlayed && aggregateTeam.matchesPlayed > 0
      ? (aggregateTeam.points ?? 0) / aggregateTeam.matchesPlayed
      : null;
  const defaultContextHref = defaultContext ? buildCanonicalTeamPath(defaultContext, teamId) : null;
  const contextCards = availableContexts.slice(0, 8);

  return (
    <ProfileShell className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
        <Link className="transition-colors hover:text-[#00513b]" href={buildTeamsPath(sharedFilters)}>
          Times
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{aggregateTeam.teamName}</span>
      </div>

      <ProfilePanel className="profile-hero-clean overflow-hidden p-0" tone="accent">
        <div className="grid gap-6 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_11.5rem] xl:items-stretch">
          <div className="flex min-h-full flex-col gap-5 xl:justify-between">
            <div className="flex flex-wrap gap-2">
              <ProfileTag>{resolveScopeLabel(competitionId, seasonId)}</ProfileTag>
              <ProfileTag>Arquivo histórico</ProfileTag>
            </div>

            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <ProfileMedia
                alt={`Escudo de ${aggregateTeam.teamName}`}
                assetId={aggregateTeam.teamId}
                category="clubs"
                className="h-24 w-24 shrink-0 border border-white/18 bg-white/12"
                fallback={getTeamMonogram(aggregateTeam.teamName)}
                imageClassName="p-3"
                tone="contrast"
              />
              <div className="min-w-0">
                <p className="text-[0.7rem] font-bold uppercase tracking-[0.22em] text-white/58">
                  Perfil agregado do clube
                </p>
                <h1 className="mt-2 max-w-2xl break-words font-[family:var(--font-profile-headline)] text-4xl font-extrabold leading-[0.92] tracking-[-0.055em] text-white md:text-5xl">
                  {aggregateTeam.teamName}
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/62">
                  Recorte consolidado a partir das competições e temporadas disponíveis no acervo.
                </p>
              </div>
            </div>

            <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <AggregateHeroKpi
                label="Posição"
                value={aggregateTeam.position ? `${aggregateTeam.position}º` : "-"}
                hint={aggregateTeam.totalTeams ? `entre ${formatInteger(aggregateTeam.totalTeams)} times` : "ranking do recorte"}
                icon="shield"
              />
              <AggregateHeroKpi
                label="Pontos"
                value={formatInteger(aggregateTeam.points)}
                hint={`${formatDecimal(pointsPerMatch)} por jogo`}
                icon="chart"
              />
              <AggregateHeroKpi
                compactValue
                label="Campanha"
                value={`${formatInteger(aggregateTeam.wins)}-${formatInteger(aggregateTeam.draws)}-${formatInteger(aggregateTeam.losses)}`}
                hint={`${formatInteger(aggregateTeam.matchesPlayed)} jogos`}
                icon="form"
              />
              <AggregateHeroKpi
                label="Saldo"
                value={formatGoalDiff(aggregateTeam.goalDiff)}
                hint={`Aproveitamento ${formatPercentage(winRate)}`}
                icon="trend"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              {defaultContextHref ? (
                <Link className="button-pill button-pill-primary" href={defaultContextHref}>
                  Abrir temporada principal
                </Link>
              ) : null}
              <Link className="button-pill button-pill-soft" href={buildRankingsHubPath(sharedFilters)}>
                Rankings do recorte
              </Link>
              <Link className="button-pill button-pill-soft" href={buildTeamsPath(sharedFilters)}>
                Ver times no recorte
              </Link>
            </div>

            {honorsPreview ? <TeamHonorsSection honors={honorsPreview} /> : null}
          </div>

          <aside className="grid auto-rows-fr content-start gap-3 xl:pt-14">
            <AggregateMetricTile icon="grid" label="Competições" value={competitionCount || "-"} />
            <AggregateMetricTile icon="calendar" label="Temporadas" value={seasonCount || "-"} />
            <AggregateMetricTile icon="goal" label="Gols pró" value={formatInteger(aggregateTeam.goalsFor)} />
            <AggregateMetricTile icon="shield" label="Gols contra" value={formatInteger(aggregateTeam.goalsAgainst)} />
          </aside>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Entradas do clube no acervo
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Competições e temporadas disponíveis
            </h2>
          </div>
          <ProfileTag>{formatInteger(availableContexts.length)} recortes</ProfileTag>
        </div>

        {contextCards.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {contextCards.map((context) => (
              <Link
                className="group rounded-[1.25rem] border border-[rgba(216,227,251,0.78)] bg-white/78 p-4 transition hover:border-[#8bd6b6] hover:bg-white"
                href={buildCanonicalTeamPath(context, teamId)}
                key={`${context.competitionId}-${context.seasonId}`}
              >
                <p className="text-[0.64rem] font-bold uppercase tracking-[0.18em] text-[#69778d]">
                  {context.seasonLabel}
                </p>
                <p className="mt-2 text-sm font-bold text-[#111c2d]">
                  {context.competitionName}
                </p>
                <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#00513b]">
                  Abrir perfil completo
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Sem recortes detalhados"
            description="O agregado existe, mas os caminhos por competição e temporada ainda não foram retornados."
          />
        )}
      </ProfilePanel>
    </ProfileShell>
  );
}
