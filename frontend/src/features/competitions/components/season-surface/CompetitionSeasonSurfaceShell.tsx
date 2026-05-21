"use client";

import type { ReactNode } from "react";

import Link from "next/link";

import {
  ProfileShell,
  ProfileTabs,
} from "@/shared/components/profile/ProfilePrimitives";
import { CanonicalRouteContextSync } from "@/shared/components/routing/CanonicalRouteContextSync";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import { buildCompetitionHubPath } from "@/shared/utils/context-routing";

type SeasonSurfaceNavItem = {
  badge?: ReactNode;
  href: string;
  isActive: boolean;
  key: string;
  label: ReactNode;
  customComponent?: ReactNode;
};

type CompetitionSeasonSurfaceShellProps = {
  context: CompetitionSeasonContext;
  density?: "compact" | "default";
  hero?: ReactNode;
  mainCanvas?: ReactNode;
  navAside?: ReactNode;
  navClassName?: string;
  navItems: SeasonSurfaceNavItem[];
  secondaryRail?: ReactNode;
  showLocalBreadcrumbs?: boolean;
  summaryStrip?: ReactNode;
  supportingModules?: ReactNode;
};

export function CompetitionSeasonSurfaceShell({
  context,
  density = "default",
  hero,
  mainCanvas,
  navAside,
  navClassName,
  navItems,
  secondaryRail,
  showLocalBreadcrumbs = true,
  summaryStrip,
  supportingModules,
}: CompetitionSeasonSurfaceShellProps) {
  const hasStructuredCanvas = Boolean(mainCanvas) || Boolean(secondaryRail);
  const isCompact = density === "compact";

  return (
    <CanonicalRouteContextSync context={context}>
      <ProfileShell contentClassName={isCompact ? "space-y-3" : undefined} variant="plain">
        {showLocalBreadcrumbs ? (
          <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-[#455468]">
            <Link className="transition-colors hover:text-[#003526]" href="/competitions">
              Competicoes
            </Link>
            <span className="text-[#8fa097]">/</span>
            <Link
              className="transition-colors hover:text-[#003526]"
              href={buildCompetitionHubPath(context.competitionKey)}
            >
              {context.competitionName}
            </Link>
            <span className="text-[#8fa097]">/</span>
            <span>{context.seasonLabel}</span>
          </div>
        ) : null}

        {hero ? <header className={isCompact ? "w-full" : "w-full pb-2"}>{hero}</header> : null}
        {summaryStrip ? (
          <section className="overflow-hidden rounded-[1.7rem] border border-[rgba(208,220,236,0.88)] bg-[rgba(255,255,255,0.96)] shadow-[0_20px_56px_-48px_rgba(17,28,45,0.2)]">
            <div className="px-5 py-4 md:px-6">
              {summaryStrip}
            </div>
          </section>
        ) : null}

        {navItems.length > 0 ? (
          <ProfileTabs
            ariaLabel="Navegacao da edição"
            aside={navAside}
            className={navClassName}
            density={density}
            items={navItems}
          />
        ) : null}

        {hasStructuredCanvas ? (
          <section
            className={
              secondaryRail
                ? isCompact
                  ? "grid gap-4 xl:grid-cols-[minmax(0,1.58fr)_minmax(320px,0.82fr)]"
                  : "grid gap-6 xl:grid-cols-[minmax(0,1.58fr)_minmax(320px,0.82fr)]"
                : isCompact
                  ? "grid gap-4"
                  : "grid gap-6"
            }
          >
            <div className="min-w-0">{mainCanvas}</div>
            {secondaryRail ? (
              <aside className={isCompact ? "min-w-0 space-y-4" : "min-w-0 space-y-6"}>
                {secondaryRail}
              </aside>
            ) : null}
          </section>
        ) : null}

        {supportingModules ? (
          <section className={isCompact ? "space-y-4" : "space-y-6"}>{supportingModules}</section>
        ) : null}
      </ProfileShell>
    </CanonicalRouteContextSync>
  );
}
