import type { CoverageState } from "@/shared/types/coverage.types";
import { CoverageBadge } from "@/shared/components/coverage/CoverageBadge";

type PartialDataBannerProps = {
  coverage: CoverageState;
  message?: string;
  className?: string;
};

export function PartialDataBanner({
  coverage,
  message,
  className,
}: PartialDataBannerProps) {
  if (coverage.status === "complete") {
    return null;
  }

  const defaultMessage =
    coverage.status === "not_available"
      ? "Não há dados suficientes para este recorte."
      : coverage.status === "insufficient"
        ? "A amostra deste recorte é insuficiente para algumas análises."
        : "Parte dos dados deste recorte tem cobertura parcial.";

  return (
    <section
      className={[
        "flex flex-col gap-3 rounded-[1.1rem] border border-[rgba(191,201,195,0.46)] bg-white/78 px-4 py-3 text-sm text-[#404944] sm:flex-row sm:items-center sm:justify-between",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <p>{message ?? defaultMessage}</p>
      <CoverageBadge coverage={coverage} />
    </section>
  );
}
