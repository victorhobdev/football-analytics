"use client";

import { useEffect, useMemo } from "react";

import { useSearchParams } from "next/navigation";

import { buildWorldCupTeamPath } from "@/features/world-cup/routes";
import { TeamProfileContent } from "@/features/teams/components/TeamProfileContent";
import { useTeamProfile } from "@/features/teams/hooks/useTeamProfile";
import type { TeamHonorsPreview } from "@/features/teams/types";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import type { CompetitionSeasonContext } from "@/shared/types/context.types";
import { buildCanonicalClubPath, buildSeasonHubPath } from "@/shared/utils/context-routing";

type ContextualTeamRouteResolverProps = {
  context: CompetitionSeasonContext;
  honorsPreview?: TeamHonorsPreview | null;
  surface: "clubs" | "teams";
  teamId: string;
};

export function ContextualTeamRouteResolver({
  context,
  honorsPreview,
  surface,
  teamId,
}: ContextualTeamRouteResolverProps) {
  const searchParams = useSearchParams();
  const currentQueryString = useMemo(() => {
    const serialized = searchParams.toString();
    return serialized.length > 0 ? `?${serialized}` : "";
  }, [searchParams]);
  const profileQuery = useTeamProfile(
    teamId,
    { includeRecentMatches: false, includeSquad: false, includeStats: false },
    context,
  );
  const teamType = profileQuery.data?.identity.teamType;
  const resolvedTeamId = profileQuery.data?.team.teamId ?? teamId;
  const redirectHref =
    teamType === "club" && surface === "teams"
      ? `${buildCanonicalClubPath(context, resolvedTeamId)}${currentQueryString}`
      : teamType === "national_team" && context.competitionKey === "fifa_world_cup_mens"
        ? `${buildWorldCupTeamPath(teamId)}${currentQueryString}`
        : null;

  useEffect(() => {
    if (!redirectHref) {
      return;
    }

    const currentHref = `${window.location.pathname}${window.location.search}`;
    if (currentHref !== redirectHref) {
      window.location.replace(redirectHref);
    }
  }, [redirectHref]);

  if (redirectHref) {
    return (
      <PlatformStateSurface
        description="Estamos levando você para a superfície correta desta entidade."
        kicker="Abrindo perfil"
        loading
        title="Abrindo entidade"
      />
    );
  }

  if (profileQuery.isLoading) {
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
    return (
      <TeamProfileContent contextOverride={context} honorsPreview={honorsPreview} teamId={teamId} />
    );
  }

  const isClubSurface = surface === "clubs";

  return (
    <PlatformStateSurface
      actionHref={buildSeasonHubPath(context)}
      actionLabel="Voltar para a temporada"
      description={
        isClubSurface
          ? "Esta entidade não possui uma identidade de clube confirmada neste contexto."
          : "Esta entidade não possui uma identidade de equipe confirmada neste contexto."
      }
      kicker="Entidade não encontrada"
      title={isClubSurface ? "Perfil de clube indisponível" : "Equipe indisponível"}
      tone="warning"
    />
  );
}
