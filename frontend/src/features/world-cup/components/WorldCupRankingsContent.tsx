"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { ProfilePanel, ProfileShell, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";

import { WorldCupArchiveHero } from "@/features/world-cup/components/WorldCupArchiveHero";
import { useWorldCupRankings } from "@/features/world-cup/hooks/useWorldCupRankings";
import {
  buildWorldCupEditionPath,
  buildWorldCupHubPath,
  buildWorldCupTeamPath,
} from "@/features/world-cup/routes";
import type { WorldCupRankingBiggestWinRecord, WorldCupRankingFinalRecord } from "@/features/world-cup/types/world-cup.types";

const PLAYER_CARD_PAGE_SIZE = 10;
const FEATURED_CARD_LIMIT = 8;
const SECONDARY_CARD_LIMIT = 4;
const EDITION_CARD_LIMIT = 6;
const MATCH_RECORDS_LIMIT = 6;
const WORLD_CUP_COMPETITION_KEY = "wc_mens";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatWholeNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPerMatch(total: number | null | undefined, matches: number | null | undefined): string {
  if (
    typeof total !== "number" ||
    typeof matches !== "number" ||
    Number.isNaN(total) ||
    Number.isNaN(matches) ||
    matches <= 0
  ) {
    return "-";
  }

  return formatDecimal(total / matches);
}

function buildFallbackLabel(value: string | null | undefined): string {
  const tokens = (value ?? "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (tokens.length === 0) {
    return "WC";
  }

  if (tokens.length === 1) {
    return tokens[0].slice(0, 3).toUpperCase();
  }

  return tokens
    .slice(0, 2)
    .map((token) => token[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

function buildTiedRankSet(items: Array<{ rank: number }>): Set<number> {
  const countsByRank = new Map<number, number>();

  for (const item of items) {
    countsByRank.set(item.rank, (countsByRank.get(item.rank) ?? 0) + 1);
  }

  return new Set(
    [...countsByRank.entries()]
      .filter(([, count]) => count > 1)
      .map(([rank]) => rank),
  );
}

function formatScoreline(params: {
  awayScore: number | null | undefined;
  awayTeamName: string | null | undefined;
  homeScore: number | null | undefined;
  homeTeamName: string | null | undefined;
}): string {
  return `${params.homeTeamName ?? "Não identificado"} ${formatWholeNumber(params.homeScore)} x ${formatWholeNumber(
    params.awayScore,
  )} ${params.awayTeamName ?? "Não identificado"}`;
}

function isBiggestWinRecord(
  match: WorldCupRankingFinalRecord | WorldCupRankingBiggestWinRecord,
): match is WorldCupRankingBiggestWinRecord {
  return "goalDiff" in match;
}

function getMatchVenueMeta(
  match: WorldCupRankingFinalRecord | WorldCupRankingBiggestWinRecord,
): string | null {
  return "venueName" in match && match.venueName ? `Estádio ${match.venueName}` : null;
}

function formatFixtureLabel(params: {
  awayTeamName: string | null | undefined;
  homeTeamName: string | null | undefined;
}): string {
  return `${params.homeTeamName ?? "Não identificado"} x ${params.awayTeamName ?? "Não identificado"}`;
}

function SectionJumpLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      className="button-pill button-pill-on-dark"
      href={href}
    >
      {children}
    </a>
  );
}

function RankingGlyph({
  className,
  icon,
}: {
  className?: string;
  icon: "ball" | "chart" | "trophy" | "flash" | "stadium";
}) {
  if (icon === "chart") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path d="M5 17.5h14M7.5 15V11M12 15V7.5M16.5 15v-4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        <path d="m9 8.5 3-3 3 2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      </svg>
    );
  }

  if (icon === "trophy") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M8 4.5h8v2.8c0 2.6-1.6 4.8-4 5.7-2.4-.9-4-3.1-4-5.7V4.5Zm0 0H5.5c0 2.4 1 4.2 2.9 5.1M16 4.5h2.5c0 2.4-1 4.2-2.9 5.1M10 15.2v2.3M14 15.2v2.3M7.5 19.5h9"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "flash") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M12.5 3.5 6.8 12h4.2l-1 8.5 7-9.9h-4.3l-.2-7.1Z"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "stadium") {
    return (
      <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
        <path
          d="M4.5 16.5h15M6 16.5v-6l6-3 6 3v6M9 9.7v6.8M15 9.7v6.8M10.2 16.5v-3h3.6v3"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
      <path
        d="M12 4.2 15 5.4l2.4-.4 2 2-.4 2.4 1.2 3-1.2 3 .4 2.4-2 2-2.4-.4-3 1.2-3-1.2-2.4.4-2-2 .4-2.4-1.2-3 1.2-3-.4-2.4 2-2 2.4.4 3-1.2Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.6"
      />
      <path d="m9 8.8 3-1.2 3 1.2.8 3-.8 3-3 1.2-3-1.2-.8-3 .8-3Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" />
      <path d="M8.2 9.5 12 12l3.8-2.5M9.1 14.6h5.8M10.2 7.9 12 12l1.8-4.1" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4" />
    </svg>
  );
}

function HeroHighlightCard({
  description,
  href,
  media,
  title,
  label,
}: {
  description: ReactNode;
  href?: string;
  media: ReactNode;
  title: ReactNode;
  label: string;
}) {
  const className =
    "group flex min-h-[6.75rem] items-center rounded-[1.15rem] border border-white/10 bg-white/10 px-3.5 py-3 shadow-[0_20px_42px_-34px_rgba(15,8,1,0.62)] backdrop-blur-xl transition-colors hover:bg-white/14";

  const content = (
    <div className="flex w-full items-center gap-3.5">
      {media}
      <div className="flex min-w-0 flex-col justify-center">
        <p className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-white/62">{label}</p>
        <p className="font-[family:var(--font-profile-headline)] text-[0.98rem] font-extrabold leading-5 tracking-[-0.03em] text-white">
          {title}
        </p>
        <p className="mt-1 text-[0.78rem]/5 text-white/72">{description}</p>
      </div>
    </div>
  );

  if (href) {
    return (
      <Link className={className} href={href}>
        {content}
      </Link>
    );
  }

  return <article className={className}>{content}</article>;
}

function SectionHeading({
  aside,
  description,
  headingId,
  kicker,
  title,
}: {
  aside?: ReactNode;
  description?: ReactNode;
  headingId: string;
  kicker: string;
  title: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#6d5c3f]">{kicker}</p>
        <h2
          className="scroll-mt-32 font-[family:var(--font-profile-headline)] text-[1.8rem] font-extrabold tracking-[-0.045em] text-[#1d160c] md:text-[2rem]"
          id={headingId}
        >
          {title}
        </h2>
        {description ? <p className="max-w-3xl text-sm/6 text-[#6d5c3f]">{description}</p> : null}
      </div>

      {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
    </header>
  );
}

function MetaPill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-[rgba(138,109,24,0.12)] bg-white/66 px-2.5 py-1 text-[0.58rem] font-semibold uppercase tracking-[0.14em] text-[#7b6b4f]">
      {children}
    </span>
  );
}

function RankingPositionBadge({
  rank,
  isTied = false,
  tone = "base",
}: {
  rank: number;
  isTied?: boolean;
  tone?: "base" | "lead";
}) {
  return (
    <span
      className={joinClasses(
        "inline-flex min-w-[3.35rem] items-center justify-center gap-1 rounded-full border px-3 py-1 text-[0.58rem] font-bold uppercase tracking-[0.14em]",
        tone === "lead"
          ? "border-[rgba(138,109,24,0.18)] bg-[linear-gradient(180deg,rgba(255,247,224,0.98)_0%,rgba(255,255,255,0.92)_100%)] text-[#5f430a] shadow-[0_18px_32px_-26px_rgba(95,67,10,0.32)]"
          : "border-[rgba(191,201,195,0.32)] bg-white/88 text-[#6d5c3f]",
      )}
    >
      <span>#{rank}</span>
      {isTied ? <span className="text-[0.5rem] font-semibold tracking-[0.12em] text-[#8a6d18]">emp.</span> : null}
    </span>
  );
}

function SectionToggleGroup<TValue extends string>({
  ariaLabel,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  onChange: (value: TValue) => void;
  options: Array<{
    icon?: ReactNode;
    label: string;
    value: TValue;
  }>;
  value: TValue;
}) {
  return (
    <div aria-label={ariaLabel} className="flex flex-wrap items-center gap-1.5" role="group">
      {options.map((option) => {
        const isActive = option.value === value;

        return (
          <button
            aria-pressed={isActive}
            className={joinClasses(
              "button-pill gap-1.5",
              isActive ? "button-pill-primary" : "button-pill-secondary hover:bg-[#f0faf6]",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.icon ? <span className="hidden shrink-0 sm:inline-flex">{option.icon}</span> : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function EditionRankingVisual({
  compact = false,
  tone,
  year,
}: {
  compact?: boolean;
  tone: "volume" | "media";
  year: number;
}) {
  return (
    <div
      className={joinClasses(
        "relative isolate flex shrink-0 items-center justify-center rounded-[1.15rem] border border-[rgba(138,109,24,0.16)] bg-[linear-gradient(180deg,rgba(255,251,240,0.96)_0%,rgba(255,255,255,0.92)_100%)] shadow-[0_20px_34px_-28px_rgba(95,67,10,0.28)]",
        compact ? "h-14 w-14" : "h-[4.9rem] w-[4.9rem]",
      )}
    >
      <ProfileMedia
        alt="Identidade da Copa do Mundo"
        assetId={WORLD_CUP_COMPETITION_KEY}
        category="competitions"
        className={joinClasses(compact ? "h-9 w-9 rounded-[0.95rem]" : "h-12 w-12 rounded-[1rem]")}
        fallback="FIFA"
        imageClassName={compact ? "p-1.5" : "p-2"}
        shape="rounded"
      />
      <span className="absolute left-2 top-2 inline-flex items-center justify-center rounded-full bg-white/92 p-1 text-[#8a6d18] shadow-[0_10px_20px_-18px_rgba(95,67,10,0.45)]">
        <RankingGlyph className="h-3.5 w-3.5" icon={tone === "volume" ? "ball" : "chart"} />
      </span>
      <span
        className={joinClasses(
          "absolute -bottom-1.5 -right-1.5 rounded-full border border-[rgba(138,109,24,0.18)] bg-white px-2 py-1 font-[family:var(--font-profile-headline)] font-extrabold leading-none tracking-[-0.04em] text-[#1d160c] shadow-[0_12px_28px_-22px_rgba(95,67,10,0.38)]",
          compact ? "text-[0.66rem]" : "text-[0.78rem]",
        )}
      >
        {year}
      </span>
    </div>
  );
}

function MatchScoreVisual({
  awayScore,
  awayTeamId,
  awayTeamName,
  compact = false,
  homeScore,
  homeTeamId,
  homeTeamName,
  tone,
}: {
  awayScore: number | null | undefined;
  awayTeamId: string | null | undefined;
  awayTeamName: string | null | undefined;
  compact?: boolean;
  homeScore: number | null | undefined;
  homeTeamId: string | null | undefined;
  homeTeamName: string | null | undefined;
  tone: "finais" | "goleadas";
}) {
  const mediaSizeClassName = compact ? "h-10 w-10" : "h-12 w-12";

  return (
    <div
      className={joinClasses(
        "relative isolate flex shrink-0 items-center gap-2 rounded-[1.15rem] border border-[rgba(138,109,24,0.14)] bg-[linear-gradient(180deg,rgba(255,251,240,0.94)_0%,rgba(255,255,255,0.94)_100%)] shadow-[0_20px_34px_-30px_rgba(95,67,10,0.26)]",
        compact ? "px-2.5 py-2" : "px-3 py-2.5",
      )}
    >
      <span className="absolute -right-1.5 -top-1.5 inline-flex items-center justify-center rounded-full bg-white p-1 text-[#8a6d18] shadow-[0_10px_22px_-16px_rgba(95,67,10,0.42)]">
        <RankingGlyph className="h-3.5 w-3.5" icon={tone === "finais" ? "trophy" : "flash"} />
      </span>

      <ProfileMedia
        alt={homeTeamName ?? "Seleção"}
        assetId={homeTeamId}
        category="clubs"
        className={`${mediaSizeClassName} rounded-full`}
        fallback={buildFallbackLabel(homeTeamName)}
        imageClassName="p-0.5"
        shape="circle"
      />

      <div
        className={joinClasses(
          "min-w-[4.25rem] rounded-[0.95rem] border border-[rgba(191,201,195,0.26)] bg-white/92 px-2.5 py-2 text-center",
          compact ? "min-w-[4.5rem]" : "min-w-[5rem]",
        )}
      >
        <p className={joinClasses("font-[family:var(--font-profile-headline)] font-extrabold leading-none tracking-[-0.05em] text-[#1d160c]", compact ? "text-[1.05rem]" : "text-[1.2rem]")}>
          {formatWholeNumber(homeScore)} x {formatWholeNumber(awayScore)}
        </p>
      </div>

      <ProfileMedia
        alt={awayTeamName ?? "Seleção"}
        assetId={awayTeamId}
        category="clubs"
        className={`${mediaSizeClassName} rounded-full`}
        fallback={buildFallbackLabel(awayTeamName)}
        imageClassName="p-0.5"
        shape="circle"
      />
    </div>
  );
}

function EditorialLeadCard({
  href,
  isTied = false,
  meta,
  metricHint,
  metricLabel,
  metricValue,
  rank,
  subtitle,
  title,
  visual,
}: {
  href?: string;
  isTied?: boolean;
  meta?: ReactNode;
  metricHint?: ReactNode;
  metricLabel: string;
  metricValue: ReactNode;
  rank: number;
  subtitle?: ReactNode;
  title: ReactNode;
  visual?: ReactNode;
}) {
  const className =
    "group block rounded-[1.35rem] border border-[rgba(138,109,24,0.18)] bg-[linear-gradient(180deg,rgba(255,251,240,0.98)_0%,rgba(255,255,255,0.94)_100%)] p-4 shadow-[0_28px_62px_-48px_rgba(95,67,10,0.28)] transition-[border-color,transform,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5 hover:border-[rgba(138,109,24,0.3)] hover:shadow-[0_32px_72px_-50px_rgba(95,67,10,0.34)] md:p-5";

  const content = (
    <div
      className={joinClasses(
        "grid gap-4 md:items-center",
        visual ? "md:grid-cols-[auto_auto_minmax(0,1fr)_auto]" : "md:grid-cols-[auto_minmax(0,1fr)_auto]",
      )}
    >
      <div className="md:self-start">
        <RankingPositionBadge isTied={isTied} rank={rank} tone="lead" />
      </div>

      {visual ? <div className="md:self-start">{visual}</div> : null}

      <div className="min-w-0">
        <p className="font-[family:var(--font-profile-headline)] text-[1.9rem] font-extrabold leading-none tracking-[-0.06em] text-[#1d160c] md:text-[2.2rem]">
          {title}
        </p>
        {subtitle ? <div className="mt-2 text-[0.96rem]/6 text-[#6d5c3f]">{subtitle}</div> : null}
        {meta ? (
          <div className="mt-3 text-[0.68rem]/5 font-semibold uppercase tracking-[0.14em] text-[#8a785a]">{meta}</div>
        ) : null}
      </div>

      <div className="md:border-l md:border-[rgba(138,109,24,0.12)] md:pl-4 md:text-right">
        <p className="text-[0.58rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">{metricLabel}</p>
        <p className="mt-1 font-[family:var(--font-profile-headline)] text-[2.15rem] font-extrabold leading-none tracking-[-0.05em] text-[#1d160c]">
          {metricValue}
        </p>
        {metricHint ? <div className="mt-1 text-[0.72rem]/5 text-[#7b6b4f]">{metricHint}</div> : null}
      </div>
    </div>
  );

  if (href) {
    return <Link className={className} href={href}>{content}</Link>;
  }

  return <article className={className}>{content}</article>;
}

function EditorialCompactRow({
  href,
  isTied = false,
  meta,
  metricLabel,
  metricValue,
  rank,
  subtitle,
  title,
  visual,
}: {
  href?: string;
  isTied?: boolean;
  meta?: ReactNode;
  metricLabel: string;
  metricValue: ReactNode;
  rank: number;
  subtitle?: ReactNode;
  title: ReactNode;
  visual?: ReactNode;
}) {
  const className = joinClasses(
    "group grid gap-3 py-3 transition-colors md:items-center",
    visual ? "md:grid-cols-[auto_auto_minmax(0,1fr)_auto]" : "md:grid-cols-[auto_minmax(0,1fr)_auto]",
  );

  const titleNode = (
    <p
      className={joinClasses(
        "font-[family:var(--font-profile-headline)] text-[1.12rem] font-extrabold tracking-[-0.03em] text-[#1d160c]",
        href ? "transition-colors group-hover:text-[#5f430a]" : null,
      )}
    >
      {title}
    </p>
  );

  const content = (
    <>
      <div className="md:self-start">
        <RankingPositionBadge isTied={isTied} rank={rank} />
      </div>

      {visual ? <div className="md:self-start">{visual}</div> : null}

      <div className="min-w-0">
        {titleNode}
        {subtitle ? <div className="mt-1 text-[0.84rem]/5 text-[#6d5c3f]">{subtitle}</div> : null}
        {meta ? (
          <div className="mt-1.5 text-[0.64rem]/5 font-semibold uppercase tracking-[0.14em] text-[#8a785a]">{meta}</div>
        ) : null}
      </div>

      <div className="md:border-l md:border-[rgba(191,201,195,0.28)] md:pl-4 md:text-right">
        <p className="text-[0.54rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">{metricLabel}</p>
        <p className="mt-1 font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-none tracking-[-0.03em] text-[#1d160c]">
          {metricValue}
        </p>
      </div>
    </>
  );

  if (href) {
    return <Link className={className} href={href}>{content}</Link>;
  }

  return <article className={className}>{content}</article>;
}

function RankingCard({
  title,
  metricLabel,
  children,
  footer,
  className,
  tone = "base",
}: {
  title: string;
  metricLabel: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  tone?: "base" | "featured" | "soft";
}) {
  const toneClassName =
    tone === "featured"
      ? "border-[rgba(138,109,24,0.2)] bg-[linear-gradient(180deg,rgba(255,251,240,0.98)_0%,rgba(255,255,255,0.92)_100%)] shadow-[0_24px_60px_-48px_rgba(95,67,10,0.24)]"
      : tone === "soft"
        ? "border-[rgba(216,227,251,0.76)] bg-[rgba(249,251,255,0.92)]"
        : "border-[rgba(191,201,195,0.42)] bg-white/84";

  return (
    <article className={joinClasses("rounded-[1.35rem] border p-3.5 md:p-4", toneClassName, className)}>
      <header className="space-y-1">
        <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">{metricLabel}</p>
        <h3 className="font-[family:var(--font-profile-headline)] text-[1.25rem] font-extrabold tracking-[-0.035em] text-[#1d160c] md:text-[1.35rem]">
          {title}
        </h3>
      </header>

      <div className="mt-3 space-y-2">{children}</div>
      {footer ? <div className="mt-3">{footer}</div> : null}
    </article>
  );
}

function RankingListRow({
  rank,
  title,
  href,
  subtitle,
  meta,
  metricLabel,
  metricValue,
  media,
  metricVariant = "tile",
  isTied = false,
}: {
  rank: number;
  title: ReactNode;
  href?: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  metricLabel: string;
  metricValue: ReactNode;
  media?: ReactNode;
  metricVariant?: "tile" | "pill" | "inline";
  isTied?: boolean;
}) {
  const metricNode =
    metricVariant === "pill" ? (
      <div className="flex shrink-0 self-center flex-col items-center justify-center rounded-full border border-[rgba(191,201,195,0.22)] bg-white/82 px-3 py-1.5 text-center shadow-[0_12px_24px_-22px_rgba(17,28,45,0.18)]">
        <p className="text-[0.52rem] font-semibold uppercase tracking-[0.14em] text-[#6d5c3f]">{metricLabel}</p>
        <p className="mt-0.5 font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold leading-none text-[#1d160c]">
          {metricValue}
        </p>
      </div>
    ) : metricVariant === "inline" ? (
      <div className="shrink-0 md:border-l md:border-[rgba(191,201,195,0.24)] md:pl-3 md:text-right">
        <p className="text-[0.56rem] font-semibold uppercase tracking-[0.14em] text-[#6d5c3f]">{metricLabel}</p>
        <p className="mt-0.5 font-[family:var(--font-profile-headline)] text-[1.15rem] font-extrabold leading-none text-[#1d160c]">
          {metricValue}
        </p>
      </div>
    ) : (
      <div className="shrink-0 self-center md:border-l md:border-[rgba(191,201,195,0.24)] md:pl-3 md:text-right">
        <p className="text-[0.54rem] font-semibold uppercase tracking-[0.14em] text-[#6d5c3f]">{metricLabel}</p>
        <p className="mt-0.5 font-[family:var(--font-profile-headline)] text-[1.5rem] font-extrabold leading-none tracking-[-0.03em] text-[#1d160c]">
          {metricValue}
        </p>
      </div>
    );

  return (
    <div className="flex items-start justify-between gap-3 rounded-[1rem] border border-[rgba(191,201,195,0.24)] bg-[rgba(246,248,252,0.82)] px-3 py-2.5">
      <div className="flex min-w-0 flex-1 gap-3">
        {media ? <div className="shrink-0 self-center">{media}</div> : null}

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <RankingPositionBadge isTied={isTied} rank={rank} />
          </div>

          {href ? (
            <Link
              className={joinClasses(
                "block font-[family:var(--font-profile-headline)] text-[1.03rem] font-extrabold tracking-[-0.025em] text-[#1d160c] transition-colors hover:text-[#5f430a]",
                metricVariant === "tile" ? "truncate" : "leading-5",
              )}
              href={href}
            >
              {title}
            </Link>
          ) : (
            <p
              className={joinClasses(
                "font-[family:var(--font-profile-headline)] text-[1.03rem] font-extrabold tracking-[-0.025em] text-[#1d160c]",
                metricVariant === "tile" ? "truncate" : "leading-5",
              )}
            >
              {title}
            </p>
          )}

          {subtitle ? <div className="text-[0.82rem]/5 text-[#6d5c3f]">{subtitle}</div> : null}
          {meta ? <div className="flex flex-wrap gap-1.5">{meta}</div> : null}
        </div>
      </div>

      {metricNode}
    </div>
  );
}

function ChipLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      className="inline-flex items-center rounded-full border border-[rgba(138,109,24,0.12)] bg-white/78 px-2.5 py-1 text-[0.58rem] font-semibold uppercase tracking-[0.14em] text-[#6d5c3f] transition-colors hover:border-[rgba(138,109,24,0.24)] hover:bg-white hover:text-[#5f430a]"
      href={href}
    >
      {children}
    </Link>
  );
}

function LoadMoreButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="button-pill button-pill-primary"
      onClick={onClick}
      type="button"
    >
      Mostrar mais
    </button>
  );
}

function TeamLink({ teamId, teamName }: { teamId: string | null | undefined; teamName: string | null | undefined }) {
  if (teamId && teamName) {
    return (
      <Link className="font-semibold text-[#5f430a] transition-colors hover:text-[#8a6d18]" href={buildWorldCupTeamPath(teamId)}>
        {teamName}
      </Link>
    );
  }

  return <span>{teamName ?? "Seleção não identificada"}</span>;
}

export function WorldCupRankingsContent() {
  const rankingsQuery = useWorldCupRankings();
  const [visibleScorers, setVisibleScorers] = useState(PLAYER_CARD_PAGE_SIZE);
  const [visibleSquadAppearances, setVisibleSquadAppearances] = useState(PLAYER_CARD_PAGE_SIZE);
  const [selectedEditionView, setSelectedEditionView] = useState<"volume" | "media">("volume");
  const [selectedMatchView, setSelectedMatchView] = useState<"finais" | "goleadas">("finais");

  if (rankingsQuery.isLoading && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        description="Estamos consolidando os rankings históricos da Copa do Mundo."
        kicker="Copa do Mundo"
        loading
        title="Carregando rankings históricos"
      />
    );
  }

  if (rankingsQuery.isError && !rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="Não foi possível carregar os rankings históricos agora."
        kicker="Copa do Mundo"
        title="Falha ao abrir rankings"
        tone="critical"
      />
    );
  }

  if (!rankingsQuery.data) {
    return (
      <PlatformStateSurface
        actionHref={buildWorldCupHubPath()}
        actionLabel="Voltar ao hub"
        description="A vertical não retornou dados suficientes para montar os rankings."
        kicker="Copa do Mundo"
        title="Rankings indisponíveis"
        tone="warning"
      />
    );
  }

  const { editionRankings, matchRankings, playerRankings, teamRankings } = rankingsQuery.data;
  const scorersToRender = playerRankings.scorers.items.slice(0, visibleScorers);
  const squadAppearancesToRender = playerRankings.squadAppearances.items.slice(0, visibleSquadAppearances);
  const squadAppearancesLabel = `${playerRankings.squadAppearances.minimumAppearancesCount}+ Copas`;
  const titleLeaders = teamRankings.titles.items.slice(0, FEATURED_CARD_LIMIT);
  const winLeaders = teamRankings.wins.items.slice(0, SECONDARY_CARD_LIMIT);
  const goalLeaders = teamRankings.goalsScored.items.slice(0, SECONDARY_CARD_LIMIT);
  const matchLeaders = teamRankings.matches.items.slice(0, SECONDARY_CARD_LIMIT);
  const topFourLeaders = teamRankings.topFourAppearances.items.slice(0, SECONDARY_CARD_LIMIT);
  const activeEditionBlock = selectedEditionView === "volume" ? editionRankings.goals : editionRankings.goalsPerMatch;
  const activeEditionItems = activeEditionBlock.items.slice(0, EDITION_CARD_LIMIT);
  const activeEditionLead = activeEditionItems[0] ?? null;
  const activeEditionRemainder = activeEditionItems.slice(1);
  const activeMatchBlock =
    selectedMatchView === "finais" ? matchRankings.highestScoringFinals : matchRankings.biggestWins;
  const activeMatchItems = activeMatchBlock.items.slice(0, MATCH_RECORDS_LIMIT);
  const activeMatchLead = activeMatchItems[0] ?? null;
  const activeMatchRemainder = activeMatchItems.slice(1);
  const titleTiedRanks = buildTiedRankSet(titleLeaders);
  const winTiedRanks = buildTiedRankSet(winLeaders);
  const goalTiedRanks = buildTiedRankSet(goalLeaders);
  const matchTiedRanks = buildTiedRankSet(matchLeaders);
  const topFourTiedRanks = buildTiedRankSet(topFourLeaders);
  const scorerTiedRanks = buildTiedRankSet(scorersToRender);
  const squadAppearanceTiedRanks = buildTiedRankSet(squadAppearancesToRender);
  const activeEditionTiedRanks = buildTiedRankSet(activeEditionItems);
  const activeMatchTiedRanks = buildTiedRankSet(activeMatchItems);

  const heroChampion = teamRankings.titles.items[0] ?? null;
  const heroEdition = editionRankings.goals.items[0] ?? null;
  const heroScorer = playerRankings.scorers.items[0] ?? null;
  const heroFinal = matchRankings.highestScoringFinals.items[0] ?? null;

  return (
    <ProfileShell className="world-cup-theme space-y-5" variant="plain">
      <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
        <Link className="transition-colors hover:text-[#003526]" href="/">
          Início
        </Link>
        <span className="text-[#8fa097]">/</span>
        <Link className="transition-colors hover:text-[#003526]" href={buildWorldCupHubPath()}>
          Copa do Mundo
        </Link>
        <span className="text-[#8fa097]">/</span>
        <span>Rankings</span>
      </div>

      <WorldCupArchiveHero
        aside={
          <>
            {heroChampion ? (
              <HeroHighlightCard
                description={`${formatWholeNumber(heroChampion.titlesCount)} títulos · ${formatWholeNumber(heroChampion.finalsCount)} finais`}
                href={buildWorldCupTeamPath(heroChampion.teamId)}
                label="Maior campeão"
                media={
                  <ProfileMedia
                    alt={heroChampion.teamName ?? "Seleção"}
                    assetId={heroChampion.teamId}
                    category="clubs"
                    className="h-14 w-14 rounded-full"
                    fallback={buildFallbackLabel(heroChampion.teamName)}
                    imageClassName="p-2"
                    shape="circle"
                    tone="contrast"
                  />
                }
                title={heroChampion.teamName ?? "Não identificado"}
              />
            ) : null}

            {heroEdition ? (
              <HeroHighlightCard
                description={`${formatWholeNumber(heroEdition.goalsCount)} gols · ${formatPerMatch(heroEdition.goalsCount, heroEdition.matchesCount)} por jogo`}
                href={buildWorldCupEditionPath(heroEdition.seasonLabel)}
                label="Copa mais artilheira"
                media={
                  <span className="inline-flex h-14 min-w-14 items-center justify-center rounded-[1rem] border border-white/10 bg-white/12 px-3 font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-white">
                    {heroEdition.year}
                  </span>
                }
                title={heroEdition.editionName}
              />
            ) : null}

            {heroScorer ? (
              <HeroHighlightCard
                description={`${heroScorer.teamName ?? "Seleção histórica"} · ${formatWholeNumber(heroScorer.goals)} gols`}
                label="Artilheiro histórico"
                media={
                  <ProfileMedia
                    alt={heroScorer.playerName ?? "Jogador"}
                    assetId={heroScorer.playerId}
                    category="players"
                    className="h-14 w-14 rounded-[1rem]"
                    fallback={buildFallbackLabel(heroScorer.playerName)}
                    imageClassName="p-2"
                    shape="rounded"
                    tone="contrast"
                  />
                }
                title={heroScorer.playerName ?? "Não identificado"}
              />
            ) : null}

            {heroFinal ? (
              <HeroHighlightCard
                description={`${formatWholeNumber(heroFinal.totalGoals)} gols · ${formatScoreline({
                  awayScore: heroFinal.awayScore,
                  awayTeamName: heroFinal.awayTeam?.teamName,
                  homeScore: heroFinal.homeScore,
                  homeTeamName: heroFinal.homeTeam?.teamName,
                })}`}
                href={buildWorldCupEditionPath(heroFinal.seasonLabel)}
                label="Final mais aberta"
                media={
                  <span className="inline-flex h-14 min-w-14 items-center justify-center rounded-[1rem] border border-white/10 bg-white/12 px-3 font-[family:var(--font-profile-headline)] text-[1.05rem] font-extrabold tracking-[-0.03em] text-white">
                    {heroFinal.year}
                  </span>
                }
                title="Decisão recordista"
              />
            ) : null}
          </>
        }
        asideClassName="grid gap-2.5 sm:grid-cols-2"
        description="Seleções, edições, jogadores e partidas em um recorte único dos recordes históricos da Copa do Mundo."
        footer={
          <nav aria-label="Âncoras dos rankings" className="flex flex-wrap items-center gap-2">
            <SectionJumpLink href="#rankings-selecoes">Seleções</SectionJumpLink>
            <SectionJumpLink href="#rankings-edicoes">Edições</SectionJumpLink>
            <SectionJumpLink href="#rankings-jogadores">Jogadores</SectionJumpLink>
            <SectionJumpLink href="#rankings-partidas">Partidas</SectionJumpLink>
          </nav>
        }
        kicker="Arquivo histórico"
        title="Rankings históricos"
      />

      <ProfilePanel className="space-y-4" tone="base">
        <SectionHeading
          aside={
            <>
              <ProfileTag className="bg-[rgba(255,250,240,0.72)] text-[#5f430a]">Títulos em destaque</ProfileTag>
            </>
          }
          headingId="rankings-selecoes"
          kicker="Seleções"
          title="Lideranças Históricas"
        />

        <div className="grid gap-3 xl:grid-cols-3 xl:items-start">
          <RankingCard
            className="xl:self-start"
            metricLabel={teamRankings.titles.metricLabel}
            title={teamRankings.titles.label}
            tone="featured"
          >
            {titleLeaders.map((team) => (
              <RankingListRow
                href={buildWorldCupTeamPath(team.teamId)}
                isTied={titleTiedRanks.has(team.rank)}
                key={`${teamRankings.titles.label}-${team.teamId}`}
                media={
                  <ProfileMedia
                    alt={team.teamName ?? "Seleção"}
                    assetId={team.teamId}
                    category="clubs"
                    className="h-14 w-14 rounded-full"
                    fallback={buildFallbackLabel(team.teamName)}
                    imageClassName="p-0.5"
                    shape="circle"
                  />
                }
                meta={
                  <>
                    <MetaPill>{formatWholeNumber(team.finalsCount)} finais</MetaPill>
                    <MetaPill>{formatWholeNumber(team.participationsCount)} Copas</MetaPill>
                  </>
                }
                metricLabel="Títulos"
                metricValue={formatWholeNumber(team.titlesCount)}
                rank={team.rank}
                title={team.teamName ?? "Não identificado"}
              />
            ))}
            </RankingCard>

          <div className="space-y-3">
            <RankingCard metricLabel={teamRankings.wins.metricLabel} title={teamRankings.wins.label} tone="soft">
              {winLeaders.map((team) => (
                <RankingListRow
                  href={buildWorldCupTeamPath(team.teamId)}
                  isTied={winTiedRanks.has(team.rank)}
                  key={`${teamRankings.wins.label}-${team.teamId}`}
                  media={
                    <ProfileMedia
                      alt={team.teamName ?? "Seleção"}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-14 w-14 rounded-full"
                      fallback={buildFallbackLabel(team.teamName)}
                      imageClassName="p-0.5"
                      shape="circle"
                    />
                  }
                  metricLabel="Vitórias"
                  metricValue={formatWholeNumber(team.wins)}
                  metricVariant="pill"
                  rank={team.rank}
                  subtitle={`${formatWholeNumber(team.matches)} jogos`}
                  title={team.teamName ?? "Não identificado"}
                />
              ))}
            </RankingCard>

            <RankingCard metricLabel={teamRankings.goalsScored.metricLabel} title={teamRankings.goalsScored.label} tone="soft">
              {goalLeaders.map((team) => (
                <RankingListRow
                  href={buildWorldCupTeamPath(team.teamId)}
                  isTied={goalTiedRanks.has(team.rank)}
                  key={`${teamRankings.goalsScored.label}-${team.teamId}`}
                  media={
                    <ProfileMedia
                      alt={team.teamName ?? "Seleção"}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-14 w-14 rounded-full"
                      fallback={buildFallbackLabel(team.teamName)}
                      imageClassName="p-0.5"
                      shape="circle"
                    />
                  }
                  metricLabel="Gols"
                  metricValue={formatWholeNumber(team.goalsScored)}
                  metricVariant="pill"
                  rank={team.rank}
                  subtitle={`${formatWholeNumber(team.matches)} jogos`}
                  title={team.teamName ?? "Não identificado"}
                />
              ))}
            </RankingCard>
          </div>

          <div className="space-y-3">
            <RankingCard metricLabel={teamRankings.matches.metricLabel} title={teamRankings.matches.label} tone="soft">
              {matchLeaders.map((team) => (
                <RankingListRow
                  href={buildWorldCupTeamPath(team.teamId)}
                  isTied={matchTiedRanks.has(team.rank)}
                  key={`${teamRankings.matches.label}-${team.teamId}`}
                  media={
                    <ProfileMedia
                      alt={team.teamName ?? "Seleção"}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-14 w-14 rounded-full"
                      fallback={buildFallbackLabel(team.teamName)}
                      imageClassName="p-0.5"
                      shape="circle"
                    />
                  }
                  metricLabel="Jogos"
                  metricValue={formatWholeNumber(team.matches)}
                  metricVariant="pill"
                  rank={team.rank}
                  subtitle={`${formatWholeNumber(team.wins)} vitórias`}
                  title={team.teamName ?? "Não identificado"}
                />
              ))}
            </RankingCard>

            <RankingCard
              metricLabel={teamRankings.topFourAppearances.metricLabel}
              title={teamRankings.topFourAppearances.label}
              tone="soft"
            >
              {topFourLeaders.map((team) => (
                <RankingListRow
                  href={buildWorldCupTeamPath(team.teamId)}
                  isTied={topFourTiedRanks.has(team.rank)}
                  key={`${teamRankings.topFourAppearances.label}-${team.teamId}`}
                  media={
                    <ProfileMedia
                      alt={team.teamName ?? "Seleção"}
                      assetId={team.teamId}
                      category="clubs"
                      className="h-14 w-14 rounded-full"
                      fallback={buildFallbackLabel(team.teamName)}
                      imageClassName="p-0.5"
                      shape="circle"
                    />
                  }
                  metricLabel="Top 4"
                  metricValue={formatWholeNumber(team.topFourCount)}
                  metricVariant="pill"
                  rank={team.rank}
                  subtitle={`${formatWholeNumber(team.titlesCount)} títulos`}
                  title={team.teamName ?? "Não identificado"}
                />
              ))}
            </RankingCard>
          </div>
        </div>
      </ProfilePanel>

      <ProfilePanel className="space-y-4" tone="base">
        <SectionHeading
          aside={
            <SectionToggleGroup
              ariaLabel="Visões de gols por Copa"
              onChange={setSelectedEditionView}
              options={[
                { label: "Volume", value: "volume" },
                { label: "Média", value: "media" },
              ]}
              value={selectedEditionView}
            />
          }
          description="Volume bruto e média por jogo em leitura alternada, para entender quais edições aceleraram mais o torneio."
          headingId="rankings-edicoes"
          kicker="Edições"
          title="Gols por Copa"
        />

        {activeEditionLead ? (
          <article className="rounded-[1.55rem] border border-[rgba(191,201,195,0.42)] bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(249,251,255,0.96)_100%)] p-4 shadow-[0_24px_62px_-52px_rgba(17,28,45,0.22)] md:p-5">
            <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div className="space-y-1.5">
                <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">
                  {activeEditionBlock.metricLabel}
                </p>
                <h3 className="font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold tracking-[-0.04em] text-[#1d160c] md:text-[1.6rem]">
                  {activeEditionBlock.label}
                </h3>
                <p className="max-w-3xl text-sm/6 text-[#6d5c3f]">
                  {selectedEditionView === "volume"
                    ? "Um ranking mais bruto e direto, para entender quais Copas empilharam produção total mesmo com formatos diferentes."
                    : "Um recorte normalizado por partida, melhor para comparar edições curtas e longas sem distorção de calendário."}
                </p>
              </div>

              <div className="rounded-[1rem] border border-[rgba(138,109,24,0.12)] bg-[rgba(255,251,240,0.74)] px-4 py-3">
                <p className="text-[0.56rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">Leitura ativa</p>
                <p className="mt-1 font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-none tracking-[-0.04em] text-[#1d160c]">
                  {selectedEditionView === "volume" ? "Volume" : "Média"}
                </p>
                <p className="mt-1 text-[0.72rem]/5 text-[#7b6b4f]">Top {formatWholeNumber(activeEditionItems.length)} edições</p>
              </div>
            </header>

            <div className="mt-4">
              <EditorialLeadCard
                href={buildWorldCupEditionPath(activeEditionLead.seasonLabel)}
                isTied={activeEditionTiedRanks.has(activeEditionLead.rank)}
                meta={`${formatWholeNumber(activeEditionLead.goalsCount)} gols em ${formatWholeNumber(activeEditionLead.matchesCount)} jogos`}
                metricHint={
                  selectedEditionView === "volume"
                    ? `${formatPerMatch(activeEditionLead.goalsCount, activeEditionLead.matchesCount)} por jogo`
                    : `${formatWholeNumber(activeEditionLead.goalsCount)} gols no total`
                }
                metricLabel={selectedEditionView === "volume" ? "Gols" : "Média"}
                metricValue={
                  selectedEditionView === "volume"
                    ? formatWholeNumber(activeEditionLead.goalsCount)
                    : formatPerMatch(activeEditionLead.goalsCount, activeEditionLead.matchesCount)
                }
                rank={activeEditionLead.rank}
                subtitle={activeEditionLead.editionName}
                title={activeEditionLead.year}
                visual={
                  <EditionRankingVisual
                    tone={selectedEditionView}
                    year={activeEditionLead.year}
                  />
                }
              />

              {activeEditionRemainder.length > 0 ? (
                <div className="mt-3 divide-y divide-[rgba(191,201,195,0.22)]">
                  {activeEditionRemainder.map((edition) => (
                    <EditorialCompactRow
                      href={buildWorldCupEditionPath(edition.seasonLabel)}
                      isTied={activeEditionTiedRanks.has(edition.rank)}
                      key={`${activeEditionBlock.label}-${edition.seasonLabel}`}
                      meta={
                        selectedEditionView === "volume"
                          ? `${formatPerMatch(edition.goalsCount, edition.matchesCount)} por jogo · ${formatWholeNumber(edition.matchesCount)} jogos`
                          : `${formatWholeNumber(edition.goalsCount)} gols · ${formatWholeNumber(edition.matchesCount)} jogos`
                      }
                      metricLabel={selectedEditionView === "volume" ? "Gols" : "Média"}
                      metricValue={
                        selectedEditionView === "volume"
                          ? formatWholeNumber(edition.goalsCount)
                          : formatPerMatch(edition.goalsCount, edition.matchesCount)
                      }
                      rank={edition.rank}
                      subtitle={edition.editionName}
                      title={edition.year}
                      visual={
                        <EditionRankingVisual
                          compact
                          tone={selectedEditionView}
                          year={edition.year}
                        />
                      }
                    />
                  ))}
                </div>
              ) : null}
            </div>
          </article>
        ) : null}
      </ProfilePanel>

      <ProfilePanel className="space-y-4" tone="base">
        <SectionHeading
          aside={
            <>
              <ProfileTag className="bg-[rgba(255,250,240,0.72)] text-[#5f430a]">3+ gols</ProfileTag>
              <ProfileTag className="bg-[rgba(255,250,240,0.72)] text-[#5f430a]">{squadAppearancesLabel}</ProfileTag>
            </>
          }
          description="Artilharia consolidada por edição e nomes que atravessaram várias convocações do torneio."
          headingId="rankings-jogadores"
          kicker="Jogadores"
          title="Artilharia e longevidade"
        />

        <div className="grid gap-3 xl:grid-cols-2">
          <RankingCard
            footer={
              visibleScorers < playerRankings.scorers.items.length ? (
                <LoadMoreButton onClick={() => setVisibleScorers((current) => current + PLAYER_CARD_PAGE_SIZE)} />
              ) : null
            }
            metricLabel={playerRankings.scorers.metricLabel}
            title="Artilheiros"
            tone="featured"
          >
            {scorersToRender.map((scorer) => (
              <RankingListRow
                isTied={scorerTiedRanks.has(scorer.rank)}
                key={`${scorer.playerId ?? scorer.playerName ?? "scorer"}-${scorer.rank}`}
                media={
                  <ProfileMedia
                    alt={scorer.playerName ?? "Jogador"}
                    assetId={scorer.playerId}
                    category="players"
                    className="h-14 w-14 rounded-[1rem]"
                    fallback={buildFallbackLabel(scorer.playerName)}
                    imageClassName="p-0"
                    shape="rounded"
                  />
                }
                metricLabel="Gols"
                metricValue={formatWholeNumber(scorer.goals)}
                meta={scorer.editions.map((edition) => (
                  <ChipLink href={buildWorldCupEditionPath(edition.seasonLabel)} key={`${scorer.playerId ?? scorer.playerName ?? "scorer"}-${edition.seasonLabel}`}>
                    {edition.year} · {edition.goals}
                  </ChipLink>
                ))}
                rank={scorer.rank}
                subtitle={<TeamLink teamId={scorer.teamId} teamName={scorer.teamName} />}
                title={scorer.playerName ?? "Não identificado"}
              />
            ))}
          </RankingCard>

          <RankingCard
            footer={
              visibleSquadAppearances < playerRankings.squadAppearances.items.length ? (
                <LoadMoreButton onClick={() => setVisibleSquadAppearances((current) => current + PLAYER_CARD_PAGE_SIZE)} />
              ) : null
            }
            metricLabel={playerRankings.squadAppearances.metricLabel}
            title={`Jogadores com ${squadAppearancesLabel.toLowerCase()} no elenco`}
            tone="soft"
          >
            {squadAppearancesToRender.map((player) => (
              <RankingListRow
                isTied={squadAppearanceTiedRanks.has(player.rank)}
                key={`${player.playerId}-${player.rank}`}
                media={
                  <ProfileMedia
                    alt={player.playerName ?? "Jogador"}
                    assetId={player.playerId}
                    category="players"
                    className="h-14 w-14 rounded-[1rem]"
                    fallback={buildFallbackLabel(player.playerName)}
                    imageClassName="p-0"
                    shape="rounded"
                  />
                }
                metricLabel="Copas"
                metricValue={formatWholeNumber(player.appearancesCount)}
                meta={player.editions.map((edition) => (
                  <ChipLink href={buildWorldCupEditionPath(edition.seasonLabel)} key={`${player.playerId}-${edition.seasonLabel}`}>
                    {edition.year}
                  </ChipLink>
                ))}
                rank={player.rank}
                subtitle={<TeamLink teamId={player.teamId} teamName={player.teamName} />}
                title={player.playerName ?? "Não identificado"}
              />
            ))}
          </RankingCard>
        </div>
      </ProfilePanel>

      {matchRankings.highestScoringFinals.items.length > 0 || matchRankings.biggestWins.items.length > 0 ? (
        <ProfilePanel className="space-y-4" tone="base">
          <SectionHeading
            aside={
              <SectionToggleGroup
                ariaLabel="Visões de partidas históricas"
                onChange={setSelectedMatchView}
                options={[
                  { label: "Finais", value: "finais" },
                  { label: "Goleadas", value: "goleadas" },
                ]}
                value={selectedMatchView}
              />
            }
            description="Finais mais abertas e goleadas mais largas do torneio"
            headingId="rankings-partidas"
            kicker="Partidas históricas"
            title="Partidas Históricas"
          />

          {activeMatchLead ? (
            <article className="rounded-[1.55rem] border border-[rgba(191,201,195,0.42)] bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(249,251,255,0.96)_100%)] p-4 shadow-[0_24px_62px_-52px_rgba(17,28,45,0.22)] md:p-5">
              <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div className="space-y-1.5">
                  <p className="text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">
                    {activeMatchBlock.metricLabel}
                  </p>
                  <h3 className="font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold tracking-[-0.04em] text-[#1d160c] md:text-[1.6rem]">
                    {activeMatchBlock.label}
                  </h3>
                  <p className="max-w-3xl text-sm/6 text-[#6d5c3f]">
                    {selectedMatchView === "finais"
                      ? "Decisões abertas pedem leitura de placar antes do resto. O contexto fica discreto, e o volume de gols passa a organizar a história."
                      : "Nas goleadas, o saldo é a leitura dominante. O placar vem logo depois, com estádio e contexto só como apoio editorial."}
                  </p>
                </div>

                <div className="rounded-[1rem] border border-[rgba(138,109,24,0.12)] bg-[rgba(255,251,240,0.74)] px-4 py-3">
                  <p className="text-[0.56rem] font-semibold uppercase tracking-[0.16em] text-[#6d5c3f]">Leitura ativa</p>
                  <p className="mt-1 font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-none tracking-[-0.04em] text-[#1d160c]">
                    {selectedMatchView === "finais" ? "Finais" : "Goleadas"}
                  </p>
                  <p className="mt-1 text-[0.72rem]/5 text-[#7b6b4f]">Top {formatWholeNumber(activeMatchItems.length)} partidas</p>
                </div>
              </header>

              <div className="mt-4">
                <EditorialLeadCard
                  href={buildWorldCupEditionPath(activeMatchLead.seasonLabel)}
                  isTied={activeMatchTiedRanks.has(activeMatchLead.rank)}
                  meta={
                    getMatchVenueMeta(activeMatchLead) ? (
                      <span className="inline-flex items-center gap-1.5">
                        <RankingGlyph className="h-3.5 w-3.5" icon="stadium" />
                        {getMatchVenueMeta(activeMatchLead)}
                      </span>
                    ) : undefined
                  }
                  metricHint={
                    selectedMatchView === "finais"
                      ? "final recordista"
                      : `${formatWholeNumber(activeMatchLead.totalGoals)} gols no placar total`
                  }
                  metricLabel={selectedMatchView === "finais" ? "Gols" : "Saldo"}
                  metricValue={
                    selectedMatchView === "finais"
                      ? formatWholeNumber(activeMatchLead.totalGoals)
                      : formatWholeNumber(isBiggestWinRecord(activeMatchLead) ? activeMatchLead.goalDiff : null)
                  }
                  rank={activeMatchLead.rank}
                  subtitle={formatFixtureLabel({
                    awayTeamName: activeMatchLead.awayTeam?.teamName,
                    homeTeamName: activeMatchLead.homeTeam?.teamName,
                  })}
                  title={activeMatchLead.year}
                  visual={
                    <MatchScoreVisual
                      awayScore={activeMatchLead.awayScore}
                      awayTeamId={activeMatchLead.awayTeam?.teamId}
                      awayTeamName={activeMatchLead.awayTeam?.teamName}
                      homeScore={activeMatchLead.homeScore}
                      homeTeamId={activeMatchLead.homeTeam?.teamId}
                      homeTeamName={activeMatchLead.homeTeam?.teamName}
                      tone={selectedMatchView}
                    />
                  }
                />

                {activeMatchRemainder.length > 0 ? (
                  <div className="mt-3 divide-y divide-[rgba(191,201,195,0.22)]">
                    {activeMatchRemainder.map((match) => (
                      <EditorialCompactRow
                        href={buildWorldCupEditionPath(match.seasonLabel)}
                        isTied={activeMatchTiedRanks.has(match.rank)}
                        key={"fixtureId" in match ? match.fixtureId : `${match.seasonLabel}-final`}
                        meta={
                          getMatchVenueMeta(match) ? (
                            <span className="inline-flex items-center gap-1.5">
                              <RankingGlyph className="h-3.5 w-3.5" icon="stadium" />
                              {getMatchVenueMeta(match)}
                            </span>
                          ) : undefined
                        }
                        metricLabel={selectedMatchView === "finais" ? "Gols" : "Saldo"}
                        metricValue={
                          selectedMatchView === "finais"
                            ? formatWholeNumber(match.totalGoals)
                            : formatWholeNumber(isBiggestWinRecord(match) ? match.goalDiff : null)
                        }
                        rank={match.rank}
                        subtitle={formatFixtureLabel({
                          awayTeamName: match.awayTeam?.teamName,
                          homeTeamName: match.homeTeam?.teamName,
                        })}
                        title={match.year}
                        visual={
                          <MatchScoreVisual
                            awayScore={match.awayScore}
                            awayTeamId={match.awayTeam?.teamId}
                            awayTeamName={match.awayTeam?.teamName}
                            compact
                            homeScore={match.homeScore}
                            homeTeamId={match.homeTeam?.teamId}
                            homeTeamName={match.homeTeam?.teamName}
                            tone={selectedMatchView}
                          />
                        }
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            </article>
          ) : null}
        </ProfilePanel>
      ) : null}
    </ProfileShell>
  );
}
