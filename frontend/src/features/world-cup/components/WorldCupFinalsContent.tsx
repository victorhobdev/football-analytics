"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileKpi, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { WorldCupArchiveHero } from "@/features/world-cup/components/WorldCupArchiveHero";
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
  const penaltyDecisionsCount = finals.items.filter((item) => item.resolutionType === "penalties").length;

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

      <WorldCupArchiveHero
        aside={
          <>
            <ProfileKpi
              hint="Decisões históricas carregadas nesta curadoria"
              invert
              label="Decisões"
              value={formatWholeNumber(finals.items.length)}
            />
            <ProfileKpi
              hint="Finais resolvidas nas penalidades"
              invert
              label="Pênaltis"
              value={formatWholeNumber(penaltyDecisionsCount)}
            />
          </>
        }
        asideClassName="grid gap-3 sm:grid-cols-2 xl:grid-cols-1"
        description="Ano, confronto, placar e contexto da decisão de cada Copa. Em 1950, a leitura usa Brasil x Uruguai como jogo que definiu o título."
        footer={
          <>
            <ProfileTag className="world-cup-hero-tag">Finais</ProfileTag>
            <ProfileTag className="world-cup-hero-tag">Decisões</ProfileTag>
          </>
        }
        kicker="Arquivo histórico"
        title="Finais históricas"
      />

      <WorldCupFinalsSection finals={finals.items} omittedEditions={finals.omittedEditions} tone="base" />
    </ProfileShell>
  );
}
