"use client";

import { type ReactNode, useEffect, useState } from "react";

import Link from "next/link";

import { resolveSeasonChampionArtwork } from "@/features/competitions/utils/champion-media";
import { useWorldCupEdition } from "@/features/world-cup/hooks/useWorldCupEdition";
import {
  buildWorldCupEditionPath,
  buildWorldCupHubPath,
  buildWorldCupRankingsPath,
  buildWorldCupTeamPath,
} from "@/features/world-cup/routes";
import type {
  WorldCupEditionData,
  WorldCupEditionGroup,
  WorldCupEditionNavigationItem,
  WorldCupEditionScorer,
  WorldCupEditionStandingRow,
  WorldCupKnockoutRound,
  WorldCupKnockoutTie,
  WorldCupTeamReference,
} from "@/features/world-cup/types/world-cup.types";
import { resolveWorldCupPlayerImageAssetId } from "@/features/world-cup/utils/player-profile";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";

const WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens";
const WORLD_CUP_COMPETITION_ASSET_KEY = "wc_mens";

type WorldCupBracketSnapshotColumn = {
  leftTies: WorldCupKnockoutTie[];
  rightTies: WorldCupKnockoutTie[];
  round: WorldCupKnockoutRound;
};

type WorldCupBracketSide = "left" | "right";

type WorldCupBracketTeamReference = {
  teamId?: string | null;
  teamName?: string | null;
};

type WorldCupTieScoreboardEntry = {
  goals: number | null;
  isWinner: boolean;
  team: WorldCupTeamReference;
};

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function formatSignedNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  const formattedValue = formatWholeNumber(Math.abs(value));
  if (value > 0) {
    return `+${formattedValue}`;
  }

  if (value < 0) {
    return `-${formattedValue}`;
  }

  return formattedValue;
}

function formatScoreValue(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return formatWholeNumber(value);
}

function formatKickoff(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsedDate);
}

function formatTieWindow(tie: WorldCupKnockoutTie): string | null {
  const kickoffs = tie.matches
    .map((match) => match.kickoffAt)
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
    .sort((left, right) => left.getTime() - right.getTime());

  if (kickoffs.length === 0) {
    return null;
  }

  const firstDate = formatKickoff(kickoffs[0].toISOString());
  const lastDate = formatKickoff(kickoffs[kickoffs.length - 1].toISOString());

  if (!firstDate) {
    return null;
  }

  if (!lastDate || lastDate === firstDate) {
    return firstDate;
  }

  return `${firstDate} - ${lastDate}`;
}

function buildFallbackLabel(value: string | null | undefined, emptyFallback = "WC"): string {
  const tokens = (value ?? "")
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (tokens.length === 0) {
    return emptyFallback;
  }

  if (tokens.length === 1) {
    return tokens[0].slice(0, 3).toUpperCase();
  }

  return tokens
    .slice(0, 3)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");
}

function resolveWorldCupHostCountryAssetId(
  hostCountryTeam: WorldCupTeamReference | null,
  hostCountry: string | null,
): string | null {
  if (hostCountryTeam?.teamId) {
    return hostCountryTeam.teamId;
  }

  return hostCountry === "Coreia do Sul e Japão" ? "world-cup-japan" : null;
}

function formatGoalLabel(goals: number): string {
  return goals === 1 ? "gol" : "gols";
}

function describeChampion(team: WorldCupTeamReference | null): string {
  return team?.teamName ?? "Não identificado";
}

function describeTopScorer(scorer: WorldCupEditionScorer | null): string {
  if (!scorer?.playerName) {
    return "Não identificado";
  }

  const parts = [scorer.playerName];
  if (scorer.goals > 0) {
    parts.push(`${formatWholeNumber(scorer.goals)} ${formatGoalLabel(scorer.goals)}`);
  }
  return parts.join(" · ");
}

function resolveResolutionBadge(tie: WorldCupKnockoutTie): string | null {
  switch (tie.resolutionType) {
    case "penalties":
      return "Pênaltis";
    case "replay":
      return "Replay";
    case "replay_inferred":
      return "Replay";
    case "advanced_to_next_round":
      return null;
    default:
      return null;
  }
}

function describeResolutionType(resolutionType: string | null | undefined): string | null {
  switch (resolutionType) {
    case "penalties":
      return "Pênaltis";
    case "replay":
      return "Replay";
    case "replay_inferred":
      return "Replay inferido";
    case "advanced_to_next_round":
      return null;
    case "final_round":
      return "Fase final";
    default:
      return null;
  }
}

function localizeWorldCupStageLabel(label: string): string {
  return label
    .replace(/\bgroup stage\b/i, "Fase de grupos")
    .replace(/\bknockout stage\b/i, "Mata-mata");
}

function localizeWorldCupGroupLabel(label: string): string {
  const trimmedLabel = label.trim();

  if (/^group\s+/i.test(trimmedLabel)) {
    return trimmedLabel.replace(/^group\s+/i, "Grupo ");
  }

  if (/^grupo\s+/i.test(trimmedLabel)) {
    return `Grupo ${trimmedLabel.replace(/^grupo\s+/i, "").trim()}`;
  }

  if (/^[A-Z0-9]+$/i.test(trimmedLabel)) {
    return `Grupo ${trimmedLabel}`;
  }

  return trimmedLabel;
}

function isTieWinner(team: WorldCupTeamReference | null, winner: WorldCupTeamReference | null): boolean {
  if (!team || !winner) {
    return false;
  }

  if (team.teamId && winner.teamId) {
    return team.teamId === winner.teamId;
  }

  return Boolean(team.teamName && winner.teamName && team.teamName === winner.teamName);
}

function normalizeTeamIdentityKey(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const normalized = value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  return normalized.length > 0 ? normalized : null;
}

function buildTeamIdentityCandidates(
  teamId: string | null | undefined,
  teamName: string | null | undefined,
): string[] {
  const candidates = new Set<string>();
  const normalizedId = normalizeTeamIdentityKey(teamId);
  const normalizedName = normalizeTeamIdentityKey(teamName);

  if (normalizedId) {
    candidates.add(`id:${normalizedId}`);
  }

  if (normalizedName) {
    candidates.add(`name:${normalizedName}`);
  }

  return [...candidates];
}

function matchesTeamIdentity(
  left: WorldCupBracketTeamReference,
  right: WorldCupBracketTeamReference,
): boolean {
  const leftCandidates = buildTeamIdentityCandidates(left.teamId, left.teamName);
  const rightCandidates = buildTeamIdentityCandidates(right.teamId, right.teamName);

  return leftCandidates.some((candidate) => rightCandidates.includes(candidate));
}

function buildWorldCupTieParticipants(tie: WorldCupKnockoutTie): WorldCupBracketTeamReference[] {
  const uniqueParticipants = new Map<string, WorldCupBracketTeamReference>();

  for (const match of tie.matches) {
    for (const team of [match.homeTeam, match.awayTeam]) {
      if (!team?.teamId && !team?.teamName) {
        continue;
      }

      const identity = buildTeamIdentityCandidates(team?.teamId, team?.teamName)[0] ?? `${uniqueParticipants.size}`;
      uniqueParticipants.set(identity, {
        teamId: team?.teamId,
        teamName: team?.teamName,
      });
    }
  }

  if (uniqueParticipants.size > 0) {
    return [...uniqueParticipants.values()];
  }

  return [tie.winner, tie.runnerUp]
    .filter((team): team is WorldCupTeamReference => Boolean(team?.teamId || team?.teamName))
    .map((team) => ({
      teamId: team.teamId,
      teamName: team.teamName,
    }));
}

function buildWorldCupAdvancingParticipants(tie: WorldCupKnockoutTie): WorldCupBracketTeamReference[] {
  if (tie.winner?.teamId || tie.winner?.teamName) {
    return [
      {
        teamId: tie.winner.teamId,
        teamName: tie.winner.teamName,
      },
    ];
  }

  return buildWorldCupTieParticipants(tie);
}

function worldCupTieFeedsParticipant(
  tie: WorldCupKnockoutTie,
  participant: WorldCupBracketTeamReference,
): boolean {
  return buildWorldCupAdvancingParticipants(tie).some((team) => matchesTeamIdentity(team, participant));
}

function buildParticipantsFromWorldCupTies(ties: WorldCupKnockoutTie[]): WorldCupBracketTeamReference[] {
  return ties.flatMap((tie) => buildWorldCupTieParticipants(tie));
}

function splitWorldCupTiesFallback(ties: WorldCupKnockoutTie[]) {
  const midpoint = Math.ceil(ties.length / 2);

  return {
    leftTies: ties.slice(0, midpoint),
    rightTies: ties.slice(midpoint),
  };
}

function resolveWorldCupSnapshotColumns(rounds: WorldCupKnockoutRound[]): WorldCupBracketSnapshotColumn[] {
  const sideRounds = rounds.slice(0, -1);
  const finalTie = rounds.at(-1)?.ties[0] ?? null;
  const columnsByRoundKey = new Map<string, WorldCupBracketSnapshotColumn>();
  let nextRoundParticipants: Record<WorldCupBracketSide, WorldCupBracketTeamReference[]> | null = finalTie
    ? {
        left: [
          {
            teamId: finalTie.matches[0]?.homeTeam?.teamId ?? finalTie.winner?.teamId,
            teamName: finalTie.matches[0]?.homeTeam?.teamName ?? finalTie.winner?.teamName,
          },
        ].filter((team) => team.teamId || team.teamName),
        right: [
          {
            teamId: finalTie.matches[0]?.awayTeam?.teamId ?? finalTie.runnerUp?.teamId,
            teamName: finalTie.matches[0]?.awayTeam?.teamName ?? finalTie.runnerUp?.teamName,
          },
        ].filter((team) => team.teamId || team.teamName),
      }
    : null;

  for (let index = sideRounds.length - 1; index >= 0; index -= 1) {
    const round = sideRounds[index];
    const fallback = splitWorldCupTiesFallback(round.ties);

    if (!nextRoundParticipants) {
      columnsByRoundKey.set(round.roundKey, {
        leftTies: fallback.leftTies,
        rightTies: fallback.rightTies,
        round,
      });
      nextRoundParticipants = {
        left: buildParticipantsFromWorldCupTies(fallback.leftTies),
        right: buildParticipantsFromWorldCupTies(fallback.rightTies),
      };
      continue;
    }

    const currentParticipants = nextRoundParticipants;
    const leftTies = round.ties.filter((tie) =>
      currentParticipants.left.some((participant) => worldCupTieFeedsParticipant(tie, participant)),
    );
    const rightTies = round.ties.filter((tie) =>
      currentParticipants.right.some((participant) => worldCupTieFeedsParticipant(tie, participant)),
    );
    const assignedTieKeys = new Set([...leftTies, ...rightTies].map((tie) => tie.tieKey));
    const unassignedTies = round.ties.filter((tie) => !assignedTieKeys.has(tie.tieKey));
    const canUseProgression = leftTies.length > 0 && rightTies.length > 0;
    const resolvedLeftTies = canUseProgression ? [...leftTies] : [...fallback.leftTies];
    const resolvedRightTies = canUseProgression ? [...rightTies] : [...fallback.rightTies];

    if (canUseProgression) {
      for (const tie of unassignedTies) {
        if (resolvedLeftTies.length <= resolvedRightTies.length) {
          resolvedLeftTies.push(tie);
        } else {
          resolvedRightTies.push(tie);
        }
      }
    }

    columnsByRoundKey.set(round.roundKey, {
      leftTies: resolvedLeftTies,
      rightTies: resolvedRightTies,
      round,
    });
    nextRoundParticipants = {
      left: buildParticipantsFromWorldCupTies(resolvedLeftTies),
      right: buildParticipantsFromWorldCupTies(resolvedRightTies),
    };
  }

  return sideRounds.map((round) => {
    const resolved = columnsByRoundKey.get(round.roundKey);
    if (resolved) {
      return resolved;
    }

    const fallback = splitWorldCupTiesFallback(round.ties);
    return {
      leftTies: fallback.leftTies,
      rightTies: fallback.rightTies,
      round,
    };
  });
}

function resolveOrderedWorldCupTieParticipants(tie: WorldCupKnockoutTie): WorldCupTeamReference[] {
  const orderedParticipants: WorldCupTeamReference[] = [];
  const pushParticipant = (team: WorldCupTeamReference | null | undefined) => {
    if (!team?.teamId && !team?.teamName) {
      return;
    }

    if (orderedParticipants.some((participant) => matchesTeamIdentity(participant, team))) {
      return;
    }

    orderedParticipants.push({
      teamId: team.teamId ?? null,
      teamName: team.teamName ?? null,
    });
  };

  tie.matches.forEach((match) => {
    pushParticipant(match.homeTeam);
    pushParticipant(match.awayTeam);
  });

  pushParticipant(tie.winner);
  pushParticipant(tie.runnerUp);

  return orderedParticipants.slice(0, 2);
}

function resolveWorldCupTieGoals(tie: WorldCupKnockoutTie, participant: WorldCupTeamReference): number | null {
  let totalGoals = 0;
  let hasTrackedScore = false;

  tie.matches.forEach((match) => {
    if (match.homeTeam && matchesTeamIdentity(match.homeTeam, participant) && typeof match.homeScore === "number") {
      totalGoals += match.homeScore;
      hasTrackedScore = true;
    }

    if (match.awayTeam && matchesTeamIdentity(match.awayTeam, participant) && typeof match.awayScore === "number") {
      totalGoals += match.awayScore;
      hasTrackedScore = true;
    }
  });

  return hasTrackedScore ? totalGoals : null;
}

function resolveWorldCupTieScoreboard(tie: WorldCupKnockoutTie): WorldCupTieScoreboardEntry[] {
  return resolveOrderedWorldCupTieParticipants(tie).map((team) => ({
    goals: resolveWorldCupTieGoals(tie, team),
    isWinner: isTieWinner(team, tie.winner),
    team,
  }));
}

function resolveWorldCupTieShootout(tie: WorldCupKnockoutTie) {
  return tie.matches.find((match) => match.shootout)?.shootout ?? null;
}

function resolveWorldCupTieStatusLabel(tie: WorldCupKnockoutTie): string | null {
  const resolutionLabel = resolveResolutionBadge(tie);

  if (resolutionLabel) {
    return resolutionLabel;
  }

  return tie.matches.length > 1 ? "Agregado" : null;
}

function formatMatchCountLabel(value: number): string {
  return value === 1 ? "1 jogo" : `${formatWholeNumber(value)} jogos`;
}

function WorldCupTeamBadge({
  team,
  className,
}: {
  team: WorldCupTeamReference | null;
  className?: string;
}) {
  const teamName = team?.teamName ?? "Não identificado";

  return (
    <ProfileMedia
      alt={teamName}
      assetId={team?.teamId}
      category="clubs"
      className={joinClasses("border-[rgba(191,201,195,0.4)] bg-[#f0f3ff]", className)}
      fallback={buildFallbackLabel(teamName, "WC")}
      fallbackClassName="text-[0.55rem] text-[#003526]"
      imageClassName="p-0"
      shape="circle"
    />
  );
}

function TeamPageLink({
  team,
  className,
}: {
  team: WorldCupTeamReference | null;
  className?: string;
}) {
  if (team?.teamId && team.teamName) {
    return (
      <Link className={className} href={buildWorldCupTeamPath(team.teamId)}>
        {team.teamName}
      </Link>
    );
  }

  return <span className={className}>{team?.teamName ?? "Não identificado"}</span>;
}

function SectionHeader({
  align = "start",
  description,
  eyebrow,
  title,
}: {
  align?: "center" | "start";
  description?: string;
  eyebrow: string;
  title: string;
}) {
  const wrapperClass =
    align === "center"
      ? "flex flex-col items-center gap-3 text-center"
      : "flex flex-wrap items-start justify-between gap-4";
  const copyClass = align === "center" ? "mx-auto max-w-3xl text-center" : undefined;

  return (
    <div className={wrapperClass}>
      <div className={copyClass}>
        <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">{eyebrow}</p>
        <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
          {title}
        </h2>
        {description ? <p className="mt-2 max-w-3xl text-sm/6 text-[#57657a]">{description}</p> : null}
      </div>
    </div>
  );
}

function HeroSummaryItem({
  detail,
  label,
  media,
  value,
  valueClassName,
}: {
  detail?: string;
  label: string;
  media?: ReactNode;
  value: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2.5 border-b border-[rgba(191,201,195,0.32)] py-2.5 last:border-b-0 last:pb-0">
      <div className="flex h-10 w-10 items-center justify-center">{media}</div>
      <div className="min-w-0">
        <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
        <div className={joinClasses("mt-0.5 text-base font-semibold text-[#111c2d]", valueClassName)}>{value}</div>
        {detail ? <p className="mt-0.5 text-[0.82rem] leading-5 text-[#57657a]">{detail}</p> : null}
      </div>
    </div>
  );
}

function NavigationCard({
  item,
  tone,
  title,
}: {
  item: WorldCupEditionNavigationItem;
  tone: "left" | "right";
  title: string;
}) {
  return (
    <Link
      className={joinClasses(
        "group flex h-full flex-col justify-between rounded-[1.35rem] border px-4 py-4 transition-[transform,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-1 hover:border-[#8bd6b6] hover:shadow-[0_24px_58px_-42px_rgba(17,28,45,0.22)]",
        tone === "left"
          ? "border-[rgba(191,201,195,0.5)] bg-[rgba(255,255,255,0.82)]"
          : "border-[rgba(216,227,251,0.76)] bg-[rgba(240,243,255,0.78)]",
      )}
      href={buildWorldCupEditionPath(item.seasonLabel)}
    >
      <div className="space-y-2">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">{title}</p>
        <h3 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.05em] text-[#111c2d]">
          {item.year}
        </h3>
        <p className="text-sm/6 text-[#57657a]">{item.editionName}</p>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-[rgba(191,201,195,0.38)] pt-4 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#003526]">
        <span>Abrir edição</span>
        <span className="transition-transform group-hover:translate-x-1">-&gt;</span>
      </div>
    </Link>
  );
}

function WorldCupEditionHero({
  edition,
  groupStages,
  knockoutRounds,
  seasonLabel,
}: {
  edition: WorldCupEditionData["edition"];
  groupStages: WorldCupEditionData["groupStages"];
  knockoutRounds: WorldCupEditionData["knockoutRounds"];
  seasonLabel: string;
}) {
  const artwork = resolveSeasonChampionArtwork(WORLD_CUP_COMPETITION_KEY, seasonLabel);
  const groupsCount = groupStages.reduce((total, stage) => total + stage.groups.length, 0);
  const championName = describeChampion(edition.champion);
  const runnerUpName = edition.runnerUp?.teamName ?? "Vice-campeão não identificado";
  const topScorerName = edition.topScorer?.playerName ?? "Artilharia indisponível";
  const hostCountryName = edition.hostCountry ?? "País-sede não identificado";
  const hostCountryAssetId = resolveWorldCupHostCountryAssetId(edition.hostCountryTeam, edition.hostCountry);
  const heroImageSrc = artwork?.src ?? null;
  const [isHeroPhotoUnavailable, setIsHeroPhotoUnavailable] = useState(false);
  const hasHeroPhoto = Boolean(heroImageSrc) && !isHeroPhotoUnavailable;

  useEffect(() => {
    setIsHeroPhotoUnavailable(false);
  }, [heroImageSrc]);

  return (
    <section className="relative isolate overflow-hidden rounded-[2rem] border border-white/65 bg-[linear-gradient(180deg,rgba(255,252,244,0.96)_0%,rgba(248,242,227,0.98)_48%,rgba(241,232,207,0.96)_100%)] p-4 shadow-[0_34px_88px_-58px_rgba(68,43,4,0.28)] md:p-5 xl:p-6">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-[radial-gradient(circle_at_top_left,rgba(243,223,159,0.45),transparent_48%),radial-gradient(circle_at_top_right,rgba(138,109,24,0.18),transparent_40%)]" />
      <div className="pointer-events-none absolute bottom-[-20%] right-[12%] h-56 w-56 rounded-full bg-[rgba(95,67,10,0.08)] blur-3xl" />

      <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1.22fr)_minmax(320px,0.8fr)] xl:items-stretch">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileTag className="bg-white text-[#6d5c3f]">Copa do Mundo</ProfileTag>
            {groupStages.length > 0 ? <ProfileTag className="bg-white text-[#6d5c3f]">Fase de grupos</ProfileTag> : null}
            {knockoutRounds.length > 0 ? <ProfileTag className="bg-white text-[#6d5c3f]">Mata-mata</ProfileTag> : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-[4.5rem_minmax(0,1fr)] sm:items-center">
            <ProfileMedia
              alt="Logo da Copa do Mundo FIFA"
              assetId={WORLD_CUP_COMPETITION_ASSET_KEY}
              category="competitions"
              className="h-[4.5rem] w-[4.5rem] rounded-[1.35rem] border-[rgba(191,201,195,0.55)] bg-white shadow-[0_24px_50px_-34px_rgba(68,43,4,0.32)]"
              fallback="WC"
              fallbackClassName="text-lg text-[#5f430a]"
              imageClassName="p-3"
            />

            <div className="space-y-2">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#8a6d18]">Página da edição</p>
              <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.65rem] font-extrabold leading-[0.94] tracking-[-0.06em] text-[#1d160c] md:text-[3.35rem]">
                Copa do Mundo {edition.year}
              </h1>
              <p className="max-w-3xl text-sm/6 text-[#6d5c3f] md:text-[0.95rem]">
                Sede em {hostCountryName.toLowerCase()}, {formatWholeNumber(edition.matchesCount)} partidas
                registradas e leitura completa da edição em grupos, chaveamento e artilharia.
              </p>
            </div>
          </div>

          <div className="grid gap-2.5 md:grid-cols-3">
            <div className="flex min-h-[5.6rem] flex-col items-center justify-center rounded-[1.2rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-3 py-3 text-center">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">Grupos</p>
              <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.7rem] font-extrabold leading-none text-[#1d160c]">
                {formatWholeNumber(groupsCount)}
              </p>
            </div>
            <div className="flex min-h-[5.6rem] flex-col items-center justify-center rounded-[1.2rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-3 py-3 text-center">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">Fases eliminatórias</p>
              <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.7rem] font-extrabold leading-none text-[#1d160c]">
                {formatWholeNumber(knockoutRounds.length)}
              </p>
            </div>
            <div className="flex min-h-[5.6rem] flex-col items-center justify-center rounded-[1.2rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-3 py-3 text-center">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">Participantes</p>
              <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.7rem] font-extrabold leading-none text-[#1d160c]">
                {formatWholeNumber(edition.teamsCount)}
              </p>
            </div>
          </div>

          <div className="rounded-[1.35rem] border border-[rgba(191,201,195,0.52)] bg-white/92 px-4 py-4 shadow-[0_28px_68px_-48px_rgba(68,43,4,0.22)]">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">
              Resumo da edição
            </p>
            <div className="mt-3">
              <HeroSummaryItem
                label="Campeão"
                media={
                  <ProfileMedia
                    alt={championName}
                    assetId={edition.champion?.teamId}
                    category="clubs"
                    className="h-10 w-10 border-0 bg-[rgba(240,243,255,0.82)]"
                    fallback={buildFallbackLabel(championName, "WC")}
                    imageClassName="p-1.25"
                    shape="circle"
                  />
                }
                value={
                  <TeamPageLink
                    className="truncate font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-none tracking-[-0.05em] text-[#1d160c] transition-colors hover:text-[#5f430a]"
                    team={edition.champion}
                  />
                }
                valueClassName="min-w-0"
              />
              <HeroSummaryItem
                label="Vice-campeão"
                media={
                  <ProfileMedia
                    alt={runnerUpName}
                    assetId={edition.runnerUp?.teamId}
                    category="clubs"
                    className="h-10 w-10 border-0 bg-[rgba(240,243,255,0.82)]"
                    fallback={buildFallbackLabel(runnerUpName, "WC")}
                    imageClassName="p-1.25"
                    shape="circle"
                  />
                }
                value={
                  <TeamPageLink
                    className="truncate font-[family:var(--font-profile-headline)] text-[1.2rem] font-extrabold leading-tight tracking-[-0.04em] text-[#1d160c] transition-colors hover:text-[#5f430a]"
                    team={edition.runnerUp}
                  />
                }
                valueClassName="min-w-0"
              />
              <HeroSummaryItem
                detail={`${formatWholeNumber(edition.topScorer?.goals ?? null)} ${formatGoalLabel(edition.topScorer?.goals ?? 0)}${edition.topScorer?.teamName ? ` · ${edition.topScorer.teamName}` : ""}`}
                label="Artilheiro"
                media={
                  <ProfileMedia
                    alt={topScorerName}
                    assetId={resolveWorldCupPlayerImageAssetId(
                      edition.topScorer?.imageAssetId,
                      edition.topScorer?.playerId,
                    )}
                    href={edition.topScorer?.profileUrl ?? null}
                    category="players"
                    className="h-10 w-10 border-[#d8e3fb] bg-[rgba(240,243,255,0.82)]"
                    fallback={buildFallbackLabel(topScorerName, "WC")}
                    imageClassName="p-0"
                    shape="circle"
                  />
                }
                value={topScorerName}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.16rem] font-extrabold leading-tight tracking-[-0.04em] text-[#1d160c]"
              />
              <HeroSummaryItem
                detail={hostCountryName}
                label="Estádio da final"
                media={
                  <ProfileMedia
                    alt={`País-sede ${hostCountryName}`}
                    assetId={hostCountryAssetId}
                    category="clubs"
                    className="h-10 w-10 border-0 bg-[rgba(240,243,255,0.82)]"
                    fallback={buildFallbackLabel(hostCountryName, "WC")}
                    imageClassName="p-1.25"
                    shape="circle"
                  />
                }
                value={edition.finalVenue ?? "Estádio não informado"}
                valueClassName="font-[family:var(--font-profile-headline)] text-[1.16rem] font-extrabold leading-tight tracking-[-0.04em] text-[#1d160c]"
              />
            </div>
          </div>
        </div>

        <aside className="relative min-h-[320px] overflow-hidden rounded-[1.7rem] border border-[rgba(95,67,10,0.18)] bg-[linear-gradient(135deg,#2b1d0b_0%,#5a3f0f_56%,#8a6d18_100%)] shadow-[0_34px_84px_-56px_rgba(68,43,4,0.55)]">
          {hasHeroPhoto ? (
            <img
              alt={`Celebração do campeão da Copa do Mundo ${edition.year}`}
              className="absolute inset-0 h-full w-full object-cover object-center"
              onError={() => setIsHeroPhotoUnavailable(true)}
              src={heroImageSrc ?? undefined}
            />
          ) : null}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,226,163,0.22),transparent_26%),linear-gradient(180deg,rgba(21,13,4,0.12)_0%,rgba(21,13,4,0.52)_46%,rgba(21,13,4,0.92)_100%)]" />
          {!hasHeroPhoto ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex h-40 w-40 flex-col items-center justify-center rounded-full border border-white/14 bg-white/8 text-center shadow-[0_28px_64px_-36px_rgba(0,0,0,0.4)]">
                <span className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-white/72">Copa do Mundo</span>
                <span className="mt-3 font-[family:var(--font-profile-headline)] text-[3rem] font-extrabold leading-none tracking-[-0.08em] text-white">
                  {edition.year}
                </span>
              </div>
            </div>
          ) : null}
          <div className="relative flex h-full min-h-[320px] flex-col justify-between p-5 md:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/12 bg-white/10 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/88">
                Campeão da edição
              </span>
              <span className="rounded-full border border-white/12 bg-white/8 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/72">
                {championName}
              </span>
            </div>

            <div className="space-y-4">
              <div className="max-w-[16rem]">
                <p className="text-sm/6 text-[#f8efd8]">
                  {hasHeroPhoto
                    ? `Registro visual da conquista de ${championName} na Copa do Mundo ${edition.year}.`
                    : "Estrutura pronta para receber arte temática da edição assim que o catálogo incorporar a Copa."}
                </p>
              </div>
              <div className="rounded-[1.3rem] border border-white/12 bg-[rgba(24,15,5,0.52)] px-4 py-4 backdrop-blur-sm">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#f3df9f]">Campeão</p>
                <div className="mt-3 flex items-center gap-3">
                  <ProfileMedia
                    alt={championName}
                    assetId={edition.champion?.teamId}
                    category="clubs"
                    className="h-12 w-12 border-white/12 bg-white/12 text-white"
                    fallback={buildFallbackLabel(championName, "WC")}
                    fallbackClassName="text-sm text-white"
                    imageClassName="p-1.5"
                    shape="circle"
                    tone="contrast"
                  />
                  <div className="min-w-0">
                    <p className="truncate font-[family:var(--font-profile-headline)] text-[1.65rem] font-extrabold tracking-[-0.04em] text-white">
                      {championName}
                    </p>
                    <p className="mt-1 text-sm text-[#f8efd8]">{edition.finalVenue ?? "Local da final indisponível"}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function WorldCupGroupStandingCard({ row }: { row: WorldCupEditionStandingRow }) {
  const isAdvanced = row.advanced;
  const teamName = row.teamName ?? row.teamId ?? "Seleção não identificada";

  return (
    <div
      className={
        isAdvanced
          ? "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(3,53,38,0.2)] bg-[rgba(139,214,182,0.1)] px-3 py-2.5"
          : "flex items-center justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.42)] bg-white px-3 py-2.5"
      }
    >
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={joinClasses(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
            isAdvanced ? "bg-[rgba(3,53,38,0.12)] text-[#003526]" : "bg-[rgba(3,53,38,0.06)] text-[#57657a]",
          )}
        >
          {row.position}
        </span>
        <WorldCupTeamBadge
          className="h-10 w-10"
          team={{ teamId: row.teamId, teamName }}
        />
        {row.teamId ? (
          <Link
            className="truncate text-sm font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
            href={buildWorldCupTeamPath(row.teamId)}
          >
            {teamName}
          </Link>
        ) : (
          <span className="truncate text-sm font-semibold text-[#111c2d]">{teamName}</span>
        )}
      </div>

      <div className="flex items-center gap-3 text-right">
        <div className="hidden sm:block">
          <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">V</p>
          <p className="text-xs font-bold text-[#57657a]">{row.wins}</p>
        </div>
        <div className="hidden sm:block">
          <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">SG</p>
          <p
            className={joinClasses(
              "text-xs font-bold",
              row.goalDiff > 0 ? "text-[#1b6b51]" : row.goalDiff < 0 ? "text-[#ba1a1a]" : "text-[#57657a]",
            )}
          >
            {formatSignedNumber(row.goalDiff)}
          </p>
        </div>
        <div>
          <p className="text-[0.58rem] font-bold uppercase tracking-[0.14em] text-[#8fa097]">Pts</p>
          <p className={joinClasses("text-sm font-extrabold", isAdvanced ? "text-[#003526]" : "text-[#111c2d]")}>
            {row.points}
          </p>
        </div>
      </div>
    </div>
  );
}

function WorldCupGroupPhaseSection({
  groupStages,
  knockoutRounds,
}: {
  groupStages: WorldCupEditionData["groupStages"];
  knockoutRounds: WorldCupEditionData["knockoutRounds"];
}) {
  return (
    <ProfilePanel className="space-y-5" tone="base">
      <SectionHeader
        eyebrow="Fase de grupos"
        title="Grupos da edição"
      />

      {groupStages.length === 0 ? (
        renderEmptyGroupsState({ groupStages, knockoutRounds })
      ) : (
        <div className="space-y-6">
          {groupStages.map((stage) => (
            <section className="space-y-4" key={stage.stageKey}>
              <div className="flex flex-wrap items-center gap-2">
                <ProfileTag>{localizeWorldCupStageLabel(stage.stageLabel)}</ProfileTag>
                <span className="text-sm text-[#57657a]">
                  {formatWholeNumber(stage.groups.length)} {stage.groups.length === 1 ? "grupo" : "grupos"}
                </span>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                {stage.groups.map((group) => (
                  <ProfilePanel className="space-y-4" key={`${stage.stageKey}-${group.groupKey ?? "group"}`} tone="soft">
                    <SectionHeader eyebrow="GRUPO" title={localizeWorldCupGroupLabel(group.groupLabel)} />

                    {group.rows.length === 0 ? (
                      <ProfileAlert title="Sem classificação" tone="info">
                        Ainda não há linhas suficientes para este grupo.
                      </ProfileAlert>
                    ) : (
                      <div className="space-y-2">
                        {group.rows.map((row) => (
                          <WorldCupGroupStandingCard
                            key={`${stage.stageKey}-${group.groupKey ?? "group"}-${row.teamId ?? row.teamName ?? row.position}`}
                            row={row}
                          />
                        ))}
                      </div>
                    )}
                  </ProfilePanel>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </ProfilePanel>
  );
}

function WorldCupSnapshotTieCard({
  side,
  tie,
}: {
  side: WorldCupBracketSide;
  tie: WorldCupKnockoutTie;
}) {
  const resolutionLabel = resolveWorldCupTieStatusLabel(tie);
  const scoreboard = resolveWorldCupTieScoreboard(tie);
  const shootout = resolveWorldCupTieShootout(tie);

  return (
    <div
      className="rounded-[1.02rem] border border-[rgba(191,201,195,0.5)] bg-white px-3 py-3 shadow-[0_14px_34px_-28px_rgba(17,28,45,0.2)]"
      data-bracket-side={side}
      data-tie-key={tie.tieKey}
      key={`${side}-${tie.tieKey}`}
    >
      <div className="mb-2.5 flex min-h-[0.85rem] items-center justify-center text-center text-[0.58rem] font-semibold uppercase tracking-[0.18em] text-[#6a7890]">
        {resolutionLabel ? <span>{resolutionLabel}</span> : null}
      </div>
      <div className="space-y-2">
        {scoreboard.map(({ goals, isWinner, team }) => {
          const teamName = team.teamName ?? "Não identificado";

          return (
            <div
              className="grid grid-cols-[minmax(0,1fr)_2.35rem] items-center gap-2"
              key={`${side}-${tie.tieKey}-${team.teamId ?? teamName}`}
            >
              <div className="flex min-w-0 items-center gap-2">
                <WorldCupTeamBadge className="h-9 w-9 border-0 bg-white" team={team} />
                <span
                  className={
                    isWinner
                      ? "flex min-h-9 min-w-0 items-center text-[0.97rem] font-extrabold leading-[1.08rem] text-[#003526]"
                      : "flex min-h-9 min-w-0 items-center text-[0.97rem] font-semibold leading-[1.08rem] text-[#111c2d]"
                  }
                >
                  {teamName}
                </span>
              </div>
              <span className="flex w-9 justify-end justify-self-end pr-1 text-right font-[family:var(--font-profile-headline)] text-[1.55rem] font-extrabold leading-none text-[#111c2d] tabular-nums">
                {formatScoreValue(goals)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-2.5 min-h-[1rem] text-center text-[0.68rem] text-[#57657a]">
        {shootout ? `Pênaltis: ${shootout.home} x ${shootout.away}` : null}
      </p>
    </div>
  );
}

function WorldCupSnapshotStageColumn({
  column,
  side,
}: {
  column: WorldCupBracketSnapshotColumn;
  side: WorldCupBracketSide;
}) {
  const ties = side === "left" ? column.leftTies : column.rightTies;
  const headingClass = "px-1 text-center text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]";

  return (
    <div
      className="flex h-full min-w-0 flex-col justify-center gap-2.5"
      data-bracket-column={`${column.round.roundKey}-${side}`}
      key={`${side}-${column.round.roundKey}`}
    >
      <p className={headingClass}>{column.round.roundLabel}</p>
      {ties.length === 0 ? (
        <ProfileAlert title="Fase indisponível" tone="warning">
          Não foi possível montar esta coluna.
        </ProfileAlert>
      ) : (
        <div className="space-y-2.5">
          {ties.map((tie) => (
            <WorldCupSnapshotTieCard key={`${side}-${tie.tieKey}`} side={side} tie={tie} />
          ))}
        </div>
      )}
    </div>
  );
}

function WorldCupFinalSnapshotCard({ finalRound }: { finalRound: WorldCupKnockoutRound | null }) {
  const tie = finalRound?.ties[0] ?? null;
  const championName = tie?.winner?.teamName ?? "Campeão";
  const dateLabel = tie ? formatTieWindow(tie) : null;
  const scoreboard = tie ? resolveWorldCupTieScoreboard(tie) : [];
  const shootout = tie ? resolveWorldCupTieShootout(tie) : null;
  const decisionLabel = tie ? resolveWorldCupTieStatusLabel(tie) : null;

  return (
    <div className="mx-auto w-full max-w-[264px] rounded-[1.45rem] border border-[rgba(95,67,10,0.28)] bg-[radial-gradient(circle_at_top,rgba(243,223,159,0.18),transparent_48%),linear-gradient(180deg,#3c2809_0%,#6e4c11_54%,#8a6d18_100%)] px-4 py-5 text-white shadow-[0_28px_72px_-44px_rgba(68,43,4,0.58)]">
      <p className="text-center text-[0.66rem] font-semibold uppercase tracking-[0.2em] text-[#f3df9f]">
        {finalRound?.roundLabel ?? "Final"}
      </p>

      {!tie ? (
        <ProfileAlert title="Final indisponível" tone="warning">
          Não foi possível carregar o confronto decisivo.
        </ProfileAlert>
      ) : (
        <div className="mt-4 space-y-4">
          {dateLabel ? (
            <p className="text-center text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#f8efd8]">
              {dateLabel}
            </p>
          ) : null}

          <div className="grid gap-2.5">
            {scoreboard.length > 0 ? (
              scoreboard.map(({ goals, isWinner, team }) => {
                const teamName = team.teamName ?? "Não identificado";

                return (
                  <div
                    className={
                      isWinner
                        ? "rounded-[1rem] border border-[rgba(243,223,159,0.28)] bg-[rgba(255,255,255,0.08)] px-3 py-3"
                        : "rounded-[1rem] border border-white/10 bg-[rgba(255,255,255,0.04)] px-3 py-3"
                    }
                    key={`final-${team.teamId ?? teamName}`}
                  >
                    <div className="flex items-center justify-between gap-2.5">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <WorldCupTeamBadge className="h-11 w-11 border-white/12 bg-white/12 text-white" team={team} />
                        <span className={isWinner ? "truncate text-[1rem] font-extrabold text-white" : "truncate text-[1rem] font-semibold text-white/88"}>
                          {teamName}
                        </span>
                      </div>
                      <span className="font-[family:var(--font-profile-headline)] text-[1.9rem] font-extrabold leading-none text-white">
                        {formatScoreValue(goals)}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <ProfileAlert title="Final indisponível" tone="warning">
                Sem confronto consolidado para a decisão.
              </ProfileAlert>
            )}
          </div>

          <div className="rounded-[1rem] border border-[rgba(243,223,159,0.18)] bg-[rgba(255,255,255,0.06)] px-3 py-3 text-center">
            <p className="text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-[#f3df9f]">Campeão</p>
            <p className="mt-1.5 font-[family:var(--font-profile-headline)] text-[1.52rem] font-extrabold text-white">
              {championName}
            </p>
            <p className="mt-1.5 text-[0.8rem] text-[#f8efd8]">
              {decisionLabel ?? "Decisão da edição"} • {formatMatchCountLabel(tie.matches.length)}
            </p>
            {shootout ? (
              <p className="mt-2 text-[0.72rem] text-[#f8efd8]">
                Pênaltis: {shootout.home} x {shootout.away}
              </p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function WorldCupKnockoutSection({
  data,
  knockoutRounds,
}: {
  data: WorldCupEditionData;
  knockoutRounds: WorldCupEditionData["knockoutRounds"];
}) {
  const snapshotColumns = resolveWorldCupSnapshotColumns(knockoutRounds);
  const finalRound = knockoutRounds.at(-1) ?? null;

  return (
    <ProfilePanel className="space-y-5" tone="base">
      <SectionHeader
        align="center"
        eyebrow="Chaveamento"
        title="Chaveamento até a final"
      />

      {knockoutRounds.length === 0 ? (
        renderEmptyBracketState(data)
      ) : (
        <div className="overflow-x-auto pb-1">
          <div
            className="grid items-center gap-2.5 xl:gap-3"
            style={{
              gridTemplateColumns: `repeat(${Math.max(snapshotColumns.length, 1)}, minmax(148px, 1.08fr)) minmax(228px, 1fr) repeat(${Math.max(snapshotColumns.length, 1)}, minmax(148px, 1.08fr))`,
            }}
          >
            {snapshotColumns.length > 0 ? (
              snapshotColumns.map((column) => <WorldCupSnapshotStageColumn column={column} key={`left-${column.round.roundKey}`} side="left" />)
            ) : (
              <div className="space-y-3">
                <p className="px-1 text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                  Eliminatória
                </p>
              </div>
            )}

            <div className="flex h-full flex-col justify-center">
              <WorldCupFinalSnapshotCard finalRound={finalRound} />
            </div>

            {snapshotColumns.length > 0 ? (
              [...snapshotColumns].reverse().map((column) => (
                <WorldCupSnapshotStageColumn column={column} key={`right-${column.round.roundKey}`} side="right" />
              ))
            ) : (
              <div className="space-y-3">
                <p className="px-1 text-right text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                  Eliminatória
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </ProfilePanel>
  );
}

function WorldCupEditionScorerCard({
  scorer,
}: {
  scorer: WorldCupEditionScorer;
}) {
  const playerName = scorer.playerName ?? "Não identificado";
  const teamName = scorer.teamName ?? "Seleção não identificada";
  const teamContent =
    scorer.teamId && scorer.teamName ? (
      <Link className="inline-flex items-center gap-2 transition-colors hover:text-[#00513b]" href={buildWorldCupTeamPath(scorer.teamId)}>
        <ProfileMedia
          alt={teamName}
          assetId={scorer.teamId}
          category="clubs"
          className="h-7 w-7 border-0 bg-white"
          fallback={buildFallbackLabel(teamName, "WC")}
          fallbackClassName="text-[0.58rem]"
          imageClassName="p-1"
          shape="circle"
          linkBehavior="none"
        />
        <span className="truncate">{teamName}</span>
      </Link>
    ) : (
      <span className="inline-flex items-center gap-2">
        <ProfileMedia
          alt={teamName}
          assetId={scorer.teamId}
          category="clubs"
          className="h-7 w-7 border-0 bg-white"
          fallback={buildFallbackLabel(teamName, "WC")}
          fallbackClassName="text-[0.58rem]"
          imageClassName="p-1"
          shape="circle"
        />
        <span className="truncate">{teamName}</span>
      </span>
    );

  return (
    <article className="flex items-center justify-between gap-4 rounded-[1.3rem] border border-[rgba(191,201,195,0.55)] bg-[rgba(240,243,255,0.82)] px-4 py-4 transition-colors hover:border-[#8bd6b6] hover:bg-white">
      <div className="flex min-w-0 items-center gap-4">
        <span className="inline-flex min-w-10 items-center justify-center rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#003526] shadow-[0_12px_28px_-22px_rgba(17,28,45,0.35)]">
          {scorer.rank}
        </span>

        <ProfileMedia
          alt={playerName}
          assetId={resolveWorldCupPlayerImageAssetId(scorer.imageAssetId, scorer.playerId)}
          href={scorer.profileUrl ?? null}
          category="players"
          className="h-14 w-14 border-[#d8e3fb] bg-[rgba(255,255,255,0.95)]"
          fallback={buildFallbackLabel(playerName, "WC")}
          fallbackClassName="text-sm"
          imageClassName="p-0"
          shape="circle"
        />

        <div className="min-w-0">
          <p className="truncate font-[family:var(--font-profile-headline)] text-[1.18rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
            {playerName}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
            <span>Seleção</span>
            <span className="inline-flex max-w-full items-center gap-2 rounded-full border border-[rgba(191,201,195,0.45)] bg-white/90 px-2.5 py-1 text-[#455468]">
              {teamContent}
            </span>
          </div>
        </div>
      </div>

      <div className="text-right">
        <p className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold leading-none text-[#111c2d]">
          {formatWholeNumber(scorer.goals)}
        </p>
        <p className="mt-1 text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
          {formatGoalLabel(scorer.goals)}
        </p>
      </div>
    </article>
  );
}

function WorldCupEditionRankingSection({
  scorers,
}: {
  scorers: WorldCupEditionData["scorers"];
}) {
  return (
    <ProfilePanel className="space-y-5" tone="base">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">Artilheiros</p>
            <h2 className="font-[family:var(--font-profile-headline)] text-[2rem] font-extrabold tracking-[-0.045em] text-[#111c2d]">
              Ranking da edição
            </h2>
          </div>
          <Link
            className="button-pill button-pill-secondary"
            href={buildWorldCupRankingsPath()}
          >
            Ver ranking histórico
          </Link>
        </div>

      </header>

      {scorers.length === 0 ? (
        <ProfileAlert title="Sem ranking de artilheiros" tone="warning">
          Nenhum jogador atingiu 3 gols nesta edição.
        </ProfileAlert>
      ) : (
        <div className="grid gap-3">
          {scorers.map((scorer) => (
            <WorldCupEditionScorerCard key={`${scorer.rank}-${scorer.playerId ?? scorer.playerName ?? "scorer"}`} scorer={scorer} />
          ))}
        </div>
      )}
    </ProfilePanel>
  );
}

function renderEmptyGroupsState(data: Pick<WorldCupEditionData, "groupStages" | "knockoutRounds">) {
  if (data.knockoutRounds.length > 0) {
    return (
      <ProfileAlert title="Sem grupos nesta edição" tone="info">
        Esta edição começa direto no mata-mata na estrutura registrada pelo banco.
      </ProfileAlert>
    );
  }

  return (
    <ProfileAlert title="Sem tabelas de grupos" tone="info">
      Nenhum snapshot de fase de grupos foi retornado para esta edição.
    </ProfileAlert>
  );
}

function renderEmptyBracketState(data: WorldCupEditionData) {
  if (data.groupStages.some((stage) => stage.stageKey === "final_round")) {
    return (
      <ProfileAlert title="Sem mata-mata nesta edição" tone="info">
        A decisão desta Copa foi registrada como fase final em grupos, sem chave eliminatória.
      </ProfileAlert>
    );
  }

  return (
    <ProfileAlert title="Sem chave eliminatória" tone="info">
      Nenhum confronto de mata-mata foi retornado para esta edição.
    </ProfileAlert>
  );
}

export function WorldCupEditionContent({ seasonLabel }: { seasonLabel: string }) {
  const editionQuery = useWorldCupEdition(seasonLabel);

  if (editionQuery.isLoading && !editionQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando grupos, chave eliminatória, campeão e artilheiros desta edição."
        kicker="Copa do Mundo"
        loading
        title={`Carregando a edição ${seasonLabel}`}
      />
    );
  }

  if (editionQuery.isError && !editionQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="Não foi possível carregar os dados estruturados desta edição agora."
        kicker="Copa do Mundo"
        title={`Falha ao abrir ${seasonLabel}`}
        tone="critical"
      />
    );
  }

  if (!editionQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="A edição não retornou dados suficientes para montar esta página."
        kicker="Copa do Mundo"
        title={`Edição ${seasonLabel} indisponível`}
        tone="warning"
      />
    );
  }

  const { edition, groupStages, knockoutRounds, navigation, scorers } = editionQuery.data;

  return (
    <ProfileShell className="world-cup-theme space-y-6" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Início
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupHubPath()}>
          Copa do Mundo
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>{edition.year}</span>
      </div>

      {editionQuery.isPartial ? (
        <PartialDataBanner
          coverage={editionQuery.coverage}
          message="Alguns recortes desta edição dependem de fallback controlado."
        />
      ) : null}

      <WorldCupEditionHero
        edition={edition}
        groupStages={groupStages}
        knockoutRounds={knockoutRounds}
        seasonLabel={seasonLabel}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ProfileKpi
          hint={
            describeResolutionType(edition.resolutionType)
              ? `Resolução: ${describeResolutionType(edition.resolutionType)}`
              : "Resolução não informada"
          }
          label="Campeão"
          value={
            <TeamPageLink
              className="transition-colors hover:text-[#003526]"
              team={edition.champion}
            />
          }
        />
        <ProfileKpi
          hint={edition.teamsCount ? `${formatWholeNumber(edition.teamsCount)} seleções` : "Total não informado"}
          label="Sede"
          value={edition.hostCountry ?? "-"}
        />
        <ProfileKpi
          hint={edition.topScorer?.teamName ?? "Seleção não identificada"}
          label="Artilheiro"
          value={edition.topScorer?.playerName ?? "-"}
        />
        <ProfileKpi
          hint={edition.finalVenue ?? "Sede da final não informada"}
          label="Partidas"
          value={formatWholeNumber(edition.matchesCount)}
        />
      </div>

      <WorldCupGroupPhaseSection groupStages={groupStages} knockoutRounds={knockoutRounds} />

      <WorldCupKnockoutSection data={editionQuery.data} knockoutRounds={knockoutRounds} />

      <WorldCupEditionRankingSection scorers={scorers} />

      {navigation.previousEdition || navigation.nextEdition ? (
        <ProfilePanel className="space-y-4" tone="soft">
          <header className="space-y-2">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Navegação entre edições
            </p>
            <h2 className="font-[family:var(--font-profile-headline)] text-[1.75rem] font-extrabold tracking-[-0.04em] text-[#111c2d]">
              Anterior e próxima Copa
            </h2>
          </header>

          <div className="grid gap-4 md:grid-cols-2">
            {navigation.previousEdition ? (
              <NavigationCard item={navigation.previousEdition} title="Edição anterior" tone="left" />
            ) : (
              <div className="rounded-[1.35rem] border border-dashed border-[rgba(191,201,195,0.48)] px-4 py-4 text-sm/6 text-[#57657a]">
                Esta é a primeira edição registrada no banco.
              </div>
            )}

            {navigation.nextEdition ? (
              <NavigationCard item={navigation.nextEdition} title="Próxima edição" tone="right" />
            ) : (
              <div className="rounded-[1.35rem] border border-dashed border-[rgba(191,201,195,0.48)] px-4 py-4 text-sm/6 text-[#57657a]">
                Esta é a edição mais recente disponível no banco.
              </div>
            )}
          </div>
        </ProfilePanel>
      ) : null}
    </ProfileShell>
  );
}
