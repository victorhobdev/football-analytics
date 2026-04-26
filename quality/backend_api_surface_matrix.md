# Backend API surface matrix

Status reviewed on 2026-04-26 during the final cleanup pass.

## Canonical routes

| Domain | Canonical route | Notes |
| --- | --- | --- |
| Standings | `/api/v1/standings` | Canonical standings contract. Uses `competitionId`, `seasonId`, optional `stageId` and `groupId`. |
| Team journey | `/api/v1/team-journey-history` | Current frontend consumer for historical team journey. |
| Rankings | `/api/v1/rankings/{rankingType}` | Only configured/materialized ranking types should behave as successful data routes. |

## Compatibility routes

| Route | Status | Temporary rule |
| --- | --- | --- |
| `/api/v1/group-standings` | Deprecated compatibility route | Keep for existing consumers. Do not remove until frontend and external usage are validated from logs. |

## Explicitly unavailable routes

| Route | Status | Reason |
| --- | --- | --- |
| `/api/v1/insights` | Deprecated and returns `501` | Placeholder route. It should not return `200` with empty data until real insight data exists. |
| `/api/v1/rankings/player-pass-accuracy` | Returns `501` | Metric is configured in backend as unsupported because it is not materialized for player rankings. |

## Candidate legacy routes

| Route | Status | Required validation before removal |
| --- | --- | --- |
| `/api/v1/team-progression` | Deprecated candidate legacy route | Frontend search only found `team-journey-history`. Keep route until API logs confirm no external usage. |

## Not changed in this pass

- No public route was removed.
- No frontend consumer was changed.
- Serving-layer migrations for standings and market remain separate database work.
- Broad service/repository extraction remains out of scope for this cleanup pass.
