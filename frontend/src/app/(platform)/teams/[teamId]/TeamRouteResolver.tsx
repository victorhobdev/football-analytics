"use client";

import { useEffect, useMemo } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useTeamContexts } from "@/features/teams/hooks/useTeamContexts";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildCanonicalTeamPath,
  buildRetainedFilterQueryString,
  resolveCompetitionSeasonContextFromSearchParams,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";

type TeamRouteResolverProps = {
  teamId: string;
};

function buildTeamResolverFailureCopy(isError: boolean, status?: number) {
  if (status === 404) {
    return {
      title: "Time indisponível",
      description: "Este time não está disponível no produto agora.",
      detail:
        "Volte para a lista de times ou abra competições para seguir por uma visão disponível.",
    };
  }

  if (isError) {
    return {
      title: "Não foi possível abrir este time",
      description: "Não conseguimos carregar o caminho certo para este perfil agora.",
      detail: "Tente novamente em instantes ou continue pela lista de times.",
    };
  }

  return {
    title: "Não foi possível abrir este time",
    description: "Não encontramos um caminho disponível para abrir este perfil agora.",
    detail: "Abra a lista de times ou competições para continuar a navegação.",
  };
}

export function TeamRouteResolver({ teamId }: TeamRouteResolverProps) {
  const searchParams = useSearchParams();
  const globalContext = useResolvedCompetitionContext();
  const retainedFilterQueryString = useMemo(
    () => buildRetainedFilterQueryString(searchParams),
    [searchParams],
  );
  const currentQueryString = useMemo(() => {
    const serialized = searchParams.toString();
    return serialized.length > 0 ? `?${serialized}` : "";
  }, [searchParams]);

  const localContext = useMemo(
    () => resolveCompetitionSeasonContextFromSearchParams(searchParams) ?? globalContext,
    [globalContext, searchParams],
  );
  const preferredContextFilters = useMemo(
    () => ({
      competitionId: searchParams.get("competitionId")?.trim() || globalContext?.competitionId,
      seasonId: searchParams.get("seasonId")?.trim() || globalContext?.seasonId,
    }),
    [globalContext?.competitionId, globalContext?.seasonId, searchParams],
  );
  const contextsQuery = useTeamContexts(teamId, preferredContextFilters, !localContext);
  const resolvedContext = useMemo(() => {
    const contextCandidate = localContext ?? contextsQuery.data?.defaultContext ?? null;

    if (!contextCandidate) {
      return null;
    }

    return (
      resolveCompetitionSeasonContext({
        competitionId: contextCandidate.competitionId,
        competitionKey: contextCandidate.competitionKey,
        seasonId: contextCandidate.seasonId,
        seasonLabel: contextCandidate.seasonLabel,
      }) ?? contextCandidate
    );
  }, [contextsQuery.data?.defaultContext, localContext]);

  const canonicalHref = useMemo(
    () =>
      resolvedContext
        ? `${buildCanonicalTeamPath(resolvedContext, teamId)}${retainedFilterQueryString}`
        : null,
    [resolvedContext, retainedFilterQueryString, teamId],
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
        description="Estamos levando você para o perfil do time na melhor temporada disponível."
        kicker="Abrindo perfil"
        loading
        title="Abrindo time"
      />
    );
  }

  if (!localContext && contextsQuery.isLoading) {
    return (
      <PlatformStateSurface
        description="Estamos encontrando a competição e a temporada certas para abrir este time."
        kicker="Abrindo perfil"
        loading
        title="Preparando time"
      />
    );
  }

  const failureCopy = buildTeamResolverFailureCopy(
    contextsQuery.isError,
    contextsQuery.error?.status,
  );

  return (
    <PlatformStateSurface
      actionHref={`/teams${currentQueryString}`}
      actionLabel="Voltar para times"
      description={failureCopy.description}
      detail={<p>{failureCopy.detail}</p>}
      kicker="Navegação"
      secondaryAction={
        <Link
          className="button-pill button-pill-secondary"
          href={`/competitions${currentQueryString}`}
        >
          Abrir competições
        </Link>
      }
      title={failureCopy.title}
      tone={contextsQuery.isError ? "critical" : "warning"}
    />
  );
}
