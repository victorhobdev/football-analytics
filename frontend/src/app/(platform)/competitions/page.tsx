"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  getCompetitionByKey,
  type CompetitionDef,
} from "@/config/competitions.registry";
import { useHomePage } from "@/features/home/hooks/useHomePage";
import type { HomeCompetitionCard } from "@/features/home/types/home.types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { buildCompetitionHubPath } from "@/shared/utils/context-routing";

import styles from "./page.module.css";

type ScopeFilter = "all" | "domestic" | "international" | "global";
type CatalogCompetitionType = CompetitionDef["type"];
type TypeFilter = "all" | CatalogCompetitionType;

interface CatalogCompetition {
  id: string;
  key: string;
  name: string;
  shortName: string;
  source: "published" | "transfermarkt" | "eloratings" | "multi";
  dominantSource: "published" | "transfermarkt" | "eloratings";
  additionalSources: Array<"published" | "transfermarkt" | "eloratings">;
  country: string;
  region: string;
  type: CatalogCompetitionType;
  scope: CompetitionDef["scope"];
  visualAssetId?: string;
  matchesCount: number;
  seasonsCount: number;
  latestSeasonLabel: string | null;
}

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function normalizeSearchValue(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function coerceCompetitionScope(value: HomeCompetitionCard["scope"]): CatalogCompetition["scope"] {
  return value === "domestic" || value === "continental" || value === "global" ? value : "domestic";
}

function coerceCompetitionType(value: HomeCompetitionCard["type"]): CatalogCompetitionType {
  return value === "domestic_league" || value === "domestic_cup" || value === "international_cup"
    ? value
    : "domestic_league";
}

function buildCatalogCompetition(card: HomeCompetitionCard): CatalogCompetition {
  const registryCompetition = getCompetitionByKey(card.competitionKey);
  const scope = coerceCompetitionScope(card.scope ?? registryCompetition?.scope);
  const type = coerceCompetitionType(card.type ?? registryCompetition?.type);

  return {
    id: card.competitionId,
    key: card.competitionKey,
    name: card.competitionName,
    shortName: registryCompetition?.shortName ?? card.competitionName,
    source: card.source ?? "published",
    dominantSource: card.dominantSource ?? "published",
    additionalSources: card.additionalSources ?? [],
    country: card.country ?? registryCompetition?.country ?? "Não informado",
    region: card.region ?? registryCompetition?.region ?? "Não informado",
    type,
    scope,
    visualAssetId: card.assetId ?? registryCompetition?.visualAssetId,
    matchesCount: card.matchesCount,
    seasonsCount: card.seasonsCount,
    latestSeasonLabel: card.latestContext?.seasonLabel ?? card.range.toSeasonLabel,
  };
}

function getCompetitionSourceLabel(competition: CatalogCompetition): string {
  if (competition.source === "multi" || competition.additionalSources.length > 0) {
    return "Multi-fonte";
  }

  if (competition.dominantSource === "transfermarkt") {
    return "Transfermarkt";
  }

  if (competition.dominantSource === "eloratings") {
    return "Elo+Matches";
  }

  return "Publicado";
}

function describeCompetitionTypeLabel(competition: CatalogCompetition): string {
  if (competition.type === "domestic_league") {
    return "Liga";
  }

  if (competition.type === "domestic_cup") {
    return "Copa";
  }

  return competition.scope === "global" ? "Mundial" : "Intercontinental";
}

function describeCompetitionScopeLabel(competition: CatalogCompetition): string {
  if (competition.scope === "global") {
    return "Torneio global";
  }

  if (competition.scope === "continental") {
    return "Torneio continental";
  }

  if (competition.type === "domestic_cup") {
    return "Copa doméstica";
  }

  return "Liga doméstica";
}

function getCompetitionRegionLabel(competition: CatalogCompetition): string {
  const normalizedRegion = normalizeSearchValue(competition.region);

  if (normalizedRegion.includes("europa") || normalizedRegion.includes("europe")) {
    return "Europa";
  }

  if (
    normalizedRegion.includes("america do sul") ||
    normalizedRegion.includes("america del sur") ||
    normalizedRegion.includes("south america")
  ) {
    return "América do Sul";
  }

  if (normalizedRegion.includes("global") || normalizedRegion.includes("mundo")) {
    return "Global";
  }

  return competition.region;
}

function buildCompetitionGroups(competitions: CatalogCompetition[]) {
  const domestic = competitions.filter((competition) => competition.scope === "domestic");
  const international = competitions.filter((competition) => competition.scope === "continental");
  const global = competitions.filter((competition) => competition.scope === "global");

  return { domestic, global, international };
}

function buildCompetitionCardHref(competition: CatalogCompetition): string {
  return buildCompetitionHubPath(competition.key);
}

function buildCompetitionCtaLabel(_competition: CatalogCompetition): string {
  return "Ver temporadas";
}

function buildCompetitionFallbackLabel(competition: CatalogCompetition): string {
  const normalizedTokens = competition.shortName
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (normalizedTokens.length === 0) {
    return competition.key.slice(0, 3).toUpperCase();
  }

  if (normalizedTokens.length === 1) {
    return normalizedTokens[0].slice(0, 3).toUpperCase();
  }

  return normalizedTokens
    .slice(0, 2)
    .map((token) => token[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

function buildCompetitionSearchContent(competition: CatalogCompetition): string {
  return normalizeSearchValue(
    [
      competition.name,
      competition.shortName,
      competition.country,
      competition.region,
      getCompetitionRegionLabel(competition),
      describeCompetitionTypeLabel(competition),
      describeCompetitionScopeLabel(competition),
      competition.key.replace(/_/g, " "),
    ].join(" "),
  );
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

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={joinClasses("h-4 w-4", className)}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="m16 16 4 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function HeaderMetricCard({
  detail,
  highlight = false,
  label,
  value,
}: {
  detail: string;
  highlight?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div className={joinClasses(styles.metricCard, highlight && styles.metricCardHighlight)}>
      <p className={styles.metricValue}>{value}</p>
      <p className={styles.metricLabel}>{label}</p>
      <p className={styles.metricDetail}>{detail}</p>
    </div>
  );
}

function TableAction({ competition }: { competition: CatalogCompetition }) {
  const href = buildCompetitionCardHref(competition);

  return (
    <Link
      aria-label={buildCompetitionCtaLabel(competition)}
      className={styles.tableAction}
      href={href}
      title={buildCompetitionCtaLabel(competition)}
    >
      <ArrowRightIcon />
    </Link>
  );
}

function CompetitionMatrixRow({ competition }: { competition: CatalogCompetition }) {
  return (
    <tr className={styles.matrixRow}>
      <td className={styles.matrixCell}>
        <div className={styles.competitionIdentity}>
          <ProfileMedia
            alt={`Logo de ${competition.name}`}
            assetId={competition.visualAssetId ?? competition.id}
            category="competitions"
            className={styles.competitionMedia}
            fallback={buildCompetitionFallbackLabel(competition)}
            fallbackClassName={styles.competitionFallback}
            imageClassName={styles.competitionImage}
          />

          <div className={styles.competitionLead}>
            <p className={styles.competitionName}>{competition.name}</p>
            <p className={styles.competitionScope}>
              {describeCompetitionScopeLabel(competition)} · {getCompetitionSourceLabel(competition)}
            </p>
          </div>
        </div>
      </td>
      <td className={styles.matrixCellMuted}>{getCompetitionRegionLabel(competition)}</td>
      <td className={styles.matrixCell}>{competition.country}</td>
      <td className={styles.matrixCell}>
        <span className={styles.typeBadge}>{describeCompetitionTypeLabel(competition)}</span>
      </td>
      <td className={styles.matrixCellNumeric}>{formatWholeNumber(competition.seasonsCount)}</td>
      <td className={styles.matrixCellNumeric}>{competition.latestSeasonLabel ?? "-"}</td>
      <td className={styles.matrixCellAction}>
        <TableAction competition={competition} />
      </td>
    </tr>
  );
}

function CompetitionMobileCard({ competition }: { competition: CatalogCompetition }) {
  const href = buildCompetitionCardHref(competition);
  const content = (
    <>
      <div className={styles.mobileCardHeader}>
        <div className={styles.competitionIdentity}>
          <ProfileMedia
            alt={`Logo de ${competition.name}`}
            assetId={competition.visualAssetId ?? competition.id}
            category="competitions"
            className={styles.competitionMedia}
            fallback={buildCompetitionFallbackLabel(competition)}
            fallbackClassName={styles.competitionFallback}
            imageClassName={styles.competitionImage}
            linkBehavior="none"
          />

          <div className={styles.competitionLead}>
            <p className={styles.competitionName}>{competition.name}</p>
            <p className={styles.competitionScope}>
              {describeCompetitionScopeLabel(competition)} · {getCompetitionSourceLabel(competition)}
            </p>
          </div>
        </div>

        <span className={styles.typeBadge}>{describeCompetitionTypeLabel(competition)}</span>
      </div>

      <div className={styles.mobileMetaGrid}>
        <div className={styles.mobileMetaItem}>
          <span className={styles.mobileMetaLabel}>Região</span>
          <span className={styles.mobileMetaValue}>{getCompetitionRegionLabel(competition)}</span>
        </div>
        <div className={styles.mobileMetaItem}>
          <span className={styles.mobileMetaLabel}>País</span>
          <span className={styles.mobileMetaValue}>{competition.country}</span>
        </div>
        <div className={styles.mobileMetaItem}>
          <span className={styles.mobileMetaLabel}>Temporadas</span>
          <span className={styles.mobileMetaValue}>{formatWholeNumber(competition.seasonsCount)}</span>
        </div>
        <div className={styles.mobileMetaItem}>
          <span className={styles.mobileMetaLabel}>Última edição</span>
          <span className={styles.mobileMetaValue}>{competition.latestSeasonLabel ?? "-"}</span>
        </div>
      </div>

      <div className={styles.mobileCardFooter}>
        <span>{buildCompetitionCtaLabel(competition)}</span>
        <ArrowRightIcon />
      </div>
    </>
  );

  return (
    <Link className={styles.mobileCard} href={href}>
      {content}
    </Link>
  );
}

export default function CompetitionsIndexPage() {
  const homeQuery = useHomePage();
  const allCompetitions = useMemo(
    () => (homeQuery.data?.competitions ?? []).map(buildCatalogCompetition),
    [homeQuery.data?.competitions],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("all");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [regionFilter, setRegionFilter] = useState("all");

  const totalSeasonsTracked = allCompetitions.reduce(
    (total, competition) => total + competition.seasonsCount,
    0,
  );
  const { domestic, global, international } = buildCompetitionGroups(allCompetitions);
  const unifiedCompetitionsCount = allCompetitions.filter(
    (competition) => competition.source === "multi" || competition.additionalSources.length > 0,
  ).length;
  const normalizedSearchQuery = normalizeSearchValue(searchQuery);

  const regionOptions = useMemo(() => {
    return Array.from(new Set(allCompetitions.map((competition) => getCompetitionRegionLabel(competition))))
      .sort((left, right) => left.localeCompare(right, "pt-BR"));
  }, [allCompetitions]);

  const filteredCompetitions = useMemo(() => {
    return allCompetitions.filter((competition) => {
      if (scopeFilter === "domestic" && competition.scope !== "domestic") {
        return false;
      }

      if (scopeFilter === "international" && competition.scope !== "continental") {
        return false;
      }

      if (scopeFilter === "global" && competition.scope !== "global") {
        return false;
      }

      if (typeFilter !== "all" && competition.type !== typeFilter) {
        return false;
      }

      if (regionFilter !== "all" && getCompetitionRegionLabel(competition) !== regionFilter) {
        return false;
      }

      if (
        normalizedSearchQuery &&
        !buildCompetitionSearchContent(competition).includes(normalizedSearchQuery)
      ) {
        return false;
      }

      return true;
    });
  }, [allCompetitions, normalizedSearchQuery, regionFilter, scopeFilter, typeFilter]);

  const filteredSeasonsCount = filteredCompetitions.reduce(
    (total, competition) => total + competition.seasonsCount,
    0,
  );
  const hasResults = filteredCompetitions.length > 0;
  const hasActiveFilters =
    normalizedSearchQuery.length > 0 ||
    scopeFilter !== "all" ||
    typeFilter !== "all" ||
    regionFilter !== "all";

  const emptyStateDescription = homeQuery.isLoading
    ? "Carregando o catálogo publicado no Data Warehouse."
    : homeQuery.isError
      ? "Não foi possível carregar o catálogo de competições agora."
      : hasActiveFilters
    ? "Nenhuma competição atende ao recorte atual. Limpe os filtros ou tente outro termo."
    : "Não há competições disponíveis para exibir agora.";

  const resetFilters = () => {
    setSearchQuery("");
    setScopeFilter("all");
    setTypeFilter("all");
    setRegionFilter("all");
  };

  return (
    <div className={styles.pageRoot}>
      <section className={styles.pageHeader}>
        <div className={styles.breadcrumbRow}>
          <Link className={styles.breadcrumbLink} href="/">
            Início
          </Link>
          <span className={styles.breadcrumbDivider}>/</span>
          <span className={styles.breadcrumbCurrent}>Competições</span>
        </div>

        <div className={styles.headerGrid}>
          <div className={styles.headerCopy}>
            <p className={styles.headerEyebrow}>Catálogo competitivo</p>
            <h1 className={styles.headerTitle}>Análise de competições</h1>
            <p className={styles.headerLead}>
              Explore o arquivo histórico por competição, região e tipo.
            </p>

            <div className={styles.headerTags}>
              <span className={styles.headerTag}>{formatWholeNumber(unifiedCompetitionsCount)} unificadas</span>
              <span className={styles.headerTag}>{formatWholeNumber(domestic.length)} nacionais</span>
              <span className={styles.headerTag}>
                {formatWholeNumber(international.length)} intercontinentais
              </span>
              <span className={styles.headerTag}>{formatWholeNumber(global.length)} mundiais</span>
            </div>
          </div>

          <div className={styles.metricsGrid}>
            <HeaderMetricCard
              detail="catálogo"
              label="Competições"
              value={formatWholeNumber(allCompetitions.length)}
            />
            <HeaderMetricCard
              detail="edições"
              label="Temporadas"
              value={formatWholeNumber(totalSeasonsTracked)}
            />
          </div>
        </div>
      </section>

      <section className={styles.controlBar}>
        <div className={styles.searchField}>
          <SearchIcon className={styles.searchIcon} />
          <input
            autoComplete="off"
            className={styles.searchInput}
            onChange={(event) => {
              setSearchQuery(event.target.value);
            }}
            placeholder="Buscar competição, país ou região"
            type="search"
            value={searchQuery}
          />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Escopo</span>
            <select
              className={styles.filterSelect}
              onChange={(event) => {
                setScopeFilter(event.target.value as ScopeFilter);
              }}
              value={scopeFilter}
            >
              <option value="all">Todas</option>
              <option value="domestic">Nacionais</option>
              <option value="international">Intercontinentais</option>
              <option value="global">Mundiais</option>
            </select>
          </label>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Tipo</span>
            <select
              className={styles.filterSelect}
              onChange={(event) => {
                setTypeFilter(event.target.value as TypeFilter);
              }}
              value={typeFilter}
            >
              <option value="all">Todos</option>
              <option value="domestic_league">Ligas</option>
              <option value="domestic_cup">Copas</option>
              <option value="international_cup">Intercontinentais</option>
            </select>
          </label>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Região</span>
            <select
              className={styles.filterSelect}
              onChange={(event) => {
                setRegionFilter(event.target.value);
              }}
              value={regionFilter}
            >
              <option value="all">Todas</option>
              {regionOptions.map((region) => (
                <option key={region} value={region}>
                  {region}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          className={joinClasses(
            "button-pill",
            hasActiveFilters ? "button-pill-primary" : "button-pill-secondary",
            styles.filtersResetButton,
          )}
          disabled={!hasActiveFilters}
          onClick={resetFilters}
          type="button"
        >
          Limpar filtros
        </button>
      </section>

      <section className={styles.matrixShell}>
        <div className={styles.matrixHeader}>
          <div>
            <p className={styles.matrixEyebrow}>Catálogo ativo</p>
            <h2 className={styles.matrixTitle}>Competições disponíveis</h2>
          </div>

          <div className={styles.matrixSummary}>
            <span className={styles.matrixSummaryBadge}>
              {formatWholeNumber(filteredCompetitions.length)} competições
            </span>
            <span className={styles.matrixSummaryBadge}>{formatWholeNumber(filteredSeasonsCount)} temporadas</span>
          </div>
        </div>

        {hasResults ? (
          <>
            <div className={styles.desktopMatrix}>
              <table className={styles.matrixTable}>
                <thead>
                  <tr>
                    <th>Competição</th>
                    <th>Região</th>
                    <th>País</th>
                    <th>Tipo</th>
                    <th>Temporadas</th>
                    <th>Última edição</th>
                    <th>Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCompetitions.map((competition) => (
                    <CompetitionMatrixRow competition={competition} key={competition.id} />
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.mobileMatrix}>
              {filteredCompetitions.map((competition) => (
                <CompetitionMobileCard competition={competition} key={competition.id} />
              ))}
            </div>

            <div className={styles.matrixFooter}>
              <p className={styles.matrixFooterText}>
                Mostrando {formatWholeNumber(filteredCompetitions.length)} de{" "}
                {formatWholeNumber(allCompetitions.length)} competições.
              </p>
              {hasActiveFilters ? (
                <button className={styles.inlineResetButton} onClick={resetFilters} type="button">
                  Voltar ao catálogo completo
                </button>
              ) : null}
            </div>
          </>
        ) : (
          <EmptyState
            actionLabel={hasActiveFilters ? "Limpar filtros" : undefined}
            className={styles.emptyState}
            description={emptyStateDescription}
            onAction={hasActiveFilters ? resetFilters : undefined}
            title="Nenhuma competição encontrada"
          />
        )}
      </section>
    </div>
  );
}
