import { TeamRouteResolver } from "./TeamRouteResolver";
import { loadTeamHonorsPreview } from "@/features/teams/server/teamHonorsPreview";

type TeamResolverPageProps = {
  params: Promise<{ teamId: string }>;
};

export default async function TeamResolverPage({ params }: TeamResolverPageProps) {
  const { teamId } = await params;
  const honorsPreview = await loadTeamHonorsPreview(teamId);

  return <TeamRouteResolver honorsPreview={honorsPreview} teamId={teamId} />;
}
