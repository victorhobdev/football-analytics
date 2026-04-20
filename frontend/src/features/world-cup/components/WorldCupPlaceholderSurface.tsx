import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

import { buildWorldCupHubPath } from "@/features/world-cup/routes";

type WorldCupPlaceholderSurfaceProps = {
  description: string;
  title: string;
};

export function WorldCupPlaceholderSurface({
  description,
  title,
}: WorldCupPlaceholderSurfaceProps) {
  return (
    <PlatformStateSurface
      actionHref={buildWorldCupHubPath()}
      actionLabel="Voltar ao hub"
      description={description}
      kicker="Copa do Mundo"
      title={title}
      tone="warning"
    />
  );
}
