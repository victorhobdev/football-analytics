"use client";

import Link from "next/link";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { useHomePage } from "@/features/home/hooks/useHomePage";
import { PlayerComparisonPanel } from "@/features/players/components/PlayerComparisonPanel";
import { GlobalSearchOverlay } from "@/features/search/components/GlobalSearchOverlay";
import { GlobalErrorBoundary } from "@/shared/components/feedback/GlobalErrorBoundary";
import { GlobalFilterBar } from "@/shared/components/filters/GlobalFilterBar";
import { PLATFORM_SEARCH_OPEN_EVENT } from "@/shared/components/navigation/platform-search.events";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import {
  buildCoachesPath,
  buildHeadToHeadPath,
  buildMarketPath,
  buildMatchesPath,
  buildPlayersPath,
  buildRankingsHubPath,
  buildTeamsPath,
} from "@/shared/utils/context-routing";

type PlatformShellProps = {
  children: ReactNode;
};

type ShellIconName =
  | "analytics"
  | "competition"
  | "worldCup"
  | "match"
  | "player"
  | "team"
  | "info"
  | "menu"
  | "close"
  | "search";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

const WORLD_CUP_NON_EDITION_SEGMENTS = new Set(["selecoes", "rankings", "finais"]);

function isCanonicalCompetitionSeasonRoute(pathname: string): boolean {
  return /^\/competitions\/[^/]+\/seasons\/[^/]+$/.test(pathname);
}

function isWorldCupEditionRoute(pathname: string): boolean {
  const match = pathname.match(/^\/copa-do-mundo\/([^/]+)$/);

  if (!match) {
    return false;
  }

  return !WORLD_CUP_NON_EDITION_SEGMENTS.has(match[1]);
}

function isActiveNavLink(pathname: string, href: string): boolean {
  const hrefPathname = href.split("?")[0] ?? href;

  if (hrefPathname === "/") {
    return pathname === "/";
  }

  if (hrefPathname === "/competitions") {
    return pathname.startsWith("/competitions");
  }

  if (hrefPathname === "/copa-do-mundo") {
    return pathname.startsWith("/copa-do-mundo");
  }

  if (hrefPathname.startsWith("/rankings/")) {
    return pathname.startsWith("/rankings");
  }

  if (hrefPathname === "/teams") {
    return pathname === "/teams" || pathname.startsWith("/teams/") || pathname.includes("/teams/");
  }

  if (hrefPathname === "/players") {
    return (
      pathname === "/players" || pathname.startsWith("/players/") || pathname.includes("/players/")
    );
  }

  if (hrefPathname === "/matches") {
    return pathname === "/matches" || pathname.startsWith("/matches/");
  }

  return pathname === hrefPathname || pathname.startsWith(`${hrefPathname}/`);
}

function formatArchiveValue(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "...";
  }

  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}m`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(value >= 10_000 ? 1 : 2)}k`;
  }

  return String(value);
}

function ShellIcon({ className, icon }: { className?: string; icon: ShellIconName }) {
  const sharedClasses = joinClasses("h-4 w-4", className);

  if (icon === "analytics") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="M5 18V10M12 18V6M19 18V13"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "competition") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="M8 6h8m-7 4h6m-8 8h10l2-8H5l2 8Z"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "match") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M12 4.5v15M4.5 12h15"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.2"
        />
      </svg>
    );
  }

  if (icon === "player") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M6 19c1.6-2.8 4-4.2 6-4.2S16.4 16.2 18 19"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "team") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="M12 4.5 18 7v5.2c0 3.2-2 5.8-6 7.3-4-1.5-6-4.1-6-7.3V7l6-2.5Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "search") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="m16 16 4 4"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "info") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M12 10.25v5M12 7.5h.01"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "worldCup") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="M8 5.5h8M9 3.5h6M8.5 5.5v3.2c0 1.8 1.2 3.3 3.5 4.3 2.3-1 3.5-2.5 3.5-4.3V5.5M7 18.5h10M10 14.5V18.5M14 14.5V18.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "menu") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="M4 7h16M4 12h16M4 17h16"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (icon === "close") {
    return (
      <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
        <path
          d="m6 6 12 12M18 6 6 18"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={sharedClasses} fill="none" viewBox="0 0 24 24">
      <path
        d="M10.5 6.5 6.5 10.5m0 0 4 4m-4-4h11"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function PlatformShell({ children }: PlatformShellProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const homeQuery = useHomePage();
  const archiveSummary = homeQuery.data?.archiveSummary;
  const isHomeRoute = pathname === "/";
  const isCompetitionsIndexRoute = pathname === "/competitions";
  const isCanonicalSeasonRoute =
    isCanonicalCompetitionSeasonRoute(pathname) || isWorldCupEditionRoute(pathname);
  const surfaceContentWidthClassName = isCanonicalSeasonRoute ? "max-w-[95rem]" : "max-w-7xl";
  const shouldRenderSurfaceChrome = !isHomeRoute && !isCompetitionsIndexRoute;
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const sharedFilters = {
    competitionId,
    seasonId,
    roundId,
    venue,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  };

  const platformNavLinks = [
    { href: "/", icon: "analytics" as const, label: "Início" },
    { href: "/copa-do-mundo", icon: "worldCup" as const, label: "Copa do Mundo" },
    { href: "/competitions", icon: "competition" as const, label: "Competições" },
    { href: buildRankingsHubPath(sharedFilters), icon: "analytics" as const, label: "Rankings" },
    { href: buildMatchesPath(sharedFilters), icon: "match" as const, label: "Partidas" },
    { href: buildPlayersPath(sharedFilters), icon: "player" as const, label: "Jogadores" },
    { href: buildTeamsPath(sharedFilters), icon: "team" as const, label: "Times" },
  ] as const;

  const topNavLinks = [
    { href: "/copa-do-mundo", label: "Copa do Mundo" },
    { href: "/competitions", label: "Competições" },
    { href: buildRankingsHubPath(sharedFilters), label: "Rankings" },
    { href: buildMatchesPath(sharedFilters), label: "Partidas" },
  ] as const;
  const secondaryPublicLinks = [
    {
      href: buildHeadToHeadPath(sharedFilters),
      icon: "match" as const,
      label: "Confronto direto",
      summary: "Comparar times",
    },
    {
      href: buildMarketPath(sharedFilters),
      icon: "analytics" as const,
      label: "Mercado",
      summary: "Cobertura pública",
    },
    {
      href: buildCoachesPath(sharedFilters),
      icon: "player" as const,
      label: "Técnicos",
      summary: "Domínio em preparação",
    },
    {
      href: "/landing",
      icon: "info" as const,
      label: "Sobre",
      summary: "Papel institucional",
    },
  ] as const;
  const sidebarNavLinks = [...platformNavLinks, ...secondaryPublicLinks] as const;

  useEffect(() => {
    setIsSearchOpen(false);
    setIsSidebarOpen(false);
  }, [pathname, searchParams]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsSearchOpen(true);
        return;
      }

      if (event.key === "Escape") {
        setIsSearchOpen(false);
        setIsSidebarOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    const handlePlatformSearchOpen = () => {
      setIsSearchOpen(true);
    };

    window.addEventListener(PLATFORM_SEARCH_OPEN_EVENT, handlePlatformSearchOpen);
    return () => {
      window.removeEventListener(PLATFORM_SEARCH_OPEN_EVENT, handlePlatformSearchOpen);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[var(--app-surface)] text-[var(--app-text)]">
      <div
        className={joinClasses(
          "fixed inset-0 z-40 bg-[rgba(7,16,12,0.52)] backdrop-blur-sm transition-opacity lg:hidden",
          isSidebarOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => {
          setIsSidebarOpen(false);
        }}
      />

      <aside
        className={joinClasses(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-white/8 bg-[#081612] text-white transition-transform duration-300 lg:translate-x-0",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-start justify-between px-6 pb-6 pt-5 lg:min-h-24 lg:items-end lg:px-8 lg:pb-5 lg:pt-7">
          <Link
            className="min-w-0"
            href="/"
            onClick={() => {
              setIsSidebarOpen(false);
            }}
          >
            <span className="block font-[family:var(--font-app-headline)] text-xl font-extrabold tracking-[-0.04em] text-emerald-50 lg:text-[1.9rem]">
              Football Analytics
            </span>
            <span className="mt-1 block text-[0.62rem] font-semibold uppercase tracking-[0.34em] text-emerald-300/82 lg:mt-2 lg:text-[0.72rem] lg:tracking-[0.28em]">
              Acervo histórico
            </span>
          </Link>

          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 text-slate-200 transition-colors hover:border-emerald-300/40 hover:text-white lg:hidden"
            onClick={() => {
              setIsSidebarOpen(false);
            }}
            type="button"
          >
            <ShellIcon icon="close" />
          </button>
        </div>

        <nav aria-label="Navegação principal" className="flex-1 px-3">
          <div className="space-y-1">
            {sidebarNavLinks.map((item) => {
              const isActive = isActiveNavLink(pathname, item.href);

              return (
                <Link
                  className={joinClasses(
                    "flex items-center gap-3 px-4 py-3 text-[0.72rem] font-semibold uppercase tracking-[0.2em] transition-colors",
                    isActive
                      ? item.href === "/copa-do-mundo"
                        ? "border-r-4 border-[var(--wc-accent)] bg-[rgba(138,109,24,0.18)] text-[var(--wc-accent-soft)]"
                        : "border-r-4 border-emerald-400 bg-emerald-900/15 text-emerald-300"
                      : item.href === "/copa-do-mundo"
                        ? "text-[var(--wc-accent-soft)]/85 hover:bg-[rgba(138,109,24,0.14)] hover:text-[var(--wc-accent-soft)]"
                        : "text-slate-400 hover:bg-slate-900/55 hover:text-emerald-100",
                  )}
                  href={item.href}
                  key={item.href}
                  onClick={() => {
                    setIsSidebarOpen(false);
                  }}
                >
                  <ShellIcon icon={item.icon} />
                  <span>{item.label}</span>
                  {item.href === "/copa-do-mundo" ? (
                    <span className="world-cup-nav-badge ml-auto rounded-full px-2 py-0.5 text-[0.56rem] font-bold uppercase tracking-[0.16em]">
                      Copa
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="border-t border-white/10 bg-white/3 px-6 py-8">
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-slate-500">
                Competições
              </p>
              <p className="mt-1 font-[family:var(--font-app-headline)] text-xl font-extrabold text-emerald-50">
                {formatArchiveValue(archiveSummary?.competitions)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-slate-500">
                Temporadas
              </p>
              <p className="mt-1 font-[family:var(--font-app-headline)] text-xl font-extrabold text-emerald-50">
                {formatArchiveValue(archiveSummary?.seasons)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-slate-500">
                Partidas
              </p>
              <p className="mt-1 font-[family:var(--font-app-headline)] text-xl font-extrabold text-emerald-50">
                {formatArchiveValue(archiveSummary?.matches)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-slate-500">
                Jogadores
              </p>
              <p className="mt-1 font-[family:var(--font-app-headline)] text-xl font-extrabold text-emerald-50">
                {formatArchiveValue(archiveSummary?.players)}
              </p>
            </div>
          </div>

          <Link
            className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-[linear-gradient(135deg,#003526_0%,#004e39_100%)] px-4 py-3 text-[0.68rem] font-bold uppercase tracking-[0.26em] text-white transition-transform hover:-translate-y-0.5"
            href="/competitions"
            onClick={() => {
              setIsSidebarOpen(false);
            }}
          >
            Abrir catálogo
          </Link>
        </div>

        <div className="border-t border-white/10 p-3">
          <button
            className="flex w-full items-center gap-3 px-4 py-2 text-xs text-slate-400 transition-colors hover:text-emerald-100"
            onClick={() => {
              setIsSearchOpen(true);
              setIsSidebarOpen(false);
            }}
            type="button"
          >
            <ShellIcon icon="search" />
            <span>Busca global</span>
          </button>
          <Link
            className="flex items-center gap-3 px-4 py-2 text-xs text-slate-400 transition-colors hover:text-emerald-100"
            href={buildRankingsHubPath(sharedFilters)}
            onClick={() => {
              setIsSidebarOpen(false);
            }}
          >
            <ShellIcon icon="analytics" />
            <span>Rankings</span>
          </Link>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="fixed left-0 right-0 top-0 z-30 h-16 border-b border-[rgba(225,230,240,0.92)] bg-white/95 shadow-[0_16px_36px_-32px_rgba(15,23,42,0.45)] backdrop-blur-xl lg:left-64 lg:h-24">
          <div className="flex h-full items-center gap-4 px-4 md:px-8 lg:gap-8 lg:px-10 xl:gap-12 xl:px-12">
            <button
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[rgba(112,121,116,0.22)] bg-white/88 text-[#1f2d40] transition-colors hover:border-[#8bd6b6] hover:text-[#003526] lg:hidden"
              onClick={() => {
                setIsSidebarOpen(true);
              }}
              type="button"
            >
              <ShellIcon icon="menu" />
            </button>

            <button
              aria-label="02 Busca global Buscar competições, partidas, times ou jogadores"
              aria-expanded={isSearchOpen}
              aria-haspopup="dialog"
              className="group inline-flex min-w-0 flex-1 items-center justify-between gap-4 rounded-[1rem] bg-[#eef3ff] px-4 py-2.5 text-left transition-colors hover:bg-[#e3ebff] md:max-w-[520px] lg:flex-none lg:min-w-[29rem] lg:max-w-[32rem] lg:rounded-[1.15rem] lg:px-5 lg:py-4"
              onClick={() => {
                setIsSearchOpen(true);
              }}
              type="button"
            >
              <span className="flex min-w-0 items-center gap-3.5">
                <ShellIcon className="h-5 w-5 shrink-0 text-[#9aa9c4]" icon="search" />
                <span className="block truncate text-sm font-medium text-[#7d889e] lg:text-[1.02rem]">
                  Buscar competições, times, partidas ou jogadores...
                </span>
              </span>
            </button>

            <nav aria-label="Atalhos principais" className="hidden h-full items-center lg:flex lg:flex-1 lg:justify-center lg:gap-10 xl:gap-14">
              {topNavLinks.map((item) => {
                const isActive = isActiveNavLink(pathname, item.href);
                return (
                  <Link
                    className={joinClasses(
                      "inline-flex h-full items-center gap-2 border-b-[3px] px-1 pt-1 text-[1.02rem] font-medium transition-colors",
                      isActive
                        ? item.href === "/copa-do-mundo"
                          ? "border-[var(--wc-accent)] text-[var(--wc-accent-strong)]"
                          : "border-[#0b6a56] text-[#0b6a56]"
                        : item.href === "/copa-do-mundo"
                          ? "border-transparent text-[var(--wc-accent-strong)] hover:text-[var(--wc-accent)]"
                        : "border-transparent text-[#6a7485] hover:text-[#0b6a56]",
                    )}
                    href={item.href}
                    key={item.href}
                  >
                    <span>{item.label}</span>
                    {"badge" in item && item.badge ? (
                      <span className="world-cup-nav-badge rounded-full px-2 py-1 text-[0.54rem] font-bold uppercase tracking-[0.16em]">
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </nav>

            <div className="ml-auto hidden items-center gap-3 sm:flex lg:hidden">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,#003526_0%,#004e39_100%)] font-[family:var(--font-app-headline)] text-sm font-extrabold text-white">
                FA
              </div>
            </div>
          </div>
        </header>

        <div className="pt-16 lg:pt-24">
          {shouldRenderSurfaceChrome ? (
            <section
              aria-label="Filtros globais"
              className="border-b border-[rgba(191,201,195,0.3)] bg-white/76 shadow-[0_16px_40px_-36px_rgba(17,28,45,0.28)]"
            >
              <div
                className={joinClasses(
                  "mx-auto w-full px-6 md:px-8",
                  isCanonicalSeasonRoute ? "py-2" : "py-4",
                  surfaceContentWidthClassName,
                )}
              >
                <Suspense
                  fallback={
                    <p className="animate-pulse text-sm text-[#57657a]">
                      Carregando filtros globais...
                    </p>
                  }
                >
                  <GlobalFilterBar />
                </Suspense>
              </div>
            </section>
          ) : null}

          <div
            className={
              isHomeRoute
                ? ""
                : joinClasses("px-6 md:px-8", isCanonicalSeasonRoute ? "py-4" : "py-8")
            }
          >
            <GlobalErrorBoundary>
              <main
                className={joinClasses(
                  isHomeRoute
                    ? "min-h-[calc(100vh-4rem)]"
                    : joinClasses("mx-auto w-full", surfaceContentWidthClassName),
                )}
              >
                {children}
              </main>
              <PlayerComparisonPanel />
            </GlobalErrorBoundary>
          </div>
        </div>
      </div>

      <GlobalSearchOverlay
        isOpen={isSearchOpen}
        onClose={() => {
          setIsSearchOpen(false);
        }}
      />
    </div>
  );
}
