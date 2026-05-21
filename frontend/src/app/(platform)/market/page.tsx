import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { buildPassthroughSearchParamsQueryString } from "@/shared/utils/context-routing";

type MarketPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function MarketPage({ searchParams }: MarketPageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const queryString = buildPassthroughSearchParamsQueryString(resolvedSearchParams);

  return (
    <PlatformStateSurface
      actionHref={`/players${queryString}`}
      actionLabel="Abrir jogadores"
      description="A trilha de transferências ainda não tem contrato público estável neste produto."
      detail={
        <p>
          Use jogadores, times, rankings e partidas para continuar a exploração no mesmo recorte
          competitivo.
        </p>
      }
      kicker="Mercado"
      secondaryAction={
        <Link
          className="button-pill button-pill-secondary"
          href={`/competitions${queryString}`}
        >
          Abrir competições
        </Link>
      }
      title="Mercado indisponível"
      tone="warning"
    />
  );
}
