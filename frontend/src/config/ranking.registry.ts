import { METRICS_REGISTRY, getMetric } from "@/config/metrics.registry";
import type { RankingDefinition, RankingEntity, RankingRegistry } from "@/config/ranking.types";

// Adicionar ranking = adicionar entrada no registry; nao criar componente novo.
type RegisteredMetricKey = keyof typeof METRICS_REGISTRY;
type RegistryRankingDefinition = Omit<RankingDefinition, "metricKey"> & {
  metricKey: RegisteredMetricKey;
};

const RANKINGS_LIST: RegistryRankingDefinition[] = [
  {
    id: "player-goals",
    label: "Artilharia",
    description: "Jogadores com mais gols no recorte selecionado.",
    entity: "player",
    metricKey: "goals",
    endpoint: "/api/v1/rankings/player-goals",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
  {
    id: "player-assists",
    label: "Assistências",
    description: "Jogadores com mais assistências no recorte selecionado.",
    entity: "player",
    metricKey: "assists",
    endpoint: "/api/v1/rankings/player-assists",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
  {
    id: "player-shots-total",
    label: "Finalizações",
    description: "Jogadores com mais finalizações totais.",
    entity: "player",
    metricKey: "shots_total",
    endpoint: "/api/v1/rankings/player-shots-total",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
  {
    id: "player-shots-on-target",
    label: "Finalizações no alvo",
    description: "Jogadores com mais finalizações no alvo.",
    entity: "player",
    metricKey: "shots_on_target",
    endpoint: "/api/v1/rankings/player-shots-on-target",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
  {
    id: "player-rating",
    label: "Nota",
    description: "Jogadores com melhor nota média no recorte.",
    entity: "player",
    metricKey: "player_rating",
    endpoint: "/api/v1/rankings/player-rating",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
    coverageWarning: "A nota depende da disponibilidade da fonte de origem.",
  },
  {
    id: "player-cards",
    label: "Cartões",
    description: "Jogadores com mais cartões no recorte (amarelos + vermelhos).",
    entity: "player",
    metricKey: "cards_total",
    endpoint: "/api/v1/rankings/player-cards",
    defaultSort: "desc",
    minSample: { field: "minutes_played", min: 1800 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
    coverageWarning: "A cobertura de cartões pode variar conforme a fonte.",
  },
  {
    id: "team-possession",
    label: "Posse de bola",
    description: "Times com maior posse média no recorte selecionado.",
    entity: "team",
    metricKey: "team_possession_pct",
    endpoint: "/api/v1/rankings/team-possession",
    defaultSort: "desc",
    minSample: { field: "matches_played", min: 20 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
  {
    id: "team-pass-accuracy",
    label: "Precisão de passe do time",
    description: "Times com melhor precisão de passe no recorte selecionado.",
    entity: "team",
    metricKey: "team_pass_accuracy_pct",
    endpoint: "/api/v1/rankings/team-pass-accuracy",
    defaultSort: "desc",
    minSample: { field: "matches_played", min: 20 },
    availableFilters: ["competitionId", "seasonId", "roundId", "venue", "lastN", "dateRange"],
  },
];

function createRankingRegistry(rankings: RegistryRankingDefinition[]): RankingRegistry {
  return rankings.reduce<RankingRegistry>((registry, ranking) => {
    if (registry[ranking.id]) {
      throw new Error(`Duplicate ranking id detected in registry: ${ranking.id}`);
    }

    if (!getMetric(ranking.metricKey)) {
      throw new Error(
        `Unknown metric key "${ranking.metricKey}" in ranking "${ranking.id}". Add the metric to metrics.registry.ts first.`,
      );
    }

    const metric = getMetric(ranking.metricKey);

    registry[ranking.id] = {
      ...ranking,
      format: ranking.format ?? metric?.format,
      coverageWarning: ranking.coverageWarning ?? metric?.coverageWarning,
    };

    return registry;
  }, {});
}

const LEGACY_RANKING_ALIASES: Record<string, string> = {
  "player-yellow-cards": "player-cards",
};

export function normalizeRankingType(rankingType: string): string {
  return LEGACY_RANKING_ALIASES[rankingType] ?? rankingType;
}

export const RANKING_REGISTRY: Readonly<RankingRegistry> = Object.freeze(createRankingRegistry(RANKINGS_LIST));

export const RANKING_DEFINITIONS: ReadonlyArray<RankingDefinition> = Object.freeze(Object.values(RANKING_REGISTRY));

export function getRankingDefinition(rankingType: string): RankingDefinition | undefined {
  return RANKING_REGISTRY[normalizeRankingType(rankingType)];
}

export function listRankingsByEntity(entity: RankingEntity): RankingDefinition[] {
  return RANKING_DEFINITIONS.filter((ranking) => ranking.entity === entity);
}
