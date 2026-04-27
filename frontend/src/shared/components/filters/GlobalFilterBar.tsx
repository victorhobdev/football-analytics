"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useGlobalFilters } from "@/shared/hooks/useGlobalFilters";
import { useGlobalFiltersStore } from "@/shared/stores/globalFilters.store";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type { GlobalFiltersState, VenueFilter } from "@/shared/types/filters.types";
import { getCompetitionById, SUPPORTED_COMPETITIONS } from "@/config/competitions.registry";
import {
  getSeasonById,
  getSeasonByQueryId,
  listSeasonsForCompetition,
  resolveSeasonForCompetition,
  SUPPORTED_SEASONS,
} from "@/config/seasons.registry";
import {
  buildCanonicalTeamPath,
  buildCompetitionHubPath,
  buildSeasonHubPath,
  getContextQueryKeysToLockForPath,
  getContextQueryKeysToOmitForPath,
  resolveCompetitionSeasonContextFromPathname,
} from "@/shared/utils/context-routing";
import { describeTimeWindowLabel } from "@/shared/utils/filter-descriptions";

const FILTER_QUERY_KEYS = [
  "competitionId",
  "seasonId",
  "teamId",
  "roundId",
  "venue",
  "lastN",
  "dateRangeStart",
  "dateRangeEnd",
] as const;
const WORLD_CUP_STATIC_PATH_SEGMENTS = new Set(["finais", "rankings", "selecoes"]);

type SearchParamsLike = Pick<URLSearchParams, "get">;
type SeasonSelectOption = {
  value: string;
  label: string;
};

function isWorldCupEditionPathname(pathname: string): boolean {
  const match = pathname.match(/^\/copa-do-mundo\/([^/]+)(?:\/|$)/);

  if (!match) {
    return false;
  }

  return !WORLD_CUP_STATIC_PATH_SEGMENTS.has(match[1]);
}

function isSeasonHubRootPathname(pathname: string): boolean {
  return (
    /^\/competitions\/[^/]+\/seasons\/[^/]+\/?$/.test(pathname) ||
    isWorldCupEditionPathname(pathname)
  );
}

function resolveCanonicalTeamIdFromPathname(pathname: string): string | null {
  const match = pathname.match(/^\/competitions\/[^/]+\/seasons\/[^/]+\/teams\/([^/]+)(?:\/|$)/);

  if (!match) {
    return null;
  }

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

function parseVenue(value: string | null): VenueFilter {
  if (value === "home" || value === "away" || value === "all") {
    return value;
  }

  return "all";
}

function parseNullableText(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (trimmed.toLowerCase() === "all") {
    return null;
  }

  return trimmed.length > 0 ? trimmed : null;
}

function parseLastN(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }

  return parsed;
}

function buildSeasonOptions(
  competitionId: string | null,
  selectedSeasonId: string | null,
): SeasonSelectOption[] {
  const competition = getCompetitionById(competitionId);

  if (competition) {
    const options = listSeasonsForCompetition(competition).map((season) => ({
      value: season.queryId,
      label: season.label,
    }));

    const selectedSeason = getSeasonByQueryId(selectedSeasonId, competition.seasonCalendar);

    if (
      selectedSeason &&
      !options.some(
        (option) =>
          option.value === selectedSeason.queryId && option.label === selectedSeason.label,
      )
    ) {
      options.unshift({
        value: selectedSeason.queryId,
        label: selectedSeason.label,
      });
    }

    return options;
  }

  const options: SeasonSelectOption[] = [];
  const seenQueryIds = new Set<string>();

  for (const season of SUPPORTED_SEASONS) {
    if (seenQueryIds.has(season.queryId)) {
      continue;
    }

    seenQueryIds.add(season.queryId);
    options.push({
      value: season.queryId,
      label: season.queryId,
    });
  }

  return options;
}

function parseFiltersFromSearchParams(searchParams: SearchParamsLike): GlobalFiltersState {
  const competitionId = parseNullableText(searchParams.get("competitionId"));
  const seasonId = parseNullableText(searchParams.get("seasonId"));
  const teamId = parseNullableText(searchParams.get("teamId"));
  const roundId = parseNullableText(searchParams.get("roundId"));
  const venue = parseVenue(searchParams.get("venue"));
  const lastN = parseLastN(searchParams.get("lastN"));
  const dateRangeStartFromQuery = parseNullableText(searchParams.get("dateRangeStart"));
  const dateRangeEndFromQuery = parseNullableText(searchParams.get("dateRangeEnd"));
  const hasLastN = lastN !== null;

  return {
    competitionId,
    seasonId,
    teamId,
    roundId,
    venue,
    lastN,
    dateRangeStart: hasLastN ? null : dateRangeStartFromQuery,
    dateRangeEnd: hasLastN ? null : dateRangeEndFromQuery,
  };
}

function areFiltersEqual(a: GlobalFiltersState, b: GlobalFiltersState): boolean {
  return (
    a.competitionId === b.competitionId &&
    a.seasonId === b.seasonId &&
    a.teamId === b.teamId &&
    a.roundId === b.roundId &&
    a.venue === b.venue &&
    a.lastN === b.lastN &&
    a.dateRangeStart === b.dateRangeStart &&
    a.dateRangeEnd === b.dateRangeEnd
  );
}

function readGlobalFiltersSnapshot(): GlobalFiltersState {
  const state = useGlobalFiltersStore.getState();

  return {
    competitionId: state.competitionId,
    seasonId: state.seasonId,
    teamId: state.teamId,
    roundId: state.roundId,
    venue: state.venue,
    lastN: state.lastN,
    dateRangeStart: state.dateRangeStart,
    dateRangeEnd: state.dateRangeEnd,
  };
}

function upsertQueryParams(
  currentSearchParams: URLSearchParams,
  filters: GlobalFiltersState,
  omittedContextKeys: ReadonlySet<string>,
): URLSearchParams {
  const nextSearchParams = new URLSearchParams(currentSearchParams.toString());

  for (const key of FILTER_QUERY_KEYS) {
    nextSearchParams.delete(key);
  }

  if (filters.competitionId && !omittedContextKeys.has("competitionId")) {
    nextSearchParams.set("competitionId", filters.competitionId);
  }

  if (filters.seasonId && !omittedContextKeys.has("seasonId")) {
    nextSearchParams.set("seasonId", filters.seasonId);
  }

  if (filters.teamId) {
    nextSearchParams.set("teamId", filters.teamId);
  }

  if (filters.roundId) {
    nextSearchParams.set("roundId", filters.roundId);
  }

  if (filters.venue !== "all") {
    nextSearchParams.set("venue", filters.venue);
  }

  if (filters.lastN !== null) {
    nextSearchParams.set("lastN", String(filters.lastN));
  } else {
    if (filters.dateRangeStart) {
      nextSearchParams.set("dateRangeStart", filters.dateRangeStart);
    }

    if (filters.dateRangeEnd) {
      nextSearchParams.set("dateRangeEnd", filters.dateRangeEnd);
    }
  }

  return nextSearchParams;
}

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function FieldHeader({
  badge,
  compact = false,
  label,
}: {
  badge?: ReactNode;
  compact?: boolean;
  label: string;
}) {
  return (
    <div className={joinClasses("flex items-center justify-between gap-2", compact ? "mb-1" : "mb-[0.42rem]")}>
      <span
        className={joinClasses(
          "font-bold uppercase text-[#69778d]",
          compact ? "text-[0.68rem] tracking-[0.14em]" : "text-[0.74rem] tracking-[0.16em]",
        )}
      >
        {label}
      </span>
      {badge}
    </div>
  );
}

function FilterField({
  label,
  badge,
  children,
  compact = false,
}: {
  label: string;
  badge?: ReactNode;
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <label className="flex min-w-0 flex-col text-sm text-[#223146]">
      <FieldHeader badge={badge} compact={compact} label={label} />
      {children}
    </label>
  );
}

function StyledSelect({
  compact = false,
  disabled = false,
  id,
  label,
  onChange,
  options,
  placeholder,
  value,
}: {
  compact?: boolean;
  disabled?: boolean;
  id: string;
  label: string;
  onChange: (value: string) => void;
  options: SeasonSelectOption[];
  placeholder: string;
  value: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find((option) => option.value === value);
  const displayValue = selectedOption?.label ?? placeholder;

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (containerRef.current?.contains(event.target as Node)) {
        return;
      }

      setIsOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={label}
        className={joinClasses(
          "flex w-full items-center justify-between gap-3 bg-white/95 text-left font-semibold text-[#162235] shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)] outline-none transition-[box-shadow,background-color,transform] duration-180 ease-[cubic-bezier(0.23,1,0.32,1)] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,53,38,0.14),inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)] active:scale-[0.99]",
          compact
            ? "min-h-[2.35rem] rounded-[0.78rem] px-3 py-2 text-[0.84rem]"
            : "min-h-[2.9rem] rounded-[0.95rem] px-[0.85rem] py-[0.7rem] text-[0.92rem]",
          disabled
            ? "cursor-not-allowed bg-[rgba(222,228,237,0.72)] text-[#93a0b4]"
            : "hover:bg-white",
        )}
        disabled={disabled}
        id={id}
        onClick={() => {
          setIsOpen((current) => !current);
        }}
        type="button"
      >
        <span className="truncate">{displayValue}</span>
        <span
          aria-hidden="true"
          className={joinClasses(
            "h-2 w-2 shrink-0 rotate-45 border-b-2 border-r-2 border-[#7a879a] transition-transform duration-180 ease-[cubic-bezier(0.23,1,0.32,1)]",
            isOpen && "translate-y-0.5 rotate-[225deg]",
          )}
        />
      </button>

      {isOpen ? (
        <div
          className="absolute left-0 top-[calc(100%+0.45rem)] z-50 max-h-80 w-full min-w-[16rem] overflow-y-auto rounded-[0.95rem] border border-[rgba(214,223,236,0.9)] bg-white p-1.5 shadow-[0_24px_56px_-34px_rgba(17,28,45,0.32)]"
          role="listbox"
        >
          {options.map((option) => {
            const isSelected = option.value === value;

            return (
              <button
                aria-selected={isSelected}
                className={joinClasses(
                  "flex min-h-9 w-full items-center rounded-[0.7rem] px-3 py-2 text-left text-[0.9rem] font-semibold transition-[background-color,color] duration-150 ease-[cubic-bezier(0.23,1,0.32,1)]",
                  isSelected
                    ? "bg-[#003526] text-white"
                    : "text-[#162235] hover:bg-[rgba(216,227,251,0.62)]",
                )}
                key={`${option.value}-${option.label}`}
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                role="option"
                type="button"
              >
                <span className="truncate">{option.label}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function StaticField({
  controlId,
  controlValue,
  label,
  value,
  badge,
  compact = false,
}: {
  controlId?: string;
  controlValue?: string;
  label: string;
  value: string;
  badge?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col text-sm text-[#223146]">
      <FieldHeader badge={badge} compact={compact} label={label} />
      <div
        className={joinClasses(
          "flex items-center bg-white/95 font-semibold text-[#162235] shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)]",
          compact
            ? "min-h-[2.35rem] rounded-[0.78rem] px-3 py-2 text-[0.84rem]"
            : "min-h-[2.9rem] rounded-[0.95rem] px-[0.85rem] py-[0.7rem] text-[0.92rem]",
        )}
      >
        <span className="truncate">{value}</span>
      </div>
      {controlId ? (
        <input
          aria-hidden="true"
          className="sr-only"
          disabled
          id={controlId}
          readOnly
          tabIndex={-1}
          type="text"
          value={controlValue ?? ""}
        />
      ) : null}
    </div>
  );
}

export function GlobalFilterBar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const hydratedUrlRef = useRef<string | null>(null);
  const pendingUrlRef = useRef<string | null>(null);
  const [isUrlHydrated, setIsUrlHydrated] = useState(false);

  const {
    competitionId,
    seasonId,
    teamId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
    setCompetitionId,
    setSeasonId,
    setTeamId,
    setRoundId,
    setVenue,
    setTimeRange,
  } = useGlobalFilters();

  const { activeMode } = useTimeRange();
  const omittedContextKeys = useMemo(
    () => new Set(getContextQueryKeysToOmitForPath(pathname)),
    [pathname],
  );
  const lockedContextKeys = useMemo(
    () => new Set(getContextQueryKeysToLockForPath(pathname)),
    [pathname],
  );
  const canonicalTeamId = useMemo(() => resolveCanonicalTeamIdFromPathname(pathname), [pathname]);
  const isCompetitionContextLocked = lockedContextKeys.has("competitionId");
  const isSeasonContextLocked = canonicalTeamId === null && lockedContextKeys.has("seasonId");
  const hasLockedRouteContext = isCompetitionContextLocked || isSeasonContextLocked;
  const isCompetitionScopedPath = useMemo(
    () => /^\/competitions\/[^/]+(?:\/|$)/.test(pathname) || pathname === "/copa-do-mundo" || pathname.startsWith("/copa-do-mundo/"),
    [pathname],
  );
  const isCompetitionSeasonScopedPath = useMemo(
    () => /^\/competitions\/[^/]+\/seasons\/[^/]+(?:\/|$)/.test(pathname) || isWorldCupEditionPathname(pathname),
    [pathname],
  );
  const isSeasonHubRootPath = useMemo(() => isSeasonHubRootPathname(pathname), [pathname]);
  const pathnameContext = useMemo(
    () => resolveCompetitionSeasonContextFromPathname(pathname),
    [pathname],
  );
  const effectiveCompetitionId = competitionId ?? pathnameContext?.competitionId ?? null;
  const effectiveSeasonId = seasonId ?? pathnameContext?.seasonId ?? null;
  const selectedCompetition = useMemo(
    () => getCompetitionById(effectiveCompetitionId),
    [effectiveCompetitionId],
  );
  const selectedSeason = useMemo(() => {
    if (selectedCompetition) {
      return (
        getSeasonByQueryId(effectiveSeasonId, selectedCompetition.seasonCalendar) ??
        getSeasonById(effectiveSeasonId)
      );
    }

    return getSeasonById(effectiveSeasonId);
  }, [effectiveSeasonId, selectedCompetition]);
  const seasonOptions = useMemo(
    () => buildSeasonOptions(effectiveCompetitionId, effectiveSeasonId),
    [effectiveCompetitionId, effectiveSeasonId],
  );
  const competitionOptions = useMemo(
    () => [
      { value: "", label: "Todas as competições" },
      ...SUPPORTED_COMPETITIONS.map((competition) => ({
        value: competition.id,
        label: competition.name,
      })),
    ],
    [],
  );
  const seasonDropdownOptions = useMemo(
    () => [{ value: "", label: "Todas as temporadas" }, ...seasonOptions],
    [seasonOptions],
  );
  const resetButtonLabel = "Limpar filtros";
  const selectedCompetitionLabel =
    selectedCompetition?.shortName ?? selectedCompetition?.name ?? "Todas as competições";
  const selectedSeasonLabel = selectedSeason?.label ?? "Todas as temporadas";
  const activeWindowSummary =
    lastN !== null
      ? `Últimos ${lastN} jogos`
      : dateRangeStart !== null || dateRangeEnd !== null
        ? `Período ${dateRangeStart ?? "aberto"} até ${dateRangeEnd ?? "aberto"}`
        : describeTimeWindowLabel({
            roundId,
            lastN,
            dateRangeStart,
            dateRangeEnd,
          });
  const hasSeasonHubExtraFilters = Boolean(
    teamId || roundId || venue !== "all" || lastN !== null || dateRangeStart || dateRangeEnd,
  );
  const hasResettableFilters = Boolean(
    isSeasonHubRootPath
      ? hasSeasonHubExtraFilters
      : (!isCompetitionContextLocked && competitionId) ||
          (!isSeasonContextLocked && seasonId) ||
          teamId ||
          roundId ||
          venue !== "all" ||
          lastN !== null ||
          dateRangeStart ||
          dateRangeEnd,
  );
  const isWorldCupPath = pathname === "/copa-do-mundo" || pathname.startsWith("/copa-do-mundo/");
  const shouldUseCompactFilterBar = isWorldCupPath;
  const shouldShowActiveWindowSummary =
    activeWindowSummary !== "Temporada inteira" &&
    (activeMode !== "lastN" || lastN !== null || dateRangeStart !== null || dateRangeEnd !== null);
  const compactStatusSummary = [
    roundId ? `Rodada ${roundId}` : null,
    shouldShowActiveWindowSummary ? activeWindowSummary : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const controlBarClasses = joinClasses(
    isWorldCupPath
      ? "border border-[rgba(138,109,24,0.14)] bg-[linear-gradient(180deg,rgba(255,251,241,0.92),rgba(255,255,255,0.96))] shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_16px_34px_-32px_rgba(95,67,10,0.16)]"
      : "bg-[linear-gradient(180deg,rgba(240,243,255,0.82),rgba(248,251,255,0.92))] shadow-[inset_0_1px_0_rgba(255,255,255,0.84),0_16px_36px_-34px_rgba(17,28,45,0.18)]",
    isWorldCupPath ? "rounded-[1rem] p-2.5 md:p-3" : "rounded-[1.35rem] p-4",
  );
  const resetButtonClasses = joinClasses(
    "button-pill w-full self-end lg:w-auto lg:self-end lg:whitespace-nowrap",
    hasResettableFilters ? "button-pill-primary" : "button-pill-secondary border-[rgba(191,201,195,0.36)] bg-white/65 text-[#93a0b4]",
  );

  const currentFilters = useMemo(
    () => ({
      competitionId,
      seasonId,
      roundId,
      venue,
      teamId,
      lastN,
      dateRangeStart,
      dateRangeEnd,
    }),
    [competitionId, dateRangeEnd, dateRangeStart, lastN, roundId, seasonId, teamId, venue],
  );
  const currentUrlSignature = useMemo(
    () => `${pathname}?${searchParams.toString()}`,
    [pathname, searchParams],
  );
  const replaceFiltersInUrl = useCallback(
    (overrides: Partial<GlobalFiltersState>, nextPathname?: string) => {
      const targetPathname = nextPathname ?? pathname;
      const targetOmittedContextKeys = new Set(getContextQueryKeysToOmitForPath(targetPathname));

      if (!isUrlHydrated && hydratedUrlRef.current !== currentUrlSignature) {
        hydratedUrlRef.current = currentUrlSignature;
        setIsUrlHydrated(true);
      }

      const pendingUrl = pendingUrlRef.current;
      const pendingPathname = pendingUrl?.split("?")[0] ?? null;
      const baseSearchParams =
        pendingUrl && pendingPathname === targetPathname
          ? new URLSearchParams(pendingUrl.split("?")[1] ?? "")
          : new URLSearchParams(searchParams.toString());
      const nextFilters = {
        ...readGlobalFiltersSnapshot(),
        ...overrides,
      };
      const nextSearchParams = upsertQueryParams(
        baseSearchParams,
        nextFilters,
        targetOmittedContextKeys,
      );
      const nextQuery = nextSearchParams.toString();
      const nextUrl = nextQuery.length > 0 ? `${targetPathname}?${nextQuery}` : targetPathname;

      if ((pendingUrl ?? currentUrlSignature) === nextUrl) {
        return;
      }

      pendingUrlRef.current = nextUrl;
      router.replace(nextUrl, { scroll: false });
    },
    [currentUrlSignature, isUrlHydrated, pathname, router, searchParams],
  );
  const applySeasonHubContextChange = useCallback(
    ({
      nextCompetitionId,
      nextPathname,
      nextSeasonId,
    }: {
      nextCompetitionId: string | null;
      nextPathname: string;
      nextSeasonId: string | null;
    }) => {
      setCompetitionId(nextCompetitionId);
      setSeasonId(nextSeasonId);
      if (teamId !== null) {
        setTeamId(null);
      }
      if (roundId !== null) {
        setRoundId(null);
      }
      if (venue !== "all") {
        setVenue("all");
      }
      setTimeRange({ mode: "lastN", lastN: null });
      replaceFiltersInUrl(
        {
          competitionId: nextCompetitionId,
          seasonId: nextSeasonId,
          teamId: null,
          roundId: null,
          venue: "all",
          lastN: null,
          dateRangeStart: null,
          dateRangeEnd: null,
        },
        nextPathname,
      );
    },
    [
      replaceFiltersInUrl,
      roundId,
      setCompetitionId,
      setRoundId,
      setSeasonId,
      setTeamId,
      setTimeRange,
      setVenue,
      teamId,
      venue,
    ],
  );
  const handleReset = useCallback(() => {
    if (isSeasonHubRootPath) {
      if (teamId !== null) {
        setTeamId(null);
      }
      if (roundId !== null) {
        setRoundId(null);
      }
      if (venue !== "all") {
        setVenue("all");
      }
      setTimeRange({ mode: "lastN", lastN: null });
      replaceFiltersInUrl({
        competitionId: effectiveCompetitionId,
        seasonId: effectiveSeasonId,
        teamId: null,
        roundId: null,
        venue: "all",
        lastN: null,
        dateRangeStart: null,
        dateRangeEnd: null,
      });
      return;
    }

    const nextCompetitionId = isCompetitionContextLocked ? competitionId : null;
    const nextSeasonId = isSeasonContextLocked ? seasonId : null;

    setCompetitionId(nextCompetitionId);
    setSeasonId(nextSeasonId);
    setTeamId(null);
    setRoundId(null);
    setVenue("all");
    setTimeRange({ mode: "lastN", lastN: null });
    replaceFiltersInUrl(
      {
        competitionId: nextCompetitionId,
        seasonId: nextSeasonId,
        teamId: null,
        roundId: null,
        venue: "all",
        lastN: null,
        dateRangeStart: null,
        dateRangeEnd: null,
      },
      canonicalTeamId ? `/teams/${encodeURIComponent(canonicalTeamId)}` : undefined,
    );
  }, [
    canonicalTeamId,
    competitionId,
    effectiveCompetitionId,
    effectiveSeasonId,
    isSeasonHubRootPath,
    isCompetitionContextLocked,
    isSeasonContextLocked,
    replaceFiltersInUrl,
    roundId,
    seasonId,
    setCompetitionId,
    setRoundId,
    setSeasonId,
    setTeamId,
    setTimeRange,
    setVenue,
    teamId,
    venue,
  ]);

  useEffect(() => {
    if (!selectedCompetition || !seasonId) {
      return;
    }

    const seasonStillAvailable = seasonOptions.some((option) => option.value === seasonId);
    if (!seasonStillAvailable) {
      setSeasonId(null);
      if (roundId !== null) {
        setRoundId(null);
      }
    }
  }, [roundId, seasonId, seasonOptions, selectedCompetition, setRoundId, setSeasonId]);

  useLayoutEffect(() => {
    if (hydratedUrlRef.current === currentUrlSignature) {
      return;
    }

    const pendingUrl = pendingUrlRef.current;
    const pendingPathname = pendingUrl?.split("?")[0] ?? null;

    if (pendingUrl && pendingPathname === pathname) {
      hydratedUrlRef.current = currentUrlSignature;
      setIsUrlHydrated(true);

      if (currentUrlSignature === pendingUrl) {
        pendingUrlRef.current = null;
      }

      return;
    }

    if (pendingUrl && pendingPathname !== pathname) {
      pendingUrlRef.current = null;
    }

    const parsedFilters = parseFiltersFromSearchParams(searchParams);
    if (pathnameContext) {
      parsedFilters.competitionId = pathnameContext.competitionId;
      parsedFilters.seasonId = pathnameContext.seasonId;
    }
    const currentStoreFilters = readGlobalFiltersSnapshot();

    if (!areFiltersEqual(currentStoreFilters, parsedFilters)) {
      setCompetitionId(parsedFilters.competitionId);
      setSeasonId(parsedFilters.seasonId);
      setTeamId(parsedFilters.teamId);
      setRoundId(parsedFilters.roundId);
      setVenue(parsedFilters.venue);

      if (parsedFilters.lastN !== null) {
        setTimeRange({ mode: "lastN", lastN: parsedFilters.lastN });
      } else if (parsedFilters.dateRangeStart !== null || parsedFilters.dateRangeEnd !== null) {
        setTimeRange({
          mode: "dateRange",
          dateRangeStart: parsedFilters.dateRangeStart,
          dateRangeEnd: parsedFilters.dateRangeEnd,
        });
      } else {
        setTimeRange({ mode: "lastN", lastN: null });
      }
    }

    hydratedUrlRef.current = currentUrlSignature;
    setIsUrlHydrated(true);
  }, [
    currentUrlSignature,
    currentFilters,
    pathnameContext,
    pathname,
    searchParams,
    setCompetitionId,
    setRoundId,
    setSeasonId,
    setTeamId,
    setTimeRange,
    setVenue,
  ]);

  useEffect(() => {
    if (!isUrlHydrated) {
      return;
    }

    const currentSearchParams = new URLSearchParams(searchParams.toString());
    const nextSearchParams = upsertQueryParams(
      currentSearchParams,
      readGlobalFiltersSnapshot(),
      omittedContextKeys,
    );
    const currentQuery = currentSearchParams.toString();
    const nextQuery = nextSearchParams.toString();

    if (currentQuery === nextQuery) {
      return;
    }

    const nextUrl = nextQuery.length > 0 ? `${pathname}?${nextQuery}` : pathname;
    pendingUrlRef.current = nextUrl;
    router.replace(nextUrl, { scroll: false });
  }, [currentFilters, isUrlHydrated, omittedContextKeys, pathname, router, searchParams]);

  useEffect(() => {
    if (!effectiveCompetitionId || !effectiveSeasonId) {
      if (teamId !== null) {
        setTeamId(null);
        replaceFiltersInUrl({ teamId: null });
      }
    }
  }, [effectiveCompetitionId, effectiveSeasonId, replaceFiltersInUrl, setTeamId, teamId]);

  if (isSeasonHubRootPath) {
    return (
      <section
        aria-label="Contexto da edição"
        data-url-hydrated={isUrlHydrated ? "true" : "false"}
        className={controlBarClasses}
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px] lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-end">
          <FilterField label="Competição">
            <StyledSelect
              id="global-filter-competition-id"
              label="Competição"
              onChange={(nextValue) => {
                const nextCompetitionId = parseNullableText(nextValue);
                const nextCompetition = getCompetitionById(nextCompetitionId);
                const nextSeason = nextCompetition
                  ? resolveSeasonForCompetition(nextCompetition, {
                      seasonId: effectiveSeasonId,
                      seasonLabel: selectedSeason?.label ?? effectiveSeasonId,
                    })
                  : null;

                applySeasonHubContextChange({
                  nextCompetitionId,
                  nextPathname: nextCompetition
                    ? nextSeason
                      ? buildSeasonHubPath({
                          competitionKey: nextCompetition.key,
                          seasonLabel: nextSeason.label,
                        })
                      : buildCompetitionHubPath(nextCompetition.key)
                    : "/competitions",
                  nextSeasonId: nextSeason?.queryId ?? null,
                });
              }}
              options={competitionOptions}
              placeholder="Todas as competições"
              value={effectiveCompetitionId ?? ""}
            />
          </FilterField>

          <FilterField label="Temporada">
            <StyledSelect
              disabled={!selectedCompetition}
              id="global-filter-season-id"
              label="Temporada"
              onChange={(nextValue) => {
                const nextSeasonId = parseNullableText(nextValue);
                const nextSeason =
                  selectedCompetition && nextSeasonId
                    ? resolveSeasonForCompetition(selectedCompetition, {
                        seasonId: nextSeasonId,
                        seasonLabel:
                          getSeasonByQueryId(nextSeasonId, selectedCompetition.seasonCalendar)
                            ?.label ?? nextSeasonId,
                      })
                    : null;

                applySeasonHubContextChange({
                  nextCompetitionId: effectiveCompetitionId,
                  nextPathname: selectedCompetition
                    ? nextSeason
                      ? buildSeasonHubPath({
                          competitionKey: selectedCompetition.key,
                          seasonLabel: nextSeason.label,
                        })
                      : buildCompetitionHubPath(selectedCompetition.key)
                    : "/competitions",
                  nextSeasonId: nextSeason?.queryId ?? null,
                });
              }}
              options={seasonDropdownOptions}
              placeholder="Todas as temporadas"
              value={effectiveSeasonId ?? ""}
            />
          </FilterField>

          <button
            className={resetButtonClasses}
            disabled={!hasResettableFilters}
            onClick={handleReset}
            type="button"
          >
            {resetButtonLabel}
          </button>
        </div>
        {compactStatusSummary ? (
          <p className="mt-3 text-[0.8rem] font-semibold text-[#687790]">{compactStatusSummary}</p>
        ) : null}
      </section>
    );
  }

  return (
    <section
      aria-label="Filtros do produto"
      data-url-hydrated={isUrlHydrated ? "true" : "false"}
      className={controlBarClasses}
    >
      <div
        className={joinClasses(
          "grid",
          shouldUseCompactFilterBar
            ? "gap-2 md:grid-cols-[minmax(0,1fr)_200px] lg:grid-cols-[minmax(0,1fr)_200px_auto] lg:items-center"
            : "gap-3 md:grid-cols-[minmax(0,1fr)_220px] lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-end",
        )}
      >
        {isCompetitionContextLocked ? (
          <StaticField
            compact={shouldUseCompactFilterBar}
            controlId="global-filter-competition-id"
            controlValue={competitionId ?? ""}
            label="Competição"
            value={selectedCompetitionLabel}
          />
        ) : (
          <FilterField compact={shouldUseCompactFilterBar} label="Competição">
            <StyledSelect
              compact={shouldUseCompactFilterBar}
              disabled={isCompetitionContextLocked}
              id="global-filter-competition-id"
              label="Competição"
              onChange={(nextValue) => {
                const nextCompetitionId = parseNullableText(nextValue);
                const nextCompetition = getCompetitionById(nextCompetitionId);
                const nextSeason = nextCompetition
                  ? resolveSeasonForCompetition(nextCompetition, {
                      seasonId,
                      seasonLabel: selectedSeason?.label ?? seasonId,
                    })
                  : null;
                const nextSeasonId = nextSeason?.queryId ?? null;
                const nextPathname = canonicalTeamId
                  ? nextCompetition && nextSeason
                    ? buildCanonicalTeamPath(
                        {
                          competitionId: nextCompetition.id,
                          competitionKey: nextCompetition.key,
                          competitionName: nextCompetition.name,
                          seasonId: nextSeason.queryId,
                          seasonLabel: nextSeason.label,
                        },
                        canonicalTeamId,
                      )
                    : `/teams/${encodeURIComponent(canonicalTeamId)}`
                  : !isCompetitionScopedPath
                    ? undefined
                    : nextCompetition
                      ? isCompetitionSeasonScopedPath && nextSeason
                        ? buildSeasonHubPath({
                            competitionKey: nextCompetition.key,
                            seasonLabel: nextSeason.label,
                          })
                        : buildCompetitionHubPath(nextCompetition.key)
                      : "/competitions";

                setCompetitionId(nextCompetitionId);
                setSeasonId(nextSeasonId);
                if (teamId !== null) {
                  setTeamId(null);
                }
                if (roundId !== null) {
                  setRoundId(null);
                }
                replaceFiltersInUrl(
                  {
                    competitionId: nextCompetitionId,
                    seasonId: nextSeasonId,
                    teamId: null,
                    roundId: null,
                  },
                  nextPathname,
                );
              }}
              options={competitionOptions}
              placeholder="Todas as competições"
              value={competitionId ?? ""}
            />
          </FilterField>
        )}

        {isSeasonContextLocked ? (
          <StaticField
            compact={shouldUseCompactFilterBar}
            controlId="global-filter-season-id"
            controlValue={seasonId ?? ""}
            label="Temporada"
            value={selectedSeasonLabel}
          />
        ) : (
          <FilterField compact={shouldUseCompactFilterBar} label="Temporada">
            <StyledSelect
              compact={shouldUseCompactFilterBar}
              disabled={isSeasonContextLocked}
              id="global-filter-season-id"
              label="Temporada"
              onChange={(nextValue) => {
                const nextSeasonId = parseNullableText(nextValue);
                const nextRoundId = roundId !== null ? null : roundId;
                const nextSeason =
                  selectedCompetition && nextSeasonId
                    ? resolveSeasonForCompetition(selectedCompetition, {
                        seasonId: nextSeasonId,
                        seasonLabel:
                          getSeasonByQueryId(nextSeasonId, selectedCompetition.seasonCalendar)
                            ?.label ?? nextSeasonId,
                      })
                    : null;
                const nextPathname = canonicalTeamId
                  ? selectedCompetition && nextSeason
                    ? buildCanonicalTeamPath(
                        {
                          competitionId: selectedCompetition.id,
                          competitionKey: selectedCompetition.key,
                          competitionName: selectedCompetition.name,
                          seasonId: nextSeason.queryId,
                          seasonLabel: nextSeason.label,
                        },
                        canonicalTeamId,
                      )
                    : `/teams/${encodeURIComponent(canonicalTeamId)}`
                  : undefined;

                setSeasonId(nextSeasonId);
                if (teamId !== null) {
                  setTeamId(null);
                }
                if (roundId !== null) {
                  setRoundId(null);
                }
                replaceFiltersInUrl({
                  seasonId: nextSeasonId,
                  teamId: null,
                  roundId: nextRoundId,
                }, nextPathname);
              }}
              options={seasonDropdownOptions}
              placeholder="Todas as temporadas"
              value={seasonId ?? ""}
            />
          </FilterField>
        )}

        <button
          className={resetButtonClasses}
          disabled={!hasResettableFilters}
          onClick={handleReset}
          type="button"
        >
          {resetButtonLabel}
        </button>
      </div>
      {compactStatusSummary ? (
        <p className={joinClasses(shouldUseCompactFilterBar ? "mt-2 text-[0.74rem]" : "mt-3 text-[0.8rem]", "font-semibold text-[#687790]")}>
          {compactStatusSummary}
        </p>
      ) : null}
    </section>
  );
}
