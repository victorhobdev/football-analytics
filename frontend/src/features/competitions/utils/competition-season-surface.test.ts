import { describe, expect, it } from "vitest";

import type { CompetitionStructureData, CompetitionStructureStage } from "@/features/competitions/types";
import {
  normalizeCompetitionSeasonSurfaceSection,
  mapCompetitionSeasonSurfaceSectionToLegacyTab,
  resolveCompetitionSeasonSurface,
  resolveCompetitionSeasonSurfaceSection,
  resolveHybridTableSectionLabel,
} from "@/features/competitions/utils/competition-season-surface";

function buildStage(
  stageId: string,
  stageFormat: CompetitionStructureStage["stageFormat"],
  stageOrder: number,
): CompetitionStructureStage {
  return {
    stageId,
    stageName: `Stage ${stageId}`,
    stageCode: `stage_${stageId}`,
    stageFormat,
    stageOrder,
    standingsContextMode: null,
    bracketContextMode: null,
    groupMode: null,
    eliminationMode: null,
    isCurrent: false,
    expectedTeams: null,
    groups: [],
    transitions: [],
  };
}

function buildStructure(stages: CompetitionStructureStage[]): CompetitionStructureData {
  return {
    competition: {
      competitionKey: "test_competition",
      competitionName: "Test Competition",
      seasonLabel: "2024",
      formatFamily: "test",
      seasonFormatCode: "test_format",
      participantScope: "club",
    },
    stages,
  };
}

describe("competition-season-surface utils", () => {
  it("resolve league when structure exposes only table stages", () => {
    const resolution = resolveCompetitionSeasonSurface({
      competitionType: "domestic_cup",
      structure: buildStructure([
        buildStage("regular", "league_table", 1),
      ]),
    });

    expect(resolution.type).toBe("league");
    expect(resolution.source).toBe("structure");
    expect(resolution.primaryTableStage?.stageId).toBe("regular");
  });

  it("resolve cup when structure exposes only knockout stages", () => {
    const resolution = resolveCompetitionSeasonSurface({
      competitionType: "domestic_league",
      structure: buildStructure([
        buildStage("quarter", "knockout", 1),
        buildStage("final", "knockout", 2),
      ]),
    });

    expect(resolution.type).toBe("cup");
    expect(resolution.source).toBe("structure");
    expect(resolution.finalKnockoutStage?.stageId).toBe("final");
  });

  it("resolve hybrid when structure mixes table and knockout stages", () => {
    const resolution = resolveCompetitionSeasonSurface({
      competitionType: "international_cup",
      structure: buildStructure([
        buildStage("groups", "group_table", 1),
        buildStage("quarter", "knockout", 2),
        buildStage("final", "knockout", 3),
      ]),
    });

    expect(resolution.type).toBe("hybrid");
    expect(resolution.source).toBe("structure");
    expect(resolution.tableStages).toHaveLength(1);
    expect(resolution.knockoutStages).toHaveLength(2);
  });

  it("fallback to competition type when structure is missing", () => {
    expect(
      resolveCompetitionSeasonSurface({
        competitionType: "domestic_league",
        structure: null,
      }).type,
    ).toBe("league");

    expect(
      resolveCompetitionSeasonSurface({
        competitionType: "international_cup",
        structure: null,
      }).type,
    ).toBe("cup");
  });

  it("maps legacy tabs to the editorial sections during transition", () => {
    expect(resolveCompetitionSeasonSurfaceSection(null)).toBe("overview");
    expect(resolveCompetitionSeasonSurfaceSection("standings")).toBe("structure");
    expect(resolveCompetitionSeasonSurfaceSection("calendar")).toBe("matches");
    expect(resolveCompetitionSeasonSurfaceSection("rankings")).toBe("highlights");
    expect(resolveCompetitionSeasonSurfaceSection("unknown")).toBe("overview");
    expect(resolveCompetitionSeasonSurfaceSection("rankings", "hybrid")).toBe("overview");
    expect(resolveCompetitionSeasonSurfaceSection("rounds", "hybrid")).toBe("matches");
    expect(normalizeCompetitionSeasonSurfaceSection("highlights", "hybrid")).toBe("overview");
    expect(normalizeCompetitionSeasonSurfaceSection("rounds", "hybrid")).toBe("matches");
    expect(mapCompetitionSeasonSurfaceSectionToLegacyTab("structure")).toBe("standings");
    expect(mapCompetitionSeasonSurfaceSectionToLegacyTab("matches")).toBe("calendar");
    expect(mapCompetitionSeasonSurfaceSectionToLegacyTab("highlights")).toBe("rankings");
  });

  it("resolves the hybrid table label from the detected table stage", () => {
    expect(resolveHybridTableSectionLabel(buildStage("groups", "group_table", 1))).toBe(
      "Fase de grupos",
    );
    expect(resolveHybridTableSectionLabel(buildStage("league", "league_table", 1))).toBe(
      "Fase classificatoria",
    );
    expect(resolveHybridTableSectionLabel(null)).toBe("Fase classificatoria");
  });
});
