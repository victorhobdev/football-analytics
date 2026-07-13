import { redirect } from "next/navigation";

import { buildPassthroughSearchParamsQueryString } from "@/shared/utils/context-routing";

type LegacyRankingPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function RankingsPage({ searchParams }: LegacyRankingPageProps) {
  redirect(`/analises${buildPassthroughSearchParamsQueryString(await searchParams)}`);
}
