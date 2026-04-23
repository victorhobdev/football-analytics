"use client";

import { useDeferredValue, useMemo, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useMarketTransfers } from "@/features/market/hooks";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfileCoveragePill,
  ProfileKpi,
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import {
  buildMatchesPath,
  buildPlayerResolverPath,
  buildPlayersPath,
  buildSeasonHubTabPath,
  buildTeamResolverPath,
  buildTeamsPath,
  resolveCompetitionSeasonContextFromSearchParams,
} from "@/shared/utils/context-routing";

function describeVenue(venue: string | null | undefined): string {
  if (venue === "home") {
    return "Casa";
  }

  if (venue === "away") {
    return "Fora";
  }

  return "Todos os mandos";
}

function describeTransferWindow(params: {
  roundId: string | null;
  lastN: number | null;
  dateRangeStart: string | null;
  dateRangeEnd: string | null;
}): string {
  if (typeof params.lastN === "number" && params.lastN > 0) {
    return `Últimas ${params.lastN} movimentações`;
  }

  if (params.dateRangeStart || params.dateRangeEnd) {
    return `${params.dateRangeStart ?? "..."} até ${params.dateRangeEnd ?? "..."}`;
  }

  if (params.roundId) {
    return `Times da rodada ${params.roundId}`;
  }

  return "Base completa";
}

function formatTransferDate(value: string | null | undefined): string {
  if (!value) {
    return "Data não informada";
  }

  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(parsedDate);
}

function formatAmount(value: string | null | undefined): string {
  if (!value) {
    return "Não informado";
  }

  const normalized = Number(value);

  if (!Number.isFinite(normalized)) {
    return value;
  }

  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 0,
  }).format(normalized);
}

function formatMovement(item: {
  fromTeamName?: string | null;
  toTeamName?: string | null;
  careerEnded: boolean;
}): string {
  const fromTeam = item.fromTeamName ?? "Origem não informada";
  const toTeam = item.careerEnded ? "Fim de carreira" : item.toTeamName ?? "Destino não informado";

  return `${fromTeam} -> ${toTeam}`;
}

function getPlayerMonogram(playerName: string): string {
  const initials = playerName
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "TRF";
}

export function MarketPageContent() {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const searchParams = useSearchParams();
  const resolvedGlobalContext = useResolvedCompetitionContext();
  const resolvedContext = useMemo(
    () => resolvedGlobalContext ?? resolveCompetitionSeasonContextFromSearchParams(searchParams),
    [resolvedGlobalContext, searchParams],
  );
  const { competitionId, seasonId, roundId, venue, lastN, dateRangeStart, dateRangeEnd } =
    useGlobalFiltersState();
  const marketQuery = useMarketTransfers(
    {
      search: deferredSearch,
      pageSize: 24,
      sortBy: "transferDate",
      sortDirection: "desc",
    },
    resolvedContext,
  );
  const sharedFilters = useMemo(
    () => ({
      competitionId,
      seasonId,
      roundId,
      venue,
      lastN,
      dateRangeStart,
      dateRangeEnd,
    }),
    [competitionId, dateRangeEnd, dateRangeStart, lastN, roundId, seasonId, venue],
  );
  const seasonHubHref = resolvedContext
    ? buildSeasonHubTabPath(resolvedContext, "calendar", sharedFilters)
    : "/competitions";
  const playersHref = buildPlayersPath(sharedFilters);
  const teamsHref = buildTeamsPath(sharedFilters);
  const matchesHref = buildMatchesPath(sharedFilters);
  const activeWindowLabel = describeTransferWindow({
    roundId,
    lastN,
    dateRangeStart,
    dateRangeEnd,
  });
  const usesScopedTeamApproximation = Boolean(competitionId || seasonId || roundId);

  if (marketQuery.isLoading) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mercado
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Carregando transferências
          </h1>
        </header>
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
        <LoadingSkeleton height={140} />
      </ProfileShell>
    );
  }

  if (marketQuery.isError && !marketQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mercado
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Falha ao carregar transferências
          </h1>
        </header>
        <ProfileAlert title="Erro no carregamento" tone="critical">
          <p>{marketQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (marketQuery.isEmpty || !marketQuery.data) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Mercado
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            Nenhuma transferência encontrada
          </h1>
        </header>
        <EmptyState
          title="Sem movimentações neste recorte"
          description="Não encontramos transferências com os filtros atuais."
        />
      </ProfileShell>
    );
  }

  const items = marketQuery.data.items;
  const completedTransfers = items.filter((item) => item.completed).length;
  const mappedTransfers = items.filter((item) => item.fromTeamId || item.toTeamId).length;

  return (
    <ProfileShell className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.95fr)]">
        <ProfilePanel className="space-y-5" tone="accent">
          <div className="flex flex-wrap items-center gap-2">
            <ProfileCoveragePill coverage={marketQuery.coverage} className="bg-white/16 text-white" />
            <ProfileTag className="bg-white/12 text-white/82">
              {resolvedContext ? "Contexto fechado" : "Entrada direta"}
            </ProfileTag>
            <ProfileTag className="bg-white/12 text-white/82">{items.length} movimentos</ProfileTag>
          </div>

          <div className="space-y-3">
            <p className="text-[0.72rem] uppercase tracking-[0.18em] text-white/62">
              Mercado público
            </p>
            <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {resolvedContext
                ? `Transferências em ${resolvedContext.competitionName} ${resolvedContext.seasonLabel}`
                : "Transferências reais por jogador e clube"}
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/74">
              O domínio agora consome movimentações reais da base de dados em vez de dados
              estáticos.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <ProfileKpi hint="Linhas nesta visão" invert label="Transferências" value={items.length} />
            <ProfileKpi
              hint="Status concluído nos dados recebidos"
              invert
              label="Concluídas"
              value={completedTransfers}
            />
            <ProfileKpi hint={activeWindowLabel} invert label="Janela" value={activeWindowLabel} />
          </div>
        </ProfilePanel>

        <div className="grid gap-4">
          <ProfilePanel className="space-y-4">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Busca
            </p>
            <label className="block">
              <span className="sr-only">Buscar jogador ou time</span>
              <input
                className="w-full rounded-[1.1rem] border border-[rgba(191,201,195,0.65)] bg-white/92 px-4 py-3 text-sm text-[#111c2d] outline-none transition-colors placeholder:text-[#7f8b99] focus:border-[#8bd6b6]"
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
                placeholder="Buscar jogador, origem ou destino"
                value={search}
              />
            </label>
            <dl className="space-y-3 text-sm text-[#1f2d40]">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Competição</dt>
                <dd className="text-right font-medium">{resolvedContext?.competitionName ?? "Todas"}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Temporada</dt>
                <dd className="text-right font-medium">{resolvedContext?.seasonLabel ?? "Todas"}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-[#57657a]">Mando</dt>
                <dd className="text-right font-medium">{describeVenue(venue)}</dd>
              </div>
            </dl>
          </ProfilePanel>

          <ProfilePanel className="space-y-3" tone="soft">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Atalhos
            </p>
            <div className="flex flex-wrap gap-2">
              <Link
                className="button-pill button-pill-primary"
                href={seasonHubHref}
              >
                Voltar para temporada
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href={playersHref}
              >
                Abrir jogadores
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href={teamsHref}
              >
                Abrir times
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href={matchesHref}
              >
                Abrir partidas
              </Link>
            </div>
          </ProfilePanel>
        </div>
      </section>

      <ProfileAlert
        title="Como o recorte funciona no mercado"
        tone={usesScopedTeamApproximation ? "warning" : "info"}
      >
        <p>
          {usesScopedTeamApproximation
            ? "Quando competição, temporada ou rodada estão ativas, a lista filtra transferências pelos times que aparecem nas partidas materializadas do recorte. Isso evita dados fictícios, mas não representa uma janela oficial de inscrição."
            : "Sem recorte competitivo ativo, a lista usa a base integral de transferências e aplica somente busca e janela temporal sobre a data da movimentação."}
        </p>
      </ProfileAlert>

      <PartialDataBanner
        coverage={marketQuery.coverage}
        message="Parte das movimentações pode ficar fora quando o recorte competitivo depende de times presentes nas partidas materializadas."
      />

      <section className="grid gap-4 lg:grid-cols-2">
        {items.map((item) => {
          const playerHref = item.playerId ? buildPlayerResolverPath(item.playerId, sharedFilters) : null;
          const fromTeamHref = item.fromTeamId ? buildTeamResolverPath(item.fromTeamId, sharedFilters) : null;
          const toTeamHref = item.toTeamId ? buildTeamResolverPath(item.toTeamId, sharedFilters) : null;

          return (
            <div
              className="rounded-[1.45rem] border border-[rgba(191,201,195,0.6)] bg-white/90 p-5 shadow-[0_24px_70px_-54px_rgba(17,28,45,0.28)]"
              key={item.transferId}
            >
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#003526] text-sm font-extrabold uppercase tracking-[0.16em] text-white">
                  {getPlayerMonogram(item.playerName)}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                      {item.playerName}
                    </h2>
                    <ProfileTag>{item.completed ? "Concluida" : "Pendente"}</ProfileTag>
                    {item.careerEnded ? <ProfileTag>Fim de carreira</ProfileTag> : null}
                  </div>
                  <p className="mt-1 text-sm/6 text-[#57657a]">
                    {formatTransferDate(item.transferDate)} • {formatMovement(item)}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Origem</p>
                  <p className="text-base font-extrabold text-[#111c2d]">
                    {item.fromTeamName ?? "Não informada"}
                  </p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Destino</p>
                  <p className="text-base font-extrabold text-[#111c2d]">
                    {item.careerEnded ? "Fim de carreira" : item.toTeamName ?? "Não informado"}
                  </p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Valor</p>
                  <p className="text-base font-extrabold text-[#111c2d]">{formatAmount(item.amount)}</p>
                </ProfilePanel>
                <ProfilePanel className="space-y-1" tone="soft">
                  <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">Tipo</p>
                  <p className="text-base font-extrabold text-[#111c2d]">
                    {item.typeId ? `Tipo #${item.typeId}` : "Não informado"}
                  </p>
                </ProfilePanel>
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                {playerHref ? (
                  <Link
                    className="button-pill button-pill-primary"
                    href={playerHref}
                  >
                    Abrir jogador
                  </Link>
                ) : null}
                {fromTeamHref ? (
                  <Link
                    className="button-pill button-pill-secondary"
                    href={fromTeamHref}
                  >
                    Time de origem
                  </Link>
                ) : null}
                {toTeamHref ? (
                  <Link
                    className="button-pill button-pill-secondary"
                    href={toTeamHref}
                  >
                    Time de destino
                  </Link>
                ) : null}
              </div>
            </div>
          );
        })}
      </section>

      <ProfilePanel className="grid gap-3 md:grid-cols-3" tone="soft">
        <ProfileKpi
          hint="Linhas com origem ou destino mapeados"
          label="Movimentos mapeados"
          value={mappedTransfers}
        />
        <ProfileKpi
          hint="Cobertura dos dados exibidos nesta página"
          label="Cobertura"
          value={marketQuery.coverage.status}
        />
        <ProfileKpi hint="Páginas futuras podem expandir o contrato" label="Entrega" value="Lista pública" />
      </ProfilePanel>
    </ProfileShell>
  );
}
