import type { CoverageState } from "@/shared/types/coverage.types";

export interface WorldCupTeamReference {
  teamId: string | null;
  teamName: string | null;
}

export interface WorldCupHistoricalTopScorer {
  playerId: string | null;
  playerName: string | null;
  teamId: string | null;
  teamName: string | null;
  goals: number;
}

export interface WorldCupHubSummary {
  editionsCount: number;
  matchesCount: number;
  distinctChampionsCount: number;
  topScorer: WorldCupHistoricalTopScorer | null;
}

export interface WorldCupHubEdition {
  seasonLabel: string;
  year: number;
  editionName: string;
  hostCountry: string | null;
  hostCountryTeam: WorldCupTeamReference | null;
  teamsCount: number | null;
  matchesCount: number;
  champion: WorldCupTeamReference | null;
  runnerUp: WorldCupTeamReference | null;
  finalVenue: string | null;
  resolutionType: string | null;
  coverage: CoverageState;
  coverageNote?: string | null;
  formatFlags: Record<string, boolean>;
}

export interface WorldCupHubData {
  summary: WorldCupHubSummary;
  editions: WorldCupHubEdition[];
  updatedAt: string;
}

export interface WorldCupEditionNavigationItem {
  seasonLabel: string;
  year: number;
  editionName: string;
}

export interface WorldCupEditionScorer {
  rank: number;
  playerId: string | null;
  playerName: string | null;
  teamId: string | null;
  teamName: string | null;
  goals: number;
}

export interface WorldCupEditionStandingRow {
  position: number;
  teamId: string | null;
  teamName: string | null;
  matchesPlayed: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  points: number;
  advanced: boolean;
}

export interface WorldCupEditionGroup {
  groupKey: string | null;
  groupLabel: string;
  rows: WorldCupEditionStandingRow[];
}

export interface WorldCupEditionGroupStage {
  stageKey: string;
  stageLabel: string;
  groups: WorldCupEditionGroup[];
}

export interface WorldCupKnockoutShootoutScore {
  home: number;
  away: number;
}

export interface WorldCupKnockoutMatch {
  fixtureId: string;
  kickoffAt: string | null;
  venueName: string | null;
  homeTeam: WorldCupTeamReference | null;
  awayTeam: WorldCupTeamReference | null;
  homeScore: number | null;
  awayScore: number | null;
  shootout: WorldCupKnockoutShootoutScore | null;
  isReplay: boolean;
}

export interface WorldCupKnockoutTie {
  tieKey: string;
  roundKey: string;
  roundLabel: string;
  winner: WorldCupTeamReference | null;
  runnerUp: WorldCupTeamReference | null;
  resolutionType: string | null;
  resolutionNote: string | null;
  matches: WorldCupKnockoutMatch[];
}

export interface WorldCupKnockoutRound {
  roundKey: string;
  roundLabel: string;
  ties: WorldCupKnockoutTie[];
}

export interface WorldCupEditionSummary extends WorldCupHubEdition {
  topScorer: WorldCupEditionScorer | null;
  coverageNotes: string[];
}

export interface WorldCupEditionData {
  edition: WorldCupEditionSummary;
  navigation: {
    previousEdition: WorldCupEditionNavigationItem | null;
    nextEdition: WorldCupEditionNavigationItem | null;
  };
  groupStages: WorldCupEditionGroupStage[];
  knockoutRounds: WorldCupKnockoutRound[];
  scorers: WorldCupEditionScorer[];
  updatedAt: string;
}

export interface WorldCupTeamListItem {
  teamId: string;
  teamName: string | null;
  participationsCount: number;
  titlesCount: number;
  bestResultLabel: string;
  firstEdition: number;
  lastEdition: number;
}

export interface WorldCupTeamsData {
  teams: WorldCupTeamListItem[];
  updatedAt: string;
}

export interface WorldCupTeamParticipationTopScorer {
  playerId: string | null;
  playerName: string | null;
  goals: number;
}

export interface WorldCupTeamParticipation {
  seasonLabel: string;
  year: number;
  editionName: string;
  matchesCount: number;
  resultLabel: string;
  resultRank: number;
  topScorer: WorldCupTeamParticipationTopScorer | null;
}

export interface WorldCupTeamHistoricalScorer {
  rank: number;
  playerId: string | null;
  playerName: string | null;
  goals: number;
}

export interface WorldCupTeamSummary {
  teamId: string;
  teamName: string | null;
  participationsCount: number;
  titlesCount: number;
  bestResultLabel: string;
  firstEdition: number;
  lastEdition: number;
}

export interface WorldCupTeamData {
  team: WorldCupTeamSummary;
  participations: WorldCupTeamParticipation[];
  historicalScorers: WorldCupTeamHistoricalScorer[];
  updatedAt: string;
}

export interface WorldCupRankingScorerEdition {
  seasonLabel: string;
  year: number;
  teamId: string | null;
  teamName: string | null;
  goals: number;
}

export interface WorldCupRankingScorer {
  rank: number;
  playerId: string | null;
  playerName: string | null;
  teamId: string | null;
  teamName: string | null;
  goals: number;
  editions: WorldCupRankingScorerEdition[];
}

export interface WorldCupRankingTeam {
  rank: number;
  teamId: string;
  teamName: string | null;
  titlesCount: number;
  participationsCount: number;
  finalsCount: number;
}

export interface WorldCupRankingBlock<TItem> {
  label: string;
  metricLabel: string;
  items: TItem[];
}

export interface WorldCupRankingTeamWinsItem {
  rank: number;
  teamId: string;
  teamName: string | null;
  wins: number;
  matches: number;
}

export interface WorldCupRankingTeamMatchesItem {
  rank: number;
  teamId: string;
  teamName: string | null;
  matches: number;
  wins: number;
}

export interface WorldCupRankingTeamGoalsItem {
  rank: number;
  teamId: string;
  teamName: string | null;
  goalsScored: number;
  matches: number;
}

export interface WorldCupRankingTeamTopFourItem {
  rank: number;
  teamId: string;
  teamName: string | null;
  topFourCount: number;
  titlesCount: number;
}

export interface WorldCupRankingEditionGoalAverageItem {
  rank: number;
  seasonLabel: string;
  year: number;
  editionName: string;
  matchesCount: number;
  goalsCount: number;
  goalsPerMatch: number;
}

export interface WorldCupRankingEditionGoalsItem {
  rank: number;
  seasonLabel: string;
  year: number;
  editionName: string;
  matchesCount: number;
  goalsCount: number;
}

export interface WorldCupRankingPlayerSquadEdition {
  seasonLabel: string;
  year: number;
}

export interface WorldCupRankingPlayerSquadAppearance {
  rank: number;
  playerId: string;
  playerName: string | null;
  teamId: string | null;
  teamName: string | null;
  appearancesCount: number;
  editions: WorldCupRankingPlayerSquadEdition[];
}

export interface WorldCupFinalItem {
  seasonLabel: string;
  year: number;
  homeTeam: WorldCupTeamReference | null;
  awayTeam: WorldCupTeamReference | null;
  homeScore: number | null;
  awayScore: number | null;
  shootout: WorldCupKnockoutShootoutScore | null;
  venueName: string | null;
  champion: WorldCupTeamReference | null;
  runnerUp: WorldCupTeamReference | null;
  resolutionType: string | null;
  resolutionNote: string | null;
}

export interface WorldCupFinalOmission {
  seasonLabel: string;
  year: number;
  reason: string;
}

export interface WorldCupRankingFinalRecord {
  rank: number;
  seasonLabel: string;
  year: number;
  homeTeam: WorldCupTeamReference | null;
  awayTeam: WorldCupTeamReference | null;
  homeScore: number;
  awayScore: number;
  shootout: WorldCupKnockoutShootoutScore | null;
  venueName: string | null;
  totalGoals: number;
}

export interface WorldCupRankingBiggestWinRecord {
  rank: number;
  fixtureId: string;
  seasonLabel: string;
  year: number;
  homeTeam: WorldCupTeamReference | null;
  awayTeam: WorldCupTeamReference | null;
  homeScore: number;
  awayScore: number;
  goalDiff: number;
  totalGoals: number;
}

export interface WorldCupRankingsData {
  scorers: WorldCupRankingScorer[];
  teams: WorldCupRankingTeam[];
  teamRankings: {
    titles: WorldCupRankingBlock<WorldCupRankingTeam>;
    wins: WorldCupRankingBlock<WorldCupRankingTeamWinsItem>;
    matches: WorldCupRankingBlock<WorldCupRankingTeamMatchesItem>;
    goalsScored: WorldCupRankingBlock<WorldCupRankingTeamGoalsItem>;
    topFourAppearances: WorldCupRankingBlock<WorldCupRankingTeamTopFourItem>;
  };
  editionRankings: {
    goalsPerMatch: WorldCupRankingBlock<WorldCupRankingEditionGoalAverageItem>;
    goals: WorldCupRankingBlock<WorldCupRankingEditionGoalsItem>;
  };
  playerRankings: {
    scorers: WorldCupRankingBlock<WorldCupRankingScorer>;
    squadAppearances: WorldCupRankingBlock<WorldCupRankingPlayerSquadAppearance> & {
      minimumAppearancesCount: number;
    };
  };
  matchRankings: {
    highestScoringFinals: WorldCupRankingBlock<WorldCupRankingFinalRecord>;
    biggestWins: WorldCupRankingBlock<WorldCupRankingBiggestWinRecord>;
  };
  finals: {
    items: WorldCupFinalItem[];
    omittedEditions: WorldCupFinalOmission[];
  };
  updatedAt: string;
}
