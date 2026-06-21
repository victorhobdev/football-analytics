import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import type { CoverageState } from "@/shared/types/coverage.types";

export interface HomeArchiveSummary {
  competitions: number;
  seasons: number;
  matches: number;
  players: number;
  matchesWithOdds?: number;
  matchesWithTeamStats?: number;
  teamStatRows?: number;
  marketTransfers?: number;
  marketValuations?: number;
}

export interface HomeCompetitionRange {
  fromSeasonId: string | null;
  fromSeasonLabel: string | null;
  toSeasonId: string | null;
  toSeasonLabel: string | null;
}

export interface HomeCompetitionCard {
  competitionId: string;
  competitionKey: string;
  competitionName: string;
  assetId: string | null;
  source?: "published" | "transfermarkt" | "eloratings" | "brasileirao" | "multi" | null;
  dominantSource?: "published" | "transfermarkt" | "eloratings" | "brasileirao" | null;
  additionalSources?: Array<"published" | "transfermarkt" | "eloratings" | "brasileirao">;
  country?: string | null;
  region?: string | null;
  scope?: "domestic" | "continental" | "global" | null;
  type?: "domestic_league" | "domestic_cup" | "international_cup" | null;
  matchesCount: number;
  seasonsCount: number;
  range: HomeCompetitionRange;
  latestContext: CompetitionSeasonContext | null;
  coverage: CoverageState;
}

export interface HomeEditorialMetrics {
  matchesPlayed: number;
  goals: number;
  assists: number;
  rating: number | null;
}

export interface HomeEditorialHighlight {
  id: string;
  eyebrow: string;
  competitionLabel: string;
  title: string;
  description: string;
  playerId: string;
  playerName: string;
  teamId: string | null;
  teamName: string | null;
  imageAssetId: string | null;
  context: CompetitionSeasonContext;
  metrics: HomeEditorialMetrics;
}

export interface HomePageData {
  archiveSummary: HomeArchiveSummary;
  competitions: HomeCompetitionCard[];
  editorialHighlights: HomeEditorialHighlight[];
}
