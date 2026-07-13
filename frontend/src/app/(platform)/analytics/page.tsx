import { redirect } from "next/navigation";

import { buildPassthroughSearchParamsQueryString } from "@/shared/utils/context-routing";

type LegacyAnalyticsPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AnalyticsPage({ searchParams }: LegacyAnalyticsPageProps) {
  redirect(`/analises${buildPassthroughSearchParamsQueryString(await searchParams)}`);
}
