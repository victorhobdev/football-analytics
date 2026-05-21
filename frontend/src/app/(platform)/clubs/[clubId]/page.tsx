import { TeamRouteResolver } from "@/app/(platform)/teams/[teamId]/TeamRouteResolver";
import { loadTeamHonorsPreview } from "@/features/teams/server/teamHonorsPreview";

type ClubDetailsPageProps = {
  params: Promise<{ clubId: string }>;
};

export default async function ClubDetailsPage({ params }: ClubDetailsPageProps) {
  const { clubId } = await params;
  const honorsPreview = await loadTeamHonorsPreview(clubId);

  return <TeamRouteResolver honorsPreview={honorsPreview} teamId={clubId} />;
}
