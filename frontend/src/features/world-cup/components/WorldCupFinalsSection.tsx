"use client";

import Link from "next/link";

import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileAlert, ProfilePanel } from "@/shared/components/profile/ProfilePrimitives";

import { buildWorldCupEditionPath, buildWorldCupTeamPath } from "@/features/world-cup/routes";
import type { WorldCupFinalItem, WorldCupFinalOmission, WorldCupTeamReference } from "@/features/world-cup/types/world-cup.types";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function normalizeCompareValue(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function buildTeamFallback(teamName: string | null | undefined): string {
  const normalized = (teamName ?? "")
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean);

  if (normalized.length === 0) {
    return "WC";
  }

  if (normalized.length === 1) {
    return normalized[0].slice(0, 3).toUpperCase();
  }

  return `${normalized[0][0] ?? ""}${normalized[1][0] ?? ""}`.toUpperCase();
}

function teamsMatch(left: WorldCupTeamReference | null | undefined, right: WorldCupTeamReference | null | undefined): boolean {
  if (!left || !right) {
    return false;
  }

  if (left.teamId && right.teamId) {
    return left.teamId === right.teamId;
  }

  return normalizeCompareValue(left.teamName) === normalizeCompareValue(right.teamName);
}

function TeamLink({
  className,
  teamId,
  teamName,
}: {
  className?: string;
  teamId: string | null | undefined;
  teamName: string | null | undefined;
}) {
  if (teamId && teamName) {
    return (
      <Link className={joinClasses("font-semibold text-[#111c2d] transition-colors hover:text-[#003526]", className)} href={buildWorldCupTeamPath(teamId)}>
        {teamName}
      </Link>
    );
  }

  return <span className={joinClasses("font-semibold text-[#111c2d]", className)}>{teamName ?? "Não identificado"}</span>;
}

function FinalsGlyph({
  className,
  icon,
}: {
  className?: string;
  icon: "trophy" | "stadium" | "info" | "shootout";
}) {
  if (icon === "stadium") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M4.5 16.5h15M6 16.5v-6l6-3 6 3v6M9 9.7v6.8M15 9.7v6.8M10.2 16.5v-3h3.6v3"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "shootout") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 6.8 7.4v4.8c0 3.4 2.1 6.5 5.2 7.3 3.1-.8 5.2-3.9 5.2-7.3V7.4L12 4.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M9.4 12.1 11 13.7l3.8-3.8"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "info") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 16.2v-4.4M12 7.8h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
      <path
        d="M8 4.5h8v2.8c0 2.6-1.6 4.8-4 5.7-2.4-.9-4-3.1-4-5.7V4.5Zm0 0H5.5c0 2.4 1 4.2 2.9 5.1M16 4.5h2.5c0 2.4-1 4.2-2.9 5.1M10 15.2v2.3M14 15.2v2.3M7.5 19.5h9"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function FinalMetaChip({
  icon,
  label,
  tone = "base",
}: {
  icon: "trophy" | "stadium" | "info" | "shootout";
  label: string;
  tone?: "base" | "success";
}) {
  return (
    <span
      className={joinClasses(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em]",
        tone === "success"
          ? "border-[rgba(18,105,74,0.14)] bg-[rgba(160,219,191,0.2)] text-[#00513b]"
          : "border-[rgba(205,188,143,0.34)] bg-[rgba(252,248,238,0.94)] text-[#6b5320]",
      )}
    >
      <FinalsGlyph className="h-3.5 w-3.5" icon={icon} />
      {label}
    </span>
  );
}

function FinalTeamCard({
  isWinner,
  roleLabel,
  team,
  teamTone = "base",
}: {
  isWinner: boolean;
  roleLabel: string;
  team: WorldCupTeamReference | null | undefined;
  teamTone?: "base" | "inverse";
}) {
  return (
    <div
      className={joinClasses(
        "flex h-full items-center gap-3 rounded-[1.25rem] border px-4 py-3.5",
        isWinner
          ? "border-[rgba(18,105,74,0.18)] bg-[linear-gradient(135deg,rgba(234,247,240,0.98),rgba(247,250,247,0.9))] shadow-[0_20px_44px_-34px_rgba(0,81,59,0.34)]"
          : "border-[rgba(191,201,195,0.36)] bg-[rgba(248,250,251,0.9)]",
        teamTone === "inverse" ? "lg:flex-row-reverse lg:text-right" : "",
      )}
    >
      <ProfileMedia
        alt={team?.teamName ?? "Seleção"}
        assetId={team?.teamId}
        category="clubs"
        className="h-12 w-12"
        fallback={buildTeamFallback(team?.teamName)}
        shape="circle"
      />

      <div className={joinClasses("min-w-0 space-y-1", teamTone === "inverse" ? "lg:text-right" : "")}>
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#6c7b71]">{roleLabel}</p>
        <TeamLink
          className="block truncate font-[family:var(--font-profile-headline)] text-[1.4rem] font-extrabold tracking-[-0.04em]"
          teamId={team?.teamId}
          teamName={team?.teamName}
        />
        
      </div>
    </div>
  );
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
    <ProfilePanel className="space-y-6" tone={tone}>
      <header className="space-y-2">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Finais históricas</p>
        <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
          Lista de decisões
        </h2>
        <p className="max-w-3xl text-sm/6 text-[#57657a]">
          Ano, confronto, placar e contexto da partida que definiu cada edição. Em 1950, a leitura usa o duelo
          decisivo do grupo final.
        </p>
      </header>

      {omittedEditions.length > 0 ? (
        <ProfileAlert className="border border-[rgba(219,173,86,0.22)] bg-[linear-gradient(180deg,rgba(255,247,235,0.96),rgba(255,251,244,0.92))]" title="Edições fora da lista principal" tone="warning">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[rgba(219,173,86,0.2)] bg-white/90 text-[#9a6d1b]">
              <FinalsGlyph className="h-4 w-4" icon="info" />
            </span>
            <div className="space-y-1.5">
              {omittedEditions.map((item) => (
                <p key={item.seasonLabel}>
                  <span className="font-semibold">{item.year}</span>: {item.reason}
                </p>
              ))}
            </div>
          </div>
        </ProfileAlert>
      ) : null}

      <div className="space-y-3">
        {finals.map((item) => (
          <article
            className="group relative overflow-hidden rounded-[1.55rem] border border-[rgba(191,201,195,0.42)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,250,248,0.94))] px-4 py-4 shadow-[0_28px_72px_-58px_rgba(17,28,45,0.26)] md:px-5"
            key={item.seasonLabel}
          >
            <div className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-[linear-gradient(180deg,rgba(188,151,54,0.1),transparent)]" />
            <div className="pointer-events-none absolute -right-12 top-8 h-32 w-32 rounded-full bg-[radial-gradient(circle,rgba(192,154,56,0.14),transparent_72%)]" />

            <div className="relative space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#617088]">Edição</p>
                  <Link
                    className="inline-flex font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.05em] text-[#111c2d] transition-colors hover:text-[#003526]"
                    href={buildWorldCupEditionPath(item.seasonLabel)}
                  >
                    {item.year}
                  </Link>
                  <p className="text-sm/5 text-[#6a5a3a]">Copa do Mundo FIFA {item.year}</p>
                </div>

                <div className="flex flex-wrap items-center justify-end gap-2">
                  {item.resolutionType === "final_round" ? <FinalMetaChip icon="info" label="Grupo final" /> : null}
                  {item.resolutionType === "penalties" ? <FinalMetaChip icon="shootout" label="Pênaltis" /> : null}
                  {item.champion?.teamName ? <FinalMetaChip icon="trophy" label={item.champion.teamName} tone="success" /> : null}
                </div>
              </div>

              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-stretch">
                <FinalTeamCard
                  isWinner={teamsMatch(item.homeTeam, item.champion)}
                  roleLabel={teamsMatch(item.homeTeam, item.champion) ? "Campeão" : "Vice-campeão"}
                  team={item.homeTeam}
                />

                <div className="flex min-w-[10.5rem] flex-col items-center justify-center rounded-[1.3rem] border border-[rgba(198,173,111,0.3)] bg-[radial-gradient(circle_at_top,rgba(255,250,238,0.98),rgba(247,243,232,0.94))] px-4 py-4 text-center shadow-[0_20px_48px_-36px_rgba(106,90,58,0.42)]">
                  <span className="mb-2 inline-flex h-9 w-9 items-center justify-center rounded-full border border-[rgba(198,173,111,0.3)] bg-white/92 text-[#8a6d18]">
                    <FinalsGlyph className="h-4 w-4" icon="trophy" />
                  </span>

                  <p className="font-[family:var(--font-profile-headline)] text-[2.45rem] font-extrabold leading-none tracking-[-0.05em] text-[#111c2d]">
                    {formatWholeNumber(item.homeScore)} x {formatWholeNumber(item.awayScore)}
                  </p>

                  <p className="mt-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#6b5320]">
                    {item.shootout
                      ? `Pênaltis ${formatWholeNumber(item.shootout.home)} x ${formatWholeNumber(item.shootout.away)}`
                      : item.resolutionType === "final_round"
                        ? "Jogo do título"
                        : "Placar final"}
                  </p>
                </div>

                <FinalTeamCard
                  isWinner={teamsMatch(item.awayTeam, item.champion)}
                  roleLabel={teamsMatch(item.awayTeam, item.champion) ? "Campeão" : "Vice-campeão"}
                  team={item.awayTeam}
                  teamTone="inverse"
                />
              </div>

              {item.venueName || item.resolutionNote ? (
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-[rgba(191,201,195,0.28)] pt-3 text-sm/6 text-[#57657a]">
                  {item.venueName ? (
                    <span className="inline-flex items-center gap-2">
                      <FinalsGlyph className="h-4 w-4 text-[#8a6d18]" icon="stadium" />
                      {item.venueName}
                    </span>
                  ) : null}

                  {item.resolutionNote ? (
                    <span className="inline-flex items-center gap-2">
                      <FinalsGlyph className="h-4 w-4 text-[#8a6d18]" icon="info" />
                      {item.resolutionNote}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </ProfilePanel>
  );
}
