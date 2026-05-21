"use client";

import Link from "next/link";

import { ProfileAlert, ProfilePanel } from "@/shared/components/profile/ProfilePrimitives";

import { buildWorldCupEditionPath, buildWorldCupTeamPath } from "@/features/world-cup/routes";
import type { WorldCupFinalItem, WorldCupFinalOmission } from "@/features/world-cup/types/world-cup.types";

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function TeamLink({
  teamId,
  teamName,
}: {
  teamId: string | null | undefined;
  teamName: string | null | undefined;
}) {
  if (teamId && teamName) {
    return (
      <Link className="font-semibold text-[#111c2d] transition-colors hover:text-[#003526]" href={buildWorldCupTeamPath(teamId)}>
        {teamName}
      </Link>
    );
  }

  return <span className="font-semibold text-[#111c2d]">{teamName ?? "Nao identificado"}</span>;
}

export function WorldCupFinalsSection({
  finals,
  omittedEditions,
  tone = "base",
}: {
  finals: WorldCupFinalItem[];
  omittedEditions: WorldCupFinalOmission[];
  tone?: "base" | "soft";
}) {
  return (
    <ProfilePanel className="space-y-5" tone={tone}>
      <header className="space-y-2">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Finais historicas</p>
        <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
          Lista de decisoes
        </h2>
        <p className="max-w-3xl text-sm/6 text-[#57657a]">
          Ano, selecoes, placar registrado e local da final unica quando esse formato existe de forma objetiva no banco.
        </p>
      </header>

      {omittedEditions.length > 0 ? (
        <ProfileAlert title="Edicoes omitidas da lista de finais" tone="warning">
          <div className="space-y-2">
            {omittedEditions.map((item) => (
              <p key={item.seasonLabel}>
                {item.year}: {item.reason}
              </p>
            ))}
          </div>
        </ProfileAlert>
      ) : null}

      <div className="space-y-4">
        {finals.map((item) => (
          <article
            className="rounded-[1.35rem] border border-[rgba(191,201,195,0.42)] bg-white/82 px-4 py-4"
            key={item.seasonLabel}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">Edicao</p>
                <Link
                  className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.05em] text-[#111c2d] transition-colors hover:text-[#003526]"
                  href={buildWorldCupEditionPath(item.seasonLabel)}
                >
                  {item.year}
                </Link>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {item.resolutionType === "penalties" ? (
                  <span className="rounded-full bg-[rgba(216,227,251,0.78)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
                    Pênaltis
                  </span>
                ) : null}
                {item.champion?.teamName ? (
                  <span className="rounded-full bg-[rgba(139,214,182,0.22)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#00513b]">
                    {item.champion.teamName}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-center">
              <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
                <TeamLink teamId={item.homeTeam?.teamId} teamName={item.homeTeam?.teamName} />
              </div>

              <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-4 py-3 text-center">
                <p className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                  {formatWholeNumber(item.homeScore)} x {formatWholeNumber(item.awayScore)}
                </p>
                {item.shootout ? (
                  <p className="mt-1 text-xs/5 text-[#57657a]">
                    Pênaltis: {item.shootout.home} x {item.shootout.away}
                  </p>
                ) : null}
              </div>

              <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
                <TeamLink teamId={item.awayTeam?.teamId} teamName={item.awayTeam?.teamName} />
              </div>
            </div>

            {item.venueName ? <p className="mt-3 text-sm/6 text-[#57657a]">{item.venueName}</p> : null}
            {item.resolutionNote ? <p className="mt-2 text-xs/5 text-[#57657a]">{item.resolutionNote}</p> : null}
          </article>
        ))}
      </div>
    </ProfilePanel>
  );
}
