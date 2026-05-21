import type { CompetitionDef, CompetitionSeasonCalendar } from "@/config/competitions.registry";

export interface SeasonDef {
  id: string; // Canonical route/display identifier (e.g. "2024", "2024/2025")
  label: string; // Display label (e.g. "2024", "2024/2025")
  calendar: CompetitionSeasonCalendar;
  queryId: string; // Filter/BFF identifier (e.g. "2024" for split-year seasons)
  catalogLabel: string; // Raw/control catalog label (e.g. "2024_25")
}

const ANNUAL_SEASON_PATTERN = /^\d{4}$/;
const SPLIT_YEAR_LABEL_PATTERN = /^(\d{4})\/(\d{4})$/;
const SPLIT_YEAR_CATALOG_PATTERN = /^(\d{4})_(\d{2}|\d{4})$/;
const MIN_SUPPORTED_SEASON_YEAR = 1900;
const MAX_SUPPORTED_SEASON_YEAR = 2100;

export const SUPPORTED_SEASONS: SeasonDef[] = [
  { id: "2025", label: "2025", calendar: "annual", queryId: "2025", catalogLabel: "2025" },
  { id: "2024", label: "2024", calendar: "annual", queryId: "2024", catalogLabel: "2024" },
  { id: "2023", label: "2023", calendar: "annual", queryId: "2023", catalogLabel: "2023" },
  { id: "2022", label: "2022", calendar: "annual", queryId: "2022", catalogLabel: "2022" },
  { id: "2021", label: "2021", calendar: "annual", queryId: "2021", catalogLabel: "2021" },
  {
    id: "2024/2025",
    label: "2024/2025",
    calendar: "split_year",
    queryId: "2024",
    catalogLabel: "2024_25",
  },
  {
    id: "2023/2024",
    label: "2023/2024",
    calendar: "split_year",
    queryId: "2023",
    catalogLabel: "2023_24",
  },
  {
    id: "2022/2023",
    label: "2022/2023",
    calendar: "split_year",
    queryId: "2022",
    catalogLabel: "2022_23",
  },
  {
    id: "2021/2022",
    label: "2021/2022",
    calendar: "split_year",
    queryId: "2021",
    catalogLabel: "2021_22",
  },
  {
    id: "2020/2021",
    label: "2020/2021",
    calendar: "split_year",
    queryId: "2020",
    catalogLabel: "2020_21",
  },
];

export const SUPPORTED_SEASON_QUERY_IDS = Array.from(
  new Set(SUPPORTED_SEASONS.map((season) => season.queryId)),
);

export const SUPPORTED_SEASON_COVERAGE_COUNT = SUPPORTED_SEASON_QUERY_IDS.length;

function normalizeSeasonValue(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmedValue = value.trim();
  return trimmedValue.length > 0 ? trimmedValue : null;
}

function isSeasonSupportedByCompetition(
  competition: CompetitionDef,
  season: SeasonDef,
): boolean {
  const supportedSeasonQueryIds = competition.supportedSeasonQueryIds;

  if (!supportedSeasonQueryIds || supportedSeasonQueryIds.length === 0) {
    return true;
  }

  return supportedSeasonQueryIds.includes(season.queryId);
}

function toCatalogSeasonLabel(value: string): string {
  const normalizedValue = value.trim();
  const slashMatch = normalizedValue.match(/^(\d{4})\/(\d{4})$/);

  if (slashMatch) {
    return `${slashMatch[1]}_${slashMatch[2].slice(-2)}`;
  }

  return normalizedValue;
}

function isSupportedSeasonYear(year: number): boolean {
  return year >= MIN_SUPPORTED_SEASON_YEAR && year <= MAX_SUPPORTED_SEASON_YEAR;
}

function buildAnnualSeason(year: number): SeasonDef {
  const label = String(year);

  return {
    id: label,
    label,
    calendar: "annual",
    queryId: label,
    catalogLabel: label,
  };
}

function buildSplitYearSeason(startYear: number): SeasonDef {
  const queryId = String(startYear);
  const nextYear = startYear + 1;

  return {
    id: `${queryId}/${nextYear}`,
    label: `${queryId}/${nextYear}`,
    calendar: "split_year",
    queryId,
    catalogLabel: `${queryId}_${String(nextYear).slice(-2)}`,
  };
}

function parseAnnualSeasonYear(value: string | null | undefined): number | null {
  if (!value || !ANNUAL_SEASON_PATTERN.test(value)) {
    return null;
  }

  const parsedYear = Number.parseInt(value, 10);
  return isSupportedSeasonYear(parsedYear) ? parsedYear : null;
}

function parseSplitYearStartYear(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }

  const slashMatch = value.match(SPLIT_YEAR_LABEL_PATTERN);

  if (slashMatch) {
    const startYear = Number.parseInt(slashMatch[1], 10);
    const endYear = Number.parseInt(slashMatch[2], 10);

    if (endYear === startYear + 1 && isSupportedSeasonYear(startYear)) {
      return startYear;
    }

    return null;
  }

  const catalogMatch = value.match(SPLIT_YEAR_CATALOG_PATTERN);

  if (!catalogMatch) {
    return null;
  }

  const startYear = Number.parseInt(catalogMatch[1], 10);
  const trailingYear = catalogMatch[2];
  const expectedEndYear = startYear + 1;
  const parsedEndYear =
    trailingYear.length === 2
      ? Number.parseInt(`${catalogMatch[1].slice(0, 2)}${trailingYear}`, 10)
      : Number.parseInt(trailingYear, 10);

  if (parsedEndYear === expectedEndYear && isSupportedSeasonYear(startYear)) {
    return startYear;
  }

  return null;
}

function buildDynamicSeasonFromQueryId(
  queryId: string | null | undefined,
  calendar: CompetitionSeasonCalendar,
): SeasonDef | undefined {
  const seasonYear = parseAnnualSeasonYear(queryId);

  if (seasonYear === null) {
    return undefined;
  }

  return calendar === "annual" ? buildAnnualSeason(seasonYear) : buildSplitYearSeason(seasonYear);
}

function buildDynamicSeasonFromLabel(
  label: string | null | undefined,
  calendar?: CompetitionSeasonCalendar,
): SeasonDef | undefined {
  const annualSeasonYear = parseAnnualSeasonYear(label);

  if (annualSeasonYear !== null) {
    if (!calendar || calendar === "annual") {
      return buildAnnualSeason(annualSeasonYear);
    }
  }

  const splitYearSeasonStart = parseSplitYearStartYear(label);

  if (splitYearSeasonStart !== null) {
    if (!calendar || calendar === "split_year") {
      return buildSplitYearSeason(splitYearSeasonStart);
    }
  }

  return undefined;
}

export function getSeasonById(id: string | null | undefined): SeasonDef | undefined {
  const normalizedId = normalizeSeasonValue(id);
  if (!normalizedId) {
    return undefined;
  }

  return (
    SUPPORTED_SEASONS.find((season) => season.id === normalizedId) ??
    buildDynamicSeasonFromLabel(normalizedId)
  );
}

export function getSeasonByLabel(label: string | null | undefined): SeasonDef | undefined {
  const normalizedLabel = normalizeSeasonValue(label);
  if (!normalizedLabel) {
    return undefined;
  }

  const catalogLabel = toCatalogSeasonLabel(normalizedLabel);

  return (
    SUPPORTED_SEASONS.find(
      (season) =>
        season.label === normalizedLabel ||
        season.catalogLabel === normalizedLabel ||
        season.catalogLabel === catalogLabel,
    ) ?? buildDynamicSeasonFromLabel(normalizedLabel)
  );
}

export function getSeasonByQueryId(
  queryId: string | null | undefined,
  calendar: CompetitionSeasonCalendar,
): SeasonDef | undefined {
  const normalizedQueryId = normalizeSeasonValue(queryId);
  if (!normalizedQueryId) {
    return undefined;
  }

  return (
    SUPPORTED_SEASONS.find(
      (season) => season.calendar === calendar && season.queryId === normalizedQueryId,
    ) ?? buildDynamicSeasonFromQueryId(normalizedQueryId, calendar)
  );
}

export function listSeasonsForCompetition(
  competition: CompetitionDef | null | undefined,
): SeasonDef[] {
  if (!competition) {
    return [];
  }

  if (competition.supportedSeasonQueryIds && competition.supportedSeasonQueryIds.length > 0) {
    const seasons: SeasonDef[] = [];
    const seenSeasonIds = new Set<string>();

    for (const queryId of competition.supportedSeasonQueryIds) {
      const season = getSeasonByQueryId(queryId, competition.seasonCalendar);

      if (!season || seenSeasonIds.has(season.id)) {
        continue;
      }

      seenSeasonIds.add(season.id);
      seasons.push(season);
    }

    return seasons;
  }

  return SUPPORTED_SEASONS.filter(
    (season) =>
      season.calendar === competition.seasonCalendar &&
      isSeasonSupportedByCompetition(competition, season),
  );
}

export function getLatestSeasonForCompetition(
  competition: CompetitionDef | null | undefined,
): SeasonDef | undefined {
  return listSeasonsForCompetition(competition)[0];
}

export function resolveSeasonForCompetition(
  competition: CompetitionDef | null | undefined,
  input: {
    seasonId?: string | null;
    seasonLabel?: string | null;
  },
): SeasonDef | null {
  if (!competition) {
    return null;
  }

  const seasons = listSeasonsForCompetition(competition);
  const normalizedSeasonId = normalizeSeasonValue(input.seasonId);
  const normalizedSeasonLabel = normalizeSeasonValue(input.seasonLabel);

  const seasonFromId =
    seasons.find((season) => season.id === normalizedSeasonId) ??
    getSeasonByQueryId(normalizedSeasonId, competition.seasonCalendar);
  const seasonFromLabel = seasons.find((season) => {
    if (!normalizedSeasonLabel) {
      return false;
    }

    const catalogLabel = toCatalogSeasonLabel(normalizedSeasonLabel);
    return (
      season.label === normalizedSeasonLabel ||
      season.catalogLabel === normalizedSeasonLabel ||
      season.catalogLabel === catalogLabel
    );
  }) ?? buildDynamicSeasonFromLabel(normalizedSeasonLabel, competition.seasonCalendar);

  if (seasonFromId && seasonFromLabel && seasonFromId.id !== seasonFromLabel.id) {
    return null;
  }

  const resolvedSeason = seasonFromId ?? seasonFromLabel ?? null;

  if (!resolvedSeason) {
    return null;
  }

  return isSeasonSupportedByCompetition(competition, resolvedSeason) ? resolvedSeason : null;
}
