export type CoverageStatus = "complete" | "partial" | "insufficient" | "not_available" | "empty" | "unknown";

export interface CoverageState {
  status: CoverageStatus;
  percentage?: number;
  label?: string;
}
