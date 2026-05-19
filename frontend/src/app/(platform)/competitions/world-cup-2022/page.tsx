import { ApiClientError } from "@/shared/services/api-client";
import { WorldCup2022CompetitionHubView, WorldCup2022ErrorState } from "@/features/world-cup-2022/components/WorldCup2022Views";
import { fetchWorldCup2022CompetitionHub } from "@/features/world-cup-2022/services/world-cup-2022.service";

export default async function WorldCup2022CompetitionHubPage() {
  try {
    const response = await fetchWorldCup2022CompetitionHub();
    return <WorldCup2022CompetitionHubView data={response.data} meta={response.meta} />;
  } catch (error) {
    if (error instanceof ApiClientError) {
      return (
        <WorldCup2022ErrorState
          description={error.message}
          title={error.status === 404 ? "Hub da Copa indisponível" : "Falha ao carregar a Copa 2022"}
        />
      );
    }

    return (
      <WorldCup2022ErrorState
        description="Não foi possível carregar o hub inicial da Copa 2022 agora."
        title="Falha ao carregar a Copa 2022"
      />
    );
  }
}
