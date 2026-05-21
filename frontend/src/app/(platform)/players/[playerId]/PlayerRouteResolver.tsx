"use client";

import { useEffect, useMemo } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { PlayerProfileContent } from "./PlayerProfileContent";

import { usePlayerContexts } from "@/features/players/hooks";
import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";
import { ProfileAlert } from "@/shared/components/profile/ProfilePrimitives";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildCanonicalPlayerPath,
  buildRetainedFilterQueryString,
  resolveCompetitionSeasonContextFromSearchParams,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";

type PlayerRouteResolverProps = {
  playerId: string;
};

function buildPlayerResolverFailureCopy(isError: boolean, status?: number) {
  if (status === 404) {
    return {
      title: "Jogador indisponível",
      description: "Este jogador não está disponível agora.",
      detail:
        "Volte para a lista de jogadores ou abra competições para seguir por uma visão disponível.",
    };
  }

  if (isError) {
    return {
      title: "Não foi possível abrir este jogador",
      description: "Não conseguimos carregar o caminho certo para este perfil agora.",
      detail: "Tente novamente em instantes ou continue pela lista de jogadores.",
    };
  }

  return {
    title: "Não foi possível abrir este jogador",
    description: "Não encontramos um caminho disponível para abrir este perfil agora.",
    detail: "Abra a lista de jogadores ou competições para continuar a navegação.",
  };
}

export function PlayerRouteResolver({ playerId }: PlayerRouteResolverProps) {
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
  const contextsQuery = usePlayerContexts(playerId, preferredContextFilters, !localContext);
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
        ? `${buildCanonicalPlayerPath(resolvedContext, playerId)}${retainedFilterQueryString}`
        : null,
    [playerId, resolvedContext, retainedFilterQueryString],
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
        description="Estamos levando você para o perfil do jogador na melhor temporada disponível."
        kicker="Abrindo perfil"
        loading
        title="Abrindo jogador"
      />
    );
  }

  if (!localContext && contextsQuery.isLoading) {
    return (
      <PlatformStateSurface
        description="Estamos encontrando a competição e a temporada certas para abrir este jogador."
        kicker="Abrindo perfil"
        loading
        title="Preparando jogador"
      />
    );
  }

  if (!localContext && !contextsQuery.isError && !canonicalHref) {
    return (
      <PlayerProfileContent
        notice={
          <ProfileAlert title="Perfil básico" tone="info">
            <p>Mostrando as informações disponíveis para este jogador.</p>
          </ProfileAlert>
        }
        playerId={playerId}
      />
    );
  }

  const failureCopy = buildPlayerResolverFailureCopy(
    contextsQuery.isError,
    contextsQuery.error?.status,
  );

  return (
    <PlatformStateSurface
      actionHref={`/players${currentQueryString}`}
      actionLabel="Voltar para jogadores"
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
