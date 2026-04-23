export type CompetitionSeasonCalendar = "annual" | "split_year";
export type CompetitionScope = "domestic" | "continental" | "global";

export interface CompetitionDef {
  id: string;
  key: string;
  name: string;
  shortName: string;
  country: string;
  region: string;
  type: "domestic_league" | "domestic_cup" | "international_cup";
  scope: CompetitionScope;
  seasonCalendar: CompetitionSeasonCalendar;
  visualAssetId?: string;
  supportedSeasonQueryIds?: string[];
  providerId?: number; // Keep track of the original sportmonks id if needed
}

const CLOSED_ANNUAL_SEASON_QUERY_IDS = ["2025", "2024", "2023", "2022", "2021"];
const WORLD_CUP_SEASON_QUERY_IDS = [
  "2022",
  "2018",
  "2014",
  "2010",
  "2006",
  "2002",
  "1998",
  "1994",
  "1990",
  "1986",
  "1982",
  "1978",
  "1974",
  "1970",
  "1966",
  "1962",
  "1958",
  "1954",
  "1950",
  "1938",
  "1934",
  "1930",
];

export const SUPPORTED_COMPETITIONS: CompetitionDef[] = [
  {
    id: "71", // Brasileirão Série A
    key: "brasileirao_a",
    name: "Campeonato Brasileiro Série A",
    shortName: "Brasileirão",
    country: "Brasil",
    region: "South America",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "annual",
    visualAssetId: "648",
    supportedSeasonQueryIds: CLOSED_ANNUAL_SEASON_QUERY_IDS,
    providerId: 71,
  },
  {
    id: "651", // Brasileirão Série B
    key: "brasileirao_b",
    name: "Campeonato Brasileiro Série B",
    shortName: "Série B",
    country: "Brasil",
    region: "South America",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "annual",
    supportedSeasonQueryIds: CLOSED_ANNUAL_SEASON_QUERY_IDS,
    providerId: 651,
  },
  {
    id: "390", // Libertadores
    key: "libertadores",
    name: "Copa Libertadores da América",
    shortName: "Libertadores",
    country: "América do Sul",
    region: "America do Sul",
    type: "international_cup",
    scope: "continental",
    seasonCalendar: "annual",
    visualAssetId: "1122",
    supportedSeasonQueryIds: CLOSED_ANNUAL_SEASON_QUERY_IDS,
    providerId: 390,
  },
  {
    id: "1116", // Copa Sudamericana
    key: "sudamericana",
    name: "Copa Sudamericana",
    shortName: "Sudamericana",
    country: "América do Sul",
    region: "America do Sul",
    type: "international_cup",
    scope: "continental",
    seasonCalendar: "annual",
    supportedSeasonQueryIds: ["2025", "2024"],
    providerId: 1116,
  },
  {
    id: "732", // Copa do Brasil
    key: "copa_do_brasil",
    name: "Copa do Brasil",
    shortName: "CdB",
    country: "Brasil",
    region: "America do Sul",
    type: "domestic_cup",
    scope: "domestic",
    seasonCalendar: "annual",
    visualAssetId: "654",
    supportedSeasonQueryIds: CLOSED_ANNUAL_SEASON_QUERY_IDS,
    providerId: 732,
  },
  {
    id: "1798", // Supercopa do Brasil
    key: "supercopa_do_brasil",
    name: "Supercopa do Brasil",
    shortName: "Supercopa",
    country: "Brasil",
    region: "America do Sul",
    type: "domestic_cup",
    scope: "domestic",
    seasonCalendar: "annual",
    supportedSeasonQueryIds: ["2025"],
    providerId: 1798,
  },
  {
    id: "0", // FIFA World Cup
    key: "fifa_world_cup_mens",
    name: "Copa do Mundo FIFA",
    shortName: "Copa do Mundo",
    country: "Mundo",
    region: "Global",
    type: "international_cup",
    scope: "global",
    seasonCalendar: "annual",
    visualAssetId: "wc_mens",
    supportedSeasonQueryIds: WORLD_CUP_SEASON_QUERY_IDS,
  },
  {
    id: "1452", // FIFA Intercontinental Cup
    key: "fifa_intercontinental_cup",
    name: "FIFA Intercontinental Cup",
    shortName: "Intercontinental",
    country: "Mundo",
    region: "Global",
    type: "international_cup",
    scope: "global",
    seasonCalendar: "annual",
    supportedSeasonQueryIds: ["2024"],
    providerId: 1452,
  },
  {
    id: "8", // Premier League
    key: "premier_league",
    name: "Premier League",
    shortName: "Premier League",
    country: "Inglaterra",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    providerId: 8,
  },
  {
    id: "2", // Champions League
    key: "champions_league",
    name: "UEFA Champions League",
    shortName: "UCL",
    country: "Europa",
    region: "Europa",
    type: "international_cup",
    scope: "continental",
    seasonCalendar: "split_year",
    providerId: 2,
  },
  {
    id: "564", // La Liga
    key: "la_liga",
    name: "La Liga",
    shortName: "La Liga",
    country: "Espanha",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    providerId: 564,
  },
  {
    id: "384", // Serie A Italy
    key: "serie_a_italy",
    name: "Serie A (Itália)",
    shortName: "Serie A IT",
    country: "Itália",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    providerId: 384,
  },
  {
    id: "82", // Bundesliga
    key: "bundesliga",
    name: "Bundesliga",
    shortName: "Bundesliga",
    country: "Alemanha",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    providerId: 82,
  },
  {
    id: "301", // Ligue 1
    key: "ligue_1",
    name: "Ligue 1",
    shortName: "Ligue 1",
    country: "França",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    providerId: 301,
  },
  {
    id: "462", // Liga Portugal
    key: "primeira_liga",
    name: "Liga Portugal",
    shortName: "Liga Portugal",
    country: "Portugal",
    region: "Europa",
    type: "domestic_league",
    scope: "domestic",
    seasonCalendar: "split_year",
    supportedSeasonQueryIds: ["2024", "2023"],
    providerId: 462,
  },
];

export function getCompetitionById(id: string | null | undefined): CompetitionDef | undefined {
  if (!id) return undefined;
  return SUPPORTED_COMPETITIONS.find((comp) => comp.id === id);
}

export function getCompetitionByKey(key: string | null | undefined): CompetitionDef | undefined {
  if (!key) return undefined;
  return SUPPORTED_COMPETITIONS.find((comp) => comp.key === key);
}

export function getCompetitionVisualAssetId(
  competition: CompetitionDef | null | undefined,
): string | null {
  if (!competition) {
    return null;
  }

  return competition.visualAssetId ?? competition.id;
}
