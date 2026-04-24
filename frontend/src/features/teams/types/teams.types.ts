import type { VenueFilter } from "@/shared/types/filters.types";
import type { CoverageState } from "@/shared/types/coverage.types";

export interface Team {
  teamId: string;
  teamName: string;
  competitionId?: string | null;
  competitionName?: string | null;
  seasonId?: string | null;
  seasonLabel?: string | null;
}

export interface TeamListItem extends Team {
  position?: number | null;
  totalTeams?: number | null;
  matchesPlayed?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  goalsFor?: number | null;
  goalsAgainst?: number | null;
  goalDiff?: number | null;
  points?: number | null;
}

export interface TeamStatsSummary {
  matchesPlayed?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  goalsFor?: number | null;
  goalsAgainst?: number | null;
  goalDiff?: number | null;
  points?: number | null;
}

export interface TeamStandingSnapshot {
  position?: number | null;
  totalTeams?: number | null;
}

export type TeamFormResult = "win" | "draw" | "loss";

export interface TeamRecentMatch {
  matchId: string;
  playedAt?: string | null;
  opponentTeamId?: string | null;
  opponentName?: string | null;
  venue?: "home" | "away" | null;
  goalsFor?: number | null;
  goalsAgainst?: number | null;
  result?: TeamFormResult | null;
}

export interface TeamSquadPlayer {
  playerId?: string | null;
  playerName?: string | null;
  positionName?: string | null;
  shirtNumber?: number | null;
  appearances?: number | null;
  starts?: number | null;
  minutesPlayed?: number | null;
  averageMinutes?: number | null;
  lastAppearanceAt?: string | null;
}

export interface TeamStatsTrendPoint {
  periodKey?: string | null;
  label?: string | null;
  matches?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  goalsFor?: number | null;
  goalsAgainst?: number | null;
  goalDiff?: number | null;
  points?: number | null;
}

export interface TeamProfileStats {
  pointsPerMatch?: number | null;
  winRatePct?: number | null;
  goalsForPerMatch?: number | null;
  goalsAgainstPerMatch?: number | null;
  cleanSheets?: number | null;
  failedToScore?: number | null;
  trend?: TeamStatsTrendPoint[];
}

export interface TeamJourneyStage {
  stageId: string;
  stageName?: string | null;
  stageFormat?: string | null;
  stageOrder?: number | null;
  matchesPlayed: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  progressionType?: string | null;
  tieOutcome?: string | null;
  sourcePosition?: number | null;
  groupId?: string | null;
  groupName?: string | null;
  tieCount: number;
  tiesWon: number;
  tiesLost: number;
  stageResult: string;
}

export interface TeamJourneySeason {
  seasonLabel: string;
  formatFamily?: string | null;
  seasonFormatCode?: string | null;
  summary: {
    matchesPlayed: number;
    wins: number;
    draws: number;
    losses: number;
    goalsFor: number;
    goalsAgainst: number;
    finalOutcome: string;
  };
  stages: TeamJourneyStage[];
}

export interface TeamJourneyHistoryData {
  competition: {
    competitionKey: string;
    competitionName: string;
  };
  team: {
    teamId: string;
    teamName: string;
  };
  seasons: TeamJourneySeason[];
  updatedAt?: string | null;
}

export interface TeamProfileSectionCoverage {
  overview?: CoverageState;
  squad?: CoverageState;
  stats?: CoverageState;
}

export interface TeamMatchListItem {
  matchId: string;
  fixtureId?: string | null;
  competitionId?: string | null;
  competitionName?: string | null;
  seasonId?: string | null;
  roundId?: string | null;
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

export interface TeamProfile {
  team: Team;
  summary: TeamStatsSummary;
  standing?: TeamStandingSnapshot | null;
  form?: TeamFormResult[];
  recentMatches?: TeamRecentMatch[];
  squad?: TeamSquadPlayer[];
  stats?: TeamProfileStats | null;
  sectionCoverage?: TeamProfileSectionCoverage;
}

export type TeamHonorScope = "mundial" | "continental" | "nacional" | "estadual";

export interface TeamHonorItem {
  label: string;
  count: number;
}

export interface TeamHonorScopeSummary {
  scope: TeamHonorScope;
  label: string;
  total: number;
  items: TeamHonorItem[];
}

export interface TeamHonorsPreview {
  teamSlug: string;
  teamName: string;
  criterionLabel: string;
  scopes: TeamHonorScopeSummary[];
}

export interface TeamsListData {
  items: TeamListItem[];
}

export interface TeamMatchesListData {
  items: TeamMatchListItem[];
}

export interface TeamsGlobalFilters {
  competitionId?: string | null;
  seasonId?: string | null;
  roundId?: string | null;
  venue?: VenueFilter;
  lastN?: number | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
}

export type TeamsListSortBy = "teamName" | "points" | "goalDiff" | "wins" | "position";
export type TeamsListSortDirection = "asc" | "desc";
export type TeamMatchesListSortBy = "kickoffAt" | "status" | "homeTeamName" | "awayTeamName";
export type TeamMatchesListSortDirection = "asc" | "desc";

export interface TeamsListLocalFilters {
  search?: string;
  page?: number;
  pageSize?: number;
  sortBy?: TeamsListSortBy;
  sortDirection?: TeamsListSortDirection;
}

export interface TeamProfileLocalFilters {
  includeRecentMatches?: boolean;
  includeSquad?: boolean;
  includeStats?: boolean;
}

export interface TeamJourneyHistoryFilters {
  competitionKey?: string | null;
  teamId?: string | null;
}

export interface TeamMatchesListLocalFilters {
  search?: string;
  status?: string | null;
  page?: number;
  pageSize?: number;
  sortBy?: TeamMatchesListSortBy;
  sortDirection?: TeamMatchesListSortDirection;
}

export type TeamsListFilters = TeamsGlobalFilters & TeamsListLocalFilters;
export type TeamProfileFilters = TeamsGlobalFilters & TeamProfileLocalFilters;
export type TeamMatchesListFilters = TeamsGlobalFilters &
  TeamMatchesListLocalFilters & {
    teamId?: string | null;
  };
