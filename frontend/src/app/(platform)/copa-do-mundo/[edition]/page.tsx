import { WorldCupEditionContent } from "@/features/world-cup/components/WorldCupEditionContent";

type WorldCupEditionPageProps = {
  params: Promise<{
    edition: string;
  }>;
};

export default async function WorldCupEditionPage({
  params,
}: WorldCupEditionPageProps) {
  const { edition } = await params;

  return <WorldCupEditionContent seasonLabel={decodeURIComponent(edition)} />;
}
