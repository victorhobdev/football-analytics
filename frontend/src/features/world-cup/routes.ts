function normalizePathSegment(value: string): string {
  return encodeURIComponent(value.trim());
}

export function buildWorldCupHubPath(): string {
  return "/copa-do-mundo";
}

export function buildWorldCupEditionPath(seasonLabel: string): string {
  return `/copa-do-mundo/${normalizePathSegment(seasonLabel)}`;
}

export function buildWorldCupTeamsPath(): string {
  return "/copa-do-mundo/selecoes";
}

export function buildWorldCupTeamPath(teamId: string): string {
  return `/copa-do-mundo/selecoes/${normalizePathSegment(teamId)}`;
}

export function buildWorldCupRankingsPath(): string {
  return "/copa-do-mundo/rankings";
}

export function buildWorldCupFinalsPath(): string {
  return "/copa-do-mundo/finais";
}
