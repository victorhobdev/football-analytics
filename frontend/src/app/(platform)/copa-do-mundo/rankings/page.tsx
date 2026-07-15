import { redirect } from "next/navigation";

import { buildAnalysesPath } from "@/shared/utils/context-routing";

export default function WorldCupRankingsPage() {
  redirect(buildAnalysesPath({ competitionKey: "fifa_world_cup_mens" }));
}
