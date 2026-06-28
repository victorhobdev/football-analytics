export type AnalyticsTab = "overview" | "trends" | "olap" | "comparisons" | "superlatives" | "coverage";

export type AnalyticsComparisonType =
  | "team_vs_team"
  | "season_vs_season"
  | "home_vs_away"
  | "period_vs_period";

export type AnalyticsSuperlativeCategory =
  | "most_goals_match"
  | "biggest_win"
  | "best_attack"
  | "best_defense"
  | "best_goal_diff"
  | "most_goals_round"
  | "highest_avg_goals_round"
  | "best_team_ppg"
  | "coach_best_ppm"
  | "coach_most_matches";

export interface AnalyticsOverviewScope {
  competitionId: string | null;
  competitionLabel: string | null;
  seasonId: string | null;
  seasonLabel: string | null;
}

export interface AnalyticsOverviewSummary {
  totalMatches: number;
  totalGoals: number;
  avgGoalsPerMatch: number | null;
  totalTeams: number;
  totalCoaches: number | null;
  totalPlayers: number | null;
  homeWins: number;
  awayWins: number;
  draws: number;
  homeWinRate: number | null;
  awayWinRate: number | null;
  drawRate: number | null;
}

export interface AnalyticsTopScorerTeam {
  teamId: string;
  teamName: string;
  goalsFor: number;
}

export interface AnalyticsBestDefenseTeam {
  teamId: string;
  teamName: string;
  goalsAgainst: number;
}

export interface AnalyticsBestPpmCoach {
  coachId: string;
  coachName: string;
  pointsPerMatch: number | null;
  matches: number;
  coverageStatus: string | null;
}

export interface AnalyticsOverview {
  scope: AnalyticsOverviewScope;
  summary: AnalyticsOverviewSummary;
  topScorerTeam?: AnalyticsTopScorerTeam | null;
  bestDefenseTeam?: AnalyticsBestDefenseTeam | null;
  bestPpmCoach?: AnalyticsBestPpmCoach | null;
}

export interface TrendPoint {
  period: string;
  periodLabel: string;
  value: number;
  sampleSize: number;
}

export interface AnalyticsTrends {
  metric: string;
  periodType: string;
  series: TrendPoint[];
  trendDirection: string | null;
  minPeriodsRequired: number;
  totalPeriods: number;
}

export interface OlapRow {
  dimensionKey: string;
  dimensionLabel: string;
  value: number;
  sampleSize: number;
  matchId?: string;
  breakdown: {
    key: string;
    label: string;
    value: number;
  } | null;
}

export interface AnalyticsOlap {
  metric: string;
  dimension: string;
  grain: string;
  operation: string;
  rows: OlapRow[];
  total: number;
  drillThroughAvailable: boolean;
}

export interface ComparisonEntity {
  id: string;
  label: string;
  matches: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  avgGoalsPerMatch: number | null;
  pointsPerMatch?: number | null;
}

export interface AnalyticsComparisonDifference {
  points: number;
  goalDiff: number;
  wins: number;
  draws: number;
  losses: number;
}

export interface EntityCoverage {
  status: string;
  percentage: number | null;
  sampleSize: number;
  expectedSize: number;
  label: string | null;
}

export interface AnalyticsComparisonCoverage {
  entityA: EntityCoverage;
  entityB: EntityCoverage;
}

export interface AnalyticsComparison {
  type: string;
  entityA: ComparisonEntity;
  entityB: ComparisonEntity;
  difference?: AnalyticsComparisonDifference | null;
  coverage?: AnalyticsComparisonCoverage | null;
}

export interface SuperlativeRecord {
  position: number;
  entityId: string;
  entityLabel: string;
  value: number;
  scope: string;
  sampleSize: number;
  tiebreaker: string | null;
}

export interface AnalyticsSuperlatives {
  category: string;
  limit: number;
  records: SuperlativeRecord[];
  categoryLabel?: string | null;
}

export interface CoverageMetric {
  count: number;
  percentage: number | null;
  status: string;
}

export interface AnalyticsCoverageScope {
  competitionId: string | null;
  seasonId: string | null;
}

export interface AnalyticsHiddenMetric {
  metric: string;
  reason: string;
}

export interface AnalyticsCoverage {
  scope: AnalyticsCoverageScope;
  totalMatches: number;
  metrics: Record<string, CoverageMetric>;
  hiddenMetrics: AnalyticsHiddenMetric[];
  enabledMetrics: string[];
}

export interface AnalyticsFilters {
  competitionId?: string | null;
  seasonId?: string | null;
  roundId?: string | null;
  stageId?: string | null;
  teamId?: string | null;
  coachId?: string | null;
  venue?: string | null;
  lastN?: number | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
}

export interface TrendsFilters extends AnalyticsFilters {
  metric: string;
  periodType: "round" | "month";
  entityId?: string;
}

export interface OlapFilters extends AnalyticsFilters {
  metric: string;
  dimension: string;
  grain: string;
  operation?: string;
  breakdown?: string;
}

export interface ComparisonFilters extends AnalyticsFilters {
  type: AnalyticsComparisonType;
  entityA: string;
  entityB: string;
}

export interface SuperlativeFilters extends AnalyticsFilters {
  category?: AnalyticsSuperlativeCategory;
  limit?: number;
}
