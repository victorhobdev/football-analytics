import { CanonicalRouteContextSync } from "@/shared/components/routing/CanonicalRouteContextSync";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { TeamProfileContent } from "@/features/teams/components/TeamProfileContent";
import { loadTeamHonorsPreview } from "@/features/teams/server/teamHonorsPreview";
import { resolveCompetitionSeasonContext } from "@/shared/utils/context-routing";

type CanonicalTeamProfilePageProps = {
  params: Promise<{
    competitionKey: string;
    seasonLabel: string;
    teamId: string;
  }>;
};

export default async function CanonicalTeamProfilePage({ params }: CanonicalTeamProfilePageProps) {
  const { competitionKey, seasonLabel, teamId } = await params;
  const honorsPreview = await loadTeamHonorsPreview(teamId);
  const context = resolveCompetitionSeasonContext({
    competitionKey,
    seasonLabel,
  });

  if (!context) {
    return (
      <PlatformStateSurface
        actionHref="/competitions"
        actionLabel="Ir para competições"
        description="Esta temporada não corresponde a um contexto válido para abrir o time."
        kicker="Time"
        title="Perfil de time indisponível"
        tone="critical"
      />
    );
  }

  return (
    <CanonicalRouteContextSync context={context}>
      <TeamProfileContent contextOverride={context} honorsPreview={honorsPreview} teamId={teamId} />
    </CanonicalRouteContextSync>
  );
}
