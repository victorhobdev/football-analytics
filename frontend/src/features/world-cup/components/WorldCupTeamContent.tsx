"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileAlert, ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { useWorldCupTeam } from "@/features/world-cup/hooks/useWorldCupTeam";
import { buildWorldCupEditionPath, buildWorldCupHubPath, buildWorldCupTeamsPath } from "@/features/world-cup/routes";
import type { WorldCupTeamParticipation, WorldCupTeamSummary } from "@/features/world-cup/types/world-cup.types";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function buildFallbackLabel(value: string | null | undefined): string {
  const tokens = (value ?? "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (tokens.length === 0) {
    return "WC";
  }

  if (tokens.length === 1) {
    return tokens[0].slice(0, 3).toUpperCase();
  }

  return tokens
    .slice(0, 2)
    .map((token) => token[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

function buildHeroMeta(team: WorldCupTeamSummary): string {
  const titlesLabel =
    team.titlesCount === 1 ? "1 título" : `${formatWholeNumber(team.titlesCount)} títulos`;

  return `${formatWholeNumber(team.participationsCount)} Copas · ${titlesLabel} · ${team.bestResultLabel}`;
}

function SummaryIcon({ kind }: { kind: "participations" | "titles" | "best" }) {
  if (kind === "participations") {
    return (
      <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
        <path
          d="M12 3.5 19 6.8v5.7c0 4-2.4 7.2-7 8.9-4.6-1.7-7-4.9-7-8.9V6.8l7-3.3Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (kind === "titles") {
    return (
      <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
        <path
          d="M8 5.5h8M9 3.5h6M8.5 5.5v3.2c0 1.8 1.2 3.3 3.5 4.3 2.3-1 3.5-2.5 3.5-4.3V5.5M7 18.5h10M10 14.5V18.5M14 14.5V18.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
      <path
        d="M6 17.5h12M7.5 14.5h9M12 4.5v10"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
      <circle cx="12" cy="7" fill="currentColor" r="1.2" />
    </svg>
  );
}

function SummaryCard({
  kind,
  label,
  support,
  value,
}: {
  kind: "participations" | "titles" | "best";
  label: string;
  support: string;
  value: string;
}) {
  const iconToneClassName =
    kind === "participations"
      ? "bg-[rgba(214,242,229,0.92)] text-[#00513b]"
      : kind === "titles"
        ? "bg-[rgba(255,232,214,0.94)] text-[#7b4207]"
        : "bg-[rgba(216,227,251,0.92)] text-[#39537f]";

  return (
    <article className="rounded-[1.5rem] border border-[rgba(191,201,195,0.44)] bg-[linear-gradient(180deg,rgba(255,255,255,0.92)_0%,rgba(248,250,253,0.96)_100%)] p-4 shadow-[0_24px_60px_-52px_rgba(17,28,45,0.28)]">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
          <p className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.05em] text-[#111c2d]">
            {value}
          </p>
        </div>
        <span
          className={joinClasses(
            "inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/80 shadow-[0_18px_34px_-24px_rgba(17,28,45,0.34)]",
            iconToneClassName,
          )}
        >
          <SummaryIcon kind={kind} />
        </span>
      </div>
      <p className="mt-4 text-sm/6 text-[#57657a]">{support}</p>
    </article>
  );
}

function ParticipationCard({ participation }: { participation: WorldCupTeamParticipation }) {
  const topScorerName = participation.topScorer?.playerName ?? "Sem registro";
  const topScorerGoalsLabel = participation.topScorer
    ? `${participation.topScorer.goals} gol${participation.topScorer.goals === 1 ? "" : "s"}`
    : "Sem gols";

  return (
    <article className="rounded-[1.55rem] border border-[rgba(191,201,195,0.44)] bg-[linear-gradient(180deg,rgba(255,255,255,0.9)_0%,rgba(248,250,253,0.96)_100%)] p-4 shadow-[0_24px_64px_-56px_rgba(17,28,45,0.26)] md:p-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)_auto] xl:items-center">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[rgba(216,227,251,0.76)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
              {participation.resultLabel}
            </span>
          </div>
          <div className="space-y-1">
            <h3 className="font-[family:var(--font-profile-headline)] text-[2.3rem] font-extrabold leading-none tracking-[-0.06em] text-[#111c2d]">
              {participation.year}
            </h3>
            <p className="text-sm/6 text-[#57657a]">{participation.editionName}</p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[9rem_minmax(0,1fr)]">
          <div className="rounded-[1.15rem] border border-[rgba(191,201,195,0.36)] bg-[rgba(246,248,252,0.88)] px-4 py-3">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">Jogos</p>
            <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.9rem] font-extrabold leading-none text-[#111c2d]">
              {participation.matchesCount}
            </p>
          </div>

          <div className="rounded-[1.15rem] border border-[rgba(191,201,195,0.36)] bg-[rgba(246,248,252,0.88)] px-4 py-3">
            <div className="flex items-center gap-3">
              <ProfileMedia
                alt={topScorerName}
                assetId={participation.topScorer?.playerId}
                category="players"
                className="h-14 w-14 rounded-[1.1rem]"
                fallback={buildFallbackLabel(topScorerName)}
                imageClassName="p-2"
                shape="rounded"
              />
              <div className="min-w-0">
                <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">Artilheiro</p>
                <p className="mt-1 truncate font-semibold text-[#111c2d]">{topScorerName}</p>
                <p className="mt-1 text-sm/6 text-[#57657a]">{topScorerGoalsLabel}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center xl:justify-end">
          <Link
            className="inline-flex items-center rounded-full bg-[#003526] px-4 py-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white shadow-[0_18px_36px_-20px_rgba(0,53,38,0.58)] transition-colors hover:bg-[#00513b]"
            href={buildWorldCupEditionPath(participation.seasonLabel)}
          >
            Abrir edição
          </Link>
        </div>
      </div>
    </article>
  );
}

export function WorldCupTeamContent({ teamId }: { teamId: string }) {
  const teamQuery = useWorldCupTeam(teamId);

  if (teamQuery.isLoading && !teamQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos montando o histórico desta seleção."
        kicker="Copa do Mundo"
        loading
        title="Carregando seleção"
      />
    );
  }

  if (teamQuery.isError && !teamQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupTeamsPath()}
        actionLabel="Voltar às seleções"
        description="Não foi possível carregar esta seleção agora."
        kicker="Copa do Mundo"
        title="Falha ao abrir seleção"
        tone="critical"
      />
    );
  }

  if (!teamQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupTeamsPath()}
        actionLabel="Voltar às seleções"
        description="Esta seleção não retornou dados suficientes."
        kicker="Copa do Mundo"
        title="Seleção indisponível"
        tone="warning"
      />
    );
  }

  const { team, participations, historicalScorers } = teamQuery.data;
  const orderedParticipations = [...participations].sort((left, right) => right.year - left.year);

  return (
    <ProfileShell className="world-cup-theme space-y-6" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Início
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupHubPath()}>
          Copa do Mundo
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupTeamsPath()}>
          Seleções
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{team.teamName ?? "Seleção"}</span>
      </div>

      <ProfilePanel className="world-cup-hero overflow-hidden" tone="accent">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)] xl:items-center">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <ProfileTag className="world-cup-hero-tag">Copa do Mundo</ProfileTag>
              <ProfileTag className="world-cup-hero-tag">Seleção</ProfileTag>
            </div>

            <div className="space-y-3">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-white/72">Seleção histórica</p>
              <h1 className="font-[family:var(--font-profile-headline)] text-[3rem] font-extrabold leading-[0.95] tracking-[-0.08em] text-white md:text-[4rem]">
                {team.teamName ?? "Seleção"}
              </h1>
              <p className="max-w-2xl text-sm/7 text-white/80 md:text-[1rem]/7">{buildHeroMeta(team)}</p>
            </div>

            <div className="flex flex-wrap gap-2 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-white/84">
              <span className="rounded-full border border-white/12 bg-white/10 px-3 py-2">
                Janela {team.firstEdition}–{team.lastEdition}
              </span>
            </div>
          </div>

          <aside className="relative isolate overflow-hidden rounded-[1.9rem] border border-white/12 bg-white/10 p-5 shadow-[0_28px_64px_-44px_rgba(2,12,9,0.58)] backdrop-blur-xl">
            <div className="absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.2),transparent_68%)]" />
            <span className="pointer-events-none absolute -right-4 bottom-[-1.5rem] text-[5.8rem] font-black uppercase tracking-[-0.08em] text-white/10 md:text-[7rem]">
              {buildFallbackLabel(team.teamName)}
            </span>

            <div className="relative space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/68">Acervo visual</p>
                  <p className="max-w-[14rem] text-sm/6 text-white/78">Visão direta do histórico da seleção.</p>
                </div>

                <ProfileMedia
                  alt={team.teamName ?? "Seleção"}
                  assetId={team.teamId}
                  category="clubs"
                  className="h-24 w-24 rounded-[1.5rem] md:h-28 md:w-28"
                  fallback={buildFallbackLabel(team.teamName)}
                  fallbackClassName="text-lg tracking-[0.18em]"
                  imageClassName="p-4"
                  shape="rounded"
                  tone="contrast"
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.2rem] border border-white/10 bg-white/8 px-4 py-3">
                  <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-white/62">Melhor resultado</p>
                  <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.4rem] font-extrabold tracking-[-0.04em] text-white">
                    {team.bestResultLabel}
                  </p>
                </div>
                <div className="rounded-[1.2rem] border border-white/10 bg-white/8 px-4 py-3">
                  <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-white/62">Última Copa</p>
                  <p className="mt-2 font-[family:var(--font-profile-headline)] text-[1.4rem] font-extrabold tracking-[-0.04em] text-white">
                    {team.lastEdition}
                  </p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </ProfilePanel>

      <div className="grid gap-4 md:grid-cols-3">
        <SummaryCard
          kind="participations"
          label="Participações"
          support={`${team.firstEdition}–${team.lastEdition}`}
          value={formatWholeNumber(team.participationsCount)}
        />
        <SummaryCard
          kind="titles"
          label="Títulos"
          support="No recorte exibido"
          value={formatWholeNumber(team.titlesCount)}
        />
        <SummaryCard
          kind="best"
          label="Melhor resultado"
          support="Pico histórico"
          value={team.bestResultLabel}
        />
      </div>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Participações</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            Linha do tempo por edição
          </h2>
        </header>

        <div className="space-y-4">
          {orderedParticipations.map((participation) => (
            <ParticipationCard key={`${participation.seasonLabel}-${participation.resultLabel}`} participation={participation} />
          ))}
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Artilharia</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            Histórico da seleção
          </h2>
        </header>

        {historicalScorers.length === 0 ? (
          <ProfileAlert title="Sem artilharia destacada" tone="warning">
            Nenhum jogador atingiu 3 gols no recorte disponível.
          </ProfileAlert>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[rgba(191,201,195,0.34)] text-sm">
              <thead className="bg-[rgba(246,248,252,0.9)] text-[0.68rem] uppercase tracking-[0.14em] text-[#57657a]">
                <tr>
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Jogador</th>
                  <th className="px-3 py-2 text-right">Gols</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(191,201,195,0.28)]">
                {historicalScorers.map((scorer) => (
                  <tr className="bg-white/72" key={`${scorer.rank}-${scorer.playerId ?? scorer.playerName ?? "scorer"}`}>
                    <td className="px-3 py-2 font-semibold text-[#111c2d]">{scorer.rank}</td>
                    <td className="px-3 py-2 font-semibold text-[#111c2d]">{scorer.playerName ?? "Não identificado"}</td>
                    <td className="px-3 py-2 text-right font-semibold text-[#111c2d]">{scorer.goals}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ProfilePanel>
    </ProfileShell>
  );
}
