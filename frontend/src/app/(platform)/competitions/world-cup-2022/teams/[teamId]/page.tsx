import { ApiClientError } from "@/shared/services/api-client";
import { WorldCup2022ErrorState, WorldCup2022TeamView } from "@/features/world-cup-2022/components/WorldCup2022Views";
import { fetchWorldCup2022TeamView } from "@/features/world-cup-2022/services/world-cup-2022.service";

type WorldCup2022TeamPageProps = {
  params: Promise<{ teamId: string }>;
};

export default async function WorldCup2022TeamPage({ params }: WorldCup2022TeamPageProps) {
  const { teamId } = await params;

  try {
    const response = await fetchWorldCup2022TeamView(teamId);
    return <WorldCup2022TeamView data={response.data} meta={response.meta} />;
  } catch (error) {
    if (error instanceof ApiClientError) {
      return (
        <WorldCup2022ErrorState
          description={error.message}
          title={error.status === 404 ? "Seleção da Copa indisponível" : "Falha ao carregar a seleção"}
        />
      );
    }

    return (
      <WorldCup2022ErrorState
        description="Não foi possível carregar a visão da seleção da Copa 2022 agora."
        title="Falha ao carregar a seleção"
      />
    );
  }
}
