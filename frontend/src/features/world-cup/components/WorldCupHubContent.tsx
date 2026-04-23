"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import {
  ProfileKpi,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";

import { WorldCupArchiveHero } from "@/features/world-cup/components/WorldCupArchiveHero";
import { useWorldCupHub } from "@/features/world-cup/hooks/useWorldCupHub";
import {
  buildWorldCupEditionPath,
  buildWorldCupFinalsPath,
  buildWorldCupRankingsPath,
  buildWorldCupTeamsPath,
} from "@/features/world-cup/routes";
import type {
  WorldCupHistoricalTopScorer,
  WorldCupHubEdition,
} from "@/features/world-cup/types/world-cup.types";

const WORLD_CUP_COMPETITION_KEY = "wc_mens";

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

function describeTopScorer(topScorer: WorldCupHistoricalTopScorer | null): string {
  if (!topScorer || !topScorer.playerName) {
    return "Não identificado";
  }

  return topScorer.playerName;
}

function describeTopScorerHint(topScorer: WorldCupHistoricalTopScorer | null): string {
  if (!topScorer) {
    return "Sem dado suficiente";
  }

  const parts = [`${formatWholeNumber(topScorer.goals)} gols`];
  if (topScorer.teamName) {
    parts.push(topScorer.teamName);
  }

  return parts.join(" · ");
}

function countRegisteredFinals(editions: WorldCupHubEdition[]): number {
  return editions.filter((edition) => edition.resolutionType !== "final_round").length;
}

function QuickLinkGlyph({ icon }: { icon: "teams" | "rankings" | "finals" }) {
  if (icon === "teams") {
    return (
      <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 18 7v5.2c0 3.2-2 5.8-6 7.3-4-1.5-6-4.1-6-7.3V7l6-2.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "rankings") {
    return (
      <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
        <path
          d="M6 18v-5M12 18V8M18 18V5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

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

function QuickLinkCard({
  description,
  href,
  label,
  badge,
  icon,
}: {
  description: string;
  href: string;
  label: string;
  badge: string;
  icon: "teams" | "rankings" | "finals";
}) {
  const iconToneClassName =
    icon === "teams"
      ? "bg-[rgba(214,242,229,0.92)] text-[#00513b]"
      : icon === "rankings"
        ? "bg-[rgba(216,227,251,0.9)] text-[#39537f]"
        : "bg-[rgba(255,232,214,0.9)] text-[#7b4207]";

  return (
    <Link
      className="group flex h-full flex-col justify-between rounded-[1.45rem] border border-[rgba(191,201,195,0.46)] bg-[linear-gradient(180deg,rgba(255,255,255,0.9)_0%,rgba(248,250,253,0.96)_100%)] px-4 py-4 transition-[transform,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-1 hover:border-[#8bd6b6] hover:shadow-[0_24px_58px_-42px_rgba(17,28,45,0.22)]"
      href={href}
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <span className="inline-flex rounded-full bg-[rgba(216,227,251,0.72)] px-3 py-1 text-[0.66rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
            {badge}
          </span>
          <span
            className={joinClasses(
              "inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/70 shadow-[0_16px_32px_-24px_rgba(17,28,45,0.34)]",
              iconToneClassName,
            )}
          >
            <QuickLinkGlyph icon={icon} />
          </span>
        </div>
        <h3 className="font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold tracking-[-0.035em] text-[#111c2d]">
          {label}
        </h3>
        <p className="text-sm/6 text-[#57657a]">{description}</p>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-[rgba(191,201,195,0.38)] pt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
        <span>Abrir rota</span>
        <span className="transition-transform group-hover:translate-x-1">-&gt;</span>
      </div>
    </Link>
  );
}

function TimelineEditionCard({ edition }: { edition: WorldCupHubEdition }) {
  const championName = edition.champion?.teamName ?? "Campeão não identificado";
  const hostCountryName = edition.hostCountry ?? "País-sede não identificado";
  const hostCountryAssetId =
    edition.hostCountryTeam?.teamId ?? (hostCountryName === "Coreia do Sul e Japão" ? "world-cup-japan" : null);

  return (
    <Link
      className={joinClasses(
        "group flex h-full flex-col gap-4 rounded-[1.55rem] border px-4 py-4 transition-[transform,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-1 hover:border-[#8bd6b6] hover:shadow-[0_26px_62px_-46px_rgba(17,28,45,0.22)]",
        "border-[rgba(191,201,195,0.48)] bg-[linear-gradient(180deg,rgba(255,255,255,0.92)_0%,rgba(248,250,253,0.95)_100%)]",
      )}
      href={buildWorldCupEditionPath(edition.seasonLabel)}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-[family:var(--font-profile-headline)] text-[2.25rem] font-extrabold leading-none tracking-[-0.06em] text-[#111c2d]">
            {edition.year}
          </h3>
        </div>
        <span className="rounded-full bg-[rgba(255,255,255,0.78)] px-3 py-1 text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-[#57657a] shadow-[0_12px_24px_-20px_rgba(17,28,45,0.28)]">
          {formatWholeNumber(edition.matchesCount)} partidas
        </span>
      </div>

      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.42)] bg-[rgba(246,248,252,0.84)] px-3 py-3">
            <div className="flex items-center gap-3">
              <ProfileMedia
                alt={`Campeão ${championName}`}
                assetId={edition.champion?.teamId}
                category="clubs"
                className="h-10 w-10 rounded-full"
                fallback={buildFallbackLabel(championName)}
                imageClassName="p-1.5"
                shape="circle"
              />
              <div className="min-w-0">
                <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                  Campeão
                </p>
                <p className="mt-1 truncate font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
                  {championName}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[1.1rem] border border-[rgba(191,201,195,0.42)] bg-[rgba(246,248,252,0.84)] px-3 py-3">
            <div className="flex items-center gap-3">
              <ProfileMedia
                alt={`País-sede ${hostCountryName}`}
                assetId={hostCountryAssetId}
                category="clubs"
                className="h-10 w-10 rounded-full"
                fallback={buildFallbackLabel(hostCountryName)}
                imageClassName="p-1.5"
                shape="circle"
              />
              <div className="min-w-0">
                <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
                  País-sede
                </p>
                <p className="mt-1 truncate font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-[#111c2d]">
                  {hostCountryName}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-start justify-between gap-3 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[#57657a]">
          <div className="flex flex-wrap gap-2">
            {edition.teamsCount ? (
              <span className="rounded-full bg-white/72 px-2.5 py-1">
                {formatWholeNumber(edition.teamsCount)} seleções
              </span>
            ) : null}
          </div>
          {edition.finalVenue ? (
            <span className="max-w-[16rem] rounded-full bg-white/72 px-2.5 py-1 text-right">
              {edition.finalVenue}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-[rgba(191,201,195,0.38)] pt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
        <span>Abrir edição</span>
        <span className="transition-transform group-hover:translate-x-1">-&gt;</span>
      </div>
    </Link>
  );
}

export function WorldCupHubContent() {
  const hubQuery = useWorldCupHub();

  if (hubQuery.isLoading && !hubQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando a linha do tempo das edições, métricas centrais e portas de entrada da vertical."
        kicker="Copa do Mundo"
        loading
        title="Carregando o hub da Copa do Mundo"
      />
    );
  }

  if (hubQuery.isError && !hubQuery.data) {
    return (
      <PlatformStateSurface
        actionHref="/"
        actionLabel="Voltar ao início"
        description="Não foi possível carregar o hub dedicado da Copa do Mundo agora."
        kicker="Copa do Mundo"
        title="Falha ao abrir a vertical"
        tone="critical"
      />
    );
  }

  if (!hubQuery.data) {
    return (
      <PlatformStateSurface
        actionHref="/"
        actionLabel="Voltar ao início"
        description="A vertical não recebeu dados suficientes para montar o hub neste momento."
        kicker="Copa do Mundo"
        title="Hub indisponível"
        tone="warning"
      />
    );
  }

  const { summary, editions } = hubQuery.data;
  const orderedEditions = [...editions].sort((left, right) => right.year - left.year);
  const latestEdition = orderedEditions[0] ?? null;
  const registeredFinalsCount = countRegisteredFinals(editions);

  return (
    <ProfileShell className="world-cup-theme space-y-6" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Início
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>Copa do Mundo</span>
      </div>

      <WorldCupArchiveHero
        aside={
          <>
            <div className="flex items-center gap-4 rounded-[1.3rem] border border-white/10 bg-white/[0.05] p-4">
              <ProfileMedia
                alt="Identidade visual da Copa do Mundo"
                assetId={WORLD_CUP_COMPETITION_KEY}
                category="competitions"
                className="h-20 w-20 rounded-[1.4rem]"
                fallback="FIFA"
                fallbackClassName="text-lg tracking-[0.18em]"
                imageClassName="p-3"
                shape="rounded"
                tone="contrast"
              />
              <div className="space-y-2">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/70">
                  Entrada dedicada
                </p>
                <p className="font-[family:var(--font-profile-headline)] text-[1.65rem] font-extrabold leading-none tracking-[-0.05em] text-white">
                  {formatWholeNumber(summary.editionsCount)} edições
                </p>
                <p className="text-sm/6 text-white/70">
                  {latestEdition ? `Última edição disponível: ${latestEdition.year}.` : "Linha do tempo em atualização."}
                </p>
              </div>
            </div>

            <div className="rounded-[1.3rem] border border-white/10 bg-white/[0.05] p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/70">
                Maior artilheiro de todas as copas
              </p>
              <div className="mt-3 flex items-center gap-3">
                <ProfileMedia
                  alt={`Maior artilheiro ${describeTopScorer(summary.topScorer)}`}
                  assetId={summary.topScorer?.playerId}
                  category="players"
                  className="h-14 w-14 rounded-full"
                  fallback={buildFallbackLabel(describeTopScorer(summary.topScorer))}
                  imageClassName="p-1.5"
                  shape="circle"
                  tone="contrast"
                />
                <div className="min-w-0">
                  <p className="truncate font-[family:var(--font-profile-headline)] text-[1.35rem] font-extrabold tracking-[-0.04em] text-white">
                    {describeTopScorer(summary.topScorer)}
                  </p>
                  <p className="mt-1 text-[0.72rem] uppercase tracking-[0.14em] text-white/68">
                    {describeTopScorerHint(summary.topScorer)}
                  </p>
                </div>
              </div>
            </div>
          </>
        }
        asideClassName="space-y-4"
        description="Edições, seleções, rankings e finais em uma navegação única do arquivo histórico."
        footer={
          <>
            <ProfileTag className="world-cup-hero-tag">Arquivo histórico</ProfileTag>
            <ProfileTag className="world-cup-hero-tag">Edições</ProfileTag>
            <ProfileTag className="world-cup-hero-tag">Seleções</ProfileTag>
            <ProfileTag className="world-cup-hero-tag">Finais</ProfileTag>
          </>
        }
        kicker="Copa do Mundo FIFA"
        metrics={
          <>
            <ProfileKpi invert label="Edições" value={formatWholeNumber(summary.editionsCount)} />
            <ProfileKpi invert label="Partidas" value={formatWholeNumber(summary.matchesCount)} />
            <ProfileKpi invert label="Campeões distintos" value={formatWholeNumber(summary.distinctChampionsCount)} />
            <ProfileKpi invert label="Finais únicas" value={formatWholeNumber(registeredFinalsCount)} />
          </>
        }
        title="Arquivo histórico da Copa do Mundo"
      />

      <ProfilePanel className="space-y-5" tone="soft">
        <div>
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
            Navegação principal
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <QuickLinkCard
            badge="Seleções"
            description="Abre a superfície dedicada para exploração do histórico por seleção."
            href={buildWorldCupTeamsPath()}
            icon="teams"
            label="Explorar por seleção"
          />
          <QuickLinkCard
            badge="Rankings"
            description="Entra na área de rankings multi-edição do arquivo da Copa."
            href={buildWorldCupRankingsPath()}
            icon="rankings"
            label="Rankings históricos"
          />
          <QuickLinkCard
            badge="Finais"
            description="Abre a rota das decisões históricas, sem antecipar o conteúdo do bloco de rankings."
            href={buildWorldCupFinalsPath()}
            icon="finals"
            label="Finais"
          />
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Linha do tempo
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2.1rem] font-extrabold tracking-[-0.05em] text-[#111c2d]">
              Edições disponíveis no arquivo
            </h2>
          </div>
          <ProfileTag>{formatWholeNumber(orderedEditions.length)} edições</ProfileTag>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {orderedEditions.map((edition) => (
            <TimelineEditionCard edition={edition} key={edition.seasonLabel} />
          ))}
        </div>
      </ProfilePanel>
    </ProfileShell>
  );
}
