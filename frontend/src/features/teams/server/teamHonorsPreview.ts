import { readFile } from "node:fs/promises";
import path from "node:path";

import type { TeamHonorsPreview } from "@/features/teams/types";

const PREVIEW_SLUG_BY_TEAM_ID: Record<string, string> = {
  "1024": "flamengo",
  flamengo: "flamengo",
};

function getPreviewSlug(teamId: string): string | null {
  return PREVIEW_SLUG_BY_TEAM_ID[teamId.trim().toLowerCase()] ?? null;
}

function getPreviewPathCandidates(previewSlug: string): string[] {
  const fileName = `${previewSlug}.json`;

  return [
    path.resolve(process.cwd(), "data", "team_honors_preview", fileName),
    path.resolve(process.cwd(), "..", "data", "team_honors_preview", fileName),
  ];
}

export async function loadTeamHonorsPreview(
  teamId: string,
): Promise<TeamHonorsPreview | null> {
  const previewSlug = getPreviewSlug(teamId);

  if (!previewSlug) {
    return null;
  }

  for (const candidatePath of getPreviewPathCandidates(previewSlug)) {
    try {
      const fileContent = await readFile(candidatePath, "utf-8");
      return JSON.parse(fileContent) as TeamHonorsPreview;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;

      if (code !== "ENOENT") {
        throw error;
      }
    }
  }

  return null;
}
