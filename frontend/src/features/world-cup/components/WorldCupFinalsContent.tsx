"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileKpi, ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { WorldCupFinalsSection } from "@/features/world-cup/components/WorldCupFinalsSection";
import { useWorldCupRankings } from "@/features/world-cup/hooks/useWorldCupRankings";
import { buildWorldCupHubPath } from "@/features/world-cup/routes";

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

export function WorldCupFinalsContent() {
  const rankingsQuery = useWorldCupRankings();

  if (rankingsQuery.isLoading && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando a lista historica de finais de Copa do Mundo."
        kicker="Copa do Mundo"
        loading
        title="Carregando finais historicas"
      />
    );
  }

  if (rankingsQuery.isError && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="Nao foi possivel carregar a lista de finais agora."
        kicker="Copa do Mundo"
        title="Falha ao abrir finais"
        tone="critical"
      />
    );
  }

  if (!rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="A vertical nao retornou finais suficientes para montar esta pagina."
        kicker="Copa do Mundo"
        title="Finais indisponiveis"
        tone="warning"
      />
    );
  }

  const { finals } = rankingsQuery.data;

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
        <span>Finais</span>
      </div>

      <ProfilePanel className="world-cup-hero space-y-6" tone="accent">
        <div className="flex flex-wrap items-center gap-2">
          <ProfileTag className="world-cup-hero-tag">Finais</ProfileTag>
          <ProfileTag className="world-cup-hero-tag">Historia</ProfileTag>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)] xl:items-end">
          <div className="space-y-4">
            <h1 className="font-[family:var(--font-profile-headline)] text-[2.8rem] font-extrabold leading-none tracking-[-0.07em] text-white md:text-[3.5rem]">
              Finais historicas
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/78 md:text-[0.96rem]/7">
              Recorte dedicado das decisoes de Copa com ano, placar, local e sinalizacao honesta quando nao houve final unica.
            </p>
          </div>

          <aside className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <ProfileKpi
              hint="Finais unicas com placar e local registrados"
              invert
              label="Finais"
              value={formatWholeNumber(finals.items.length)}
            />
            <ProfileKpi
              hint="Edicoes fora da lista por ambiguidade de formato"
              invert
              label="Omissoes"
              value={formatWholeNumber(finals.omittedEditions.length)}
            />
          </aside>
        </div>
      </ProfilePanel>

      <WorldCupFinalsSection finals={finals.items} omittedEditions={finals.omittedEditions} tone="base" />
    </ProfileShell>
  );
}
