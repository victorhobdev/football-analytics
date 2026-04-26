import type { VenueFilter } from "@/shared/types/filters.types";

export type MarketTransfersSortBy = "transferDate" | "playerName" | "amount";

export type MarketTransfersSortDirection = "asc" | "desc";

export type MarketTeamDirection = "all" | "arrivals" | "departures";

export type MarketTransferMovementKind =
  | "permanent_transfer"
  | "loan_out"
  | "loan_return"
  | "free_transfer"
  | "contract_end"
  | "career_end"
  | "unknown";

export interface MarketGlobalFilters {
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

export interface MarketTransfersLocalFilters {
  search?: string;
  clubSearch?: string;
  teamDirection?: MarketTeamDirection;
  typeId?: number | null;
  hasAmount?: boolean;
  minAmount?: number;
  maxAmount?: number;
  page?: number;
  pageSize?: number;
  sortBy?: MarketTransfersSortBy;
  sortDirection?: MarketTransfersSortDirection;
}

export type MarketTransfersFilters = MarketGlobalFilters & MarketTransfersLocalFilters;

export interface MarketTransferItem {
  transferId: string;
  playerId?: string | null;
  playerName: string;
  fromTeamId?: string | null;
  fromTeamName?: string | null;
  toTeamId?: string | null;
  toTeamName?: string | null;
  transferDate?: string | null;
  completed: boolean;
  careerEnded: boolean;
  typeId?: number | null;
  typeName?: string | null;
  movementKind?: MarketTransferMovementKind | null;
  amount?: string | null;
  amountValue?: number | null;
  currency?: string | null;
}

export interface MarketTransfersData {
  items: MarketTransferItem[];
}
