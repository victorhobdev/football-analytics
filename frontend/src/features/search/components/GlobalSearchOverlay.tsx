"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import Link from "next/link";

import { useGlobalSearch } from "@/features/search/hooks";
import type {
  CompetitionSearchResult,
  MatchSearchResult,
  PlayerSearchResult,
  SearchDefaultContext,
  SearchGroup,
  TeamSearchResult,
} from "@/features/search/types";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfilePanel, ProfileTag } from "@/shared/components/profile/ProfilePrimitives";
import type {
  CompetitionSeasonContext,
  CompetitionSeasonContextInput,
} from "@/shared/types/context.types";
import {
  buildCompetitionHubPath,
  buildMatchCenterPath,
  buildPlayerResolverPath,
  buildTeamResolverPath,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";
import { formatDate } from "@/shared/utils/formatters";

type GlobalSearchOverlayProps = {
  isOpen: boolean;
  onClose: () => void;
};

const SEARCH_GROUP_LABELS: Record<SearchGroup["type"], string> = {
  competition: "Competições",
  match: "Partidas",
  player: "Jogadores",
  team: "Times",
};

const SEARCH_GROUP_TAGS = ["Competições", "Partidas", "Times", "Jogadores"] as const;

type SearchDisplayContext =
  | (CompetitionSeasonContext & CompetitionSeasonContextInput)
  | SearchDefaultContext;

function resolveDisplayContext(
  context: SearchDefaultContext | null | undefined,
): SearchDisplayContext | null {
  if (!context) {
    return null;
  }

  return (
    resolveCompetitionSeasonContext({
      competitionId: context.competitionId,
      seasonId: context.seasonId,
    }) ?? context
  );
}

function buildTeamResultHref(result: TeamSearchResult): string {
  return buildTeamResolverPath(result.teamId, {
    competitionId: result.defaultContext.competitionId,
    competitionKey: result.defaultContext.competitionKey,
    seasonId: result.defaultContext.seasonId,
  });
}

function buildPlayerResultHref(result: PlayerSearchResult): string {
  return buildPlayerResolverPath(result.playerId, {
    competitionId: result.defaultContext.competitionId,
    seasonId: result.defaultContext.seasonId,
  });
}

function buildMatchResultHref(result: MatchSearchResult): string {
  return buildMatchCenterPath(result.matchId, {
    competitionId: result.defaultContext.competitionId,
    seasonId: result.defaultContext.seasonId,
  });
}

function buildContextLine(context: SearchDisplayContext | null): string | null {
  const maybeRecord = context as Record<string, unknown> | null;
  const competitionName =
    maybeRecord && typeof maybeRecord.competitionName === "string"
      ? maybeRecord.competitionName
      : null;

  if (!competitionName || !context?.seasonLabel) {
    return null;
  }

  return `${competitionName} • ${context.seasonLabel}`;
}

function buildMatchScoreLine(result: MatchSearchResult): string {
  const hasHomeScore = typeof result.homeScore === "number" && Number.isFinite(result.homeScore);
  const hasAwayScore = typeof result.awayScore === "number" && Number.isFinite(result.awayScore);

  if (hasHomeScore && hasAwayScore) {
    return `${result.homeScore} x ${result.awayScore}`;
  }

  return "x";
}

function buildMatchMetaLine(result: MatchSearchResult): string | null {
  const displayContext = resolveDisplayContext(result.defaultContext);
  const contextLine = buildContextLine(displayContext);
  const kickoffLabel = result.kickoffAt ? formatDate(result.kickoffAt) : null;
  const roundLabel = result.roundId ? `Rodada ${result.roundId}` : null;

  const subtitle = [contextLine, roundLabel, kickoffLabel].filter(Boolean).join(" • ");
  return subtitle.length > 0 ? subtitle : null;
}

function buildSearchErrorDescription(): string {
  return "Não foi possível carregar os resultados agora. Tente novamente em instantes.";
}

function buildSearchFooterLabel(hasQuery: boolean, totalResults: number): string {
  if (!hasQuery) {
    return "Busque por nome, competição ou número da partida";
  }

  return `${totalResults} resultado${totalResults === 1 ? "" : "s"}`;
}

function renderGroupItems(group: SearchGroup, onClose: () => void) {
  if (group.type === "competition") {
    return group.items.map((item: CompetitionSearchResult) => (
      <Link
        className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-[rgba(191,201,195,0.4)] bg-white/85 px-4 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
        href={buildCompetitionHubPath(item.competitionKey)}
        key={`competition-${item.competitionId}`}
        onClick={onClose}
      >
        <div className="min-w-0">
          <p className="font-semibold text-[#111c2d]">{item.competitionName}</p>
          <p className="mt-1 text-xs text-[#57657a]">Visão geral da competição</p>
        </div>
        <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#003526]">
          Abrir
        </span>
      </Link>
    ));
  }

  if (group.type === "team") {
    return group.items.map((item: TeamSearchResult) => {
      const displayContext = resolveDisplayContext(item.defaultContext);
      const contextLine = buildContextLine(displayContext);

      return (
        <Link
          className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-[rgba(191,201,195,0.4)] bg-white/85 px-4 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
          href={buildTeamResultHref(item)}
          key={`team-${item.teamId}`}
          onClick={onClose}
        >
          <div className="min-w-0">
            <p className="font-semibold text-[#111c2d]">{item.teamName}</p>
            <p className="mt-1 text-xs text-[#57657a]">{contextLine ?? "Abrir perfil do time"}</p>
          </div>
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#003526]">
            Time
          </span>
        </Link>
      );
    });
  }

  if (group.type === "match") {
    return group.items.map((item: MatchSearchResult) => {
      const metaLine = buildMatchMetaLine(item);

      return (
        <Link
          className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-[rgba(191,201,195,0.4)] bg-white/85 px-4 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
          href={buildMatchResultHref(item)}
          key={`match-${item.matchId}`}
          onClick={onClose}
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold text-[#111c2d]">
                {item.homeTeamName ?? "Mandante"} x {item.awayTeamName ?? "Visitante"}
              </p>
              <span className="rounded-full bg-[rgba(216,227,251,0.76)] px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-[#1f2d40]">
                {item.status?.trim().length ? item.status : "Partida"}
              </span>
            </div>
            <p className="mt-1 text-xs text-[#57657a]">{metaLine ?? "Abrir detalhes da partida"}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-sm font-bold text-[#003526]">{buildMatchScoreLine(item)}</p>
            <span className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
              {item.status?.trim().length ? item.status : "Partida"}
            </span>
          </div>
        </Link>
      );
    });
  }

  return group.items.map((item: PlayerSearchResult) => {
    const displayContext = resolveDisplayContext(item.defaultContext);
    const contextLine = buildContextLine(displayContext);
    const subtitle = [item.teamName, contextLine].filter(Boolean).join(" • ");

    return (
      <Link
        className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-[rgba(191,201,195,0.4)] bg-white/85 px-4 py-3 transition-colors hover:border-[#8bd6b6] hover:bg-white"
        href={buildPlayerResultHref(item)}
        key={`player-${item.playerId}`}
        onClick={onClose}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-[#111c2d]">{item.playerName}</p>
            {item.position ? (
              <span className="rounded-full bg-[rgba(216,227,251,0.76)] px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-[#1f2d40]">
                {item.position}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-[#57657a]">
            {subtitle.length > 0 ? subtitle : "Abrir perfil do jogador"}
          </p>
        </div>
        <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#003526]">
          Jogador
        </span>
      </Link>
    );
  });
}

export function GlobalSearchOverlay({ isOpen, onClose }: GlobalSearchOverlayProps) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim());
  const inputRef = useRef<HTMLInputElement | null>(null);
  const searchQuery = useGlobalSearch(deferredQuery, {
    enabled: isOpen,
  });

  const visibleGroups = useMemo(
    () => (searchQuery.data?.groups ?? []).filter((group) => group.total > 0),
    [searchQuery.data?.groups],
  );
  const hasResults = visibleGroups.length > 0;
  const hasQuery = deferredQuery.length >= 2;

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      return;
    }

    inputRef.current?.focus();
    inputRef.current?.select();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(7,16,12,0.58)] px-4 pb-8 pt-24 backdrop-blur-md"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      role="dialog"
    >
      <div className="w-full max-w-4xl overflow-hidden rounded-[1.9rem] border border-[rgba(191,201,195,0.45)] bg-[rgba(245,248,241,0.96)] shadow-[0_40px_120px_rgba(7,16,12,0.35)]">
        <div className="border-b border-[rgba(191,201,195,0.45)] px-5 py-5 md:px-6">
          <div className="relative">
            <input
              className="w-full rounded-[1.6rem] border border-[rgba(112,121,116,0.22)] bg-white/92 px-5 py-4 pr-24 text-base font-medium text-[#111c2d] outline-none transition-colors focus:border-[#003526] focus:ring-2 focus:ring-[#003526]"
              id="global-search-input"
              onChange={(event) => {
                setQuery(event.target.value);
              }}
              placeholder="Buscar competições, partidas, times ou jogadores"
              ref={inputRef}
              value={query}
            />
            <button
              className="absolute right-3 top-1/2 inline-flex -translate-y-1/2 items-center rounded-full bg-[rgba(216,227,251,0.82)] px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[#1f2d40] transition-colors hover:bg-[rgba(216,227,251,0.98)]"
              onClick={onClose}
              type="button"
            >
              Esc
            </button>
          </div>
          <p className="mt-3 text-xs uppercase tracking-[0.16em] text-[#57657a]">
            Encontre competições, partidas, times e jogadores nas telas disponíveis agora.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {SEARCH_GROUP_TAGS.map((tag) => (
              <ProfileTag key={tag}>{tag}</ProfileTag>
            ))}
          </div>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-5 py-5 md:px-6">
          {!hasQuery ? (
            <EmptyState
              className="rounded-[1.45rem] border-[rgba(191,201,195,0.55)] bg-white/80"
              description="Busque por competição, time, jogador ou número da partida."
              title="Comece pela busca"
            />
          ) : null}

          {hasQuery && searchQuery.isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }, (_, index) => (
                <LoadingSkeleton height={84} key={`global-search-loading-${index}`} />
              ))}
            </div>
          ) : null}

          {hasQuery && searchQuery.isError ? (
            <EmptyState
              className="rounded-[1.45rem] border-[rgba(191,201,195,0.55)] bg-white/80"
              description={buildSearchErrorDescription()}
              title="Busca indisponível"
            />
          ) : null}

          {hasQuery && !searchQuery.isLoading && !searchQuery.isError && searchQuery.isPartial ? (
            <section
              aria-live="polite"
              className="mb-5 rounded-[1.35rem] border border-[#ffdcc3] bg-[#fff3e8] px-4 py-3 text-sm text-[#6e3900]"
            >
              <strong className="font-semibold uppercase tracking-[0.12em]">
                Resultados parciais.
              </strong>{" "}
              Alguns resultados podem aparecer em quantidade reduzida neste momento.
            </section>
          ) : null}

          {hasQuery && !searchQuery.isLoading && !searchQuery.isError && !hasResults ? (
            <EmptyState
              className="rounded-[1.45rem] border-[rgba(191,201,195,0.55)] bg-white/80"
              description={`Nenhum resultado foi encontrado para "${deferredQuery}". Tente o nome completo ou o número da partida.`}
              title="Sem resultados"
            />
          ) : null}

          {hasQuery && !searchQuery.isLoading && !searchQuery.isError && hasResults ? (
            <div className="space-y-5">
              {visibleGroups.map((group) => (
                <ProfilePanel className="space-y-4" key={group.type} tone="soft">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                      {SEARCH_GROUP_LABELS[group.type]}
                    </p>
                    <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#8b9790]">
                      {group.total} resultado{group.total === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="grid gap-3">{renderGroupItems(group, onClose)}</div>
                </ProfilePanel>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[rgba(191,201,195,0.45)] bg-[rgba(232,238,228,0.72)] px-5 py-4 text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a] md:px-6">
          <span>{buildSearchFooterLabel(hasQuery, searchQuery.data?.totalResults ?? 0)}</span>
          <div className="flex flex-wrap items-center gap-3">
            <span>Ctrl/Cmd + K para abrir, Esc para fechar</span>
          </div>
        </div>
      </div>
    </div>
  );
}
