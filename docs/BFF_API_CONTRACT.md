# BFF API Contract (Frontend Integration)

Reference date: 2026-03-21  
Scope: official BFF contract for frontend integration, aligned with:
- `docs/GUIA_MESTRE_APLICACAO.md`
- `docs/MART_FRONTEND_BFF_CONTRACTS.md`
- `frontend/src/config/metrics.registry.ts`
- `frontend/src/config/ranking.registry.ts`

## 1) Global Rules

## 1.1 Base path
- Official base path: `/api/v1`

## 1.2 Standard success response

```json
{
  "data": {},
  "meta": {
    "pagination": {
      "page": 1,
      "pageSize": 20,
      "totalCount": 200,
      "totalPages": 10,
      "hasNextPage": true,
      "hasPreviousPage": false
    },
    "coverage": {
      "status": "complete",
      "percentage": 100,
      "label": "Complete coverage"
    },
    "requestId": "req_01H...",
    "generatedAt": "2026-02-21T13:30:00Z"
  }
}
```

Type contract:
- `ApiResponse<T>`: `{ data: T; meta?: ApiResponseMeta }`
- `Pagination`: `page`, `pageSize`, `totalCount`, optional `totalPages`, `hasNextPage`, `hasPreviousPage`
- `CoverageState`:
  - `status`: `complete | partial | empty | unknown`
  - `percentage?`: `0..100`
  - `label?`: string

Coverage rule:
- `meta.coverage` must be returned when data quality/completeness is relevant.
- Expected in: `/players`, `/players/{playerId}`, `/search`, `/standings`, `/competition-structure`, `/group-standings`, `/ties`, `/team-progression`, `/rankings/{rankingType}`, `/matches/{matchId}`, `/insights`.
- Optional in `/matches`.

## 1.3 Standard error response

```json
{
  "message": "Invalid ranking type.",
  "code": "INVALID_RANKING_TYPE",
  "status": 400,
  "details": {
    "rankingType": "unknown-ranking"
  }
}
```

Type contract:
- `ApiError`: `message` (required), `code?`, `status?`, `details?`
- `HttpError`: same shape, with `status` required

## 1.4 Global filters and time range

Global filters:
- `competitionId` (string)
- `seasonId` (string; BFF query identifier. For split-year seasons the canonical route may display `2024/2025`, but the BFF query still sends `2024`.)
- `roundId` (string; canonical numeric round identifier used by `matches`, `standings` and `rankings`, not the provider round id)
- `venue` (`home | away | all`)

Time range (mutually exclusive):
- Option A: `lastN` (int > 0)
- Option B: `dateStart` + `dateEnd` (`YYYY-MM-DD`)

Validation:
1. `lastN` cannot coexist with `dateStart/dateEnd`.
2. `dateStart` without `dateEnd` (or vice-versa) is invalid.
3. Invalid combinations return `400 INVALID_TIME_RANGE`.

Migration compatibility:
- BFF may accept legacy aliases `dateRangeStart/dateRangeEnd`.
- Official contract is `dateStart/dateEnd`.

## 1.5 Context rule for canonical club/player pages

Rule:
- `competitionId` + `seasonId` are mandatory whenever frontend is rendering the canonical club/player pages.
- `/players/{playerId}` without these filters remains compatibility mode only; it is not sufficient for the final season-scoped UI.
- the same rule will apply to `/teams/{teamId}` when that router is introduced.

Frontend routing alignment:
- canonical frontend URLs are contextualized by `competitionKey + seasonLabel + entityId`.
- short URLs (`/teams/{teamId}`, `/players/{playerId}`) exist only to resolve the proper context and redirect.

Implemented BFF additions for this flow:
- `GET /api/v1/teams`
- `GET /api/v1/teams/{teamId}/contexts`
- `GET /api/v1/players/{playerId}/contexts`
- `GET /api/v1/teams/{teamId}` as the contextualized team-profile contract with `overview`, `squad`, `stats` and `sectionCoverage`
- `GET /api/v1/players/{playerId}` as the contextualized player-profile contract with `recentMatches`, `history`, `stats` and `sectionCoverage`
- `GET /api/v1/search` for global search (`competition`, `team`, `player`, `match`)

Expected response shape for `*/contexts`:
```json
{
  "data": {
    "defaultContext": {
      "competitionId": "71",
      "competitionKey": "brasileirao_a",
      "seasonId": "2024",
      "seasonLabel": "2024"
    },
    "availableContexts": []
  }
}
```

---

## 2) Endpoints

## 2.1 GET `/players`

Purpose:
- List players with aggregated stats in the selected scope.

Query params:
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `search` (string)
  - `teamId` (string)
  - `position` (string)
  - `minMinutes` (int >= 0)
- Pagination:
  - `page` (default `1`)
  - `pageSize` (default `20`, recommended max `100`)
- Sort:
  - `sortBy` (`playerName | minutesPlayed | goals | assists | rating`)
  - `sortDirection` (`asc | desc`, default `desc`)

Request example:
```http
GET /api/v1/players?competitionId=648&seasonId=2024&lastN=5&page=1&pageSize=20&sortBy=goals&sortDirection=desc
```

Response `data` shape:
- `{ items: PlayerListItem[] }`
- `PlayerListItem`:
  - required: `playerId`, `playerName`
  - optional: `teamId`, `teamName`, `position`, `nationality`, `matchesPlayed`, `minutesPlayed`, `goals`, `assists`, `shotsTotal`, `passAccuracyPct`, `yellowCards`, `redCards`, `rating`

Rules:
- `meta.pagination` required.
- `meta.coverage` expected.

---

## 2.2 GET `/players/{playerId}`

Purpose:
- Player profile final under canonical competition/season context, with overview, participation history, match log and stable aggregated stats.

Path params:
- `playerId` (required)

Query params:
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `includeRecentMatches` (`true|false`, default `true`)
  - `includeHistory` (`true|false`, default `true`)
  - `includeStats` (`true|false`, default `true`)
  - `recentMatchesLimit` (int, default `10`)
- Pagination: N/A (resource detail)
- Sort: N/A for top-level profile (recent matches default `playedAt desc`)

Request example:
```http
GET /api/v1/players/p-1?competitionId=648&seasonId=2024&dateStart=2026-02-01&dateEnd=2026-02-20&includeRecentMatches=true&includeHistory=true&includeStats=true
```

Response `data` shape:
- `PlayerProfile`
  - `player`
  - `summary`
  - `recentMatches?`
    - match log entries may include: `matchId`, `competitionId`, `competitionName`, `seasonId`, `roundId`, `teamId`, `teamName`, `opponentTeamId`, `opponentName`, `venue`, `goalsFor`, `goalsAgainst`, `result`, `minutesPlayed`, `goals`, `assists`, `shotsTotal`, `shotsOnTarget`, `passesAttempted`, `rating`
  - `history?`
    - multi-context participation rows derived from `mart.player_match_summary`, grouped by competition + season + team
    - expected fields: `competitionId`, `competitionKey`, `competitionName`, `seasonId`, `seasonLabel`, `teamId`, `teamName`, `matchesPlayed`, `minutesPlayed`, `goals`, `assists`, `rating`, `lastMatchAt`
  - `stats?`
    - stable scoped aggregates such as `minutesPerMatch`, `goalsPer90`, `assistsPer90`, `goalContributionsPer90`, `shotsPer90`, `shotsOnTargetPer90`, `shotsOnTargetPct`, `passesAttemptedPer90`, `yellowCardsPer90`, `redCardsPer90`
    - `trend?` with monthly consolidated points: `periodKey`, `label`, `matchesPlayed`, `minutesPlayed`, `goals`, `assists`, `shotsTotal`, `shotsOnTarget`, `passesAttempted`, `rating`
  - `sectionCoverage?`
    - `overview?`
    - `history?`
    - `matches?`
    - `stats?`

Rules:
- `404 PLAYER_NOT_FOUND` if missing.
- `meta.coverage` expected.
- `data.sectionCoverage` must expose independent coverage for `overview`, `history`, `matches` and `stats`.
- canonical player page must always send `competitionId` and `seasonId`.
- `history` is intentionally limited to contexts provably available in project data; it must not pretend to be full career history when provider coverage does not support that claim.

---

## 2.2.1 GET `/players/{playerId}/contexts`

Purpose:
- Resolve canonical competition/season contexts for player deep links and short-route redirect.

Path params:
- `playerId` (required)

Query params:
- optional preference:
  - `competitionId` (string)
  - `seasonId` (string)

Response `data` shape:
- `defaultContext`
- `availableContexts`

Rules:
- `404 PLAYER_NOT_FOUND` if missing.
- `defaultContext` may be `null` when the player exists but no canonical competition mapping is available.
- `availableContexts` is ordered by latest known match context, then filtered in frontend/BFF by supported canonical competition mapping.

---

## 2.2.2 GET `/teams/{teamId}/contexts`

Purpose:
- Resolve canonical competition/season contexts for club deep links and short-route redirect.

Path params:
- `teamId` (required)

Query params:
- optional preference:
  - `competitionId` (string)
  - `seasonId` (string)

Response `data` shape:
- `defaultContext`
- `availableContexts`

Rules:
- `404 TEAM_NOT_FOUND` if missing.
- `defaultContext` may be `null` when the team exists but no canonical competition mapping is available.

---

## 2.2.3 GET `/teams`

Purpose:
- Serve the teams discovery surface as a first-class list in the shell and season context.

Query params:
- optional structural context:
  - `competitionId` (string)
  - `seasonId` (string)
  - `roundId`
  - `venue`
  - `lastN` or `dateStart/dateEnd`
- optional list controls:
  - `search`
  - `page`
  - `pageSize`
  - `sortBy` (`teamName|points|goalDiff|wins|position`)
  - `sortDirection` (`asc|desc`)

Response `data` shape:
- `items[]`
  - `teamId`
  - `teamName`
  - `position?`
  - `totalTeams?`
  - `matchesPlayed`
  - `wins`
  - `draws`
  - `losses`
  - `goalsFor`
  - `goalsAgainst`
  - `goalDiff`
  - `points`

Rules:
- `meta.coverage` expected.
- `meta.pagination` expected.
- The list reuses stable `fact_matches` aggregates; there is no provider caveat-specific section coverage here.

---

## 2.2.4 GET `/teams/{teamId}`

Purpose:
- Contextualized team profile contract for canonical club pages, now expanded to close the `teams` domain.

Path params:
- `teamId` (required)

Query params:
- required context:
  - `competitionId` (string)
  - `seasonId` (string)
- optional global + time:
  - `roundId`
  - `venue`
  - `lastN` or `dateStart/dateEnd`
- local:
  - `includeRecentMatches` (`true|false`, default `true`)
  - `includeSquad` (`true|false`, default `true`)
  - `includeStats` (`true|false`, default `true`)
  - `recentMatchesLimit` (int, default `10`)

Response `data` shape:
- `team`
- `summary`
- `recentMatches?`
- `squad?`
- `stats?`
- `sectionCoverage?`
  - `overview`
  - `squad`
  - `stats`

Rules:
- `400 INVALID_QUERY_PARAM` if `competitionId` or `seasonId` is missing.
- `404 TEAM_NOT_FOUND` if missing.
- `meta.coverage` expected.
- `squad` is aggregated from `mart.fact_fixture_lineups`, with honest `partial` coverage when raw lineup rows exist but valid identified players are missing in mart.
- `stats` stays restricted to stable aggregates and monthly trend derived from the scoped match set.

---

## 2.2.5 GET `/search`

Purpose:
- Serve the first useful version of global search in the shell, limited to canonical entities that already have a safe navigation target in the current frontend.

Query params:
- required:
  - `q` (string, minimum 2 meaningful characters)
- optional:
  - `types` (repeatable or comma-separated; allowed values: `competition`, `team`, `player`, `match`)
  - `competitionId` (string; preference signal for canonical context selection, not a hard filter)
  - `seasonId` (string; preference signal for canonical context selection, not a hard filter)
  - `limitPerType` (int, default `5`, max `10`)

Request examples:
```http
GET /api/v1/search?q=prem
GET /api/v1/search?q=liv&types=team&competitionId=8&seasonId=2024
GET /api/v1/search?q=salah&types=player&competitionId=8&seasonId=2024
GET /api/v1/search?q=liv&types=match&competitionId=8&seasonId=2024
```

Response `data` shape:
- `query`
- `totalResults`
- `groups[]`
  - `type` (`competition | team | player | match`)
  - `total`
  - `items`
    - `competition`
      - `competitionId`
      - `competitionKey`
      - `competitionName`
    - `team`
      - `teamId`
      - `teamName`
      - `defaultContext`
    - `player`
      - `playerId`
      - `playerName`
      - `teamId?`
      - `teamName?`
      - `position?`
      - `defaultContext`
    - `match`
      - `matchId`
      - `competitionId?`
      - `competitionName?`
      - `seasonId?`
      - `roundId?`
      - `kickoffAt?`
      - `status?`
      - `homeTeamId?`
      - `homeTeamName?`
      - `awayTeamId?`
      - `awayTeamName?`
      - `homeScore?`
      - `awayScore?`
      - `defaultContext`

Rules:
- `400 INVALID_QUERY_PARAM` if `q` has fewer than 2 meaningful characters.
- `400 INVALID_QUERY_PARAM` if any `types` value is outside `competition | team | player | match`.
- search only returns `team`, `player` and `match` rows that already resolve to a supported canonical competition mapping in the current frontend.
- `competitionId` and `seasonId` act as preference signals to choose `defaultContext`; they do not fully scope the search result set.
- the endpoint applies deterministic relevance signals in this order:
  - lexical match strength (`exact > exact token > prefix > token prefix > contains`)
  - preferred `competitionId + seasonId`
  - recent activity / recency inside the chosen canonical context
- `meta.coverage` is expected and represents navigability coverage of the returned result set:
  - `complete` when all matched rows included in the response close in safe navigation targets
  - `partial` when some matched rows were dropped because they do not resolve safely
  - `empty` when only non-navigable matches were found

---

## 2.2.6 GET `/standings`

Purpose:
- Return the canonical standings table for a competition/season scope, with round metadata for the season hub.

Query params:
- required context:
  - `competitionId` (string)
  - `seasonId` (string)
- optional:
  - `roundId` (string; canonical round number inside the resolved standings stage)
  - `stageId` (string; explicit stage selector when the competition-season has more than one standings boundary)
  - `groupId` (string; required when the resolved stage has `stageFormat=group_table`)

Request examples:
```http
GET /api/v1/standings?competitionId=8&seasonId=2024
GET /api/v1/standings?competitionId=8&seasonId=2024&roundId=29
GET /api/v1/standings?competitionId=390&seasonId=2024&stageId=77468966&groupId=23036f64061bf2ff6a088aa90b6659bd
```

Response `data` shape:
- `competition`
  - `competitionId`
  - `competitionKey?`
  - `competitionName`
  - `seasonId`
  - `seasonLabel`
  - `providerSeasonId?`
- `stage?`
  - `stageId`
  - `stageName?`
  - `stageFormat?`
  - `expectedTeams?`
- `group?`
  - `groupId`
  - `groupName?`
  - `groupOrder?`
  - `expectedTeams?`
- `selectedRound?`
- `currentRound?`
- `rounds`
- `rows`
- `updatedAt?`

`selectedRound/currentRound/rounds` minimum:
- `roundId`
- `providerRoundId?`
- `roundName?`
- `label`
- `startingAt?`
- `endingAt?`
- `isCurrent`

`rows` minimum:
- `position`
- `teamId`
- `teamName`
- `matchesPlayed`
- `wins`
- `draws`
- `losses`
- `goalsFor`
- `goalsAgainst`
- `goalDiff`
- `points`

Rules:
- `400 INVALID_QUERY_PARAM` if `competitionId` or `seasonId` is missing.
- `400 INVALID_QUERY_PARAM` if `roundId` does not exist in the resolved standings stage.
- `400 INVALID_QUERY_PARAM` if `groupId` is omitted when the resolved stage has `stageFormat=group_table`.
- `400 INVALID_QUERY_PARAM` if `groupId` is sent for a non-group standings stage.
- `meta.coverage` required.
- empty provider/data coverage must return `200` with `rows: []`, `rounds: []` and `meta.coverage.status = empty`.

---

## 2.2.7 GET `/competition-structure`

Purpose:
- Return the structural hub of a competition edition, driven by `competitionKey + seasonLabel`.

Query params:
- required:
  - `competitionKey` (string)
  - `seasonLabel` (string; accepts annual labels like `2024` and split-year labels like `2024/2025`)

Response `data` shape:
- `competition`
  - `competitionId?`
  - `competitionKey`
  - `competitionName`
  - `seasonId?`
  - `seasonLabel`
  - `providerSeasonId?`
  - `formatFamily`
  - `seasonFormatCode`
  - `participantScope`
  - `groupRankingRuleCode?`
  - `tieRuleCode?`
- `stages[]`
  - `stageId`
  - `stageName?`
  - `stageCode?`
  - `stageFormat?`
  - `stageOrder?`
  - `standingsContextMode?`
  - `bracketContextMode?`
  - `groupMode?`
  - `eliminationMode?`
  - `isCurrent`
  - `groups[]`
    - `groupId`
    - `groupName?`
    - `groupOrder?`
    - `expectedTeams?`
  - `transitions[]`
    - `progressionScope`
    - `progressionType`
    - `positionFrom?`
    - `positionTo?`
    - `tieOutcome?`
    - `toStageId?`
    - `toStageName?`
    - `toStageFormat?`
    - `toStageOrder?`
- `updatedAt?`

Rules:
- `404 COMPETITION_SEASON_NOT_FOUND` if the edition is not configured.
- `meta.coverage` required.

---

## 2.2.8 GET `/group-standings`

Purpose:
- Return the standings table of a single group, always scoped by `competitionKey + seasonLabel + stageId + groupId`.

Query params:
- required:
  - `competitionKey`
  - `seasonLabel`
  - `stageId`
  - `groupId`
- optional:
  - `roundId`

Response `data` shape:
- same base contract of `/standings`, always with `group` populated and `stage.stageFormat = group_table`

Rules:
- `400 INVALID_QUERY_PARAM` if `stageId` does not point to a grouped stage.
- `400 INVALID_QUERY_PARAM` if `groupId` does not exist inside the informed stage.
- `meta.coverage` required.

---

## 2.2.9 GET `/ties`

Purpose:
- Return all knockout ties of a specific stage in a competition edition.

Query params:
- required:
  - `competitionKey`
  - `seasonLabel`
  - `stageId`

Response `data` shape:
- `competition`
- `stage`
- `ties[]`
  - `tieId`
  - `tieOrder`
  - `homeTeamId`
  - `homeTeamName`
  - `awayTeamId`
  - `awayTeamName`
  - `matchCount`
  - `firstLegAt?`
  - `lastLegAt?`
  - `homeGoals`
  - `awayGoals`
  - `winnerTeamId?`
  - `winnerTeamName?`
  - `resolutionType?`
  - `hasExtraTimeMatch`
  - `hasPenaltiesMatch`
  - `nextStageId?`
  - `nextStageName?`

Rules:
- `400 INVALID_QUERY_PARAM` if the informed stage is not knockout or qualification knockout.
- `meta.coverage` required.

---

## 2.2.10 GET `/team-progression`

Purpose:
- Return the structural trajectory of a team across one competition edition.

Query params:
- required:
  - `competitionKey`
  - `seasonLabel`
  - `teamId`

Response `data` shape:
- `competition`
- `team`
  - `teamId`
  - `teamName?`
- `progression[]`
  - `progressionId`
  - `fromStageId`
  - `fromStageName?`
  - `fromStageFormat?`
  - `fromStageOrder?`
  - `toStageId?`
  - `toStageName?`
  - `toStageFormat?`
  - `toStageOrder?`
  - `progressionScope`
  - `progressionType`
  - `sourcePosition?`
  - `tieOutcome?`
  - `groupId?`
  - `groupName?`

Rules:
- `404 TEAM_PROGRESSION_NOT_FOUND` if the team has no validated progression rows in the requested competition edition.
- `meta.coverage` required.

---

## 2.3 GET `/rankings/{rankingType}`

Purpose:
- Generic ranking endpoint driven by `rankingType`.

Path params:
- `rankingType` (required)

`rankingType` must be compatible with frontend registry (`frontend/src/config/ranking.registry.ts`).

Current required values:
- `player-goals`
- `player-assists`
- `player-shots-total`
- `player-shots-on-target`
- `player-pass-accuracy`
- `player-rating`
- `player-yellow-cards`
- `team-possession`
- `team-pass-accuracy`

Query params:
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `search` (string)
  - `minSampleValue` (int >= 0)
  - `freshnessClass` (`season | fast`)
- Pagination:
  - `page` (default `1`)
  - `pageSize` (default `20`)
- Sort:
  - `sortDirection` (`asc | desc`, default from ranking definition)

Request example:
```http
GET /api/v1/rankings/player-goals?competitionId=648&seasonId=2024&page=1&pageSize=50&sortDirection=desc
```

Response `data` shape:
- `RankingTableData`
  - `rankingId` (string)
  - `metricKey` (string)
  - `rows` (`RankingTableRow[]`)
  - `updatedAt?` (ISO datetime)

`RankingTableRow` minimum:
- `entityId` (required)
- optional: `entityName`, `rank`, `metricValue`, and extra ranking columns

Rules:
- `400 INVALID_RANKING_TYPE` if unsupported.
- `meta.pagination` required.
- `meta.coverage` expected.

---

## 2.4 GET `/matches`

Purpose:
- Match list with summary context.

Query params:
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `search` (string)
  - `status` (`scheduled | live | finished | cancelled` or provider-compatible values)
- Pagination:
  - `page` (default `1`)
  - `pageSize` (default `20`)
- Sort:
  - `sortBy` (`kickoffAt | status | homeTeamName | awayTeamName`)
  - `sortDirection` (`asc | desc`, default `desc`)

Request example:
```http
GET /api/v1/matches?competitionId=648&seasonId=2024&status=finished&page=1&pageSize=20&sortBy=kickoffAt&sortDirection=desc
```

Response `data` shape:
- `{ items: MatchListItem[] }`
- `MatchListItem`:
  - required: `matchId`
  - optional: `fixtureId`, `competitionId`, `competitionName`, `seasonId`, `roundId`, `kickoffAt`, `status`, `venueName`, `homeTeamId`, `homeTeamName`, `awayTeamId`, `awayTeamName`, `homeScore`, `awayScore`

Rules:
- `meta.pagination` required.
- `meta.coverage` optional.

---

## 2.5 GET `/matches/{matchId}`

Purpose:
- Match center blocks (header + timeline + lineups + team stats + player stats).

Path params:
- `matchId` (required)

Query params:
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `includeTimeline` (`true|false`, default `true`)
  - `includeLineups` (`true|false`, default `true`)
  - `includeTeamStats` (`true|false`, default `true`)
  - `includePlayerStats` (`true|false`, default `true`)
- Pagination: N/A
- Sort: N/A at top-level (timeline should be chronological)

Request example:
```http
GET /api/v1/matches/m-1001?competitionId=648&seasonId=2024&lastN=10&includeTimeline=true&includeLineups=true&includeTeamStats=true&includePlayerStats=true
```

Response `data` shape:
- `MatchCenterData`
  - `match` (required)
  - `timeline?`
  - `lineups?`
  - `teamStats?`
  - `playerStats?`
  - `sectionCoverage?`
    - `timeline?` (`CoverageState`)
    - `lineups?` (`CoverageState`)
    - `teamStats?` (`CoverageState`)
    - `playerStats?` (`CoverageState`)
- `lineups` items may include:
  - `formationField?`
  - `formationPosition?`
  - `minutesPlayed?`
- `teamStats` items may include:
  - `teamId?`
  - `teamName?`
  - `totalShots?`
  - `shotsOnGoal?`
  - `possessionPct?`
  - `totalPasses?`
  - `passesAccurate?`
  - `passAccuracyPct?`
  - `corners?`
  - `fouls?`
  - `yellowCards?`
  - `redCards?`
  - `goalkeeperSaves?`
- `playerStats` items may include:
  - `positionName?`
  - `isStarter?`
  - `shotsOnGoal?`
  - `passesTotal?`
  - `keyPasses?`
  - `tackles?`
  - `interceptions?`
  - `duels?`
  - `foulsCommitted?`
  - `yellowCards?`
  - `redCards?`
  - `goalkeeperSaves?`
  - `cleanSheets?`
  - `xg?`
  - `rating?`

Rules:
- `404 MATCH_NOT_FOUND` if missing.
- `meta.coverage` expected and must summarize the requested match-center blocks.
- `data.sectionCoverage` should expose independent `coverage-state` for `timeline`, `lineups`, `teamStats` and `playerStats`.

---

## 2.6 GET `/insights`

Purpose:
- Return insight feed for a given context.

Query params:
- Context:
  - `entityType` (required): `player | team | match | competition | global`
  - `entityId` (required when `entityType != global`)
- Global + time: `competitionId`, `seasonId`, `roundId`, `venue`, `lastN` or `dateStart/dateEnd`
- Local:
  - `severity` (`info | warning | critical`)
- Pagination (optional):
  - `page`, `pageSize`
- Sort (optional):
  - `sortBy` (`severity | referencePeriod`)
  - `sortDirection` (`asc | desc`)
  - default recommended: highest severity first

Request example:
```http
GET /api/v1/insights?entityType=player&entityId=p-1&competitionId=648&seasonId=2024&lastN=5
```

Response `data` shape:
- `InsightObject[]`
- `InsightObject`:
  - `insight_id`
  - `severity`
  - `explanation`
  - `evidences` (`Record<string, number>`)
  - `reference_period`
  - `data_source` (`string[]`)

Rules:
- `400 INVALID_INSIGHT_CONTEXT` for invalid context.
- `meta.coverage` expected.
- `meta.pagination` required only when pagination is requested/supported.

---

## 3) Recommended Error Codes

| HTTP | code | When to use |
|---|---|---|
| 400 | `INVALID_QUERY_PARAM` | invalid param type/enum/range |
| 400 | `INVALID_TIME_RANGE` | invalid `lastN` vs `dateStart/dateEnd` combination |
| 400 | `INVALID_RANKING_TYPE` | unsupported `rankingType` |
| 400 | `INVALID_INSIGHT_CONTEXT` | invalid `entityType/entityId` combination |
| 404 | `PLAYER_NOT_FOUND` | unknown player |
| 404 | `TEAM_NOT_FOUND` | unknown team |
| 404 | `MATCH_NOT_FOUND` | unknown match |
| 429 | `RATE_LIMITED` | rate limit exceeded |
| 500 | `INTERNAL_ERROR` | unexpected BFF error |

---

## 4) Frontend Compatibility Checklist

- Frontend base url + path must target `/api/v1`.
- `rankingType` must stay compatible with `ranking.registry.ts`.
- Success responses must follow `ApiResponse<T>`.
- Coverage must be present when applicable to support `loading/empty/partial/error` UX states.
- Errors must follow `ApiError` standard so frontend can render predictable fallback messages.
