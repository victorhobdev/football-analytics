export type CompetitionStageFormat =
  | "league_table"
  | "group_table"
  | "knockout"
  | "qualification_knockout"
  | "placement_match"
  | null
  | undefined;

export interface CompetitionStructureCompetitionScope {
  competitionId?: string | null;
  competitionKey: string;
  competitionName: string;
  seasonId?: string | null;
  seasonLabel: string;
  providerSeasonId?: string | null;
  formatFamily: string;
  seasonFormatCode: string;
  participantScope: string;
  groupRankingRuleCode?: string | null;
  tieRuleCode?: string | null;
}

export interface CompetitionStructureGroup {
  groupId: string;
  groupName?: string | null;
  groupOrder?: number | null;
  expectedTeams?: number | null;
}

export interface CompetitionStructureTransition {
  progressionScope?: string | null;
  progressionType?: string | null;
  positionFrom?: number | null;
  positionTo?: number | null;
  tieOutcome?: string | null;
  toStageId?: string | null;
  toStageName?: string | null;
  toStageFormat?: CompetitionStageFormat;
  toStageOrder?: number | null;
}

export interface CompetitionStructureStage {
  stageId: string;
  stageName?: string | null;
  stageCode?: string | null;
  stageFormat?: CompetitionStageFormat;
  stageOrder?: number | null;
  standingsContextMode?: string | null;
  bracketContextMode?: string | null;
  groupMode?: string | null;
  eliminationMode?: string | null;
  isCurrent: boolean;
  expectedTeams?: number | null;
  groups: CompetitionStructureGroup[];
  transitions: CompetitionStructureTransition[];
}

export interface CompetitionStructureData {
  competition: CompetitionStructureCompetitionScope;
  stages: CompetitionStructureStage[];
  updatedAt?: string | null;
}

export interface CompetitionStructureFilters {
  competitionKey?: string | null;
  seasonLabel?: string | null;
}

export type HistoricalStatEntityType = "team" | "player" | "match";

export interface CompetitionHistoricalStatItem {
  statCode: string;
  label: string;
  entityType: HistoricalStatEntityType;
  entityId?: string | null;
  entityName: string;
  value?: number | string | null;
  valueLabel?: string | null;
  rank?: number | null;
  seasonLabel?: string | null;
  occurredOn?: string | null;
  sourceUrl?: string | null;
  metadata: Record<string, unknown>;
}

export interface CompetitionHistoricalStatGroup {
  items: CompetitionHistoricalStatItem[];
  source: string;
  asOfYear: number;
}

export interface CompetitionHistoricalStatsData {
  champions: CompetitionHistoricalStatGroup;
  scorers: CompetitionHistoricalStatGroup;
  updatedAt?: string | null;
}

export interface CompetitionHistoricalStatsFilters {
  competitionKey?: string | null;
  asOfYear?: number | null;
}

export interface StageTie {
  tieId: string;
  tieOrder: number;
  homeTeamId?: string | null;
  homeTeamName?: string | null;
  awayTeamId?: string | null;
  awayTeamName?: string | null;
  matchCount: number;
  firstLegAt?: string | null;
  lastLegAt?: string | null;
  homeGoals: number;
  awayGoals: number;
  winnerTeamId?: string | null;
  winnerTeamName?: string | null;
  resolutionType?: string | null;
  hasExtraTimeMatch: boolean;
  hasPenaltiesMatch: boolean;
  nextStageId?: string | null;
  nextStageName?: string | null;
}

export interface StageTiesData {
  competition: CompetitionStructureCompetitionScope;
  stage: Omit<CompetitionStructureStage, "groups" | "transitions">;
  ties: StageTie[];
  updatedAt?: string | null;
}

export interface StageTiesFilters {
  competitionKey?: string | null;
  seasonLabel?: string | null;
  stageId?: string | null;
}

export interface CompetitionAnalyticsSeasonSummary {
  matchCount: number;
  totalStages: number;
  tableStages: number;
  knockoutStages: number;
  groupCount: number;
  tieCount: number;
  averageGoals?: number | null;
}

export interface CompetitionStageAnalyticsRow {
  stageId: string;
  stageName?: string | null;
  stageCode?: string | null;
  stageFormat?: CompetitionStageFormat;
  stageOrder?: number | null;
  isCurrent: boolean;
  matchCount: number;
  teamCount: number;
  groupCount: number;
  averageGoals?: number | null;
  homeWins: number;
  draws: number;
  awayWins: number;
  tieCount: number;
  resolvedTies: number;
  inferredTies: number;
}

export interface CompetitionSeasonComparisonRow {
  seasonLabel: string;
  formatFamily?: string | null;
  seasonFormatCode?: string | null;
  participantScope?: string | null;
  matchCount: number;
  stageCount: number;
  tableStageCount: number;
  knockoutStageCount: number;
  groupCount: number;
  tieCount: number;
  averageGoals?: number | null;
}

export interface CompetitionAnalyticsData {
  competition: CompetitionStructureCompetitionScope;
  seasonSummary: CompetitionAnalyticsSeasonSummary;
  stageAnalytics: CompetitionStageAnalyticsRow[];
  seasonComparisons: CompetitionSeasonComparisonRow[];
  updatedAt?: string | null;
}

export interface CompetitionAnalyticsFilters {
  competitionKey?: string | null;
  seasonLabel?: string | null;
}

export interface TeamJourneyStage {
  stageId: string;
  stageName?: string | null;
  stageFormat?: CompetitionStageFormat;
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

export interface TeamJourneyHistoryFilters {
  competitionKey?: string | null;
  teamId?: string | null;
}
