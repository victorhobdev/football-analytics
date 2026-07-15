import { redirect } from "next/navigation";

import { ProfileAlert, ProfileShell } from "@/shared/components/profile/ProfilePrimitives";
import {
  buildAnalysesPath,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";

import { SeasonHubContent } from "./SeasonHubContent";

type SeasonHubPageProps = {
  params: Promise<{
    competitionKey: string;
    seasonLabel: string;
  }>;
  searchParams?: Promise<{
    tab?: string | string[];
  }>;
};

export default async function SeasonHubPage({
  params,
  searchParams,
}: SeasonHubPageProps) {
  const { competitionKey, seasonLabel } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const tabParam = resolvedSearchParams?.tab;
  const context = resolveCompetitionSeasonContext({
    competitionKey,
    seasonLabel,
  });

  if (!context) {
    return (
      <ProfileShell className="space-y-6">
        <ProfileAlert title="Temporada não encontrada" tone="critical">
          Não encontramos essa temporada para a competição selecionada. Volte e escolha outra
          opção.
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (tabParam === "rankings") {
    redirect(
      buildAnalysesPath({
        competitionId: context.competitionId,
        competitionKey: context.competitionKey,
        seasonId: context.seasonId,
        seasonLabel: context.seasonLabel,
      }),
    );
  }

  return (
    <SeasonHubContent
      context={context}
      initialTab={typeof tabParam === "string" ? tabParam : null}
    />
  );
}
