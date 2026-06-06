"use client";

import Link from "next/link";

import type { TeamSquadPlayer } from "@/features/teams/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfilePanel,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import { buildCanonicalPlayerPath, buildFilterQueryString } from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type TeamSquadSectionProps = {
  competitionContext: CompetitionSeasonContext;
  coverage: CoverageState;
  filters: {
    competitionId?: string | null;
    seasonId?: string | null;
    roundId?: string | null;
    venue?: string | null;
    lastN?: number | null;
    dateRangeStart?: string | null;
    dateRangeEnd?: string | null;
  };
  squad: TeamSquadPlayer[] | undefined;
};

export function TeamSquadSection({
  competitionContext,
  coverage,
  filters,
  squad,
}: TeamSquadSectionProps) {
  const canonicalExtraQuery = buildFilterQueryString(filters, ["competitionId", "seasonId"]);
  const items = squad ?? [];

  if (items.length === 0) {
    return (
      <div className="space-y-4">
        {coverage.status === "partial" ? <PartialDataBanner coverage={coverage} /> : null}
        <EmptyState
          title="Elenco indisponível"
          description="Ainda não há jogadores identificados para este time no contexto atual."
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
              Elenco
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#111c2d]">
              Elenco por minutos jogados
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-[#57657a]">
              A ordem destaca quem mais participou da temporada e ajuda a chegar rápido ao perfil
              certo dentro do elenco.
            </p>
          </div>
          <ProfileCoveragePill coverage={coverage} />
        </div>
      </ProfilePanel>

      <ProfileAlert title="Disponibilidade do elenco" tone="info">
        Os dados disponíveis ainda não trazem afastamentos com
        consistência suficiente. Por enquanto, a leitura pública fica concentrada em participação,
        minutos e última aparição.
      </ProfileAlert>

      <section className="space-y-3">
        {items.map((player) => {
          const profileHref =
            player.playerId && player.playerId.trim().length > 0
              ? `${buildCanonicalPlayerPath(competitionContext, player.playerId)}${canonicalExtraQuery}`
              : null;

          return (
            <ProfilePanel className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]" key={`${player.playerId ?? player.playerName}-${player.positionName}`}>
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <ProfileTag>{player.positionName ?? "Sem posição"}</ProfileTag>
                  <ProfileTag>#{player.shirtNumber ?? "-"}</ProfileTag>
                  <ProfileTag>{player.starts ?? 0} titularidades</ProfileTag>
                </div>

                <div>
                  {profileHref ? (
                    <Link
                      className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d] transition-colors hover:text-[#003526]"
                      href={profileHref}
                    >
                      {player.playerName ?? "Jogador sem nome"}
                    </Link>
                  ) : (
                    <h3 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
                      {player.playerName ?? "Jogador sem nome"}
                    </h3>
                  )}
                  <p className="mt-1 text-sm text-[#57657a]">
                    Última aparição: {formatDate(player.lastAppearanceAt)}
                  </p>
                </div>
              </div>

              <div className="grid min-w-[240px] gap-3 sm:grid-cols-3 md:grid-cols-1 lg:grid-cols-3">
                <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Jogos</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{player.appearances ?? "-"}</p>
                </div>
                <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Minutos</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">{player.minutesPlayed ?? "-"}</p>
                </div>
                <div className="rounded-[1.15rem] bg-[rgba(240,243,255,0.88)] px-4 py-3">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Média</p>
                  <p className="mt-2 text-2xl font-extrabold text-[#111c2d]">
                    {typeof player.averageMinutes === "number" ? player.averageMinutes.toFixed(1) : "-"}
                  </p>
                </div>
              </div>
            </ProfilePanel>
          );
        })}
      </section>
    </div>
  );
}
