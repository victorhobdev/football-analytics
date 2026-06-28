import type { CoverageState, CoverageStatus } from "@/shared/types/coverage.types";

type CoverageBadgeProps = {
  coverage: CoverageState;
  className?: string;
};

const STATUS_LABEL: Record<CoverageStatus, string> = {
  complete: "Cobertura completa",
  partial: "Cobertura parcial",
  insufficient: "Cobertura insuficiente",
  not_available: "Cobertura indisponível",
  empty: "Sem dados",
  unknown: "Cobertura desconhecida",
};

const STATUS_CLASSES: Record<CoverageStatus, string> = {
  complete: "border-emerald-300 bg-emerald-50 text-emerald-700",
  partial: "border-amber-300 bg-amber-50 text-amber-700",
  insufficient: "border-rose-300 bg-rose-50 text-rose-700",
  not_available: "border-slate-300 bg-slate-50 text-slate-700",
  empty: "border-rose-300 bg-rose-50 text-rose-700",
  unknown: "border-slate-300 bg-slate-50 text-slate-700",
};

export function CoverageBadge({ coverage, className }: CoverageBadgeProps) {
  const defaultLabel = STATUS_LABEL[coverage.status];
  const percentageSuffix = typeof coverage.percentage === "number" ? ` (${coverage.percentage.toFixed(1)}%)` : "";
  const label = `${coverage.label ?? defaultLabel}${percentageSuffix}`;
  const classes = [
    "inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium",
    STATUS_CLASSES[coverage.status],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <span className={classes}>{label}</span>;
}
