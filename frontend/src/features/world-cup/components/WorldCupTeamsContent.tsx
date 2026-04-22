"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileAlert, ProfileKpi, ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { useWorldCupTeams } from "@/features/world-cup/hooks/useWorldCupTeams";
import { buildWorldCupHubPath, buildWorldCupTeamPath } from "@/features/world-cup/routes";
import type { WorldCupTeamListItem } from "@/features/world-cup/types/world-cup.types";

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

function TeamCard({ team }: { team: WorldCupTeamListItem }) {
  return (
    <Link
      className="group flex h-full flex-col rounded-[1.45rem] border border-[rgba(191,201,195,0.44)] bg-white/82 px-4 py-4 transition-[transform,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-1 hover:border-[#8bd6b6] hover:shadow-[0_28px_64px_-48px_rgba(17,28,45,0.24)]"
      href={buildWorldCupTeamPath(team.teamId)}
    >
      <div className="flex items-start gap-3">
        <ProfileMedia
          alt={team.teamName ?? "Selecao"}
          assetId={team.teamId}
          category="clubs"
          className="h-14 w-14 rounded-full"
          fallback={buildFallbackLabel(team.teamName)}
          imageClassName="p-2"
          shape="circle"
        />
        <div className="min-w-0 flex-1">
          <p className="font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
            {team.teamName ?? "Selecao nao identificada"}
          </p>
          <p className="mt-1 text-sm/6 text-[#57657a]">
            Melhor campanha: {team.bestResultLabel}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">Copas</p>
          <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            {team.participationsCount}
          </p>
        </div>
        <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">Titulos</p>
          <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
            {team.titlesCount}
          </p>
        </div>
        <div className="rounded-[1rem] border border-[rgba(191,201,195,0.34)] bg-[rgba(246,248,252,0.88)] px-3 py-3">
          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">Janela</p>
          <p className="mt-2 font-[family:var(--font-profile-headline)] text-lg font-extrabold text-[#111c2d]">
            {team.firstEdition}–{team.lastEdition}
          </p>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-[rgba(191,201,195,0.38)] pt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
        <span>Abrir historico</span>
        <span className="transition-transform group-hover:translate-x-1">-&gt;</span>
      </div>
    </Link>
  );
}

export function WorldCupTeamsContent() {
  const teamsQuery = useWorldCupTeams();

  if (teamsQuery.isLoading && !teamsQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando todas as selecoes que ja participaram de Copas do Mundo."
        kicker="Copa do Mundo"
        loading
        title="Carregando selecoes"
      />
    );
  }

  if (teamsQuery.isError && !teamsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="Nao foi possivel carregar a grade de selecoes agora."
        kicker="Copa do Mundo"
        title="Falha ao listar selecoes"
        tone="critical"
      />
    );
  }

  if (!teamsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="A vertical nao retornou selecoes suficientes para montar esta lista."
        kicker="Copa do Mundo"
        title="Lista indisponivel"
        tone="warning"
      />
    );
  }

  const { teams } = teamsQuery.data;
  const titleWinnersCount = teams.filter((team) => team.titlesCount > 0).length;

  return (
    <ProfileShell className="world-cup-theme space-y-6" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Inicio
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupHubPath()}>
          Copa do Mundo
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>Selecoes</span>
      </div>

      <ProfilePanel className="world-cup-hero space-y-6" tone="accent">
        <div className="flex flex-wrap items-center gap-2">
          <ProfileTag className="world-cup-hero-tag">Selecoes</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Historico</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Copas</ProfileTag>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)] xl:items-end">
          <div className="space-y-4">
            <h1 className="font-[family:var(--font-profile-headline)] text-[2.8rem] font-extrabold leading-none tracking-[-0.07em] text-white md:text-[3.5rem]">
              Explorar por selecao
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/78 md:text-[0.96rem]/7">
              Grade histórica com as seleções exibidas na vertical. Alemanha reúne Germany + West Germany; as demais
              linhagens seguem o contrato atual.
            </p>
          </div>

          <aside className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <ProfileKpi
              hint="Participantes com pelo menos uma Copa registrada"
              invert
              label="Selecoes"
              value={formatWholeNumber(teams.length)}
            />
            <ProfileKpi
              hint="Selecoes com pelo menos um titulo"
              invert
              label="Campeas"
              value={formatWholeNumber(titleWinnersCount)}
            />
          </aside>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5" tone="base">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Grade de selecoes</p>
          <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
            {formatWholeNumber(teams.length)} selecoes com participacao
          </h2>
          <p className="max-w-3xl text-sm/6 text-[#57657a]">
            Cada card resume participacoes, titulos e melhor campanha, com abertura direta para a pagina da selecao.
          </p>
        </header>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {teams.map((team) => (
            <TeamCard key={team.teamId} team={team} />
          ))}
        </div>
      </ProfilePanel>
    </ProfileShell>
  );
}
