import type { CoverageState } from "@/shared/types/coverage.types";

type PartialDataBannerProps = {
  coverage: CoverageState;
  message?: string;
  className?: string;
};

export function PartialDataBanner({
  coverage: _coverage,
  message: _message,
  className: _className,
}: PartialDataBannerProps) {
  return null;
}
