"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  SUPPORTED_COMPETITIONS,
  getCompetitionById,
  getCompetitionVisualAssetId,
  type CompetitionDef,
} from "@/config/competitions.registry";
import { useHomePage } from "@/features/home/hooks/useHomePage";
import type { HomeCompetitionCard } from "@/features/home/types/home.types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import type { CoverageState } from "@/shared/types/coverage.types";
import {
  buildCompetitionHubPath,
  buildHeadToHeadPath,
  buildRankingsHubPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

import styles from "./HomeExecutivePage.module.css";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatCompactNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(value >= 10_000 ? 1 : 2)}k`;
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function shouldDisplayCompleteCoverage(coverage: CoverageState): boolean {
  if (coverage.status === "complete") {
    return true;
  }

  return (
    coverage.status === "partial" &&
    typeof coverage.percentage === "number" &&
    coverage.percentage > 90
  );
}

function buildCoverageBadgeLabel(coverage: CoverageState): string {
  if (shouldDisplayCompleteCoverage(coverage)) {
    return "Completo";
  }

  if (coverage.status === "partial") {
    return "Parcial";
  }

  if (coverage.status === "empty") {
    return "Vazio";
  }

  return "Cobertura";
}

function buildCoverageBadgeClasses(coverage: CoverageState): string {
  if (shouldDisplayCompleteCoverage(coverage)) {
    return "bg-[#a6f2d1] text-[#00513b]";
  }

  if (coverage.status === "partial") {
    return "bg-[#ffdcc3] text-[#6e3900]";
  }

  if (coverage.status === "empty") {
    return "bg-[#ffdad6] text-[#93000a]";
  }

  return "bg-[rgba(216,227,251,0.76)] text-[#404944]";
}

function buildCompetitionOrder(items: HomeCompetitionCard[]): HomeCompetitionCard[] {
  const order = new Map<string, number>(
    SUPPORTED_COMPETITIONS.map(
      (competition, index): [string, number] => [competition.key, index],
    ),
  );

  return [...items].sort((left, right) => {
    const leftOrder = order.get(left.competitionKey) ?? 999;
    const rightOrder = order.get(right.competitionKey) ?? 999;

    return leftOrder - rightOrder;
  });
}

function buildCompetitionCardHref(competition: HomeCompetitionCard): string {
  return buildCompetitionHubPath(competition.competitionKey);
}

function buildCompetitionCtaLabel(_competition: HomeCompetitionCard): string {
  return "Ver temporadas";
}

function buildVisualAssetUrl(
  category: "competitions" | "players",
  assetId: string | null,
): string | null {
  if (!assetId) {
    return null;
  }

  return `/api/visual-assets/${category}/${assetId}`;
}

function buildCompetitionGroups(competitions: HomeCompetitionCard[]) {
  const orderedCompetitions = buildCompetitionOrder(competitions);
  const domestic: Array<HomeCompetitionCard & { meta: CompetitionDef }> = [];
  const continental: Array<HomeCompetitionCard & { meta: CompetitionDef }> = [];
  const world: Array<HomeCompetitionCard & { meta: CompetitionDef }> = [];

  for (const competition of orderedCompetitions) {
    const meta = getCompetitionById(competition.competitionId);
    if (!meta) {
      continue;
    }

    if (meta.scope === "global") {
      world.push({ ...competition, meta });
      continue;
    }

    if (meta.scope === "continental") {
      continental.push({ ...competition, meta });
      continue;
    }

    domestic.push({ ...competition, meta });
  }

  return { continental, domestic, world };
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={joinClasses("h-4 w-4", className)}
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d="M6.5 12h11m0 0-4.5-4.5M17.5 12l-4.5 4.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.9"
      />
    </svg>
  );
}

function SectionHeader({
  actionHref,
  actionLabel,
  countLabel,
  description,
  eyebrow,
  title,
}: {
  actionHref?: string;
  actionLabel?: string;
  countLabel?: string;
  description?: string;
  eyebrow?: string;
  title: string;
}) {
  const hasActions = Boolean(countLabel) || Boolean(actionHref && actionLabel);

  return (
    <div className={styles.sectionHeader}>
      <div className={styles.sectionHeaderLead}>
        {eyebrow ? <p className={styles.sectionEyebrow}>{eyebrow}</p> : null}
        <h2 className="font-[family:var(--font-app-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-[#003526] md:text-[2.35rem]">
          {title}
        </h2>
        {description ? (
          <p className="max-w-2xl text-sm leading-7 text-[#57657a] md:text-base">{description}</p>
        ) : null}
      </div>

      {hasActions ? (
        <div className={styles.sectionHeaderActions}>
          {countLabel ? <span className={styles.sectionCount}>{countLabel}</span> : null}
          {actionHref && actionLabel ? (
            <Link className={styles.sectionAction} href={actionHref}>
              <span>{actionLabel}</span>
              <ArrowRightIcon className={styles.inlineArrow} />
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function HeroMetricCard({
  detail,
  label,
  value,
}: {
  detail: string;
  label: string;
  value: string;
}) {
  return (
    <div className={styles.metricCard}>
      <p className={styles.metricLabel}>{label}</p>
      <p className={styles.metricValue}>{value}</p>
      <p className={styles.metricDetail}>{detail}</p>
    </div>
  );
}

type QuickLinkIconName = "rankings" | "headToHead" | "clubs";

function QuickLinkIcon({ icon }: { icon: QuickLinkIconName }) {
  const classes = "h-7 w-7 stroke-[1.9] text-[#003526]";

  if (icon === "rankings") {
    return (
      <svg aria-hidden="true" className={classes} fill="none" viewBox="0 0 24 24">
        <path d="M5 18V9h4v9M10 18V5h4v13M15 18v-6h4v6" stroke="currentColor" />
        <path d="M4 18.5h16" stroke="currentColor" strokeLinecap="round" />
      </svg>
    );
  }

  if (icon === "headToHead") {
    return (
      <svg aria-hidden="true" className={classes} fill="none" viewBox="0 0 24 24">
        <path
          d="M8 7 4 11l4 4"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M16 7l4 4-4 4"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M20 11H4" stroke="currentColor" strokeLinecap="round" />
      </svg>
    );
  }

  if (icon === "clubs") {
    return (
      <svg aria-hidden="true" className={classes} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 18 7v5.3c0 3.2-2 5.8-6 7.2-4-1.4-6-4-6-7.2V7l6-2.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={classes} fill="none" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" />
      <path d="M12 4.5v15M4.5 12h15" stroke="currentColor" strokeLinecap="round" />
    </svg>
  );
}

function QuickLinkCard({
  description,
  href,
  icon,
  label,
}: {
  description: string;
  href?: string;
  icon: QuickLinkIconName;
  label: string;
}) {
  const classes = joinClasses(styles.quickLinkCard, href && styles.interactiveCard);

  const content = (
    <>
      <div className={styles.quickLinkTop}>
        <div className={styles.quickLinkIconWrap}>
          <QuickLinkIcon icon={icon} />
        </div>
        <span className={styles.quickLinkBadge}>Acesso rápido</span>
      </div>

      <div className="space-y-3">
        <h3 className="font-[family:var(--font-app-headline)] text-[1.45rem] font-extrabold tracking-[-0.035em] text-[#0d2240]">
          {label}
        </h3>
        <p className="text-sm leading-6 text-[#57657a]">{description}</p>
      </div>

      <div className={styles.quickLinkFooter}>
        <span>Explorar agora</span>
        <ArrowRightIcon className={styles.quickLinkArrow} />
      </div>
    </>
  );

  if (href) {
    return (
      <Link className={classes} href={href}>
        {content}
      </Link>
    );
  }

  return <div className={classes}>{content}</div>;
}

function CompetitionCard({
  competition,
  meta,
}: {
  competition: HomeCompetitionCard;
  meta: CompetitionDef;
}) {
  const [hasCompetitionLogoError, setHasCompetitionLogoError] = useState(false);
  const assetUrl = buildVisualAssetUrl(
    "competitions",
    getCompetitionVisualAssetId(meta) ?? competition.assetId,
  );

  return (
    <Link
      className={joinClasses(styles.competitionCard, styles.interactiveCard)}
      href={buildCompetitionCardHref(competition)}
    >
      <div className={styles.competitionCardContent}>
        <div className={styles.competitionCardHeader}>
          <div className={styles.competitionCardTopRow}>
            <div className={styles.competitionIdentity}>
              <div className={styles.competitionLogoFrame}>
                {assetUrl && !hasCompetitionLogoError ? (
                  <Image
                    alt={`Logo de ${competition.competitionName}`}
                    className={joinClasses("h-10 w-10 object-contain", styles.competitionLogo)}
                    onError={() => {
                      setHasCompetitionLogoError(true);
                    }}
                    src={assetUrl}
                    unoptimized
                    height={40}
                    width={40}
                  />
                ) : (
                  <span className="font-[family:var(--font-app-headline)] text-xs font-bold uppercase tracking-[0.14em] text-[#003526]">
                    {meta.shortName}
                  </span>
                )}
              </div>

              <div className={styles.metaRow}>
                <span className={styles.metaPill}>{meta.country}</span>
              </div>
            </div>

            <span
              className={joinClasses(
                styles.coverageBadge,
                buildCoverageBadgeClasses(competition.coverage),
              )}
            >
              {buildCoverageBadgeLabel(competition.coverage)}
            </span>
          </div>

          <h3 className={styles.competitionTitle}>{competition.competitionName}</h3>
        </div>

        <div className={styles.competitionCardBottom}>
          <div className={styles.statsGrid}>
            <div className={styles.statTile}>
              <p className={styles.statLabel}>Temporadas</p>
              <p className={styles.statValue}>{formatWholeNumber(competition.seasonsCount)}</p>
            </div>
            <div className={styles.statTile}>
              <p className={styles.statLabel}>Partidas</p>
              <p className={styles.statValue}>{formatCompactNumber(competition.matchesCount)}</p>
            </div>
          </div>

          <div className={styles.cardFooter}>
            <span className={styles.cardFooterLabel}>{buildCompetitionCtaLabel(competition)}</span>
            <ArrowRightIcon className={styles.cardFooterArrow} />
          </div>
        </div>
      </div>
    </Link>
  );
}

export function HomeExecutivePage() {
  const homeQuery = useHomePage();
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const competitionGroups = useMemo(
    () => buildCompetitionGroups(homeQuery.data?.competitions ?? []),
    [homeQuery.data?.competitions],
  );
  const sharedFilters = useMemo(
    () => ({
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
    }),
    [competitionId, dateRangeEnd, dateRangeStart, lastN, roundId, seasonId, venue],
  );

  if (homeQuery.isLoading && !homeQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos montando a visão principal do produto com dados reais do acervo."
        kicker="Início"
        loading
        title="Carregando a página inicial"
      />
    );
  }

  if (homeQuery.isError && !homeQuery.data) {
    return (
      <PlatformStateSurface
        actionHref="/competitions"
        actionLabel="Abrir competições"
        description="Não foi possível carregar a página inicial agora. Abra outra área do produto ou tente novamente."
        kicker="Início"
        title="Falha ao carregar a página inicial"
        tone="critical"
      />
    );
  }

  if (!homeQuery.data) {
    return (
      <PlatformStateSurface
        actionHref="/competitions"
        actionLabel="Abrir competições"
        description="A página inicial não recebeu dados suficientes para ser montada agora."
        kicker="Início"
        title="Página inicial indisponível"
        tone="warning"
      />
    );
  }

  const archiveSummary = homeQuery.data.archiveSummary;
  const archiveMetrics = [
    {
      label: "Competições",
      value: formatWholeNumber(archiveSummary.competitions),
      detail: "campeonatos no acervo",
    },
    {
      label: "Temporadas",
      value: formatWholeNumber(archiveSummary.seasons),
      detail: "edições no acervo",
    },
    {
      label: "Partidas",
      value: formatCompactNumber(archiveSummary.matches),
      detail: "jogos prontos para análise",
    },
    {
      label: "Jogadores",
      value: formatCompactNumber(archiveSummary.players),
      detail: "atletas catalogados",
    },
  ];

  return (
    <div className={joinClasses(styles.homeRoot, "bg-[var(--app-surface)] text-[var(--app-text)]")}>
      <section className="px-6 pb-12 pt-8 md:px-10 md:pb-14 md:pt-10 xl:px-12">
        <div className="mx-auto max-w-6xl">
          {homeQuery.isPartial ? (
            <div className="mb-8">
              <PartialDataBanner coverage={homeQuery.coverage} />
            </div>
          ) : null}

          <div className={styles.heroShell}>
            <div className={styles.heroGrid}>
              <div className={styles.heroContent}>
                <h1 className={styles.heroTitle}>Explore a história do futebol em dados</h1>

                <div className={styles.heroCtaRow}>
                  <Link className={styles.primaryCta} href="/competitions">
                    <span>Explorar competições</span>
                    <ArrowRightIcon className={styles.inlineArrow} />
                  </Link>
                  <Link className={styles.secondaryCta} href={buildRankingsHubPath(sharedFilters)}>
                    <span>Ver rankings</span>
                  </Link>
                </div>
              </div>

              <aside className={styles.heroMetricsPanel}>
                <div className={styles.heroMetricsGrid}>
                  {archiveMetrics.map((metric) => (
                    <HeroMetricCard
                      detail={metric.detail}
                      key={metric.label}
                      label={metric.label}
                      value={metric.value}
                    />
                  ))}
                </div>

                
              </aside>
            </div>

            <div className={styles.quickActionsShell}>
              <div className={styles.quickActionsHeader}>
                <div>
                  <p className={styles.sectionEyebrow}>Atalhos</p>
                  <h2 className="font-[family:var(--font-app-headline)] text-[1.9rem] font-extrabold tracking-[-0.04em] text-[#003526]">
                    Acessos rápidos
                  </h2>
                </div>
              </div>

              <div className={styles.quickLinksGrid}>
                <QuickLinkCard
                  description="Artilharia, criação e eficiência no mesmo ponto de entrada."
                  href={buildRankingsHubPath(sharedFilters)}
                  icon="rankings"
                  label="Rankings"
                />
                <QuickLinkCard
                  description="Confrontos lado a lado com leitura rápida de força relativa."
                  href={buildHeadToHeadPath(sharedFilters)}
                  icon="headToHead"
                  label="Comparativos"
                />
                <QuickLinkCard
                  description="Campanha, elenco e profundidade por entidade no recorte atual."
                  href={buildTeamsPath(sharedFilters)}
                  icon="clubs"
                  label="Times"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="px-6 pb-12 md:px-10 md:pb-14 xl:px-12">
        <div className="mx-auto max-w-6xl space-y-8">
          <div className={styles.sectionPanel}>
            <SectionHeader
              actionHref="/competitions"
              actionLabel="Ver tudo"
              countLabel={`${competitionGroups.domestic.length} competições`}
              eyebrow="Catálogo"
              title="Competições Nacionais"
            />

            {competitionGroups.domestic.length > 0 ? (
              <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                {competitionGroups.domestic.map((competition) => (
                  <CompetitionCard
                    competition={competition}
                    key={competition.competitionId}
                    meta={competition.meta}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                description="A página inicial não recebeu competições nacionais suficientes agora."
                title="Sem competições nacionais"
              />
            )}
          </div>

          <div className={styles.sectionPanel}>
            <SectionHeader
              actionHref="/competitions"
              actionLabel="Ver tudo"
              countLabel={`${competitionGroups.continental.length} competições`}
              eyebrow="Catálogo"
              title="Continentais"
            />

            {competitionGroups.continental.length > 0 ? (
              <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                {competitionGroups.continental.map((competition) => (
                  <CompetitionCard
                    competition={competition}
                    key={competition.competitionId}
                    meta={competition.meta}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                description="A página inicial não recebeu competições continentais suficientes agora."
                title="Sem competições continentais"
              />
            )}
          </div>

          <div className={styles.sectionPanel}>
            <SectionHeader
              countLabel={`${competitionGroups.world.length} competições`}
              eyebrow="Catálogo"
              title="Mundiais"
            />

            {competitionGroups.world.length > 0 ? (
              <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                {competitionGroups.world.map((competition) => (
                  <CompetitionCard
                    competition={competition}
                    key={competition.competitionId}
                    meta={competition.meta}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                description="A página inicial não recebeu competições mundiais suficientes agora."
                title="Sem competições mundiais"
              />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
