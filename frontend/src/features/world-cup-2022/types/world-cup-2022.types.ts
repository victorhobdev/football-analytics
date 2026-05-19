import type { CoverageState } from "@/shared/types/coverage.types";

export type WorldCup2022CompetitionContext = {
  provider: string;
  competitionKey: string;
  competitionName: string;
  seasonLabel: string;
  seasonName: string;
  editionKey: string;
};

export type WorldCup2022Fixture = {
  fixtureId: string;
  kickoffAt: string | null;
  statusShort: string | null;
  statusLong: string | null;
  stageName: string | null;
  groupName: string | null;
  roundName: string | null;
  venueName: string | null;
  venueCity: string | null;
  referee: string | null;
  homeTeamId: string;
  homeTeamName: string | null;
  awayTeamId: string;
  awayTeamName: string | null;
  homeGoals: number | null;
  awayGoals: number | null;
  sourceProvider: string | null;
};

export type WorldCup2022StandingRow = {
  teamId: string;
  teamName: string | null;
  teamCode: string | null;
  position: number;
  points: number;
  matchesPlayed: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  advanced: boolean;
};

export type WorldCup2022StandingGroup = {
  groupKey: string;
  groupName: string;
  stageKey: string | null;
  rows: WorldCup2022StandingRow[];
};

export type WorldCup2022CompetitionHubData = {
  competition: WorldCup2022CompetitionContext;
  fixtures: WorldCup2022Fixture[];
  standings: {
    groupCount: number;
    rowCount: number;
    groups: WorldCup2022StandingGroup[];
  };
};

export type WorldCup2022LineupPlayer = {
  lineupId: string;
  playerId: string;
  playerInternalId: string | null;
  playerName: string | null;
  playerNickname: string | null;
  positionName: string | null;
  formationField: string | null;
  formationPosition: number | null;
  jerseyNumber: number | null;
  details: unknown;
  sourceName: string | null;
  sourceVersion: string | null;
};

export type WorldCup2022TeamLineup = {
  teamId: string;
  teamName: string | null;
  starters: WorldCup2022LineupPlayer[];
  bench: WorldCup2022LineupPlayer[];
};

export type WorldCup2022MatchEvent = {
  fixtureId: string;
  internalMatchId: string | null;
  sourceName: string | null;
  sourceVersion: string | null;
  sourceMatchId: string | null;
  sourceEventId: string | null;
  eventIndex: number | null;
  eventType: string | null;
  period: number | null;
  minute: number | null;
  second: number | null;
  location: {
    x: number | null;
    y: number | null;
  };
  outcomeLabel: string | null;
  playPatternLabel: string | null;
  isThreeSixtyBacked: boolean;
  team: {
    teamInternalId: string | null;
    teamName: string | null;
  };
  player: {
    playerInternalId: string | null;
    playerName: string | null;
  };
  payload: unknown;
};

export type WorldCup2022MatchViewData = {
  competition: WorldCup2022CompetitionContext;
  fixture: WorldCup2022Fixture;
  lineups: WorldCup2022TeamLineup[];
  events: WorldCup2022MatchEvent[];
  sectionCoverage: {
    lineups: CoverageState;
    events: CoverageState;
  };
};

export type WorldCup2022TeamCoach = {
  coachTenureId: string;
  coachSourceScopedId: string | null;
  fullName: string | null;
  givenName: string | null;
  familyName: string | null;
  countryName: string | null;
  identityScope: string | null;
  tenureScope: string | null;
  sourceName: string | null;
  sourceVersion: string | null;
};

export type WorldCup2022Team = {
  teamId: string;
  teamName: string | null;
  matchesPlayed: number;
};

export type WorldCup2022TeamFixture = WorldCup2022Fixture & {
  venueRole: string | null;
  opponentTeamId: string;
  opponentTeamName: string | null;
};

export type WorldCup2022TeamViewData = {
  competition: WorldCup2022CompetitionContext;
  team: WorldCup2022Team;
  coach: WorldCup2022TeamCoach | null;
  fixtures: WorldCup2022TeamFixture[];
  sectionCoverage: {
    coach: CoverageState;
    fixtures: CoverageState;
  };
};
