import type { RankingDefinition, RankingSortDirection } from "@/config/ranking.types";
import type { VenueFilter } from "@/shared/types/filters.types";

export interface RankingTableRow extends Record<string, string | number | boolean | null | undefined> {
  entityId: string;
  entityName?: string | null;
  rank?: number | null;
  metricValue?: number | null;
  metricPer90?: number | null;
  matchesPlayed?: number | null;
  minutesPlayed?: number | null;
  teamId?: string | null;
  teamName?: string | null;
  teamCount?: number | null;
  teamContextLabel?: string | null;
}

export interface RankingStageContext {
  stageId: string;
  stageName?: string | null;
  stageFormat?: string | null;
  stageFormatLabel?: string | null;
}

export interface RankingScopeVenue {
  value: VenueFilter;
  label: string;
}

export interface RankingScopeWindow {
  kind: "all" | "round" | "lastN" | "dateRange";
  label: string;
  appliesPerEntity: boolean;
  roundId?: string | null;
  lastN?: number | null;
  dateStart?: string | null;
  dateEnd?: string | null;
}

export interface RankingScopeSample {
  field?: string | null;
  label: string;
  unit?: string | null;
  unitLabel?: string | null;
  defaultValue?: number | null;
  appliedValue?: number | null;
  isDefault: boolean;
}

export interface RankingScopeContext {
  kind: "catalog" | "competition" | "season" | "competitionSeason";
  label: string;
  competitionId?: string | null;
  competitionName?: string | null;
  seasonId?: string | null;
  seasonLabel?: string | null;
  venue: RankingScopeVenue;
  window: RankingScopeWindow;
  sample?: RankingScopeSample | null;
  stage?: RankingStageContext | null;
}

export interface RankingSortMeta {
  direction: RankingSortDirection;
  label: string;
  serverSide: boolean;
}

export interface RankingTableData {
  rankingId: string;
  metricKey: string;
  entity?: string | null;
  scope: RankingScopeContext;
  rows: RankingTableRow[];
  updatedAt?: string | null;
  sort?: RankingSortMeta | null;
  freshnessClass?: RankingFreshnessClass;
}

export interface RankingsGlobalFilters {
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

export type RankingFreshnessClass = "season" | "fast";

export interface RankingLocalFilters {
  search?: string;
  page?: number;
  pageSize?: number;
  sortDirection?: RankingSortDirection;
  minSampleValue?: number | null;
  stageId?: string | null;
  stageFormat?: string | null;
  freshnessClass?: RankingFreshnessClass;
}

export type RankingQueryFilters = RankingsGlobalFilters & RankingLocalFilters;

export interface RankingCacheProfile {
  staleTimeMs: number;
  gcTimeMs: number;
  freshnessClass: RankingFreshnessClass;
}

export interface UseRankingTableOptions {
  localFilters?: RankingLocalFilters;
  enabled?: boolean;
}

export interface RankingFetchInput {
  rankingDefinition: RankingDefinition;
  filters?: RankingQueryFilters;
}
