import { getCompetitionById, getCompetitionByKey } from "@/config/competitions.registry";
import {
  buildWorldCupEditionPath,
  buildWorldCupHubPath,
  buildWorldCupTeamPath,
} from "@/features/world-cup/routes";
import { resolveSeasonForCompetition } from "@/config/seasons.registry";
import type {
  CompetitionSeasonContext,
  CompetitionSeasonContextInput,
} from "@/shared/types/context.types";

type SearchParamsLike =
  | URLSearchParams
  | Pick<URLSearchParams, "get">
  | Record<string, string | string[] | undefined>;

type SharedFilterQueryInput = CompetitionSeasonContextInput & {
  roundId?: string | null;
  stageId?: string | null;
  stageFormat?: string | null;
  venue?: string | null;
  lastN?: number | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
};

const CONTEXT_QUERY_KEYS = ["competitionId", "competitionKey", "seasonId", "seasonLabel"] as const;
export const SEASON_HUB_TABS = ["calendar", "standings", "rankings"] as const;
const WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens";
const WORLD_CUP_STATIC_PATH_SEGMENTS = new Set(["finais", "rankings", "selecoes"]);

type CompetitionSeasonPathInput =
  | CompetitionSeasonContext
  | Pick<CompetitionSeasonContextInput, "competitionKey" | "seasonLabel">;

export type SeasonHubTab = (typeof SEASON_HUB_TABS)[number];
export type ContextQueryKey = (typeof CONTEXT_QUERY_KEYS)[number];

function isSearchParamsRecord(
  searchParams: SearchParamsLike,
): searchParams is Record<string, string | string[] | undefined> {
  return !("get" in searchParams && typeof searchParams.get === "function");
}

function normalizeText(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  const trimmedValue = value.trim();

  if (trimmedValue.length === 0) {
    return null;
  }

  let normalizedValue = trimmedValue;

  try {
    normalizedValue = decodeURIComponent(trimmedValue);
  } catch {
    normalizedValue = trimmedValue;
  }

  return normalizedValue.length > 0 ? normalizedValue : null;
}

function readSearchParam(searchParams: SearchParamsLike, key: string): string | null {
  if ("get" in searchParams && typeof searchParams.get === "function") {
    return normalizeText(searchParams.get(key));
  }

  if (!isSearchParamsRecord(searchParams)) {
    return null;
  }

  const rawValue = searchParams[key];

  if (Array.isArray(rawValue)) {
    return normalizeText(rawValue[0]);
  }

  return normalizeText(rawValue);
}

function isPositiveInteger(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value.trim());
}

function encodeSeasonPathSegment(value: string): string {
  const normalizedValue = value.trim();
  const splitYearMatch = normalizedValue.match(/^(\d{4})\/(\d{4})$/);

  if (splitYearMatch) {
    return encodePathSegment(`${splitYearMatch[1]}_${splitYearMatch[2].slice(-2)}`);
  }

  return encodePathSegment(normalizedValue);
}

function normalizePathname(pathname: string): string {
  const trimmedValue = pathname.trim();

  if (trimmedValue.length === 0) {
    return "/";
  }

  const withoutTrailingSlash =
    trimmedValue.length > 1 ? trimmedValue.replace(/\/+$/, "") : trimmedValue;

  return withoutTrailingSlash.length > 0 ? withoutTrailingSlash : "/";
}

function isWorldCupEditionPath(pathname: string): boolean {
  const match = pathname.match(/^\/copa-do-mundo\/([^/]+)(?:\/|$)/);

  if (!match) {
    return false;
  }

  return !WORLD_CUP_STATIC_PATH_SEGMENTS.has(match[1]);
}

export function resolveCompetitionSeasonContext(
  input: CompetitionSeasonContextInput,
): CompetitionSeasonContext | null {
  const competitionId = normalizeText(input.competitionId);
  const competitionKey = normalizeText(input.competitionKey);
  const seasonId = normalizeText(input.seasonId);
  const seasonLabel = normalizeText(input.seasonLabel);

  const competitionFromId = getCompetitionById(competitionId);
  const competitionFromKey = getCompetitionByKey(competitionKey);

  if (competitionFromId && competitionFromKey && competitionFromId.id !== competitionFromKey.id) {
    return null;
  }

  const competition = competitionFromId ?? competitionFromKey;

  if (!competition) {
    return null;
  }

  const season = resolveSeasonForCompetition(competition, {
    seasonId,
    seasonLabel,
  });

  if (!season) {
    return null;
  }

  return {
    competitionId: competition.id,
    competitionKey: competition.key,
    competitionName: competition.name,
    seasonId: season.queryId,
    seasonLabel: season.label,
  };
}

export function resolveCompetitionSeasonContextFromSearchParams(
  searchParams: SearchParamsLike,
): CompetitionSeasonContext | null {
  return resolveCompetitionSeasonContext({
    competitionId: readSearchParam(searchParams, "competitionId"),
    competitionKey: readSearchParam(searchParams, "competitionKey"),
    seasonId: readSearchParam(searchParams, "seasonId"),
    seasonLabel: readSearchParam(searchParams, "seasonLabel"),
  });
}

export function resolveCompetitionSeasonContextFromPathname(
  pathname: string,
): CompetitionSeasonContext | null {
  const normalizedPathname = normalizePathname(pathname);

  if (isWorldCupEditionPath(normalizedPathname)) {
    const worldCupMatch = normalizedPathname.match(/^\/copa-do-mundo\/([^/]+)(?:\/|$)/);

    if (!worldCupMatch) {
      return null;
    }

    return resolveCompetitionSeasonContext({
      competitionKey: WORLD_CUP_COMPETITION_KEY,
      seasonLabel: worldCupMatch[1],
    });
  }

  const match = normalizedPathname.match(/^\/competitions\/([^/]+)\/seasons\/([^/]+)(?:\/|$)/);

  if (!match) {
    return null;
  }

  return resolveCompetitionSeasonContext({
    competitionKey: match[1],
    seasonLabel: match[2],
  });
}

export function buildCompetitionSeasonBasePath(context: CompetitionSeasonContext): string {
  return `/competitions/${encodePathSegment(context.competitionKey)}/seasons/${encodeSeasonPathSegment(context.seasonLabel)}`;
}

export function buildCompetitionHubPath(competitionKey: string): string {
  if (competitionKey.trim() === WORLD_CUP_COMPETITION_KEY) {
    return buildWorldCupHubPath();
  }

  return `/competitions/${encodePathSegment(competitionKey)}`;
}

export function buildSeasonHubPath(input: CompetitionSeasonPathInput): string {
  const competitionKey = normalizeText(input.competitionKey);
  const seasonLabel = normalizeText(input.seasonLabel);

  if (!competitionKey || !seasonLabel) {
    throw new Error("competitionKey and seasonLabel are required to build the season hub path.");
  }

  if (competitionKey === WORLD_CUP_COMPETITION_KEY) {
    return buildWorldCupEditionPath(seasonLabel);
  }

  return `/competitions/${encodePathSegment(competitionKey)}/seasons/${encodeSeasonPathSegment(seasonLabel)}`;
}

export function isSeasonHubTab(value: string | null | undefined): value is SeasonHubTab {
  return typeof value === "string" && SEASON_HUB_TABS.includes(value as SeasonHubTab);
}

export function buildSeasonHubTabPath(
  input: CompetitionSeasonPathInput,
  tab: SeasonHubTab,
  filterInput: SharedFilterQueryInput = {},
): string {
  const basePath = buildSeasonHubPath(input);
  const searchParams = new URLSearchParams(
    buildFilterQueryString(filterInput, CONTEXT_QUERY_KEYS)
      .replace(/^\?/, ""),
  );

  if (tab !== "calendar") {
    searchParams.set("tab", tab);
  }

  const serialized = searchParams.toString();
  return serialized.length > 0 ? `${basePath}?${serialized}` : basePath;
}

export function buildCanonicalPlayerPath(
  context: CompetitionSeasonContext,
  playerId: string,
): string {
  return `${buildCompetitionSeasonBasePath(context)}/players/${encodePathSegment(playerId)}`;
}

export function buildCanonicalTeamPath(context: CompetitionSeasonContext, teamId: string): string {
  if (context.competitionKey === WORLD_CUP_COMPETITION_KEY) {
    return buildWorldCupTeamPath(teamId);
  }

  return `${buildCompetitionSeasonBasePath(context)}/teams/${encodePathSegment(teamId)}`;
}

export function buildContextFilterQueryString(contextInput: CompetitionSeasonContextInput): string {
  return buildFilterQueryString(contextInput);
}

export function buildFilterQueryString(
  filterInput: SharedFilterQueryInput,
  omittedContextKeys: readonly ContextQueryKey[] = [],
): string {
  const searchParams = new URLSearchParams();
  const omittedKeys = new Set(omittedContextKeys);
  const competitionId = normalizeText(filterInput.competitionId);
  const competitionKey = normalizeText(filterInput.competitionKey);
  const seasonId = normalizeText(filterInput.seasonId);
  const seasonLabel = normalizeText(filterInput.seasonLabel);
  const roundId = normalizeText(filterInput.roundId);
  const stageId = normalizeText(filterInput.stageId);
  const stageFormat = normalizeText(filterInput.stageFormat);
  const venue = normalizeText(filterInput.venue);
  const dateRangeStart = normalizeText(filterInput.dateRangeStart);
  const dateRangeEnd = normalizeText(filterInput.dateRangeEnd);

  if (competitionId && !omittedKeys.has("competitionId")) {
    searchParams.set("competitionId", competitionId);
  }

  if (competitionKey && !omittedKeys.has("competitionKey")) {
    searchParams.set("competitionKey", competitionKey);
  }

  if (seasonId && !omittedKeys.has("seasonId")) {
    searchParams.set("seasonId", seasonId);
  }

  if (seasonLabel && !omittedKeys.has("seasonLabel")) {
    searchParams.set("seasonLabel", seasonLabel);
  }

  if (roundId) {
    searchParams.set("roundId", roundId);
  }

  if (stageId) {
    searchParams.set("stageId", stageId);
  }

  if (stageFormat) {
    searchParams.set("stageFormat", stageFormat);
  }

  if (venue && venue !== "all") {
    searchParams.set("venue", venue);
  }

  if (isPositiveInteger(filterInput.lastN)) {
    searchParams.set("lastN", String(filterInput.lastN));
  } else {
    if (dateRangeStart) {
      searchParams.set("dateRangeStart", dateRangeStart);
    }

    if (dateRangeEnd) {
      searchParams.set("dateRangeEnd", dateRangeEnd);
    }
  }

  const serialized = searchParams.toString();
  return serialized.length > 0 ? `?${serialized}` : "";
}

export function appendFilterQueryString(
  pathname: string,
  filterInput: SharedFilterQueryInput,
  omittedContextKeys: readonly ContextQueryKey[] = [],
): string {
  const queryString = buildFilterQueryString(filterInput, omittedContextKeys);

  if (!queryString) {
    return pathname;
  }

  return `${pathname}${pathname.includes("?") ? `&${queryString.slice(1)}` : queryString}`;
}

export function buildPlayerResolverPath(
  playerId: string,
  contextInput: SharedFilterQueryInput = {},
): string {
  return `/players/${encodePathSegment(playerId)}${buildFilterQueryString(contextInput)}`;
}

export function buildTeamResolverPath(
  teamId: string,
  contextInput: SharedFilterQueryInput = {},
): string {
  if (normalizeText(contextInput.competitionKey) === WORLD_CUP_COMPETITION_KEY) {
    return buildWorldCupTeamPath(teamId);
  }

  return `/teams/${encodePathSegment(teamId)}${buildFilterQueryString(contextInput)}`;
}

export function buildMatchCenterPath(
  matchId: string,
  contextInput: SharedFilterQueryInput = {},
): string {
  return `/matches/${encodePathSegment(matchId)}${buildFilterQueryString(contextInput)}`;
}

export function buildPlayersPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/players${buildFilterQueryString(contextInput)}`;
}

export function buildTeamsPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/teams${buildFilterQueryString(contextInput)}`;
}

export function buildMatchesPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/matches${buildFilterQueryString(contextInput)}`;
}

export function buildRankingsHubPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/rankings${buildFilterQueryString(contextInput)}`;
}

export function buildRankingPath(
  rankingType: string,
  contextInput: SharedFilterQueryInput = {},
): string {
  return `/rankings/${encodePathSegment(rankingType)}${buildFilterQueryString(contextInput)}`;
}

export function buildHeadToHeadPath(
  input: SharedFilterQueryInput & {
    teamA?: string | null;
    teamB?: string | null;
  } = {},
): string {
  const searchParams = new URLSearchParams(buildFilterQueryString(input).replace(/^\?/, ""));
  const teamA = normalizeText(input.teamA);
  const teamB = normalizeText(input.teamB);

  if (teamA) {
    searchParams.set("teamA", teamA);
  }

  if (teamB) {
    searchParams.set("teamB", teamB);
  }

  const serialized = searchParams.toString();
  return serialized.length > 0 ? `/head-to-head?${serialized}` : "/head-to-head";
}

export function buildMarketPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/market${buildFilterQueryString(contextInput)}`;
}

export function buildCoachesPath(contextInput: SharedFilterQueryInput = {}): string {
  return `/coaches${buildFilterQueryString(contextInput)}`;
}

export function buildRetainedFilterQueryString(searchParams: Pick<URLSearchParams, "toString">): string {
  const retainedSearchParams = new URLSearchParams(searchParams.toString());

  for (const key of CONTEXT_QUERY_KEYS) {
    retainedSearchParams.delete(key);
  }

  const serialized = retainedSearchParams.toString();
  return serialized.length > 0 ? `?${serialized}` : "";
}

export function buildPassthroughSearchParamsQueryString(
  searchParams?: Record<string, string | string[] | undefined> | null,
): string {
  if (!searchParams) {
    return "";
  }

  const serializedSearchParams = new URLSearchParams();

  for (const [key, rawValue] of Object.entries(searchParams)) {
    if (Array.isArray(rawValue)) {
      for (const value of rawValue) {
        const normalizedValue = normalizeText(value);

        if (normalizedValue) {
          serializedSearchParams.append(key, normalizedValue);
        }
      }

      continue;
    }

    const normalizedValue = normalizeText(rawValue);

    if (normalizedValue) {
      serializedSearchParams.set(key, normalizedValue);
    }
  }

  const serialized = serializedSearchParams.toString();
  return serialized.length > 0 ? `?${serialized}` : "";
}

export function getContextQueryKeysToOmitForPath(pathname: string): ContextQueryKey[] {
  const normalizedPathname = normalizePathname(pathname);

  if (isWorldCupEditionPath(normalizedPathname)) {
    return ["competitionId", "seasonId"];
  }

  if (/^\/copa-do-mundo(?:\/|$)/.test(normalizedPathname)) {
    return ["competitionId"];
  }

  if (/^\/competitions\/[^/]+\/seasons\/[^/]+(?:\/|$)/.test(normalizedPathname)) {
    return ["competitionId", "seasonId"];
  }

  if (/^\/competitions\/[^/]+(?:\/|$)/.test(normalizedPathname)) {
    return ["competitionId"];
  }

  return [];
}

export function getContextQueryKeysToLockForPath(pathname: string): ContextQueryKey[] {
  const normalizedPathname = normalizePathname(pathname);

  if (/^\/matches\/[^/]+(?:\/|$)/.test(normalizedPathname)) {
    return ["competitionId", "seasonId"];
  }

  if (isWorldCupEditionPath(normalizedPathname)) {
    return ["seasonId"];
  }

  if (/^\/competitions\/[^/]+\/seasons\/[^/]+(?:\/|$)/.test(normalizedPathname)) {
    return ["seasonId"];
  }

  return [];
}
