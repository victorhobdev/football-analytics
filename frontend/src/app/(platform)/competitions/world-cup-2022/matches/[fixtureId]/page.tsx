import { ApiClientError } from "@/shared/services/api-client";
import { WorldCup2022ErrorState, WorldCup2022MatchView } from "@/features/world-cup-2022/components/WorldCup2022Views";
import { fetchWorldCup2022MatchView } from "@/features/world-cup-2022/services/world-cup-2022.service";

type WorldCup2022MatchPageProps = {
  params: Promise<{ fixtureId: string }>;
};

export default async function WorldCup2022MatchPage({ params }: WorldCup2022MatchPageProps) {
  const { fixtureId } = await params;

  try {
    const response = await fetchWorldCup2022MatchView(fixtureId);
    return <WorldCup2022MatchView data={response.data} meta={response.meta} />;
  } catch (error) {
    if (error instanceof ApiClientError) {
      return (
        <WorldCup2022ErrorState
          description={error.message}
          title={error.status === 404 ? "Partida da Copa indisponível" : "Falha ao carregar a partida"}
        />
      );
    }

    return (
      <WorldCup2022ErrorState
        description="Não foi possível carregar a visão da partida da Copa 2022 agora."
        title="Falha ao carregar a partida"
      />
    );
  }
}
