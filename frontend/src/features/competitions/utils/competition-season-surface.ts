import type { CompetitionDef } from "@/config/competitions.registry";
import type {
  CompetitionStructureData,
  CompetitionStructureStage,
} from "@/features/competitions/types";
import {
  describeCompetitionEdition,
  isKnockoutStageFormat,
  isTableStageFormat,
} from "@/features/competitions/utils/competition-structure";

import type { SeasonHubTab } from "@/shared/utils/context-routing";

export type CompetitionSeasonSurfaceType = "league" | "cup" | "hybrid";
export type CompetitionSeasonSurfaceResolutionSource =
  | "structure"
  | "competition_type_fallback";
export type CompetitionSeasonSurfaceSection =
  | "overview"
  | "structure"
  | "matches"
  | "highlights"
  | "rounds";

export type CompetitionSeasonSurfaceResolution = {
  defaultStructureStage: CompetitionStructureStage | null;
  editionLabel: string | null;
  finalKnockoutStage: CompetitionStructureStage | null;
  knockoutStages: CompetitionStructureStage[];
  primaryTableStage: CompetitionStructureStage | null;
  source: CompetitionSeasonSurfaceResolutionSource;
  stageCount: number;
  tableStages: CompetitionStructureStage[];
  type: CompetitionSeasonSurfaceType;
};

type ResolveCompetitionSeasonSurfaceInput = {
  competitionType?: CompetitionDef["type"] | null;
  structure?: CompetitionStructureData | null;
};

function sortStages(stages: CompetitionStructureStage[]): CompetitionStructureStage[] {
  return [...stages].sort((left, right) => {
    const leftOrder = left.stageOrder ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = right.stageOrder ?? Number.MAX_SAFE_INTEGER;

    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }

    return (left.stageName ?? left.stageId).localeCompare(right.stageName ?? right.stageId);
  });
}

function resolveSurfaceTypeFromFallback(
  competitionType?: CompetitionDef["type"] | null,
): CompetitionSeasonSurfaceType {
  if (competitionType === "domestic_league") {
    return "league";
  }

  return "cup";
}

export function resolveCompetitionSeasonSurface(
  input: ResolveCompetitionSeasonSurfaceInput,
): CompetitionSeasonSurfaceResolution {
  const orderedStages = sortStages(input.structure?.stages ?? []);
  const tableStages = orderedStages.filter((stage) => isTableStageFormat(stage.stageFormat));
  const knockoutStages = orderedStages.filter((stage) => isKnockoutStageFormat(stage.stageFormat));

  let type = resolveSurfaceTypeFromFallback(input.competitionType);
  let source: CompetitionSeasonSurfaceResolutionSource = "competition_type_fallback";

  if (tableStages.length > 0 || knockoutStages.length > 0) {
    source = "structure";

    if (tableStages.length > 0 && knockoutStages.length > 0) {
      type = "hybrid";
    } else if (tableStages.length > 0) {
      type = "league";
    } else {
      type = "cup";
    }
  }

  return {
    defaultStructureStage: tableStages[0] ?? knockoutStages[0] ?? orderedStages[0] ?? null,
    editionLabel: describeCompetitionEdition(input.structure),
    finalKnockoutStage: knockoutStages.at(-1) ?? null,
    knockoutStages,
    primaryTableStage:
      tableStages.find((stage) => stage.stageFormat === "league_table") ?? tableStages[0] ?? null,
    source,
    stageCount: orderedStages.length,
    tableStages,
    type,
  };
}

export function resolveCompetitionSeasonSurfaceSection(
  tab: string | null | undefined,
): CompetitionSeasonSurfaceSection {
  if (tab === "standings") {
    return "structure";
  }

  if (tab === "calendar") {
    return "matches";
  }

  if (tab === "rankings") {
    return "highlights";
  }

  if (tab === "rounds") {
    return "rounds";
  }

  return "overview";
}

export function mapCompetitionSeasonSurfaceSectionToLegacyTab(
  section: Exclude<CompetitionSeasonSurfaceSection, "overview">,
): SeasonHubTab {
  if (section === "structure") {
    return "standings";
  }

  if (section === "highlights") {
    return "rankings";
  }

  if (section === "rounds") {
    return "rounds" as SeasonHubTab;
  }

  return "calendar";
}
