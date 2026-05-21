import type { VenueFilter } from "@/shared/types/filters.types";
import type { CoverageState } from "@/shared/types/coverage.types";

export type MatchesListSortBy = "kickoffAt" | "status" | "homeTeamName" | "awayTeamName";
export type MatchesListSortDirection = "asc" | "desc";
export type MatchStageFormat =
  | "league_table"
  | "group_table"
  | "knockout"
  | "qualification_knockout"
  | "placement_match"
  | null
  | undefined;

export interface MatchListItem {
  matchId: string;
  fixtureId?: string | null;
  competitionId?: string | null;
  competitionKey?: string | null;
  competitionName?: string | null;
  competitionType?: string | null;
  seasonId?: string | null;
  seasonLabel?: string | null;
  roundId?: string | null;
  roundName?: string | null;
  stageId?: string | null;
  stageName?: string | null;
  stageFormat?: MatchStageFormat;
  groupId?: string | null;
  groupName?: string | null;
  tieId?: string | null;
  tieOrder?: number | null;
  tieMatchCount?: number | null;
  legNumber?: number | null;
  isKnockout?: boolean | null;
  kickoffAt?: string | null;
  status?: string | null;
  venueName?: string | null;
  homeTeamId?: string | null;
  homeTeamName?: string | null;
  awayTeamId?: string | null;
  awayTeamName?: string | null;
  homeScore?: number | null;
  awayScore?: number | null;
}

export interface MatchTimelineEvent {
  eventId?: string | null;
  minute?: number | null;
  second?: number | null;
  period?: string | null;
  type?: string | null;
  detail?: string | null;
  teamId?: string | null;
  teamName?: string | null;
  playerId?: string | null;
  playerName?: string | null;
}

export interface MatchLineupPlayer {
  playerId?: string | null;
  playerName?: string | null;
  teamId?: string | null;
  teamName?: string | null;
  position?: string | null;
  formationField?: string | null;
  formationPosition?: number | null;
  shirtNumber?: number | null;
  isStarter?: boolean | null;
  minutesPlayed?: number | null;
}

export interface MatchPlayerStat {
  playerId?: string | null;
  playerName?: string | null;
  teamId?: string | null;
  teamName?: string | null;
  positionName?: string | null;
  isStarter?: boolean | null;
  minutesPlayed?: number | null;
  goals?: number | null;
  assists?: number | null;
  shotsTotal?: number | null;
  shotsOnGoal?: number | null;
  passesTotal?: number | null;
  keyPasses?: number | null;
  tackles?: number | null;
  interceptions?: number | null;
  duels?: number | null;
  foulsCommitted?: number | null;
  yellowCards?: number | null;
  redCards?: number | null;
  goalkeeperSaves?: number | null;
  cleanSheets?: number | null;
  xg?: number | null;
  rating?: number | null;
}

export interface MatchTeamStat {
  teamId?: string | null;
  teamName?: string | null;
  totalShots?: number | null;
  shotsOnGoal?: number | null;
  possessionPct?: number | null;
  totalPasses?: number | null;
  passesAccurate?: number | null;
  passAccuracyPct?: number | null;
  corners?: number | null;
  fouls?: number | null;
  yellowCards?: number | null;
  redCards?: number | null;
  goalkeeperSaves?: number | null;
}

export interface MatchCenterSectionCoverage {
  timeline?: CoverageState;
  lineups?: CoverageState;
  teamStats?: CoverageState;
  playerStats?: CoverageState;
}

export interface MatchCenterData {
  match: MatchListItem;
  timeline?: MatchTimelineEvent[];
  lineups?: MatchLineupPlayer[];
  teamStats?: MatchTeamStat[];
  playerStats?: MatchPlayerStat[];
  sectionCoverage?: MatchCenterSectionCoverage;
}

export interface MatchesListData {
  items: MatchListItem[];
}

export interface MatchesGlobalFilters {
  competitionId?: string | null;
  seasonId?: string | null;
  roundId?: string | null;
  venue?: VenueFilter;
  lastN?: number | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
}

export interface MatchesListLocalFilters {
  search?: string;
  status?: string | null;
  teamId?: string | null;
  allPages?: boolean;
  enabled?: boolean;
  page?: number;
  pageSize?: number;
  sortBy?: MatchesListSortBy;
  sortDirection?: MatchesListSortDirection;
}

export interface MatchCenterLocalFilters {
  includeTimeline?: boolean;
  includeLineups?: boolean;
  includeTeamStats?: boolean;
  includePlayerStats?: boolean;
}

export type MatchesListFilters = MatchesGlobalFilters & MatchesListLocalFilters;
export type MatchCenterFilters = MatchesGlobalFilters & MatchCenterLocalFilters;
