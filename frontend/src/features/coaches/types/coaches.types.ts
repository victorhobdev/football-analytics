import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";
import type { VenueFilter } from "@/shared/types/filters.types";

export type CoachesListSortBy =
  | "coachName"
  | "teamName"
  | "matches"
  | "adjustedPpm"
  | "pointsPerMatch"
  | "wins"
  | "startDate";

export type CoachesListSortDirection = "asc" | "desc";

export interface CoachesGlobalFilters {
  competitionId?: string | null;
  seasonId?: string | null;
  roundId?: string | null;
  stageId?: string | null;
  stageFormat?: string | null;
  venue?: VenueFilter;
  lastN?: number | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
}

export interface CoachesListLocalFilters {
  search?: string;
  minMatches?: number | null;
  includeUnknown?: boolean;
  page?: number;
  pageSize?: number;
  sortBy?: CoachesListSortBy;
  sortDirection?: CoachesListSortDirection;
}

export type CoachesListFilters = CoachesGlobalFilters & CoachesListLocalFilters;

export interface CoachListItem {
  coachId: string;
  coachName: string;
  photoUrl?: string | null;
  hasRealPhoto: boolean;
  teamId?: string | null;
  teamName?: string | null;
  active: boolean;
  temporary: boolean;
  tenureCount: number;
  activeTenures: number;
  matches: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  adjustedPpm?: number | null;
  pointsPerMatch?: number | null;
  lastMatchDate?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  context?: CompetitionSeasonContext | null;
}

export interface CoachesListData {
  items: CoachListItem[];
}

export type CoachProfileFilters = CoachesGlobalFilters;

export type CoachProfileLocalFilters = Record<string, never>;

export interface CoachTenure {
  coachTenureId: string;
  teamId?: string | null;
  teamName?: string | null;
  active: boolean;
  temporary: boolean;
  startDate?: string | null;
  endDate?: string | null;
  matches: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  pointsPerMatch?: number | null;
  lastMatchDate?: string | null;
  context?: CompetitionSeasonContext | null;
}

export interface CoachProfileSectionCoverage {
  overview: CoverageState;
  tenures: CoverageState;
}

export interface CoachProfileCoach {
  coachId: string;
  coachName: string;
  photoUrl?: string | null;
  hasRealPhoto: boolean;
  teamId?: string | null;
  teamName?: string | null;
  active: boolean;
  temporary: boolean;
  startDate?: string | null;
  endDate?: string | null;
  lastMatchDate?: string | null;
}

export interface CoachProfileSummary {
  tenureCount: number;
  activeTenures: number;
  teamsCount: number;
  matches: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  adjustedPpm?: number | null;
  pointsPerMatch?: number | null;
}

export interface CoachProfile {
  coach: CoachProfileCoach;
  summary: CoachProfileSummary;
  tenures: CoachTenure[];
  sectionCoverage: CoachProfileSectionCoverage;
}
