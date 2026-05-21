"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getCompetitionById } from "@/config/competitions.registry";
import { getSeasonById } from "@/config/seasons.registry";
import { usePlayerProfile } from "@/features/players/hooks";
import type { PlayerProfile, PlayerProfileStats, PlayerStatsSummary } from "@/features/players/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfileCoveragePill, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange, type NormalizedTimeRangeParams } from "@/shared/hooks/useTimeRange";
import { useComparisonStore } from "@/shared/stores/comparison.store";
import type { CoverageState } from "@/shared/types/coverage.types";
import { formatNumber } from "@/shared/utils/formatters";

type MetricMode = "totals" | "per90";
type MetricModeAvailability = "all" | "totalOnly" | "normalized";
type MetricGroupIcon = "overview" | "attack" | "pass" | "discipline";
type LeaderSide = "left" | "right" | "tie" | null;

type ComparisonMetricConfig = {
  id: string;
  label: string;
  modeAvailability: MetricModeAvailability;
  higherIsBetter?: boolean;
  totalValue: (summary: PlayerStatsSummary | undefined) => number | null;
  per90Value?: (stats: PlayerProfileStats | null | undefined) => number | null;
  format: (value: number) => string;
};

type MetricGroupConfig = {
  id: string;
  title: string;
  icon: MetricGroupIcon;
  metrics: ComparisonMetricConfig[];
};

const POSITION_LABELS: Record<string, string> = {
  attacker: "Atacante",
  attackingmidfield: "Meia atacante",
  attackingmidfielder: "Meia atacante",
  cam: "Meia atacante",
  centerback: "Zagueiro",
  centralmidfield: "Meia",
  centralmidfielder: "Meia",
  centreback: "Zagueiro",
  defensivemidfield: "Volante",
  defensivemidfielder: "Volante",
  defender: "Defensor",
  dm: "Volante",
  forward: "Atacante",
  goalkeeper: "Goleiro",
  gk: "Goleiro",
  leftback: "Lateral esquerdo",
  leftwing: "Ponta esquerda",
  leftwinger: "Ponta esquerda",
  midfielder: "Meia",
  rightback: "Lateral direito",
  rightwing: "Ponta direita",
  rightwinger: "Ponta direita",
  striker: "Centroavante",
};

const METRIC_GROUPS: MetricGroupConfig[] = [
  {
    id: "overview",
    title: "Visão geral",
    icon: "overview",
    metrics: [
      {
        id: "rating",
        label: "Nota média",
        modeAvailability: "all",
        totalValue: (summary) => safeNumber(summary?.rating),
        format: formatRatingValue,
      },
      {
        id: "goal_involvement",
        label: "Gols + assists",
        modeAvailability: "normalized",
        totalValue: (summary) => sumIfAny(summary?.goals, summary?.assists),
        per90Value: (stats) => safeNumber(stats?.goalContributionsPer90),
        format: formatDecimalCompact,
      },
      {
        id: "minutes",
        label: "Minutos",
        modeAvailability: "totalOnly",
        totalValue: (summary) => safeNumber(summary?.minutesPlayed),
        format: formatMinutesValue,
      },
    ],
  },
  {
    id: "attack",
    title: "Produção ofensiva",
    icon: "attack",
    metrics: [
      {
        id: "goals",
        label: "Gols",
        modeAvailability: "normalized",
        totalValue: (summary) => safeNumber(summary?.goals),
        per90Value: (stats) => safeNumber(stats?.goalsPer90),
        format: formatDecimalCompact,
      },
      {
        id: "assists",
        label: "Assists",
        modeAvailability: "normalized",
        totalValue: (summary) => safeNumber(summary?.assists),
        per90Value: (stats) => safeNumber(stats?.assistsPer90),
        format: formatDecimalCompact,
      },
      {
        id: "shots",
        label: "Chutes",
        modeAvailability: "normalized",
        totalValue: (summary) => safeNumber(summary?.shotsTotal),
        per90Value: (stats) => safeNumber(stats?.shotsPer90),
        format: formatDecimalCompact,
      },
      {
        id: "shots_on_target",
        label: "Chutes no alvo",
        modeAvailability: "normalized",
        totalValue: (summary) => safeNumber(summary?.shotsOnTarget),
        per90Value: (stats) => safeNumber(stats?.shotsOnTargetPer90),
        format: formatDecimalCompact,
      },
    ],
  },
  {
    id: "pass",
    title: "Construção / passe",
    icon: "pass",
    metrics: [
      {
        id: "passes_attempted",
        label: "Passes tentados",
        modeAvailability: "normalized",
        totalValue: (summary) => safeNumber(summary?.passesAttempted),
        per90Value: (stats) => safeNumber(stats?.passesAttemptedPer90),
        format: formatDecimalCompact,
      },
      {
        id: "pass_accuracy",
        label: "Precisão de passe",
        modeAvailability: "all",
        totalValue: (summary) => safeNumber(summary?.passAccuracyPct),
        format: formatPercentageValue,
      },
    ],
  },
  {
    id: "discipline",
    title: "Disciplina",
    icon: "discipline",
    metrics: [
      {
        id: "yellow_cards",
        label: "Amarelos",
        modeAvailability: "normalized",
        higherIsBetter: false,
        totalValue: (summary) => safeNumber(summary?.yellowCards),
        per90Value: (stats) => safeNumber(stats?.yellowCardsPer90),
        format: formatDecimalCompact,
      },
      {
        id: "red_cards",
        label: "Vermelhos",
        modeAvailability: "normalized",
        higherIsBetter: false,
        totalValue: (summary) => safeNumber(summary?.redCards),
        per90Value: (stats) => safeNumber(stats?.redCardsPer90),
        format: formatDecimalCompact,
      },
    ],
  },
];

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function safeNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sumIfAny(...values: Array<number | null | undefined>): number | null {
  let total = 0;
  let hasValue = false;

  for (const value of values) {
    const normalizedValue = safeNumber(value);

    if (normalizedValue !== null) {
      total += normalizedValue;
      hasValue = true;
    }
  }

  return hasValue ? total : null;
}

function formatIntegerValue(value: number | null | undefined): string {
  const normalizedValue = safeNumber(value);
  return normalizedValue === null ? "Sem dados" : formatNumber(normalizedValue, 0);
}

function formatDecimalCompact(value: number): string {
  const precision = Number.isInteger(value) ? 0 : 2;
  return formatNumber(value, precision);
}

function formatMinutesValue(value: number): string {
  return `${formatNumber(value, 0)} min`;
}

function formatPercentageValue(value: number): string {
  return `${formatNumber(value, 1)}%`;
}

function formatRatingValue(value: number): string {
  return formatNumber(value, 2);
}

function normalizePositionKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z]/g, "")
    .toLowerCase();
}

function formatPosition(position: string | null | undefined): string {
  if (!position) {
    return "Sem posição";
  }

  const normalizedPosition = position.trim();
  const mappedPosition = POSITION_LABELS[normalizePositionKey(normalizedPosition)];

  if (mappedPosition) {
    return mappedPosition;
  }

  if (normalizedPosition.length <= 3) {
    return normalizedPosition.toUpperCase();
  }

  return normalizedPosition;
}

function getInitials(value: string | null | undefined): string {
  const normalizedValue = value?.trim();

  if (!normalizedValue) {
    return "FA";
  }

  const parts = normalizedValue.split(/\s+/).filter(Boolean);
  const initials = parts.length === 1 ? parts[0]?.slice(0, 2) : `${parts[0]?.[0] ?? ""}${parts[parts.length - 1]?.[0] ?? ""}`;

  return initials.toUpperCase();
}

function toDisplayName(playerId: string, playerName: string | null | undefined): string {
  const normalizedName = playerName?.trim();
  return normalizedName && normalizedName.length > 0 ? normalizedName : `Jogador ${playerId}`;
}

function toShortName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);

  if (parts.length <= 2) {
    return name;
  }

  return `${parts[0]} ${parts[parts.length - 1]}`;
}

function describeTimeWindow(params: NormalizedTimeRangeParams): string {
  if (params.roundId) {
    return `Rodada ${params.roundId}`;
  }

  if (params.lastN !== null) {
    return `Últimos ${params.lastN} jogos`;
  }

  if (params.dateRangeStart && params.dateRangeEnd) {
    return `${params.dateRangeStart} a ${params.dateRangeEnd}`;
  }

  if (params.dateRangeStart) {
    return `Desde ${params.dateRangeStart}`;
  }

  if (params.dateRangeEnd) {
    return `Até ${params.dateRangeEnd}`;
  }

  return "Todos os jogos do recorte";
}

function describeVenue(venue: string): string {
  if (venue === "home") {
    return "Casa";
  }

  if (venue === "away") {
    return "Fora";
  }

  return "Casa e fora";
}

function resolveCoverageStatus(coverages: CoverageState[]): CoverageState {
  if (coverages.length === 0) {
    return { status: "unknown", label: "Dados em verificação" };
  }

  if (coverages.some((coverage) => coverage.status === "partial")) {
    return { status: "partial", label: "Dados parciais" };
  }

  if (coverages.every((coverage) => coverage.status === "complete")) {
    return { status: "complete", label: "Dados completos" };
  }

  if (coverages.every((coverage) => coverage.status === "empty")) {
    return { status: "empty", label: "Sem dados" };
  }

  if (coverages.some((coverage) => coverage.status === "empty")) {
    return { status: "partial", label: "Dados incompletos" };
  }

  return { status: "unknown", label: "Dados em verificação" };
}

function getMetricValue(
  metric: ComparisonMetricConfig,
  profile: PlayerProfile | undefined,
  mode: MetricMode,
): number | null {
  if (!profile) {
    return null;
  }

  if (mode === "per90") {
    if (metric.modeAvailability === "totalOnly") {
      return null;
    }

    if (metric.modeAvailability === "normalized") {
      return metric.per90Value?.(profile.stats) ?? null;
    }
  }

  return metric.totalValue(profile.summary);
}

function hasMetricData(
  metric: ComparisonMetricConfig,
  leftProfile: PlayerProfile | undefined,
  rightProfile: PlayerProfile | undefined,
  mode: MetricMode,
): boolean {
  return getMetricValue(metric, leftProfile, mode) !== null || getMetricValue(metric, rightProfile, mode) !== null;
}

function resolveLeader(
  leftValue: number | null,
  rightValue: number | null,
  higherIsBetter = true,
): LeaderSide {
  if (leftValue === null || rightValue === null) {
    return null;
  }

  if (Math.abs(leftValue - rightValue) < 0.0001) {
    return "tie";
  }

  if (higherIsBetter) {
    return leftValue > rightValue ? "left" : "right";
  }

  return leftValue < rightValue ? "left" : "right";
}

function buildComparisonSummary(
  leftName: string,
  rightName: string,
  leftSummary: PlayerStatsSummary | undefined,
  rightSummary: PlayerStatsSummary | undefined,
): string {
  const leftShortName = toShortName(leftName);
  const rightShortName = toShortName(rightName);
  const signals: Array<{ side: Exclude<LeaderSide, "tie" | null>; text: string }> = [];
  const leftGoalInvolvement = sumIfAny(leftSummary?.goals, leftSummary?.assists);
  const rightGoalInvolvement = sumIfAny(rightSummary?.goals, rightSummary?.assists);
  const goalInvolvementLeader = resolveLeader(leftGoalInvolvement, rightGoalInvolvement);
  const shotsLeader = resolveLeader(safeNumber(leftSummary?.shotsTotal), safeNumber(rightSummary?.shotsTotal));
  const minutesLeader = resolveLeader(safeNumber(leftSummary?.minutesPlayed), safeNumber(rightSummary?.minutesPlayed));
  const ratingLeader = resolveLeader(safeNumber(leftSummary?.rating), safeNumber(rightSummary?.rating));

  if (goalInvolvementLeader === "left" || goalInvolvementLeader === "right") {
    signals.push({ side: goalInvolvementLeader, text: "participa mais de gols" });
  }

  if (shotsLeader === "left" || shotsLeader === "right") {
    signals.push({ side: shotsLeader, text: "chuta mais" });
  }

  if (minutesLeader === "left" || minutesLeader === "right") {
    signals.push({ side: minutesLeader, text: "teve mais minutos em campo" });
  }

  if (ratingLeader === "left" || ratingLeader === "right") {
    signals.push({ side: ratingLeader, text: "tem nota média maior" });
  }

  if (signals.length === 0) {
    return "Comparação pronta para o recorte selecionado.";
  }

  const firstSignal = signals[0];
  const secondSignal = signals.find((signal, index) => index > 0 && signal.side === firstSignal.side) ?? signals[1];
  const firstName = firstSignal.side === "left" ? leftShortName : rightShortName;

  if (secondSignal && secondSignal.side === firstSignal.side) {
    return `${firstName} ${firstSignal.text} e ${secondSignal.text}.`;
  }

  if (secondSignal) {
    const secondName = secondSignal.side === "left" ? leftShortName : rightShortName;
    return `${firstName} ${firstSignal.text}. ${secondName} ${secondSignal.text}.`;
  }

  return `${firstName} ${firstSignal.text}.`;
}

function MetricGroupIcon({ icon }: { icon: MetricGroupIcon }) {
  const sharedPathClassName = "stroke-current";

  if (icon === "attack") {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
        <circle className={sharedPathClassName} cx="12" cy="12" r="7.5" strokeWidth="1.7" />
        <path className={sharedPathClassName} d="M12 4.5v15M4.5 12h15" strokeLinecap="round" strokeWidth="1.2" />
      </svg>
    );
  }

  if (icon === "pass") {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
        <path className={sharedPathClassName} d="M5 8h9m-4-4 4 4-4 4M19 16h-9m4-4-4 4 4 4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
      </svg>
    );
  }

  if (icon === "discipline") {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
        <path className={sharedPathClassName} d="M8 5h8l-1 14H9L8 5Z" strokeLinejoin="round" strokeWidth="1.7" />
        <path className={sharedPathClassName} d="M10 9h4" strokeLinecap="round" strokeWidth="1.7" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
      <path className={sharedPathClassName} d="M5 18V10M12 18V6M19 18V13" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

type PlayerCardProps = {
  displayName: string;
  profile: PlayerProfile | undefined;
  side: "left" | "right";
};

function PlayerCard({ displayName, profile, side }: PlayerCardProps) {
  const player = profile?.player;
  const summary = profile?.summary;
  const teamName = player?.teamName?.trim() || "Clube não informado";
  const nationality = player?.nationality?.trim() || "Nacionalidade não informada";
  const sideLabel = side === "left" ? "Esquerda" : "Direita";

  return (
    <article
      className={joinClasses(
        "relative overflow-hidden rounded-[1.65rem] border p-4 text-white shadow-[0_26px_72px_-54px_rgba(0,53,38,0.72)] md:p-5",
        side === "left"
          ? "border-emerald-200/14 bg-[radial-gradient(circle_at_top_left,rgba(139,214,182,0.28),transparent_44%),linear-gradient(135deg,#06271d_0%,#0b3c2d_56%,#0f513c_100%)]"
          : "border-sky-200/14 bg-[radial-gradient(circle_at_top_right,rgba(175,210,255,0.22),transparent_44%),linear-gradient(135deg,#0d1f34_0%,#14395d_58%,#1f557a_100%)]",
      )}
    >
      <div className="flex items-start gap-4">
        <ProfileMedia
          alt={`Foto de ${displayName}`}
          assetId={player?.playerId}
          category="players"
          className="h-20 w-20 border-white/18 bg-white/12"
          fallback={getInitials(displayName)}
          fallbackClassName="text-white"
          shape="circle"
          tone="contrast"
        />

        <div className="min-w-0 flex-1">
          <p className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-white/56">{sideLabel}</p>
          <h3 className="mt-1 truncate font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.03em]">
            {displayName}
          </h3>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/12 px-2.5 py-1 text-xs font-semibold text-white/86">
              <ProfileMedia
                alt={`Escudo de ${teamName}`}
                assetId={player?.teamId}
                category="clubs"
                className="h-6 w-6 rounded-full border-white/18 bg-white/12"
                fallback={getInitials(teamName)}
                fallbackClassName="text-[0.54rem] text-white"
                imageClassName="p-0.5"
                shape="circle"
                tone="contrast"
              />
              <span className="max-w-[10rem] truncate">{teamName}</span>
            </span>
            <span className="rounded-full bg-white/12 px-2.5 py-1 text-xs font-semibold text-white/78">
              {formatPosition(player?.position)}
            </span>
            <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-medium text-white/70">
              {nationality}
            </span>
          </div>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-3 gap-2">
        <div className="rounded-[1rem] bg-white/10 px-3 py-3">
          <dt className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-white/52">Jogos</dt>
          <dd className="mt-1 font-[family:var(--font-profile-headline)] text-xl font-extrabold">
            {formatIntegerValue(summary?.matchesPlayed)}
          </dd>
        </div>
        <div className="rounded-[1rem] bg-white/10 px-3 py-3">
          <dt className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-white/52">Min</dt>
          <dd className="mt-1 font-[family:var(--font-profile-headline)] text-xl font-extrabold">
            {formatIntegerValue(summary?.minutesPlayed)}
          </dd>
        </div>
        <div className="rounded-[1rem] bg-white/10 px-3 py-3">
          <dt className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-white/52">Nota</dt>
          <dd className="mt-1 font-[family:var(--font-profile-headline)] text-xl font-extrabold">
            {summary?.rating === null || summary?.rating === undefined ? "Sem dados" : formatRatingValue(summary.rating)}
          </dd>
        </div>
      </dl>
    </article>
  );
}

type MetricValueProps = {
  isLeader: boolean;
  side: "left" | "right";
  value: number | null;
  formatter: (value: number) => string;
};

function MetricValue({ formatter, isLeader, side, value }: MetricValueProps) {
  return (
    <div className={joinClasses("flex min-w-[5.5rem] items-center gap-2", side === "left" ? "justify-start md:justify-end" : "justify-start")}>
      <span
        className={joinClasses(
          "inline-flex min-w-[4.4rem] justify-center rounded-full px-2.5 py-1 text-sm font-bold tabular-nums",
          value === null
            ? "bg-[rgba(240,243,255,0.7)] text-[#8190a3]"
            : isLeader
              ? "bg-[#003526] text-white"
              : "bg-white text-[#1f2d40]",
        )}
      >
        {value === null ? "Sem dados" : formatter(value)}
      </span>
      {isLeader ? (
        <span className="hidden rounded-full bg-[#d8e3fb] px-2 py-0.5 text-[0.56rem] font-bold uppercase tracking-[0.14em] text-[#305c4a] sm:inline-flex">
          Destaque
        </span>
      ) : null}
    </div>
  );
}

type MetricComparisonRowProps = {
  leftName: string;
  leftProfile: PlayerProfile | undefined;
  metric: ComparisonMetricConfig;
  mode: MetricMode;
  rightName: string;
  rightProfile: PlayerProfile | undefined;
};

function MetricComparisonRow({
  leftName,
  leftProfile,
  metric,
  mode,
  rightName,
  rightProfile,
}: MetricComparisonRowProps) {
  const leftValue = getMetricValue(metric, leftProfile, mode);
  const rightValue = getMetricValue(metric, rightProfile, mode);
  const leader = resolveLeader(leftValue, rightValue, metric.higherIsBetter ?? true);
  const leftMagnitude = Math.max(0, leftValue ?? 0);
  const rightMagnitude = Math.max(0, rightValue ?? 0);
  const maxMagnitude = Math.max(leftMagnitude, rightMagnitude);
  const leftBarWidth = maxMagnitude > 0 ? Math.max(8, (leftMagnitude / maxMagnitude) * 100) : 8;
  const rightBarWidth = maxMagnitude > 0 ? Math.max(8, (rightMagnitude / maxMagnitude) * 100) : 8;
  const leftShortName = toShortName(leftName);
  const rightShortName = toShortName(rightName);

  if (leftValue === null && rightValue === null) {
    return null;
  }

  return (
    <li className="rounded-[1.15rem] border border-[rgba(216,227,251,0.64)] bg-[rgba(248,250,255,0.72)] p-3">
      <div className="grid gap-3 md:grid-cols-[minmax(7rem,0.85fr)_minmax(14rem,1.6fr)_minmax(7rem,0.85fr)] md:items-center">
        <MetricValue formatter={metric.format} isLeader={leader === "left"} side="left" value={leftValue} />

        <div className="min-w-0">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-[#1f2d40]">{metric.label}</p>
            <span className="text-[0.68rem] font-medium text-[#748198]">
              {mode === "per90" && metric.modeAvailability === "normalized" ? "por 90 min" : "total"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5" aria-label={`${metric.label}: ${leftShortName} contra ${rightShortName}`}>
            <div className="flex h-2.5 items-center justify-end rounded-full bg-[rgba(216,227,251,0.72)]">
              <span
                className={joinClasses(
                  "block h-2.5 rounded-full",
                  leader === "left" ? "bg-[#003526]" : "bg-[#8da0bd]",
                )}
                style={{ width: `${leftBarWidth}%` }}
              />
            </div>
            <div className="flex h-2.5 items-center rounded-full bg-[rgba(216,227,251,0.72)]">
              <span
                className={joinClasses(
                  "block h-2.5 rounded-full",
                  leader === "right" ? "bg-[#003526]" : "bg-[#8da0bd]",
                )}
                style={{ width: `${rightBarWidth}%` }}
              />
            </div>
          </div>
          <div className="mt-1.5 flex justify-between text-[0.65rem] font-medium text-[#8190a3]">
            <span className="truncate">{leftShortName}</span>
            <span className="truncate text-right">{rightShortName}</span>
          </div>
        </div>

        <MetricValue formatter={metric.format} isLeader={leader === "right"} side="right" value={rightValue} />
      </div>
    </li>
  );
}

type MetricGroupProps = {
  group: MetricGroupConfig;
  leftName: string;
  leftProfile: PlayerProfile | undefined;
  mode: MetricMode;
  rightName: string;
  rightProfile: PlayerProfile | undefined;
};

function MetricGroup({
  group,
  leftName,
  leftProfile,
  mode,
  rightName,
  rightProfile,
}: MetricGroupProps) {
  const visibleMetrics = group.metrics.filter((metric) => hasMetricData(metric, leftProfile, rightProfile, mode));

  if (visibleMetrics.length === 0) {
    return null;
  }

  return (
    <section className="rounded-[1.45rem] border border-white/70 bg-white/72 p-4 shadow-[0_22px_58px_-50px_rgba(17,28,45,0.24)]">
      <header className="mb-3 flex items-center gap-2">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#e4f6ee] text-[#003526]">
          <MetricGroupIcon icon={group.icon} />
        </span>
        <h3 className="font-[family:var(--font-profile-headline)] text-lg font-extrabold text-[#111c2d]">
          {group.title}
        </h3>
      </header>
      <ul className="space-y-2">
        {visibleMetrics.map((metric) => (
          <MetricComparisonRow
            key={metric.id}
            leftName={leftName}
            leftProfile={leftProfile}
            metric={metric}
            mode={mode}
            rightName={rightName}
            rightProfile={rightProfile}
          />
        ))}
      </ul>
    </section>
  );
}

export function PlayerComparisonPanel() {
  const searchParams = useSearchParams();
  const entityType = useComparisonStore((state) => state.entityType);
  const selectedIds = useComparisonStore((state) => state.selectedIds);
  const clearSelection = useComparisonStore((state) => state.clear);
  const { competitionId, seasonId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();
  const [metricMode, setMetricMode] = useState<MetricMode>("totals");
  const stageId = searchParams.get("stageId");
  const stageFormat = searchParams.get("stageFormat");

  const leftPlayerId = selectedIds[0] ?? null;
  const rightPlayerId = selectedIds[1] ?? null;
  const leftProfileQuery = usePlayerProfile(leftPlayerId, {
    includeRecentMatches: false,
    includeHistory: false,
    includeStats: true,
    stageId,
    stageFormat,
  });
  const rightProfileQuery = usePlayerProfile(rightPlayerId, {
    includeRecentMatches: false,
    includeHistory: false,
    includeStats: true,
    stageId,
    stageFormat,
  });

  const canRenderComparison = entityType === "player" && selectedIds.length === 2;
  const competitionName = getCompetitionById(competitionId)?.name ?? "Todas as competições";
  const seasonLabel = getSeasonById(seasonId)?.label ?? "Todas as temporadas";
  const activeWindowLabel = useMemo(() => describeTimeWindow(timeRangeParams), [timeRangeParams]);

  if (entityType !== "player" || selectedIds.length === 0) {
    return null;
  }

  const combinedCoverage = resolveCoverageStatus(
    [leftProfileQuery.coverage, rightProfileQuery.coverage].filter((coverage): coverage is CoverageState => Boolean(coverage)),
  );

  const hasLoadingState = canRenderComparison && (leftProfileQuery.isLoading || rightProfileQuery.isLoading);
  const hasErrorState = canRenderComparison && (leftProfileQuery.isError || rightProfileQuery.isError);
  const hasEmptyState = canRenderComparison && (leftProfileQuery.isEmpty || rightProfileQuery.isEmpty);
  const leftProfile = leftProfileQuery.data;
  const rightProfile = rightProfileQuery.data;
  const leftDisplayName = toDisplayName(leftPlayerId ?? "?", leftProfile?.player.playerName);
  const rightDisplayName = toDisplayName(rightPlayerId ?? "?", rightProfile?.player.playerName);
  const comparisonSummary = buildComparisonSummary(
    leftDisplayName,
    rightDisplayName,
    leftProfile?.summary,
    rightProfile?.summary,
  );
  const hasVisibleMetrics = METRIC_GROUPS.some((group) =>
    group.metrics.some((metric) => hasMetricData(metric, leftProfile, rightProfile, metricMode)),
  );

  return (
    <aside className="mt-6 overflow-hidden rounded-[1.9rem] border border-white/60 bg-[linear-gradient(180deg,rgba(243,247,241,0.96)_0%,rgba(248,250,255,0.98)_48%,rgba(245,249,245,0.96)_100%)] p-4 text-[#111c2d] shadow-[0_30px_84px_-58px_rgba(9,25,20,0.34)] md:p-5">
      <header className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.24em] text-[#647086]">
              Comparativo
            </p>
            {canRenderComparison && !hasLoadingState && !hasErrorState ? (
              <ProfileCoveragePill coverage={combinedCoverage} />
            ) : null}
          </div>
          <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d] md:text-3xl">
            {canRenderComparison ? `${leftDisplayName} x ${rightDisplayName}` : "Escolha dois jogadores"}
          </h2>
          <p className="max-w-3xl text-sm/6 text-[#57657a]">
            {canRenderComparison ? comparisonSummary : "Use a lista de jogadores para montar uma comparação lado a lado."}
          </p>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{competitionName}</ProfileTag>
            <ProfileTag>{seasonLabel}</ProfileTag>
            <ProfileTag>{activeWindowLabel}</ProfileTag>
            <ProfileTag>{describeVenue(venue)}</ProfileTag>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <div className="inline-flex rounded-full border border-[rgba(191,201,195,0.55)] bg-white/82 p-[2px]">
            {(["totals", "per90"] as const).map((mode) => (
              <button
                aria-pressed={metricMode === mode}
                className={joinClasses(
                  "button-pill",
                  metricMode === mode ? "button-pill-primary" : "button-pill-ghost border-transparent bg-transparent",
                )}
                key={mode}
                onClick={() => {
                  setMetricMode(mode);
                }}
                type="button"
              >
                {mode === "totals" ? "Totais" : "Por 90"}
              </button>
            ))}
          </div>
          <button
            className="button-pill button-pill-ghost"
            onClick={() => {
              clearSelection();
            }}
            type="button"
          >
            Limpar
          </button>
        </div>
      </header>

      {!canRenderComparison ? (
        <div className="mt-5">
          <EmptyState
            description="Selecione mais um nome na lista para abrir a comparação."
            title={selectedIds.length === 1 ? "Falta um jogador" : "Comparativo vazio"}
          />
        </div>
      ) : null}

      {canRenderComparison && hasLoadingState ? (
        <section className="mt-5 grid gap-3 md:grid-cols-2">
          <LoadingSkeleton height={220} />
          <LoadingSkeleton height={220} />
        </section>
      ) : null}

      {canRenderComparison && hasErrorState ? (
        <section className="mt-5 rounded-[1.2rem] border border-[#ffdcc3] bg-[#fff3e8] p-4 text-sm text-[#6e3900]">
          <p className="font-semibold">Não foi possível carregar a comparação.</p>
          <p className="mt-1">{leftProfileQuery.error?.message ?? rightProfileQuery.error?.message}</p>
        </section>
      ) : null}

      {canRenderComparison && hasEmptyState ? (
        <div className="mt-5">
          <EmptyState description="Um dos jogadores não tem dados suficientes neste recorte." title="Sem comparação disponível" />
        </div>
      ) : null}

      {canRenderComparison && !hasLoadingState && !hasErrorState && !hasEmptyState ? (
        <section className="mt-5 space-y-4">
          {leftProfileQuery.isPartial || rightProfileQuery.isPartial ? (
            <PartialDataBanner coverage={combinedCoverage} message="Algumas métricas podem estar incompletas neste recorte." />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <PlayerCard displayName={leftDisplayName} profile={leftProfile} side="left" />
            <PlayerCard displayName={rightDisplayName} profile={rightProfile} side="right" />
          </div>

          {hasVisibleMetrics ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {METRIC_GROUPS.map((group) => (
                <MetricGroup
                  group={group}
                  key={group.id}
                  leftName={leftDisplayName}
                  leftProfile={leftProfile}
                  mode={metricMode}
                  rightName={rightDisplayName}
                  rightProfile={rightProfile}
                />
              ))}
            </div>
          ) : (
            <EmptyState description="Troque o recorte ou volte para totais para ver mais métricas." title="Sem métricas disponíveis" />
          )}
        </section>
      ) : null}
    </aside>
  );
}
