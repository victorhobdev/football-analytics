"use client";

import { useEffect, useMemo } from "react";

import { useSearchParams } from "next/navigation";

import { TeamAggregateProfileContent } from "@/features/teams/components/TeamAggregateProfileContent";
import { useTeamContexts } from "@/features/teams/hooks/useTeamContexts";
import { useTeamProfile } from "@/features/teams/hooks/useTeamProfile";
import type { TeamHonorsPreview } from "@/features/teams/types";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { buildWorldCupTeamPath } from "@/features/world-cup/routes";
import {
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

type TeamRouteResolverProps = {
  teamId: string;
  honorsPreview?: TeamHonorsPreview | null;
  surface?: "clubs" | "teams";
};

export function TeamRouteResolver({
  teamId,
  honorsPreview,
  surface = "teams",
}: TeamRouteResolverProps) {
  const searchParams = useSearchParams();
  const localContext = useMemo(
    () => resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [searchParams],
  );
  const currentQueryString = useMemo(() => {
    const serialized = searchParams.toString();
    return serialized.length > 0 ? `?${serialized}` : "";
  }, [searchParams]);
  const contextsQuery = useTeamContexts(teamId);
  const profileContext = localContext ?? contextsQuery.data?.defaultContext ?? null;
  const profileQuery = useTeamProfile(
    teamId,
    { includeRecentMatches: false, includeSquad: false, includeStats: false },
    profileContext,
  );
  const teamType = profileQuery.data?.identity.teamType;
  const resolvedTeamId = profileQuery.data?.team.teamId ?? teamId;
  const worldCupContext = useMemo(
    () =>
      [localContext, ...(contextsQuery.data?.availableContexts ?? [])].find(
        (context) => context?.competitionKey === "fifa_world_cup_mens",
      ) ?? null,
    [contextsQuery.data?.availableContexts, localContext],
  );
  const redirectHref =
    teamType === "club" && surface === "teams"
      ? `/clubs/${encodeURIComponent(resolvedTeamId.trim())}${currentQueryString}`
      : teamType === "national_team" && worldCupContext
        ? `${buildWorldCupTeamPath(teamId)}${currentQueryString}`
        : null;

  useEffect(() => {
    if (!redirectHref) {
      return;
    }

    const currentHref = `${window.location.pathname}${window.location.search}`;
    if (currentHref === redirectHref) {
      return;
    }

    window.location.replace(redirectHref);
  }, [redirectHref]);

  if (redirectHref) {
    return (
      <PlatformStateSurface
        description="Estamos levando você para a superfície correta desta entidade."
        kicker="Abrindo perfil"
        loading
        title="Abrindo time"
      />
    );
  }

  if (contextsQuery.isLoading || profileQuery.isLoading) {
    return (
      <PlatformStateSurface
        description="Estamos verificando a identidade desta entidade antes de abrir o perfil."
        kicker="Abrindo perfil"
        loading
        title="Preparando entidade"
      />
    );
  }

  if (teamType === "club" && surface === "clubs") {
    return <TeamAggregateProfileContent honorsPreview={honorsPreview} teamId={teamId} />;
  }

  const isClubSurface = surface === "clubs";

  return (
    <PlatformStateSurface
      actionHref={`${isClubSurface ? "/clubs" : "/competitions"}${currentQueryString}`}
      actionLabel={isClubSurface ? "Voltar para clubes" : "Abrir competições"}
      description={
        isClubSurface
          ? "Esta entidade não possui uma identidade de clube confirmada neste acervo."
          : "Esta entidade não possui uma identidade de equipe confirmada neste acervo."
      }
      kicker="Entidade não encontrada"
      title={isClubSurface ? "Perfil de clube indisponível" : "Equipe indisponível"}
      tone="warning"
    />
  );
}
