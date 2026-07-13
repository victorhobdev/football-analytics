import { redirect } from "next/navigation";

import { buildPassthroughSearchParamsQueryString } from "@/shared/utils/context-routing";

type LegacyRankingsPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function RankingsPage({ searchParams }: LegacyRankingsPageProps) {
  redirect(`/analises${buildPassthroughSearchParamsQueryString(await searchParams)}`);
}
