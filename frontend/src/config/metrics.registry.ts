import type { MetricDefinition, MetricRegistry } from "@/config/metrics.types";
import {
  formatMinutes,
  formatNumber,
  formatPercentage,
  formatRating,
  formatSeconds,
  formatWithUnit,
} from "@/shared/utils/formatters";

const METRICS_LIST: MetricDefinition[] = [
  {
    key: "goals",
    label: "Gols",
    description: "Total de gols no recorte selecionado.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.player_match_summary", "mart.player_season_summary"],
  },
  {
    key: "assists",
    label: "Assistências",
    description: "Total de assistências no recorte selecionado.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.player_match_summary", "mart.player_season_summary"],
  },
  {
    key: "shots_total",
    label: "Finalizações",
    description: "Total de finalizações.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.fact_fixture_player_stats", "raw.fixture_player_statistics"],
  },
  {
    key: "shots_on_target",
    label: "Finalizações no alvo",
    description: "Total de finalizações no alvo.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.fact_fixture_player_stats", "raw.fixture_player_statistics"],
  },
  {
    key: "passes_completed",
    label: "Passes certos",
    description: "Total de passes certos.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.fact_fixture_player_stats", "raw.fixture_player_statistics"],
  },
  {
    key: "passes_attempted",
    label: "Passes tentados",
    description: "Total de passes tentados.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.fact_fixture_player_stats", "raw.fixture_player_statistics"],
  },
  {
    key: "pass_accuracy_pct",
    label: "Precisão de passe",
    description: "Percentual de acerto de passe.",
    format: "percentage",
    precision: 1,
    entity: "player",
    normalizable: false,
    sourceHints: ["mart.player_match_summary", "raw.fixture_player_statistics"],
  },
  {
    key: "minutes_played",
    label: "Minutos jogados",
    description: "Tempo em campo no recorte selecionado.",
    format: "minutes",
    precision: 0,
    entity: "player",
    normalizable: false,
    sourceHints: ["mart.fact_fixture_player_stats", "mart.player_season_summary"],
  },
  {
    key: "yellow_cards",
    label: "Cartões amarelos",
    description: "Total de cartões amarelos.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    coverageWarning: "A cobertura pode variar conforme a fonte em partidas antigas.",
    sourceHints: ["mart.player_match_summary", "raw.match_statistics"],
  },
  {
    key: "cards_total",
    label: "Cartões",
    description: "Total de cartões (amarelos + vermelhos).",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    coverageWarning: "A cobertura pode variar conforme a fonte em partidas antigas.",
    sourceHints: ["mart.player_match_summary", "raw.match_statistics"],
  },
  {
    key: "red_cards",
    label: "Cartões vermelhos",
    description: "Total de cartões vermelhos.",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    coverageWarning: "A cobertura pode variar conforme a fonte em partidas antigas.",
    sourceHints: ["mart.player_match_summary", "raw.match_statistics"],
  },
  {
    key: "saves",
    label: "Defesas",
    description: "Defesas realizadas (goleiros).",
    format: "number",
    precision: 0,
    entity: "player",
    normalizable: true,
    sourceHints: ["mart.fact_fixture_player_stats", "raw.fixture_player_statistics"],
  },
  {
    key: "team_possession_pct",
    label: "Posse de bola",
    description: "Posse média do time no recorte selecionado.",
    format: "percentage",
    precision: 1,
    entity: "team",
    normalizable: false,
    sourceHints: ["raw.match_statistics", "mart.team_monthly_stats"],
  },
  {
    key: "team_pass_accuracy_pct",
    label: "Precisão de passe do time",
    description: "Percentual de acerto de passe do time.",
    format: "percentage",
    precision: 1,
    entity: "team",
    normalizable: false,
    sourceHints: ["raw.match_statistics", "mart.team_monthly_stats"],
  },
  {
    key: "player_rating",
    label: "Nota",
    description: "Nota de desempenho do jogador.",
    format: "rating",
    precision: 2,
    entity: "player",
    normalizable: false,
    coverageWarning: "A nota depende da disponibilidade da fonte de origem.",
    sourceHints: ["mart.player_match_summary", "raw.fixture_player_statistics"],
  },
];

function createMetricsRegistry(metrics: MetricDefinition[]): MetricRegistry {
  return metrics.reduce<MetricRegistry>((registry, metric) => {
    if (registry[metric.key]) {
      throw new Error(`Duplicate metric key detected in registry: ${metric.key}`);
    }

    registry[metric.key] = metric;
    return registry;
  }, {});
}

function formatValueByDefinition(metric: MetricDefinition, value: number): string {
  const precision = metric.precision ?? 0;

  switch (metric.format) {
    case "percentage":
      return formatPercentage(value, precision);
    case "rating":
      return formatRating(value, precision);
    case "seconds":
      return formatSeconds(value, precision);
    case "minutes":
      return formatMinutes(value, precision);
    case "number":
    default:
      return formatWithUnit(formatNumber(value, precision), metric.unit);
  }
}

export const METRICS_REGISTRY: Readonly<MetricRegistry> = Object.freeze(createMetricsRegistry(METRICS_LIST));

export function getMetric(key: string): MetricDefinition | undefined {
  return METRICS_REGISTRY[key];
}

export function formatMetricValue(key: string, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || !Number.isFinite(value)) {
    return "-";
  }

  const metric = getMetric(key);

  if (!metric) {
    return formatNumber(value);
  }

  return formatValueByDefinition(metric, value);
}
