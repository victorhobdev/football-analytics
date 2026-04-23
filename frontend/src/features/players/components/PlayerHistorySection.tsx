"use client";

import Link from "next/link";

import type { PlayerHistoryEntry, PlayerProfileMeta } from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileCoveragePill,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  appendFilterQueryString,
  buildCanonicalTeamPath,
  buildSeasonHubTabPath,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type PlayerHistorySectionProps = {
  coverage: CoverageState;
  filters: {
    roundId?: string | null;
    venue?: string | null;
    lastN?: number | null;
    dateRangeStart?: string | null;
    dateRangeEnd?: string | null;
  };
  history: PlayerHistoryEntry[] | undefined;
  profileMeta?: PlayerProfileMeta | null;
};

function buildEntryContext(entry: PlayerHistoryEntry): CompetitionSeasonContext | null {
  if (!entry.competitionId || !entry.competitionKey || !entry.competitionName || !entry.seasonId || !entry.seasonLabel) {
    return null;
  }

  return {
    competitionId: entry.competitionId,
    competitionKey: entry.competitionKey,
    competitionName: entry.competitionName,
    seasonId: entry.seasonId,
    seasonLabel: entry.seasonLabel,
  };
}

export function PlayerHistorySection({
  coverage,
  filters,
  history,
  profileMeta,
}: PlayerHistorySectionProps) {
  const items = history ?? [];

  if (items.length === 0) {
    return (
      <div className="space-y-4">
        {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}
        <EmptyState
          title={profileMeta && !profileMeta.hasHistoricalStats ? "Sem histórico consolidado" : "Histórico indisponível"}
          description={
            profileMeta && !profileMeta.hasHistoricalStats
              ? "Este perfil permanece disponível, mas sem histórico competitivo consolidado na plataforma."
              : "Não há histórico suficiente para montar esta visão do jogador agora."
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}

      <ProfilePanel className="space-y-4" tone="soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Histórico
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Participação por contexto
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
              Cada contexto reúne time, temporada e volume real de participação identificado pelo
              produto.
            </p>
          </div>
          <ProfileCoveragePill coverage={coverage} />
        </div>
      </ProfilePanel>

      <section className="space-y-3">
        {items.map((entry) => {
          const entryContext = buildEntryContext(entry);
          const seasonHubHref = entryContext
            ? buildSeasonHubTabPath(entryContext, "calendar", filters)
            : null;
          const teamHref =
            entryContext && entry.teamId
              ? appendFilterQueryString(
                  buildCanonicalTeamPath(entryContext, entry.teamId),
                  filters,
                  ["competitionId", "seasonId"],
                )
              : null;

          return (
            <ProfilePanel
              className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]"
              key={`${entry.competitionId ?? "na"}-${entry.seasonId ?? "na"}-${entry.teamId ?? "na"}`}
            >
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{entry.competitionName ?? "Competição"}</ProfileTag>
                  <ProfileTag>{entry.seasonLabel ?? "Temporada"}</ProfileTag>
                  {entry.teamName ? <ProfileTag>{entry.teamName}</ProfileTag> : null}
                </div>

                <div>
                  <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                    {entry.teamName ?? "Time não informado"}
                  </h3>
                  <p className="mt-1 text-sm text-[#57657a]">
                    Última participação consolidada em {formatDate(entry.lastMatchAt)}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-5">
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Jogos</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{entry.matchesPlayed ?? "-"}</p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Min</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{entry.minutesPlayed ?? "-"}</p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Gols</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{entry.goals ?? "-"}</p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Assistências</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{entry.assists ?? "-"}</p>
                  </div>
                  <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Nota</p>
                    <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                      {typeof entry.rating === "number" ? entry.rating.toFixed(2) : "-"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex flex-col items-stretch gap-2 xl:min-w-[220px]">
                {seasonHubHref ? (
                  <Link
                    className="button-pill button-pill-soft"
                    href={seasonHubHref}
                  >
                    Abrir temporada
                  </Link>
                ) : null}
                {teamHref ? (
                  <Link
                    className="button-pill button-pill-primary"
                    href={teamHref}
                  >
                    Abrir time
                  </Link>
                ) : null}
              </div>
            </ProfilePanel>
          );
        })}
      </section>
    </div>
  );
}
