"use client";

import { useMemo } from "react";

import { usePathname, useSearchParams, type ReadonlyURLSearchParams } from "next/navigation";

import { getCompetitionById, getCompetitionByKey } from "@/config/competitions.registry";
import {
  buildWorldCupFinalsPath,
  buildWorldCupHubPath,
  buildWorldCupRankingsPath,
  buildWorldCupTeamsPath,
} from "@/features/world-cup/routes";
import { getRankingDefinition } from "@/config/ranking.registry";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import type {
  CompetitionSeasonContext,
  CompetitionSeasonContextInput,
} from "@/shared/types/context.types";
import { describeTimeWindowLabel, describeVenueLabel } from "@/shared/utils/filter-descriptions";
import {
  buildCompetitionHubPath,
  buildMatchesPath,
  buildPlayersPath,
  buildRankingsHubPath,
  buildSeasonHubPath,
  buildSeasonHubTabPath,
  buildTeamsPath,
  resolveCompetitionSeasonContext,
} from "@/shared/utils/context-routing";

type PlatformShellBreadcrumb = {
  label: string;
  href?: string;
};

type PlatformShellLink = {
  href: string;
  isActive: boolean;
  label: string;
};

type PlatformShellState = {
  breadcrumbs: PlatformShellBreadcrumb[];
  description: string;
  helperText: string;
  scopeTags: string[];
  surfaceLinks: PlatformShellLink[];
  surfaceLabel: string;
  surfaceTitle: string;
};

const COMPACT_HYBRID_SEASON_CHROME_COMPETITION_KEYS = new Set([
  "champions_league",
  "libertadores",
  "sudamericana",
]);

function decodePathSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function parseHref(href: string): { pathname: string; searchParams: URLSearchParams } {
  const [hrefPathname, hrefQuery = ""] = href.split("?");

  return {
    pathname: hrefPathname || "/",
    searchParams: new URLSearchParams(hrefQuery),
  };
}

function isCanonicalSeasonHubPath(pathname: string): boolean {
  return /^\/competitions\/[^/]+\/seasons\/[^/]+$/.test(pathname);
}

function isPathActive(
  pathname: string,
  currentSearchParams: ReadonlyURLSearchParams,
  href: string,
): boolean {
  const { pathname: hrefPathname, searchParams: hrefSearchParams } = parseHref(href);

  if (hrefPathname === pathname) {
    if (isCanonicalSeasonHubPath(hrefPathname)) {
      const expectedTab = hrefSearchParams.get("tab") ?? "calendar";
      const currentTab = currentSearchParams.get("tab") ?? "calendar";
      return expectedTab === currentTab;
    }

    return true;
  }

  if (hrefPathname === "/competitions") {
    return pathname.startsWith("/competitions");
  }

  if (hrefPathname === "/copa-do-mundo") {
    return pathname === "/copa-do-mundo";
  }

  if (hrefPathname === "/copa-do-mundo/selecoes") {
    return pathname === hrefPathname || pathname.startsWith(`${hrefPathname}/`);
  }

  if (hrefPathname === "/copa-do-mundo/rankings") {
    return pathname === hrefPathname || pathname.startsWith(`${hrefPathname}/`);
  }

  if (hrefPathname === "/copa-do-mundo/finais") {
    return pathname === hrefPathname || pathname.startsWith(`${hrefPathname}/`);
  }

  if (isCanonicalSeasonHubPath(hrefPathname)) {
    return false;
  }

  if (/^\/competitions\/[^/]+$/.test(hrefPathname)) {
    return pathname === hrefPathname;
  }

  if (hrefPathname === "/rankings") {
    return pathname === hrefPathname || pathname.startsWith(`${hrefPathname}/`);
  }

  if (hrefPathname.startsWith("/rankings/")) {
    return pathname.startsWith("/rankings/");
  }

  if (hrefPathname === "/matches") {
    return pathname.startsWith("/matches");
  }

  if (hrefPathname === "/players") {
    return (
      pathname === "/players" || pathname.startsWith("/players/") || pathname.includes("/players/")
    );
  }

  if (hrefPathname === "/teams") {
    return pathname === "/teams" || pathname.startsWith("/teams/") || pathname.includes("/teams/");
  }

  return false;
}

function buildSurfaceLink(
  pathname: string,
  currentSearchParams: ReadonlyURLSearchParams,
  label: string,
  href: string,
): PlatformShellLink {
  return {
    href,
    isActive: isPathActive(pathname, currentSearchParams, href),
    label,
  };
}

function buildScopeTags(params: {
  context: CompetitionSeasonContext | null;
  roundId: string | null;
  venue: string;
  timeWindowLabel: string;
}): string[] {
  const tags: string[] = [];
  const pushUnique = (value: string | null | undefined) => {
    if (!value || tags.includes(value)) {
      return;
    }

    tags.push(value);
  };

  if (params.context) {
    pushUnique(params.context.competitionName);
    pushUnique(params.context.seasonLabel);
  }

  if (params.roundId) {
    pushUnique(`Rodada ${params.roundId}`);
  }

  if (params.venue !== "all") {
    pushUnique(describeVenueLabel(params.venue));
  }

  if (params.timeWindowLabel !== "Temporada inteira") {
    pushUnique(params.timeWindowLabel);
  }

  return tags;
}

function shouldUseLocalSeasonSurfaceNavigation(
  pathname: string,
  context: CompetitionSeasonContext,
): boolean {
  const competition = getCompetitionByKey(context.competitionKey);

  return (
    isCanonicalSeasonHubPath(pathname) &&
    (competition?.type === "domestic_league" ||
      COMPACT_HYBRID_SEASON_CHROME_COMPETITION_KEYS.has(context.competitionKey))
  );
}

function buildSeasonSurfaceLinks(
  pathname: string,
  currentSearchParams: ReadonlyURLSearchParams,
  context: CompetitionSeasonContext,
  filterInput: CompetitionSeasonContextInput & {
    roundId: string | null;
    venue: string;
    lastN: number | null;
    dateRangeStart: string | null;
    dateRangeEnd: string | null;
  },
): PlatformShellLink[] {
  if (shouldUseLocalSeasonSurfaceNavigation(pathname, context)) {
    return [];
  }

  return [
    buildSurfaceLink(
      pathname,
      currentSearchParams,
      "Resumo",
      buildSeasonHubPath(context),
    ),
    buildSurfaceLink(
      pathname,
      currentSearchParams,
      "Estrutura",
      buildSeasonHubTabPath(context, "standings", filterInput),
    ),
    buildSurfaceLink(
      pathname,
      currentSearchParams,
      "Rankings",
      buildSeasonHubTabPath(context, "rankings", filterInput),
    ),
    buildSurfaceLink(pathname, currentSearchParams, "Jogadores", buildPlayersPath(filterInput)),
    buildSurfaceLink(pathname, currentSearchParams, "Times", buildTeamsPath(filterInput)),
    buildSurfaceLink(pathname, currentSearchParams, "Partidas", buildMatchesPath(filterInput)),
  ];
}

function resolveCanonicalContextFromPath(pathname: string): CompetitionSeasonContext | null {
  const canonicalMatch = pathname.match(/^\/competitions\/([^/]+)\/seasons\/([^/]+)(?:\/|$)/);

  if (!canonicalMatch) {
    return null;
  }

  return resolveCompetitionSeasonContext({
    competitionKey: decodePathSegment(canonicalMatch[1]),
    seasonLabel: decodePathSegment(canonicalMatch[2]),
  });
}

function resolveCompetitionFromPath(pathname: string) {
  const competitionMatch = pathname.match(/^\/competitions\/([^/]+)(?:\/|$)/);

  if (!competitionMatch) {
    return null;
  }

  return getCompetitionByKey(decodePathSegment(competitionMatch[1])) ?? null;
}

function resolveRouteContext(
  pathname: string,
  filters: CompetitionSeasonContextInput,
): {
  competitionOnly:
    | ReturnType<typeof getCompetitionById>
    | ReturnType<typeof getCompetitionByKey>
    | null;
  context: CompetitionSeasonContext | null;
} {
  const canonicalContext = resolveCanonicalContextFromPath(pathname);

  if (canonicalContext) {
    return {
      competitionOnly: getCompetitionById(canonicalContext.competitionId) ?? null,
      context: canonicalContext,
    };
  }

  const competitionOnly = resolveCompetitionFromPath(pathname);
  const context =
    resolveCompetitionSeasonContext({
      competitionId: filters.competitionId,
      seasonId: filters.seasonId,
    }) ?? null;

  return {
    competitionOnly,
    context,
  };
}

function isShortPlayerResolverPath(pathname: string): boolean {
  return /^\/players\/[^/]+$/.test(pathname);
}

function isShortTeamResolverPath(pathname: string): boolean {
  return /^\/teams\/[^/]+$/.test(pathname);
}

function isLegacyClubResolverPath(pathname: string): boolean {
  return /^\/clubs\/[^/]+$/.test(pathname);
}

export function usePlatformShellState(): PlatformShellState {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { competitionId, seasonId, roundId, venue } = useGlobalFiltersState();
  const { params: timeRangeParams } = useTimeRange();

  return useMemo(() => {
    const rankingType = pathname.startsWith("/rankings/")
      ? decodePathSegment(pathname.split("/").filter(Boolean).at(-1) ?? "")
      : null;
    const rankingDefinition = rankingType ? getRankingDefinition(rankingType) : null;
    const { competitionOnly, context } = resolveRouteContext(pathname, {
      competitionId,
      seasonId,
    });
    const timeWindowLabel = describeTimeWindowLabel({
      roundId,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
    });
    const scopeTags = buildScopeTags({
      context,
      roundId,
      venue,
      timeWindowLabel,
    });
    const sharedFilterInput = {
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN: timeRangeParams.lastN,
      dateRangeStart: timeRangeParams.dateRangeStart,
      dateRangeEnd: timeRangeParams.dateRangeEnd,
    };

    const isWorldCupRoute = pathname === "/copa-do-mundo" || pathname.startsWith("/copa-do-mundo/");
    const competitionHubHref = competitionOnly
      ? buildCompetitionHubPath(competitionOnly.key)
      : "/competitions";
    const breadcrumbs: PlatformShellBreadcrumb[] =
      pathname === "/"
        ? [
            {
              label: "Início",
            },
          ]
        : [
            {
              label: "Competições",
              href: "/competitions",
            },
          ];

    const surfaceLinks: PlatformShellLink[] = [];
    let surfaceLabel = "Visão geral";
    let surfaceTitle = context ? `${context.competitionName} ${context.seasonLabel}` : "Explore o produto";
    let description =
      "Use os atalhos da página e os filtros para navegar entre competições, rankings, jogadores e times.";
    let helperText =
      "Os filtros mantêm o recorte ativo enquanto você troca de área.";

    if (isWorldCupRoute) {
      breadcrumbs.splice(0, breadcrumbs.length, {
        label: pathname === "/copa-do-mundo" ? "Copa do Mundo" : "Copa do Mundo",
        href: "/copa-do-mundo",
      });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Hub da Copa", buildWorldCupHubPath()),
        buildSurfaceLink(pathname, searchParams, "Seleções", buildWorldCupTeamsPath()),
        buildSurfaceLink(pathname, searchParams, "Rankings", buildWorldCupRankingsPath()),
        buildSurfaceLink(pathname, searchParams, "Finais", buildWorldCupFinalsPath()),
      );
      surfaceLabel = "Copa do Mundo";
      surfaceTitle = "Entrada dedicada da Copa do Mundo";
      description =
        "A vertical da Copa ocupa entrada própria no produto e segue rota base dedicada, fora da hierarquia de ligas.";
      helperText =
        "Use esta rota como base estável da vertical enquanto o hub e as subpáginas são materializados.";
    } else if (competitionOnly) {
      breadcrumbs.push({
        label: competitionOnly.shortName,
        href: competitionHubHref,
      });
    }

    if (!isWorldCupRoute) {
      if (context) {
        breadcrumbs.push({
          label: context.seasonLabel,
          href: buildSeasonHubPath(context),
        });
        surfaceLinks.push(
          ...buildSeasonSurfaceLinks(pathname, searchParams, context, sharedFilterInput),
        );
      } else if (competitionOnly) {
        surfaceLinks.push(buildSurfaceLink(pathname, searchParams, "Competição", competitionHubHref));
      } else {
        surfaceLinks.push(
          buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
          buildSurfaceLink(
            pathname,
            searchParams,
            "Rankings",
            buildRankingsHubPath(sharedFilterInput),
          ),
          buildSurfaceLink(pathname, searchParams, "Jogadores", buildPlayersPath(sharedFilterInput)),
          buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
        );
      }
    }

    if (pathname === "/") {
      surfaceLabel = "Início";
      surfaceTitle = context
        ? `${context.competitionName} ${context.seasonLabel}`
        : "Entrada executiva do produto";
      description =
        context
          ? "Comece pela competição atual e siga para times, jogadores ou rankings."
          : "Comece por competições ou use a busca global para entrar direto em times e jogadores.";
      helperText = context
        ? "A página inicial mantém o recorte atual enquanto você abre as áreas principais."
        : "Escolha uma competição ou abra a busca global para começar.";
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
        buildSurfaceLink(pathname, searchParams, "Jogadores", buildPlayersPath(sharedFilterInput)),
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
      );
    } else if (pathname === "/copa-do-mundo") {
      surfaceLabel = "Copa do Mundo";
      surfaceTitle = "Entrada dedicada da Copa do Mundo";
      description =
        "A vertical da Copa já está posicionada como item de primeiro nível e abre por esta rota base dedicada.";
      helperText =
        "O hub completo da vertical será carregado sobre esta mesma rota.";
    } else if (pathname === "/competitions") {
      surfaceLabel = "Competições";
      surfaceTitle = "Campeonatos disponíveis";
      description =
        "Escolha uma competição para abrir a temporada mais recente ou explorar todas as temporadas.";
      helperText =
        "Cada item leva à competição e à temporada mais recente.";
    } else if (pathname.startsWith("/competitions/") && !context) {
      surfaceLabel = "Competição";
      surfaceTitle = competitionOnly ? competitionOnly.name : "Competição";
      description =
        "Veja as temporadas disponíveis e escolha por onde continuar.";
      helperText =
        "Abra a temporada para acompanhar partidas, tabela e rankings.";
    } else if (
      context &&
      pathname.startsWith("/competitions/") &&
      !pathname.includes("/players/") &&
      !pathname.includes("/teams/")
    ) {
      const activeTab = searchParams.get("tab");
      surfaceLabel = "Edição";
      surfaceTitle = `${context.competitionName} ${context.seasonLabel}`;
      description =
        activeTab === "standings"
          ? "Leitura estrutural da edição encerrada, com foco na classificação final, no chaveamento ou na fase classificatória."
          : activeTab === "rankings"
            ? "Destaques individuais e coletivos da edição no mesmo recorte competitivo."
            : activeTab === "calendar"
              ? "Confrontos e partidas concluídas da edição, sem tratamento de temporada ao vivo."
              : "Resumo editorial da edição encerrada, orientado pelo tipo real da competição.";
      helperText =
        "Os atalhos preservam competição, temporada e filtros extras enquanto você muda de leitura.";
    } else if (isShortPlayerResolverPath(pathname)) {
      surfaceLabel = "Abrindo jogador";
      surfaceTitle = "Abrindo jogador";
      description =
        "Estamos localizando a competição e a temporada mais adequadas para este perfil.";
      helperText =
        "Se houver contexto disponível, o perfil abre automaticamente.";
      breadcrumbs.push({
        label: "Abrindo jogador",
      });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Jogadores", buildPlayersPath(sharedFilterInput)),
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
      );
    } else if (isLegacyClubResolverPath(pathname) || isShortTeamResolverPath(pathname)) {
      surfaceLabel = "Compatibilidade";
      surfaceTitle = "Abrindo time";
      description = isLegacyClubResolverPath(pathname)
        ? "A rota legada de clubes encaminha automaticamente para o perfil canônico de time."
        : "Estamos localizando a competição e a temporada mais adequadas para este perfil.";
      helperText = isLegacyClubResolverPath(pathname)
        ? "O alias legado é preservado por compatibilidade, mas a experiência final continua em times."
        : "Se houver contexto disponível, o perfil abre automaticamente.";
      breadcrumbs.push({
        label: "Abrindo time",
      });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
      );
    } else if (pathname === "/players") {
      surfaceLabel = "Jogadores";
      surfaceTitle = context
        ? `Jogadores no recorte ${context.competitionName} ${context.seasonLabel}`
        : "Lista de jogadores";
      description =
        "Encontre atletas e siga para o perfil individual com o contexto atual.";
      helperText = context
        ? "Os perfis preservam o mesmo recorte sempre que ele estiver disponível."
        : "Escolha uma competição ou use a busca para entrar em um contexto específico.";
    } else if (pathname.startsWith("/players/") || pathname.includes("/players/")) {
      surfaceLabel = "Perfil de jogador";
      surfaceTitle = context
        ? `Perfil em ${context.competitionName} ${context.seasonLabel}`
        : "Perfil de jogador";
      description =
        "Resumo, histórico e estatísticas do atleta.";
      helperText = context
        ? "Use os atalhos para voltar a rankings, times e jogadores."
        : "Abra jogadores ou competições para entrar em um contexto específico.";
    } else if (pathname === "/teams") {
      surfaceLabel = "Times";
      surfaceTitle = context
        ? `Times no recorte ${context.competitionName} ${context.seasonLabel}`
        : "Lista de times";
      description =
        "Encontre times e siga para o perfil completo no recorte atual.";
      helperText = context
        ? "Os perfis preservam o mesmo recorte quando ele já estiver definido."
        : "Escolha uma competição ou abra um perfil para encontrar o melhor contexto.";
    } else if (pathname.startsWith("/teams/") || pathname.includes("/teams/")) {
      surfaceLabel = "Perfil de time";
      surfaceTitle = context
        ? `Perfil em ${context.competitionName} ${context.seasonLabel}`
        : "Perfil de time";
      description =
        "Resumo, elenco, partidas e desempenho do time.";
      helperText = context
        ? "Use os atalhos para voltar a rankings, jogadores e competição."
        : "Abra times ou competições para entrar em um contexto específico.";
    } else if (pathname === "/matches") {
      surfaceLabel = "Partidas";
      surfaceTitle = context
        ? `Partidas em ${context.competitionName} ${context.seasonLabel}`
        : "Lista de partidas";
      description =
        "Encontre jogos e siga para a central da partida.";
      helperText =
        "O contexto atual continua ativo ao abrir o detalhe da partida.";
    } else if (pathname.startsWith("/matches/")) {
      surfaceLabel = "Central da partida";
      surfaceTitle = context
        ? `Central da partida em ${context.competitionName} ${context.seasonLabel}`
        : "Central da partida";
      description =
        "Resumo, linha do tempo, escalações e estatísticas do jogo.";
      helperText =
        "Volte para competição, times, jogadores e rankings mantendo o mesmo recorte.";
    } else if (pathname === "/rankings") {
      surfaceLabel = "Rankings";
      surfaceTitle = context
        ? `Hub de rankings · ${context.competitionName} ${context.seasonLabel}`
        : "Hub de rankings";
      description =
        "Abra o catálogo completo de rankings disponíveis e escolha entre leituras de jogadores e times.";
      helperText =
        "Os cards mantêm o recorte ativo enquanto você navega entre os rankings.";
    } else if (pathname.startsWith("/rankings/")) {
      surfaceLabel = "Rankings";
      surfaceTitle = rankingDefinition
        ? `${rankingDefinition.label}${context ? ` · ${context.competitionName} ${context.seasonLabel}` : ""}`
        : "Rankings";
      description =
        "Compare líderes da temporada e entre direto em jogadores e times.";
      helperText =
        "Os atalhos mantêm o mesmo recorte ao mudar de área.";
    } else if (pathname === "/market") {
      surfaceLabel = "Mercado";
      surfaceTitle = "Mercado em preparação pública";
      description =
        "A trilha de transferências ainda não tem contrato público estável, mas o domínio já está enquadrado na arquitetura do produto.";
      helperText =
        "Use jogadores, times e rankings para explorar o contexto disponível hoje enquanto a lista pública de mercado é fechada.";
      breadcrumbs.push({ label: "Mercado" });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Jogadores", buildPlayersPath(sharedFilterInput)),
        buildSurfaceLink(
          pathname,
          searchParams,
          "Rankings",
          buildRankingsHubPath(sharedFilterInput),
        ),
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
      );
    } else if (pathname === "/head-to-head") {
      surfaceLabel = "Confronto direto";
      surfaceTitle = context
        ? `Comparar times em ${context.competitionName} ${context.seasonLabel}`
        : "Confronto direto";
      description =
        "Compare dois times no mesmo recorte e siga dos confrontos diretos para a central da partida e os perfis canônicos.";
      helperText =
        "Escolha dois times no contexto atual para montar o comparativo sem sair da temporada.";
      breadcrumbs.push({ label: "Confronto direto" });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
        buildSurfaceLink(
          pathname,
          searchParams,
          "Rankings",
          buildRankingsHubPath(sharedFilterInput),
        ),
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
      );
    } else if (pathname === "/coaches") {
      surfaceLabel = "Técnicos";
      surfaceTitle = "Cobertura de técnicos";
      description =
        "O domínio de técnicos já existe no produto, mas ainda não tem listagem pública sustentada pelo BFF atual.";
      helperText =
        "Use times e competições como portas de entrada enquanto a descoberta pública de técnicos é fechada.";
      breadcrumbs.push({ label: "Técnicos" });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
      );
    } else if (pathname.startsWith("/coaches/")) {
      surfaceLabel = "Técnicos";
      surfaceTitle = "Perfil de técnico em preparação";
      description =
        "O link direto de técnico já existe, mas o detalhe público ainda depende de um contrato dedicado para fechar histórico, ciclos e desempenho.";
      helperText =
        "Use times, jogadores e competições para navegar pelo contexto atual sem cair em rota quebrada.";
      breadcrumbs.push({ label: "Técnicos" });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Times", buildTeamsPath(sharedFilterInput)),
        buildSurfaceLink(pathname, searchParams, "Jogadores", buildPlayersPath(sharedFilterInput)),
      );
    } else if (pathname === "/audit") {
      surfaceLabel = "Área interna";
      surfaceTitle = "Área indisponível";
      description =
        "Esta rota não está aberta na navegação do produto.";
      helperText =
        "Volte para o início ou competições para continuar.";
      breadcrumbs.push({ label: "Auditoria" });
      surfaceLinks.splice(
        0,
        surfaceLinks.length,
        buildSurfaceLink(pathname, searchParams, "Início", "/"),
        buildSurfaceLink(pathname, searchParams, "Competições", "/competitions"),
      );
    }

    return {
      breadcrumbs,
      description,
      helperText,
      scopeTags,
      surfaceLinks,
      surfaceLabel,
      surfaceTitle,
    };
  }, [
    competitionId,
    pathname,
    roundId,
    searchParams,
    seasonId,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    venue,
  ]);
}
