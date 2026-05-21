import Link from "next/link";

import type { MatchListItem } from "@/features/matches/types";
import { resolveMatchDisplayContext } from "@/features/matches/utils/match-context";
import { ProfilePanel, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import type { CompetitionSeasonContextInput } from "@/shared/types/context.types";
import {
  appendFilterQueryString,
  buildCanonicalTeamPath,
  buildHeadToHeadPath,
  buildTeamResolverPath,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type MatchCenterHeaderProps = {
  match: MatchListItem;
  contextInput?: CompetitionSeasonContextInput & {
    roundId?: string | null;
    venue?: string | null;
    lastN?: number | null;
    dateRangeStart?: string | null;
    dateRangeEnd?: string | null;
  };
};

function resolveScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "-";
}

function resolveMatchStatusLabel(status: string | null | undefined): string {
  const normalizedStatus = status?.trim().toLowerCase();

  switch (normalizedStatus) {
    case "finished":
      return "Fim";
    case "live":
      return "Ao vivo";
    case "scheduled":
      return "Agendada";
    case "cancelled":
      return "Cancelada";
    default:
      return status?.trim().length ? status : "Status indefinido";
  }
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

function TeamLink({ href, name }: { href: string | null; name: string }) {
  if (!href) {
    return <span>{name}</span>;
  }

  return (
    <Link className="transition-colors hover:text-[#00513b]" href={href}>
      {name}
    </Link>
  );
}

export function MatchCenterHeader({ match, contextInput = {} }: MatchCenterHeaderProps) {
  const competitionContext = resolveCompetitionSeasonContext({
    competitionId: match.competitionId,
    seasonId: match.seasonId,
  });
  const displayContext = resolveMatchDisplayContext(match);
  const extraContextKeys = competitionContext ? (["competitionId", "seasonId"] as const) : [];
  const homeTeamName = match.homeTeamName ?? "Mandante";
  const awayTeamName = match.awayTeamName ?? "Visitante";
  const homeTeamHref =
    match.homeTeamId && competitionContext
      ? appendFilterQueryString(
          buildCanonicalTeamPath(competitionContext, match.homeTeamId),
          contextInput,
          extraContextKeys,
        )
      : match.homeTeamId
        ? buildTeamResolverPath(match.homeTeamId, {
            ...contextInput,
            competitionId: match.competitionId,
            seasonId: match.seasonId,
          })
        : null;
  const awayTeamHref =
    match.awayTeamId && competitionContext
      ? appendFilterQueryString(
          buildCanonicalTeamPath(competitionContext, match.awayTeamId),
          contextInput,
          extraContextKeys,
        )
      : match.awayTeamId
        ? buildTeamResolverPath(match.awayTeamId, {
            ...contextInput,
            competitionId: match.competitionId,
            seasonId: match.seasonId,
          })
        : null;
  const headToHeadHref =
    match.homeTeamId && match.awayTeamId
      ? buildHeadToHeadPath({
          ...contextInput,
          competitionId: match.competitionId,
          seasonId: match.seasonId,
          teamA: match.homeTeamId,
          teamB: match.awayTeamId,
        })
      : null;
  const matchStatusLabel = resolveMatchStatusLabel(match.status);
  const kickoffLabel = formatDate(match.kickoffAt);
  const venueLabel = match.venueName?.trim() || "Local indisponível";
  const seasonLabel = competitionContext?.seasonLabel ?? match.seasonLabel ?? match.seasonId;

  return (
    <ProfilePanel className="space-y-6" tone="soft">
      <div className="flex flex-wrap items-center gap-2">
        {match.competitionName ? <ProfileTag>{match.competitionName}</ProfileTag> : null}
        {seasonLabel ? <ProfileTag>Temporada {seasonLabel}</ProfileTag> : null}
        {displayContext.tags.map((tag) => (
          <ProfileTag key={`${match.matchId}-${tag}`}>{tag}</ProfileTag>
        ))}
        <ProfileTag className="bg-white/80 text-[#00513b]">{matchStatusLabel}</ProfileTag>
      </div>

      <header className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-center">
        <section className="space-y-3 text-center xl:text-left">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mandante
          </p>
          <div className="flex flex-col items-center gap-3 xl:items-start">
            <ProfileMedia
              alt={homeTeamName}
              assetId={match.homeTeamId}
              category="clubs"
              className="h-14 w-14 border-[rgba(191,201,195,0.45)] bg-white"
              fallback={getTeamMonogram(homeTeamName)}
              fallbackClassName="text-sm"
              imageClassName="p-2"
              shape="circle"
            />
            <h1 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-tight text-[#111c2d] md:text-4xl">
              <TeamLink href={homeTeamHref} name={homeTeamName} />
            </h1>
          </div>
          <p className="text-sm text-[#57657a]">
            Abra o perfil do time sem sair desta partida.
          </p>
        </section>

        <section className="rounded-[1.65rem] bg-white/88 px-6 py-5 text-center shadow-[0_24px_60px_-48px_rgba(17,28,45,0.35)]">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-[#57657a]">
            Placar
          </p>
          <div className="mt-4 flex items-center justify-center gap-4 md:gap-6">
            <span className="font-[family:var(--font-profile-headline)] text-5xl font-extrabold text-[#111c2d]">
              {resolveScore(match.homeScore)}
            </span>
            <div className="space-y-2">
              <div className="rounded-full bg-[#e7eeff] px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#404944]">
                {matchStatusLabel}
              </div>
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#57657a]">
                {kickoffLabel}
              </p>
            </div>
            <span className="font-[family:var(--font-profile-headline)] text-5xl font-extrabold text-[#111c2d]">
              {resolveScore(match.awayScore)}
            </span>
          </div>
          <p className="mt-4 text-sm font-medium text-[#1f2d40]">{venueLabel}</p>
          {headToHeadHref ? (
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link
                className="button-pill button-pill-primary"
                href={headToHeadHref}
              >
                Comparar confronto
              </Link>
            </div>
          ) : null}
        </section>

        <section className="space-y-3 text-center xl:text-right">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Visitante
          </p>
          <div className="flex flex-col items-center gap-3 xl:items-end">
            <ProfileMedia
              alt={awayTeamName}
              assetId={match.awayTeamId}
              category="clubs"
              className="h-14 w-14 border-[rgba(191,201,195,0.45)] bg-white"
              fallback={getTeamMonogram(awayTeamName)}
              fallbackClassName="text-sm"
              imageClassName="p-2"
              shape="circle"
            />
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-tight text-[#111c2d] md:text-4xl">
              <TeamLink href={awayTeamHref} name={awayTeamName} />
            </h2>
          </div>
          <p className="text-sm text-[#57657a]">
            Siga para o time visitante a partir desta partida.
          </p>
        </section>
      </header>
    </ProfilePanel>
  );
}
