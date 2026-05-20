import { expect, test, type Page, type Route } from "@playwright/test";

type ApiPayload = {
  data: unknown;
  meta?: Record<string, unknown>;
};

function json(route: Route, body: ApiPayload): Promise<void> {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function noContent(route: Route, status = 404): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify({ data: null }),
  });
}

function buildRankingResponse(pathname: string) {
  const rankingId = pathname.split("/").filter(Boolean).at(-1) ?? "player-goals";
  const isPlayerRanking = rankingId.startsWith("player");

  return {
    data: {
      rankingId,
      metricKey: isPlayerRanking ? "goals" : "team_possession_pct",
      rows: [
        {
          entityId: isPlayerRanking ? "p-1" : "40",
          entityName: isPlayerRanking ? "Mohamed Salah" : "Liverpool",
          teamId: "40",
          teamName: "Liverpool",
          rank: 1,
          metricValue: isPlayerRanking ? 28 : 61.5,
          position: isPlayerRanking ? "FW" : undefined,
        },
      ],
      updatedAt: "2026-03-21T13:31:34Z",
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Ranking coverage",
      },
    },
  };
}

function buildLeagueMatchesResponse(roundId: string) {
  return {
    data: {
      items: [
        {
          matchId: "19135048",
          fixtureId: "19135048",
          competitionId: "8",
          competitionName: "Premier League",
          seasonId: "2024",
          roundId,
          kickoffAt: "2025-05-25T15:00:00Z",
          status: "FT",
          venueName: "Anfield",
          homeTeamId: "40",
          homeTeamName: "Liverpool",
          awayTeamId: "50",
          awayTeamName: "Crystal Palace",
          homeScore: 2,
          awayScore: 1,
        },
      ],
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Match list coverage",
      },
    },
  };
}

function buildLeagueStandingsResponse(roundId: string) {
  return {
    data: {
      competition: {
        competitionId: "8",
        competitionKey: "premier_league",
        competitionName: "Premier League",
        seasonId: "2024",
        seasonLabel: "2024/2025",
        providerSeasonId: "23614",
      },
      stage: {
        stageId: "77471288",
        stageName: "Regular Season",
        expectedTeams: 20,
      },
      selectedRound: {
        roundId,
        providerRoundId: roundId === "29" ? "339264" : "339273",
        roundName: roundId,
        label: `Rodada ${roundId}`,
        startingAt: roundId === "29" ? "2025-02-19" : "2025-05-25",
        endingAt: roundId === "29" ? "2025-04-16" : "2025-05-25",
        isCurrent: roundId === "38",
      },
      currentRound: {
        roundId: "38",
        providerRoundId: "339273",
        roundName: "38",
        label: "Rodada 38",
        startingAt: "2025-05-25",
        endingAt: "2025-05-25",
        isCurrent: true,
      },
      rounds: [
        {
          roundId: "29",
          providerRoundId: "339264",
          roundName: "29",
          label: "Rodada 29",
          startingAt: "2025-02-19",
          endingAt: "2025-04-16",
          isCurrent: false,
        },
        {
          roundId: "38",
          providerRoundId: "339273",
          roundName: "38",
          label: "Rodada 38",
          startingAt: "2025-05-25",
          endingAt: "2025-05-25",
          isCurrent: true,
        },
      ],
      rows: [
        {
          position: 1,
          teamId: "40",
          teamName: "Liverpool",
          matchesPlayed: roundId === "29" ? 29 : 38,
          wins: roundId === "29" ? 21 : 25,
          draws: roundId === "29" ? 7 : 9,
          losses: roundId === "29" ? 1 : 4,
          goalsFor: roundId === "29" ? 69 : 86,
          goalsAgainst: roundId === "29" ? 27 : 41,
          goalDiff: roundId === "29" ? 42 : 45,
          points: roundId === "29" ? 70 : 84,
        },
        {
          position: 2,
          teamId: "42",
          teamName: "Arsenal",
          matchesPlayed: roundId === "29" ? 29 : 38,
          wins: roundId === "29" ? 18 : 22,
          draws: roundId === "29" ? 8 : 8,
          losses: roundId === "29" ? 3 : 8,
          goalsFor: roundId === "29" ? 54 : 72,
          goalsAgainst: roundId === "29" ? 24 : 37,
          goalDiff: roundId === "29" ? 30 : 35,
          points: roundId === "29" ? 62 : 74,
        },
      ],
      updatedAt: "2026-03-21T13:31:34Z",
    },
    meta: {
      coverage: {
        status: "partial",
        percentage: 10,
        label: "Standings coverage",
      },
    },
  };
}

function buildCupStructureResponse() {
  return {
    data: {
      competition: {
        competitionKey: "copa_do_brasil",
        competitionName: "Copa do Brasil",
        seasonLabel: "2024",
        formatFamily: "knockout",
        seasonFormatCode: "cup_knockout",
        participantScope: "club",
      },
      stages: [
        {
          stageId: "quarter",
          stageName: "Quartas de final",
          stageCode: "quarter",
          stageFormat: "knockout",
          stageOrder: 1,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "semi",
          stageName: "Semifinal",
          stageCode: "semi",
          stageFormat: "knockout",
          stageOrder: 2,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "final",
          stageName: "Final",
          stageCode: "final",
          stageFormat: "knockout",
          stageOrder: 3,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: true,
          groups: [],
          transitions: [],
        },
      ],
    },
  };
}

function buildCupTiesResponse(stageId: string) {
  if (stageId === "quarter") {
    return {
      data: {
        competition: {
          competitionKey: "copa_do_brasil",
          competitionName: "Copa do Brasil",
          seasonLabel: "2024",
          formatFamily: "knockout",
          seasonFormatCode: "cup_knockout",
          participantScope: "club",
        },
        stage: {
          stageId: "quarter",
          stageName: "Quartas de final",
          stageFormat: "knockout",
          stageOrder: 1,
          isCurrent: false,
        },
        ties: [
          {
            tieId: "quarter-1",
            tieOrder: 1,
            homeTeamId: "40",
            homeTeamName: "Flamengo",
            awayTeamId: "42",
            awayTeamName: "Palmeiras",
            matchCount: 2,
            firstLegAt: "2024-08-21",
            lastLegAt: "2024-08-29",
            homeGoals: 3,
            awayGoals: 2,
            winnerTeamId: "40",
            winnerTeamName: "Flamengo",
            resolutionType: "aggregate",
            hasExtraTimeMatch: false,
            hasPenaltiesMatch: false,
          },
        ],
      },
    };
  }

  if (stageId === "semi") {
    return {
      data: {
        competition: {
          competitionKey: "copa_do_brasil",
          competitionName: "Copa do Brasil",
          seasonLabel: "2024",
          formatFamily: "knockout",
          seasonFormatCode: "cup_knockout",
          participantScope: "club",
        },
        stage: {
          stageId: "semi",
          stageName: "Semifinal",
          stageFormat: "knockout",
          stageOrder: 2,
          isCurrent: false,
        },
        ties: [
          {
            tieId: "semi-1",
            tieOrder: 1,
            homeTeamId: "40",
            homeTeamName: "Flamengo",
            awayTeamId: "43",
            awayTeamName: "Bahia",
            matchCount: 2,
            firstLegAt: "2024-09-18",
            lastLegAt: "2024-09-26",
            homeGoals: 4,
            awayGoals: 1,
            winnerTeamId: "40",
            winnerTeamName: "Flamengo",
            resolutionType: "aggregate",
            hasExtraTimeMatch: false,
            hasPenaltiesMatch: false,
          },
        ],
      },
    };
  }

  return {
    data: {
      competition: {
        competitionKey: "copa_do_brasil",
        competitionName: "Copa do Brasil",
        seasonLabel: "2024",
        formatFamily: "knockout",
        seasonFormatCode: "cup_knockout",
        participantScope: "club",
      },
      stage: {
        stageId: "final",
        stageName: "Final",
        stageFormat: "knockout",
        stageOrder: 3,
        isCurrent: true,
      },
      ties: [
        {
          tieId: "final-1",
          tieOrder: 1,
          homeTeamId: "40",
          homeTeamName: "Flamengo",
          awayTeamId: "42",
          awayTeamName: "Palmeiras",
          matchCount: 2,
          firstLegAt: "2024-10-12",
          lastLegAt: "2024-10-19",
          homeGoals: 3,
          awayGoals: 1,
          winnerTeamId: "40",
          winnerTeamName: "Flamengo",
          resolutionType: "aggregate",
          hasExtraTimeMatch: false,
          hasPenaltiesMatch: false,
        },
      ],
    },
  };
}

function buildCupMatchesResponse() {
  return {
    data: {
      items: [
        {
          matchId: "cdp-final-1",
          fixtureId: "cdp-final-1",
          competitionId: "732",
          competitionName: "Copa do Brasil",
          seasonId: "2024",
          roundId: "final",
          kickoffAt: "2024-10-19T20:00:00Z",
          status: "FT",
          venueName: "Maracana",
          homeTeamId: "40",
          homeTeamName: "Flamengo",
          awayTeamId: "42",
          awayTeamName: "Palmeiras",
          homeScore: 2,
          awayScore: 0,
        },
      ],
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Match list coverage",
      },
    },
  };
}

function buildHybridStructureResponse() {
  return {
    data: {
      competition: {
        competitionKey: "champions_league",
        competitionName: "UEFA Champions League",
        seasonLabel: "2024/2025",
        formatFamily: "hybrid",
        seasonFormatCode: "league_phase_knockout",
        participantScope: "club",
      },
      stages: [
        {
          stageId: "league_phase",
          stageName: "League Phase",
          stageCode: "league_phase",
          stageFormat: "league_table",
          stageOrder: 1,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "round_of_16",
          stageName: "Round of 16",
          stageCode: "round_of_16",
          stageFormat: "knockout",
          stageOrder: 2,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "ucl_final",
          stageName: "Final",
          stageCode: "final",
          stageFormat: "knockout",
          stageOrder: 3,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: true,
          groups: [],
          transitions: [],
        },
      ],
    },
  };
}

function buildHybridStandingsResponse() {
  return {
    data: {
      competition: {
        competitionId: "2",
        competitionKey: "champions_league",
        competitionName: "UEFA Champions League",
        seasonId: "2024",
        seasonLabel: "2024/2025",
      },
      stage: {
        stageId: "league_phase",
        stageName: "League Phase",
        expectedTeams: 36,
      },
      selectedRound: {
        roundId: "8",
        label: "Rodada 8",
        startingAt: "2025-01-29",
        endingAt: "2025-01-29",
        isCurrent: true,
      },
      currentRound: {
        roundId: "8",
        label: "Rodada 8",
        startingAt: "2025-01-29",
        endingAt: "2025-01-29",
        isCurrent: true,
      },
      rounds: [],
      rows: [
        {
          position: 1,
          teamId: "40",
          teamName: "Liverpool",
          matchesPlayed: 8,
          wins: 7,
          draws: 0,
          losses: 1,
          goalsFor: 19,
          goalsAgainst: 6,
          goalDiff: 13,
          points: 21,
        },
        {
          position: 2,
          teamId: "50",
          teamName: "Barcelona",
          matchesPlayed: 8,
          wins: 6,
          draws: 1,
          losses: 1,
          goalsFor: 17,
          goalsAgainst: 8,
          goalDiff: 9,
          points: 19,
        },
      ],
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Standings coverage",
      },
    },
  };
}

function buildHybridTiesResponse(stageId: string) {
  if (stageId === "round_of_16") {
    return {
      data: {
        competition: {
          competitionKey: "champions_league",
          competitionName: "UEFA Champions League",
          seasonLabel: "2024/2025",
          formatFamily: "hybrid",
          seasonFormatCode: "league_phase_knockout",
          participantScope: "club",
        },
        stage: {
          stageId: "round_of_16",
          stageName: "Round of 16",
          stageFormat: "knockout",
          stageOrder: 2,
          isCurrent: false,
        },
        ties: [
          {
            tieId: "ucl-ro16-1",
            tieOrder: 1,
            homeTeamId: "40",
            homeTeamName: "Liverpool",
            awayTeamId: "60",
            awayTeamName: "Inter",
            matchCount: 2,
            firstLegAt: "2025-02-18",
            lastLegAt: "2025-02-26",
            homeGoals: 4,
            awayGoals: 2,
            winnerTeamId: "40",
            winnerTeamName: "Liverpool",
            resolutionType: "aggregate",
            hasExtraTimeMatch: false,
            hasPenaltiesMatch: false,
          },
        ],
      },
    };
  }

  return {
    data: {
      competition: {
        competitionKey: "champions_league",
        competitionName: "UEFA Champions League",
        seasonLabel: "2024/2025",
        formatFamily: "hybrid",
        seasonFormatCode: "league_phase_knockout",
        participantScope: "club",
      },
      stage: {
        stageId: "ucl_final",
        stageName: "Final",
        stageFormat: "knockout",
        stageOrder: 3,
        isCurrent: true,
      },
      ties: [
        {
          tieId: "ucl-final-1",
          tieOrder: 1,
          homeTeamId: "40",
          homeTeamName: "Liverpool",
          awayTeamId: "50",
          awayTeamName: "Barcelona",
          matchCount: 1,
          firstLegAt: "2025-05-31",
          lastLegAt: "2025-05-31",
          homeGoals: 2,
          awayGoals: 1,
          winnerTeamId: "40",
          winnerTeamName: "Liverpool",
          resolutionType: "single_match",
          hasExtraTimeMatch: false,
          hasPenaltiesMatch: false,
        },
      ],
    },
  };
}

function buildLibertadoresHybridStructureResponse() {
  return {
    data: {
      competition: {
        competitionKey: "libertadores",
        competitionName: "Copa Libertadores da América",
        seasonLabel: "2025",
        formatFamily: "hybrid",
        seasonFormatCode: "group_stage_knockout",
        participantScope: "club",
      },
      stages: [
        {
          stageId: "group_stage",
          stageName: "Fase de Grupos",
          stageCode: "group_stage",
          stageFormat: "group_table",
          stageOrder: 1,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [
            { groupId: "group_a", groupName: "Grupo A", groupOrder: 1, expectedTeams: 4 },
            { groupId: "group_b", groupName: "Grupo B", groupOrder: 2, expectedTeams: 4 },
            { groupId: "group_c", groupName: "Grupo C", groupOrder: 3, expectedTeams: 4 },
            { groupId: "group_d", groupName: "Grupo D", groupOrder: 4, expectedTeams: 4 },
          ],
          transitions: [
            {
              progressionScope: "group",
              progressionType: "qualified",
              positionFrom: 1,
              positionTo: 2,
              toStageId: "quarter_final",
              toStageName: "Quartas de final",
              toStageFormat: "knockout",
              toStageOrder: 2,
            },
          ],
        },
        {
          stageId: "quarter_final",
          stageName: "Quartas de final",
          stageCode: "quarter_final",
          stageFormat: "knockout",
          stageOrder: 2,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "semi_final",
          stageName: "Semifinal",
          stageCode: "semi_final",
          stageFormat: "knockout",
          stageOrder: 3,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: false,
          groups: [],
          transitions: [],
        },
        {
          stageId: "final",
          stageName: "Final",
          stageCode: "final",
          stageFormat: "knockout",
          stageOrder: 4,
          standingsContextMode: null,
          bracketContextMode: null,
          groupMode: null,
          eliminationMode: null,
          isCurrent: true,
          groups: [],
          transitions: [],
        },
      ],
    },
  };
}

function buildLibertadoresStandingsResponse() {
  return {
    data: {
      competition: {
        competitionId: "390",
        competitionKey: "libertadores",
        competitionName: "Copa Libertadores da América",
        seasonId: "2025",
        seasonLabel: "2025",
      },
      stage: {
        stageId: "group_stage",
        stageName: "Fase de Grupos",
        expectedTeams: 16,
      },
      selectedRound: null,
      currentRound: null,
      rounds: [],
      rows: [
        {
          position: 1,
          teamId: "40",
          teamName: "Flamengo",
          matchesPlayed: 6,
          wins: 4,
          draws: 1,
          losses: 1,
          goalsFor: 12,
          goalsAgainst: 5,
          goalDiff: 7,
          points: 13,
        },
        {
          position: 2,
          teamId: "42",
          teamName: "Palmeiras",
          matchesPlayed: 6,
          wins: 4,
          draws: 1,
          losses: 1,
          goalsFor: 11,
          goalsAgainst: 4,
          goalDiff: 7,
          points: 13,
        },
      ],
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Standings coverage",
      },
    },
  };
}

function buildLibertadoresGroupStandingsResponse(groupId: string) {
  const rowsByGroup: Record<string, Array<Record<string, number | string>>> = {
    group_a: [
      { position: 1, teamId: "40", teamName: "Flamengo", matchesPlayed: 6, wins: 4, draws: 1, losses: 1, goalsFor: 12, goalsAgainst: 5, goalDiff: 7, points: 13 },
      { position: 2, teamId: "52", teamName: "LDU Quito", matchesPlayed: 6, wins: 3, draws: 2, losses: 1, goalsFor: 9, goalsAgainst: 6, goalDiff: 3, points: 11 },
      { position: 3, teamId: "61", teamName: "Talleres", matchesPlayed: 6, wins: 2, draws: 1, losses: 3, goalsFor: 6, goalsAgainst: 8, goalDiff: -2, points: 7 },
      { position: 4, teamId: "62", teamName: "Carabobo", matchesPlayed: 6, wins: 0, draws: 2, losses: 4, goalsFor: 3, goalsAgainst: 11, goalDiff: -8, points: 2 },
    ],
    group_b: [
      { position: 1, teamId: "42", teamName: "Palmeiras", matchesPlayed: 6, wins: 4, draws: 1, losses: 1, goalsFor: 11, goalsAgainst: 4, goalDiff: 7, points: 13 },
      { position: 2, teamId: "70", teamName: "Botafogo", matchesPlayed: 6, wins: 3, draws: 1, losses: 2, goalsFor: 8, goalsAgainst: 7, goalDiff: 1, points: 10 },
      { position: 3, teamId: "71", teamName: "Barcelona SC", matchesPlayed: 6, wins: 2, draws: 1, losses: 3, goalsFor: 7, goalsAgainst: 8, goalDiff: -1, points: 7 },
      { position: 4, teamId: "72", teamName: "Universitario", matchesPlayed: 6, wins: 1, draws: 1, losses: 4, goalsFor: 4, goalsAgainst: 11, goalDiff: -7, points: 4 },
    ],
    group_c: [
      { position: 1, teamId: "73", teamName: "River Plate", matchesPlayed: 6, wins: 4, draws: 0, losses: 2, goalsFor: 10, goalsAgainst: 5, goalDiff: 5, points: 12 },
      { position: 2, teamId: "74", teamName: "Sao Paulo", matchesPlayed: 6, wins: 3, draws: 2, losses: 1, goalsFor: 9, goalsAgainst: 6, goalDiff: 3, points: 11 },
      { position: 3, teamId: "75", teamName: "Independiente del Valle", matchesPlayed: 6, wins: 2, draws: 1, losses: 3, goalsFor: 6, goalsAgainst: 7, goalDiff: -1, points: 7 },
      { position: 4, teamId: "76", teamName: "Cobresal", matchesPlayed: 6, wins: 1, draws: 1, losses: 4, goalsFor: 5, goalsAgainst: 12, goalDiff: -7, points: 4 },
    ],
    group_d: [
      { position: 1, teamId: "77", teamName: "Racing Club", matchesPlayed: 6, wins: 4, draws: 1, losses: 1, goalsFor: 11, goalsAgainst: 5, goalDiff: 6, points: 13 },
      { position: 2, teamId: "78", teamName: "Atletico Nacional", matchesPlayed: 6, wins: 3, draws: 1, losses: 2, goalsFor: 8, goalsAgainst: 6, goalDiff: 2, points: 10 },
      { position: 3, teamId: "79", teamName: "Nacional", matchesPlayed: 6, wins: 2, draws: 1, losses: 3, goalsFor: 7, goalsAgainst: 9, goalDiff: -2, points: 7 },
      { position: 4, teamId: "80", teamName: "Sportivo Trinidense", matchesPlayed: 6, wins: 1, draws: 1, losses: 4, goalsFor: 4, goalsAgainst: 10, goalDiff: -6, points: 4 },
    ],
  };

  return {
    data: {
      competition: {
        competitionId: "390",
        competitionKey: "libertadores",
        competitionName: "Copa Libertadores da América",
        seasonId: "2025",
        seasonLabel: "2025",
      },
      stage: {
        stageId: "group_stage",
        stageName: "Fase de Grupos",
        expectedTeams: 4,
      },
      selectedRound: null,
      currentRound: null,
      rounds: [],
      rows: rowsByGroup[groupId] ?? [],
    },
    meta: {
      coverage: {
        status: "complete",
        percentage: 100,
        label: "Group standings coverage",
      },
    },
  };
}

function buildLibertadoresHybridTiesResponse(stageId: string) {
  if (stageId === "quarter_final") {
    return {
      data: {
        competition: {
          competitionKey: "libertadores",
          competitionName: "Copa Libertadores da América",
          seasonLabel: "2025",
          formatFamily: "hybrid",
          seasonFormatCode: "group_stage_knockout",
          participantScope: "club",
        },
        stage: {
          stageId: "quarter_final",
          stageName: "Quartas de final",
          stageFormat: "knockout",
          stageOrder: 2,
          isCurrent: false,
        },
        ties: [
          { tieId: "lib-qf-1", tieOrder: 1, homeTeamId: "52", homeTeamName: "LDU Quito", awayTeamId: "74", awayTeamName: "Sao Paulo", matchCount: 2, firstLegAt: "2025-08-20", lastLegAt: "2025-08-27", homeGoals: 3, awayGoals: 1, winnerTeamId: "52", winnerTeamName: "LDU Quito", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
          { tieId: "lib-qf-2", tieOrder: 2, homeTeamId: "40", homeTeamName: "Flamengo", awayTeamId: "81", awayTeamName: "Estudiantes", matchCount: 2, firstLegAt: "2025-08-21", lastLegAt: "2025-08-28", homeGoals: 2, awayGoals: 0, winnerTeamId: "40", winnerTeamName: "Flamengo", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
          { tieId: "lib-qf-3", tieOrder: 3, homeTeamId: "70", homeTeamName: "Botafogo", awayTeamId: "77", awayTeamName: "Racing Club", matchCount: 2, firstLegAt: "2025-08-20", lastLegAt: "2025-08-27", homeGoals: 2, awayGoals: 1, winnerTeamId: "70", winnerTeamName: "Botafogo", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
          { tieId: "lib-qf-4", tieOrder: 4, homeTeamId: "79", homeTeamName: "Universitario", awayTeamId: "42", awayTeamName: "Palmeiras", matchCount: 2, firstLegAt: "2025-08-21", lastLegAt: "2025-08-28", homeGoals: 0, awayGoals: 3, winnerTeamId: "42", winnerTeamName: "Palmeiras", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
        ],
      },
    };
  }

  if (stageId === "semi_final") {
    return {
      data: {
        competition: {
          competitionKey: "libertadores",
          competitionName: "Copa Libertadores da América",
          seasonLabel: "2025",
          formatFamily: "hybrid",
          seasonFormatCode: "group_stage_knockout",
          participantScope: "club",
        },
        stage: {
          stageId: "semi_final",
          stageName: "Semifinal",
          stageFormat: "knockout",
          stageOrder: 3,
          isCurrent: false,
        },
        ties: [
          { tieId: "lib-sf-1", tieOrder: 1, homeTeamId: "52", homeTeamName: "LDU Quito", awayTeamId: "42", awayTeamName: "Palmeiras", matchCount: 2, firstLegAt: "2025-09-17", lastLegAt: "2025-09-24", homeGoals: 1, awayGoals: 3, winnerTeamId: "42", winnerTeamName: "Palmeiras", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
          { tieId: "lib-sf-2", tieOrder: 2, homeTeamId: "40", homeTeamName: "Flamengo", awayTeamId: "70", awayTeamName: "Botafogo", matchCount: 2, firstLegAt: "2025-09-18", lastLegAt: "2025-09-25", homeGoals: 2, awayGoals: 1, winnerTeamId: "40", winnerTeamName: "Flamengo", resolutionType: "aggregate", hasExtraTimeMatch: false, hasPenaltiesMatch: false },
        ],
      },
    };
  }

  return {
    data: {
      competition: {
        competitionKey: "libertadores",
        competitionName: "Copa Libertadores da América",
        seasonLabel: "2025",
        formatFamily: "hybrid",
        seasonFormatCode: "group_stage_knockout",
        participantScope: "club",
      },
      stage: {
        stageId: "final",
        stageName: "Final",
        stageFormat: "knockout",
        stageOrder: 4,
        isCurrent: true,
      },
      ties: [
        {
          tieId: "lib-final-1",
          tieOrder: 1,
          homeTeamId: "40",
          homeTeamName: "Flamengo",
          awayTeamId: "42",
          awayTeamName: "Palmeiras",
          matchCount: 1,
          firstLegAt: "2025-11-29",
          lastLegAt: "2025-11-29",
          homeGoals: 2,
          awayGoals: 0,
          winnerTeamId: "40",
          winnerTeamName: "Flamengo",
          resolutionType: "single_match",
          hasExtraTimeMatch: false,
          hasPenaltiesMatch: false,
        },
      ],
    },
  };
}

async function setupSeasonSurfaceRoutes(
  page: Page,
  options: { missingGroupStandings?: boolean } = {},
) {
  await page.route("**/api/v1/teams**", async (route) => {
    await json(route, { data: { items: [] } });
  });

  await page.route("**/api/v1/rankings/**", async (route) => {
    const url = new URL(route.request().url());
    await json(route, buildRankingResponse(url.pathname));
  });

  await page.route("**/api/v1/competition-analytics**", async (route) => {
    const url = new URL(route.request().url());
    const competitionKey = url.searchParams.get("competitionKey");
    const seasonLabel = url.searchParams.get("seasonLabel");

    await json(route, {
      data: {
        competition: {
          competitionKey,
          competitionName: competitionKey,
          seasonLabel,
          formatFamily:
            competitionKey === "champions_league" || competitionKey === "libertadores"
              ? "hybrid"
              : "knockout",
          seasonFormatCode: "test_format",
          participantScope: "club",
        },
        seasonSummary: {
          matchCount: competitionKey === "libertadores" ? 34 : 10,
          totalStages: competitionKey === "libertadores" ? 4 : 3,
          tableStages:
            competitionKey === "champions_league" || competitionKey === "libertadores" ? 1 : 0,
          knockoutStages: competitionKey === "libertadores" ? 3 : 2,
          groupCount: competitionKey === "libertadores" ? 4 : 0,
          tieCount: competitionKey === "libertadores" ? 7 : 2,
          averageGoals: 2.8,
        },
        stageAnalytics: [],
        seasonComparisons: [],
      },
    });
  });

  await page.route("**/api/v1/competition-structure**", async (route) => {
    const url = new URL(route.request().url());
    const competitionKey = url.searchParams.get("competitionKey");

    if (competitionKey === "copa_do_brasil") {
      await json(route, buildCupStructureResponse());
      return;
    }

    if (competitionKey === "champions_league") {
      await json(route, buildHybridStructureResponse());
      return;
    }

    if (competitionKey === "libertadores") {
      await json(route, buildLibertadoresHybridStructureResponse());
      return;
    }

    await noContent(route);
  });

  await page.route("**/api/v1/ties**", async (route) => {
    const url = new URL(route.request().url());
    const competitionKey = url.searchParams.get("competitionKey");
    const stageId = url.searchParams.get("stageId") ?? "";

    if (competitionKey === "copa_do_brasil") {
      await json(route, buildCupTiesResponse(stageId));
      return;
    }

    if (competitionKey === "champions_league") {
      await json(route, buildHybridTiesResponse(stageId));
      return;
    }

    if (competitionKey === "libertadores") {
      await json(route, buildLibertadoresHybridTiesResponse(stageId));
      return;
    }

    await noContent(route);
  });

  await page.route("**/api/v1/group-standings**", async (route) => {
    const url = new URL(route.request().url());
    const competitionKey = url.searchParams.get("competitionKey");
    const groupId = url.searchParams.get("groupId") ?? "";

    if (options.missingGroupStandings) {
      await noContent(route);
      return;
    }

    if (competitionKey === "libertadores") {
      await json(route, buildLibertadoresGroupStandingsResponse(groupId));
      return;
    }

    await noContent(route);
  });

  await page.route("**/api/v1/standings**", async (route) => {
    const url = new URL(route.request().url());
    const competitionId = url.searchParams.get("competitionId");
    const competitionKey = url.searchParams.get("competitionKey");
    const roundId = url.searchParams.get("roundId") ?? "38";

    if (competitionId === "8" || competitionKey === "premier_league") {
      await json(route, buildLeagueStandingsResponse(roundId));
      return;
    }

    if (competitionId === "390" || competitionKey === "libertadores") {
      await json(route, buildLibertadoresStandingsResponse());
      return;
    }

    await json(route, buildHybridStandingsResponse());
  });

  await page.route("**/api/v1/matches**", async (route) => {
    const url = new URL(route.request().url());
    const competitionId = url.searchParams.get("competitionId");
    const roundId = url.searchParams.get("roundId") ?? "38";

    if (competitionId === "732") {
      await json(route, buildCupMatchesResponse());
      return;
    }

    if (competitionId === "390") {
      await json(route, buildCupMatchesResponse());
      return;
    }

    await json(route, buildLeagueMatchesResponse(roundId));
  });
}

test.describe("Fluxo critico: competition season surface orientada por tipo", () => {
  test("liga preserva rota, compatibilidade de tab e deep links legados", async ({ page }) => {
    const seasonHubHref = "/competitions/premier_league/seasons/2024%2F2025";
    const seasonNav = page.getByLabel("Navegacao da edicao");

    await setupSeasonSurfaceRoutes(page);

    await page.goto("/competitions");

    await expect(page.getByRole("heading", { name: "Análise de Competições" })).toBeVisible();

    await page.locator(`a[href="${seasonHubHref}"]`).first().click();

    await expect(page).toHaveURL(/\/competitions\/premier_league\/seasons\/2024%2F2025$/);
    await expect(page.getByRole("heading", { name: "Premier League", exact: true })).toBeVisible();
    await expect(page.getByText("Temporada 2024/2025", { exact: true })).toBeVisible();
    await expect(page.getByText("Pontos Corridos", { exact: true })).toBeVisible();
    await expect(page.getByText("Classificacao final").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Liverpool" }).first()).toBeVisible();
    await expect(page.locator("#global-filter-competition-id")).toBeEnabled();

    await seasonNav.getByRole("link", { name: "Tabela completa" }).click();

    await expect(page).toHaveURL(/tab=standings/);
    await expect(page.getByText("Classificacao final").first()).toBeVisible();
    await expect(page.getByText("Dados parciais.")).toBeVisible();

    await page.goto(`${seasonHubHref}?tab=standings&roundId=29`);

    await expect.poll(() => page.url()).toContain("tab=standings");
    await expect.poll(() => page.url()).toContain("roundId=29");
    await expect.poll(() => page.url()).not.toContain("competitionId=");
    await expect.poll(() => page.url()).not.toContain("seasonId=");

    await seasonNav.getByRole("link", { name: "Partidas de fechamento" }).click();

    await expect(page).toHaveURL(/tab=calendar/);
    await expect(page).toHaveURL(/roundId=29/);
    await expect(page.getByRole("heading", { name: "Partidas marcantes da temporada" })).toBeVisible();

    await seasonNav.getByRole("link", { name: "Destaques estatisticos" }).click();

    await expect(page).toHaveURL(/tab=rankings/);
    await expect(page).toHaveURL(/roundId=29/);
    await expect(page.getByRole("heading", { name: "Artilharia" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Posse de bola" })).toBeVisible();

    await expect(page.locator('a[href^="/matches?"]').first()).toHaveAttribute("href", /competitionId=8/);
    await expect(page.locator('a[href^="/matches?"]').first()).toHaveAttribute("href", /seasonId=2024/);
    await expect(page.locator('a[href^="/matches?"]').first()).toHaveAttribute("href", /roundId=29/);
    await expect(page.locator('a[href^="/rankings/player-goals?"]').first()).toHaveAttribute("href", /competitionId=8/);
    await expect(page.locator('a[href^="/rankings/player-goals?"]').first()).toHaveAttribute("href", /seasonId=2024/);
    await expect(page.locator('a[href^="/rankings/player-goals?"]').first()).toHaveAttribute("href", /roundId=29/);
  });

  test("copa abre variante de chaveamento com caminho do campeao", async ({ page }) => {
    await setupSeasonSurfaceRoutes(page);

    await page.goto("/competitions/copa_do_brasil/seasons/2024");

    await expect(page.getByRole("heading", { name: "Copa do Brasil", exact: true })).toBeVisible();
    await expect(page.getByText("Copa", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Navegacao da edicao").getByRole("link", { name: "Chaveamento" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Flamengo ate o titulo" })).toBeVisible();

    await page.getByLabel("Navegacao da edicao").getByRole("link", { name: "Chaveamento" }).click();

    await expect(page).toHaveURL(/tab=standings/);
    await expect(page.getByRole("heading", { name: "Chaveamento finalizado" })).toBeVisible();
    await expect(page.getByText("Palmeiras").first()).toBeVisible();
  });

  test("hibrida com fase unica usa tres tabs e aliases legados", async ({ page }) => {
    const seasonNav = page.getByLabel("Navegacao da edicao");

    await setupSeasonSurfaceRoutes(page);

    await page.goto("/competitions/champions_league/seasons/2024%2F2025");

    await expect(page.getByRole("heading", { name: "UEFA Champions League 2024/2025" })).toBeVisible();
    await expect(page.getByText("Edicao hibrida encerrada", { exact: true })).toBeVisible();
    await expect(seasonNav.getByRole("link")).toHaveCount(3);
    await expect(seasonNav.getByRole("link", { name: "Visao geral" })).toHaveAttribute("aria-current", "page");
    await expect(seasonNav.getByRole("link", { name: "Fase classificatoria" })).toBeVisible();
    await expect(seasonNav.getByRole("link", { name: "Chaveamento" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Chaveamento ate a final" })).toBeVisible();

    await seasonNav.getByRole("link", { name: "Fase classificatoria" }).click();

    await expect(page).toHaveURL(/tab=standings/);
    await expect(page.getByText("League Phase").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Liverpool" }).first()).toBeVisible();

    await seasonNav.getByRole("link", { name: "Chaveamento" }).click();

    await expect(page).toHaveURL(/tab=calendar/);
    await expect(page.getByRole("heading", { name: "Chaveamento final" })).toBeVisible();
    await expect(page.getByText(/Jogo unico.*1 jogo/).first()).toBeVisible();

    await page.goto("/competitions/champions_league/seasons/2024%2F2025?tab=rankings");

    await expect(page).toHaveURL(/tab=rankings/);
    await expect(seasonNav.getByRole("link", { name: "Visao geral" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: "Chaveamento ate a final" })).toBeVisible();

    await page.goto("/competitions/champions_league/seasons/2024%2F2025?tab=rounds");

    await expect(page).toHaveURL(/tab=rounds/);
    await expect(seasonNav.getByRole("link", { name: "Chaveamento" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: "Chaveamento final" })).toBeVisible();
  });

  test("hibrida com grupos usa tres tabs e renderiza fallback de classificacao", async ({ page }) => {
    const seasonNav = page.getByLabel("Navegacao da edicao");
    const quarterFinalLeft = page.locator('[data-bracket-column="quarter_final-left"]');
    const quarterFinalRight = page.locator('[data-bracket-column="quarter_final-right"]');

    await setupSeasonSurfaceRoutes(page);

    await page.goto("/competitions/libertadores/seasons/2025");

    await expect(page.getByRole("heading", { name: "Copa Libertadores da América 2025" })).toBeVisible();
    await expect(page.getByText("Edicao hibrida encerrada", { exact: true })).toBeVisible();
    await expect(seasonNav.getByRole("link")).toHaveCount(3);
    await expect(seasonNav.getByRole("link", { name: "Visao geral" })).toHaveAttribute("aria-current", "page");
    await expect(seasonNav.getByRole("link", { name: "Fase de grupos" })).toBeVisible();
    await expect(seasonNav.getByRole("link", { name: "Chaveamento" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Grupo A" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Flamengo" }).first()).toBeVisible();

    await seasonNav.getByRole("link", { name: "Fase de grupos" }).click();

    await expect(page).toHaveURL(/tab=standings/);
    await expect(page.getByRole("heading", { name: "Fase de Grupos" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Grupo A" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Flamengo" }).first()).toBeVisible();

    await seasonNav.getByRole("link", { name: "Chaveamento" }).click();

    await expect(page).toHaveURL(/tab=calendar/);
    await expect(page.getByRole("heading", { name: "Chaveamento final" })).toBeVisible();
    await expect(quarterFinalLeft).toContainText("Flamengo");
    await expect(quarterFinalLeft).toContainText("Botafogo");
    await expect(quarterFinalLeft).not.toContainText("Palmeiras");
    await expect(quarterFinalRight).toContainText("LDU Quito");
    await expect(quarterFinalRight).toContainText("Palmeiras");
    await expect(quarterFinalRight).not.toContainText("Flamengo");

    await page.goto("/competitions/libertadores/seasons/2025?tab=rounds");

    await expect(page).toHaveURL(/tab=rounds/);
    await expect(seasonNav.getByRole("link", { name: "Chaveamento" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: "Chaveamento final" })).toBeVisible();
  });

  test("hibrida com grupos usa standings final quando group-standings falta", async ({ page }) => {
    const seasonNav = page.getByLabel("Navegacao da edicao");

    await setupSeasonSurfaceRoutes(page, { missingGroupStandings: true });

    await page.goto("/competitions/libertadores/seasons/2025");

    await expect(seasonNav.getByRole("link")).toHaveCount(3);
    await expect(page.getByRole("heading", { name: "Fase de Grupos" })).toBeVisible();
    await expect(page.getByText("A classificacao final da fase de grupos segue como referencia principal desta edicao encerrada.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Flamengo" }).first()).toBeVisible();

    await seasonNav.getByRole("link", { name: "Fase de grupos" }).click();

    await expect(page).toHaveURL(/tab=standings/);
    await expect(page.getByRole("heading", { name: "Fase de Grupos" })).toBeVisible();
    await expect(page.getByText("A fase classificatoria desta edicao foi encerrada e a tabela final segue como referencia central.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Flamengo" }).first()).toBeVisible();
  });
});
