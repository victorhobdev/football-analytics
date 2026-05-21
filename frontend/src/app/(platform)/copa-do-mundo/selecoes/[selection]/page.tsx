import { WorldCupTeamContent } from "@/features/world-cup/components/WorldCupTeamContent";

type WorldCupTeamPageProps = {
  params: Promise<{
    selection: string;
  }>;
};

export default async function WorldCupTeamPage({ params }: WorldCupTeamPageProps) {
  const { selection } = await params;

  return <WorldCupTeamContent teamId={decodeURIComponent(selection)} />;
}
