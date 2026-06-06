import Link from "next/link";

import { listRankingsByEntity } from "@/config/ranking.registry";
import type { RankingDefinition, RankingMinSample } from "@/config/ranking.types";
import { fetchRanking } from "@/features/rankings/services/rankings.service";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import type { VenueFilter } from "@/shared/types/filters.types";
import { buildRankingPath } from "@/shared/utils/context-routing";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type RankingsHubPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

type RankingGroup = {
  description: string;
  eyebrow: string;
  items: RankingHubCard[];
  key: "player" | "team";
  title: string;
};

type RankingHubCard = {
  href: string;
  leader: {
    assetId: string | null;
    name: string | null;
  };
  ranking: RankingDefinition;
  sample: RankingMinSample;
};

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function readSearchParam(
  searchParams: Record<string, string | string[] | undefined>,
  key: string,
): string | null {
  const rawValue = searchParams[key];

  const value = Array.isArray(rawValue) ? (rawValue[0] ?? null) : (rawValue ?? null);

  if (!value) {
    return null;
  }

  const normalizedValue = value.trim();
  return normalizedValue.toLowerCase() === "all" ? null : normalizedValue;
}

function parseLastNValue(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

function normalizeVenue(value: string | null): VenueFilter | undefined {
  if (value === "home" || value === "away" || value === "all") {
    return value;
  }

  return undefined;
}

function describeEntityLabel(entity: RankingDefinition["entity"]): string {
  if (entity === "team") {
    return "Times";
  }

  return "Jogadores";
}

function resolveDefaultSample(ranking: RankingDefinition): RankingMinSample {
  if (ranking.minSample) {
    return ranking.minSample;
  }

  if (ranking.entity === "player") {
    return { field: "minutes_played", min: 1800 };
  }

  return { field: "matches_played", min: 20 };
}

function describeSampleValue(sample: RankingMinSample): string {
  if (sample.field === "minutes_played") {
    return `${formatWholeNumber(sample.min)} min`;
  }

  return `${formatWholeNumber(sample.min)} jogos`;
}

function describeLeaderValue(leaderName: string | null): string {
  if (!leaderName) {
    return "Sem líder";
  }

  return leaderName;
}

function buildLeaderFallback(name: string | null): string {
  if (!name) {
    return "RK";
  }

  const initials = name
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "RK";
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

function RankingIcon({ rankingId }: { rankingId: RankingDefinition["id"] }) {
  const className = styles.cardIcon;

  if (rankingId === "player-goals") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="m12 8.3 2.4 1.7-.9 2.8h-3l-.9-2.8L12 8.3Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.5"
        />
        <path
          d="m9.6 10.1-2.5.3m9.8-.3 2.5.3M10.5 12.8l-1.6 2.2m4.6-2.2 1.6 2.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.5"
        />
      </svg>
    );
  }

  if (rankingId === "player-assists") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M6.8 14.4c1.3-2.8 4.2-5.1 7.8-5.7l3.2 3.2-2.8 2.6-3.1-3.1"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M5.8 16.8 8.6 14m8.1-5.3 1.8-1.8"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
        <path
          d="M14.7 16.6c-.9 1.4-2.2 2.6-4 3.4-1 .5-2.1.1-2.6-.9-.5-1 0-2.2 1-2.6 1.6-.8 2.7-1.9 3.4-3.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (rankingId === "player-shots-total") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="6.8" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="12" cy="12" r="2.1" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 3.8v2.3M12 17.9v2.3M3.8 12h2.3M17.9 12h2.3" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (rankingId === "player-shots-on-target") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path d="M5.5 6.5h13v11h-13z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.8" />
        <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.8" />
        <path d="m15.6 8.4 2.4-2.4M14.9 6h3.1v3.1" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (rankingId === "player-rating") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="m12 5.2 1.9 3.9 4.3.6-3.1 3 0.7 4.3-3.8-2-3.8 2 .7-4.3-3.1-3 4.3-.6L12 5.2Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (rankingId === "player-cards" || rankingId === "player-yellow-cards") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M7.4 7.3h6.5a1.5 1.5 0 0 1 1.5 1.5v7.9a1.5 1.5 0 0 1-1.5 1.5H8.8a1.5 1.5 0 0 1-1.4-1.5V8.2c0-.5.4-.9 1-.9Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M10.1 5.8h6.4a1.5 1.5 0 0 1 1.5 1.5v7.9a1.5 1.5 0 0 1-1.5 1.5h-5.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (rankingId === "team-possession") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="4.8" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M18.7 9.2a7.7 7.7 0 0 0-13.4-1.3M5.3 14.8a7.7 7.7 0 0 0 13.4 1.3"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
        <path d="m18.4 6.4.5 3.5-3.4-.8M5.6 17.6l-.5-3.5 3.4.8" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
      <path
        d="M6 16.8 10 12l2.5 2.6L18 8.8M18 8.8v4M18 8.8h-4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M5.5 19h13" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function HeaderMetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <article className={styles.metricCard}>
      <p className={styles.metricValue}>{value}</p>
      <p className={styles.metricLabel}>{label}</p>
    </article>
  );
}

function RankingsCatalogCard({
  card,
}: {
  card: RankingHubCard;
}) {
  const { href, leader, ranking, sample } = card;
  const leaderLabel = describeLeaderValue(leader.name);
  const leaderMediaCategory = ranking.entity === "team" ? "clubs" : "players";

  return (
    <Link className={styles.catalogCard} href={href}>
      <div className={styles.catalogCardContent}>
        <div className={styles.catalogCardHeader}>
          <div className={styles.cardIdentity}>
            <div className={styles.cardMarkFrame}>
              <RankingIcon rankingId={ranking.id} />
            </div>
            <span className={styles.metaPill}>{describeEntityLabel(ranking.entity)}</span>
          </div>
          <span className={styles.coverageBadge}>Disponível</span>
        </div>

        <div className={styles.catalogCardBody}>
          <h3 className={styles.catalogCardTitle}>{ranking.label}</h3>
          <p className={styles.catalogCardDescription}>{ranking.description}</p>
        </div>

        <div className={styles.statsGrid}>
          <div className={joinClasses(styles.statTile, styles.statTileLeader)}>
            <p className={styles.statLabel}>Líder</p>
            <div className={styles.leaderTileBody}>
              <ProfileMedia
                alt={leaderLabel}
                assetId={leader.assetId}
                category={leaderMediaCategory}
                className={styles.leaderMedia}
                fallback={buildLeaderFallback(leader.name)}
                fallbackClassName={styles.leaderMediaFallback}
                imageClassName={styles.leaderMediaImage}
                shape={ranking.entity === "team" ? "rounded" : "circle"}
                linkBehavior="none"
              />
              <p className={joinClasses(styles.statValue, styles.statValueLeader)}>{leaderLabel}</p>
            </div>
          </div>
          <div className={styles.statTile}>
            <p className={styles.statLabel}>Amostra</p>
            <p className={styles.statValue}>{describeSampleValue(sample)}</p>
          </div>
        </div>

        <div className={styles.cardFooter}>
          <span className={styles.cardFooterLabel}>Abrir ranking</span>
          <ArrowRightIcon className={styles.cardFooterArrow} />
        </div>
      </div>
    </Link>
  );
}

async function buildRankingHubCard(
  ranking: RankingDefinition,
  sharedFilters: {
    competitionId: string | null;
    seasonId: string | null;
    roundId: string | null;
    venue: string | null;
    lastN: number | null;
    dateRangeStart: string | null;
    dateRangeEnd: string | null;
  },
): Promise<RankingHubCard> {
  const sample = resolveDefaultSample(ranking);

  try {
    const response = await fetchRanking({
      rankingDefinition: ranking,
      filters: {
        competitionId: sharedFilters.competitionId,
        seasonId: sharedFilters.seasonId,
        roundId: sharedFilters.roundId,
        venue: normalizeVenue(sharedFilters.venue),
        lastN: sharedFilters.lastN,
        dateRangeStart: sharedFilters.dateRangeStart,
        dateRangeEnd: sharedFilters.dateRangeEnd,
        minSampleValue: sample.min,
        page: 1,
        pageSize: 1,
        sortDirection: ranking.defaultSort,
      },
    });

    return {
      href: buildRankingPath(ranking.id, sharedFilters),
      leader: {
        assetId: response.data.rows[0]?.entityId ?? null,
        name: response.data.rows[0]?.entityName ?? null,
      },
      ranking,
      sample,
    };
  } catch {
    return {
      href: buildRankingPath(ranking.id, sharedFilters),
      leader: {
        assetId: null,
        name: null,
      },
      ranking,
      sample,
    };
  }
}

export default async function RankingsHubPage({ searchParams }: RankingsHubPageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const sharedFilters = {
    competitionId: readSearchParam(resolvedSearchParams, "competitionId"),
    seasonId: readSearchParam(resolvedSearchParams, "seasonId"),
    roundId: readSearchParam(resolvedSearchParams, "roundId"),
    venue: readSearchParam(resolvedSearchParams, "venue"),
    lastN: parseLastNValue(readSearchParam(resolvedSearchParams, "lastN")),
    dateRangeStart: readSearchParam(resolvedSearchParams, "dateRangeStart"),
    dateRangeEnd: readSearchParam(resolvedSearchParams, "dateRangeEnd"),
  };

  const playerRankings = await Promise.all(
    listRankingsByEntity("player").map((ranking) => buildRankingHubCard(ranking, sharedFilters)),
  );
  const teamRankings = await Promise.all(
    listRankingsByEntity("team").map((ranking) => buildRankingHubCard(ranking, sharedFilters)),
  );
  const rankingGroups: RankingGroup[] = [
    {
      key: "player",
      eyebrow: "Jogadores",
      title: "Leituras individuais",
      description: "Gols, assistências, finalizações, nota e disciplina no mesmo lugar.",
      items: playerRankings,
    },
    {
      key: "team",
      eyebrow: "Times",
      title: "Leituras coletivas",
      description: "Visão rápida dos rankings de posse e circulação que já estão prontos para abrir.",
      items: teamRankings,
    },
  ];
  const totalRankings = playerRankings.length + teamRankings.length;

  return (
    <div className={styles.pageRoot}>
      <section className={styles.pageHeader}>
        <div className={styles.breadcrumbRow}>
          <Link className={styles.breadcrumbLink} href="/">
            Início
          </Link>
          <span className={styles.breadcrumbDivider}>/</span>
          <span className={styles.breadcrumbCurrent}>Rankings</span>
        </div>

        <div className={styles.headerGrid}>
          <div className={styles.headerCopy}>
            <p className={styles.headerEyebrow}>Catálogo analítico</p>
            <h1 className={styles.headerTitle}>Hub de rankings</h1>
            <p className={styles.headerLead}>
              Escolha o ranking certo para começar a explorar os destaques de jogadores e times.
            </p>
          </div>

          <div className={styles.metricsGrid}>
            <HeaderMetricCard label="Rankings" value={formatWholeNumber(totalRankings)} />
          </div>
        </div>
      </section>

      <div className={styles.catalogStack}>
        {rankingGroups.map((group) => (
          <section className={styles.catalogPanel} key={group.key}>
            <div className={styles.sectionHeader}>
              <div className={styles.sectionHeaderLead}>
                <p className={styles.sectionEyebrow}>{group.eyebrow}</p>
                <h2 className={styles.sectionTitle}>{group.title}</h2>
                <p className={styles.sectionDescription}>{group.description}</p>
              </div>

              <div className={styles.sectionHeaderActions}>
                <span className={styles.sectionCount}>
                  {formatWholeNumber(group.items.length)} rankings
                </span>
              </div>
            </div>

            <div className={styles.catalogGrid}>
              {group.items.map((card) => (
                <RankingsCatalogCard card={card} key={card.ranking.id} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
