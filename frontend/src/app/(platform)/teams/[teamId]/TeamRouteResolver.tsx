"use client";

import { useEffect, useMemo } from "react";

import { useSearchParams } from "next/navigation";

import { TeamAggregateProfileContent } from "@/features/teams/components/TeamAggregateProfileContent";
import type { TeamHonorsPreview } from "@/features/teams/types";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import {
  buildCanonicalTeamPath,
  buildRetainedFilterQueryString,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

type TeamRouteResolverProps = {
  teamId: string;
  honorsPreview?: TeamHonorsPreview | null;
};

export function TeamRouteResolver({ teamId, honorsPreview }: TeamRouteResolverProps) {
  const searchParams = useSearchParams();
  const retainedFilterQueryString = useMemo(
    () => buildRetainedFilterQueryString(searchParams),
    [searchParams],
  );

  const localContext = useMemo(
    () => resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [searchParams],
  );

  const canonicalHref = useMemo(
    () =>
      localContext
        ? `${buildCanonicalTeamPath(localContext, teamId)}${retainedFilterQueryString}`
        : null,
    [localContext, retainedFilterQueryString, teamId],
  );

  useEffect(() => {
    if (!canonicalHref) {
      return;
    }

    const currentHref = `${window.location.pathname}${window.location.search}`;
    if (currentHref === canonicalHref) {
      return;
    }

    window.location.replace(canonicalHref);
  }, [canonicalHref]);

  if (canonicalHref) {
    return (
      <PlatformStateSurface
        description="Estamos levando você para o perfil completo do time neste contexto."
        kicker="Abrindo perfil"
        loading
        title="Abrindo time"
      />
    );
  }

  return <TeamAggregateProfileContent honorsPreview={honorsPreview} teamId={teamId} />;
}
