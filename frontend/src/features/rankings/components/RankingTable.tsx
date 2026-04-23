"use client";

import { useDeferredValue, useEffect, useMemo, useState, type ReactNode } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { getCompetitionById } from "@/config/competitions.registry";
import { formatMetricValue, getMetric } from "@/config/metrics.registry";
import { RANKING_DEFINITIONS } from "@/config/ranking.registry";
import type { RankingDefinition, RankingSortDirection } from "@/config/ranking.types";
import { getSeasonById } from "@/config/seasons.registry";
import { useRankingTable } from "@/features/rankings/hooks";
import type { RankingScopeSample, RankingTableRow } from "@/features/rankings/types";
import { PartialDataBanner } from "@/shared/components/coverage/PartialDataBanner";
import { EmptyState } from "@/shared/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfileAlert,
  ProfilePanel,
  ProfileShell,
  ProfileTabs,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";
import { ProfileMedia } from "@/shared/components/profile/ProfileMedia";
import { useGlobalFiltersState } from "@/shared/hooks/useGlobalFilters";
import { useResolvedCompetitionContext } from "@/shared/hooks/useResolvedCompetitionContext";
import { useTimeRange } from "@/shared/hooks/useTimeRange";
import {
  buildCanonicalPlayerPath,
  buildCanonicalTeamPath,
  buildPlayerResolverPath,
  buildTeamResolverPath,
} from "@/shared/utils/context-routing";

type RankingTableProps = {
  rankingDefinition: RankingDefinition;
};

type RankingRowRecentTeam = {
  teamId: string;
  teamName?: string | null;
};

const INTEGER_FORMATTER = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});

const DECIMAL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function joinClasses(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function parseMinSample(value: string): number | null {
  const normalizedValue = value.trim();

  if (normalizedValue.length === 0) {
    return null;
  }

  const parsedValue = Number.parseInt(normalizedValue, 10);

  if (!Number.isInteger(parsedValue) || parsedValue < 0) {
    return null;
  }

  return parsedValue;
}

function parseNullableQueryValue(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const normalizedValue = value.trim();
  return normalizedValue.length > 0 ? normalizedValue : null;
}

function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return INTEGER_FORMATTER.format(value);
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }

  return DECIMAL_FORMATTER.format(value);
}

function formatUpdatedAt(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const parsedValue = new Date(value);

  if (Number.isNaN(parsedValue.getTime())) {
    return "-";
  }

  return DATE_TIME_FORMATTER.format(parsedValue);
}

function formatSampleValue(sample: RankingScopeSample | null | undefined): string {
  if (!sample || sample.appliedValue === null || sample.appliedValue === undefined) {
    return "Sem mínimo";
  }

  if (sample.unitLabel) {
    return `${formatInteger(sample.appliedValue)} ${sample.unitLabel}`;
  }

  return formatInteger(sample.appliedValue);
}

function getEntityMonogram(entityName: string): string {
  const initials = entityName
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);

  return initials.length > 0 ? initials : "RK";
}

function resolveEntityMediaCategory(
  entity: RankingDefinition["entity"],
): "clubs" | "players" | null {
  if (entity === "player") {
    return "players";
  }

  if (entity === "team") {
    return "clubs";
  }

  return null;
}

function resolveEntityHref(
  entity: RankingDefinition["entity"],
  entityId: string,
  context: ReturnType<typeof useResolvedCompetitionContext>,
  competitionId: string | null,
  seasonId: string | null,
): string | null {
  if (entity === "player") {
    return context
      ? buildCanonicalPlayerPath(context, entityId)
      : buildPlayerResolverPath(entityId, { competitionId, seasonId });
  }

  if (entity === "team") {
    return context
      ? buildCanonicalTeamPath(context, entityId)
      : buildTeamResolverPath(entityId, { competitionId, seasonId });
  }

  return null;
}

function resolveTeamHref(
  teamId: string,
  context: ReturnType<typeof useResolvedCompetitionContext>,
  competitionId: string | null,
  seasonId: string | null,
): string | null {
  return context
    ? buildCanonicalTeamPath(context, teamId)
    : buildTeamResolverPath(teamId, { competitionId, seasonId });
}

function resolveRecentTeams(row: RankingTableRow): RankingRowRecentTeam[] {
  const recentTeams = (row as RankingTableRow & { recentTeams?: RankingRowRecentTeam[] | null })
    .recentTeams;

  if (Array.isArray(recentTeams) && recentTeams.length > 0) {
    return recentTeams
      .filter((team) => typeof team.teamId === "string" && team.teamId.trim().length > 0)
      .slice(0, 5);
  }

  if (row.teamId) {
    return [{ teamId: row.teamId, teamName: row.teamName ?? null }];
  }

  return [];
}

function shouldShowCoverageNotice(status: string, percentage?: number): boolean {
  if (status !== "partial") {
    return false;
  }

  if (typeof percentage === "number") {
    return percentage < 95;
  }

  return true;
}

function resolveCoverageMessage(percentage?: number): string {
  if (typeof percentage === "number") {
    return `Cobertura parcial no recorte atual (${percentage.toFixed(0)}% coberto). Use o ranking como leitura comparativa, não como retrato exaustivo.`;
  }

  return "Cobertura parcial no recorte atual. Use o ranking como leitura comparativa, não como retrato exaustivo.";
}

function buildRankingHref(rankingId: string, currentSearch: string): string {
  return currentSearch.length > 0
    ? `/rankings/${rankingId}?${currentSearch}`
    : `/rankings/${rankingId}`;
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={joinClasses("h-4 w-4", className)}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="m16 16 4 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function RankingSummaryCard({
  detail,
  highlight = false,
  label,
  value,
}: {
  detail: ReactNode;
  highlight?: boolean;
  label: string;
  value: ReactNode;
}) {
  return (
    <article
      className={joinClasses(
        "flex min-h-[6.6rem] flex-col items-center justify-center rounded-[1.25rem] px-4 py-4 text-center shadow-[0_18px_38px_-34px_rgba(17,28,45,0.2)]",
        highlight
          ? "bg-[linear-gradient(135deg,#003526_0%,#004e39_100%)] text-white"
          : "bg-[linear-gradient(180deg,rgba(240,243,255,0.94),rgba(248,251,255,0.88))] text-[#111c2d]",
      )}
    >
      <p
        className={joinClasses(
          "break-words text-center font-[family:var(--font-profile-headline)] text-[1.65rem] font-extrabold leading-none tracking-[-0.05em] md:text-[1.85rem]",
          highlight ? "text-white" : "text-[#0f2035]",
        )}
      >
        {value}
      </p>
      <p
        className={joinClasses(
          "mt-3 text-center text-[0.66rem] font-semibold uppercase tracking-[0.18em]",
          highlight ? "text-white/86" : "text-[#69778d]",
        )}
      >
        {label}
      </p>
      <p
        className={joinClasses(
          "mt-1 text-center text-[0.82rem]/5",
          highlight ? "text-white/78" : "text-[#6b7890]",
        )}
      >
        {detail}
      </p>
    </article>
  );
}

function resolveSampleFilterLabel(
  rankingDefinition: RankingDefinition,
  sample: RankingScopeSample | null | undefined,
): string {
  const sampleField = sample?.field ?? rankingDefinition.minSample?.field;

  if (sampleField === "minutes_played" || sampleField === "minutesPlayed") {
    return "Minutos mínimos";
  }

  if (sampleField === "matches_played" || sampleField === "matchesPlayed") {
    return "Jogos mínimos";
  }

  return "Mínimo";
}

function resolveEntityCopy(entity: RankingDefinition["entity"]) {
  if (entity === "team") {
    return {
      singular: "time",
      plural: "times",
      singularTitle: "Time",
      title: "Times",
    };
  }

  return {
    singular: "jogador",
    plural: "jogadores",
    singularTitle: "Jogador",
    title: "Jogadores",
  };
}

export function RankingTable({ rankingDefinition }: RankingTableProps) {
  const metric = getMetric(rankingDefinition.metricKey);
  const searchParams = useSearchParams();
  const currentSearch = searchParams.toString();
  const selectedStageId = parseNullableQueryValue(searchParams.get("stageId"));
  const selectedStageFormat = parseNullableQueryValue(searchParams.get("stageFormat"));
  const { competitionId, seasonId } = useGlobalFiltersState();
  const resolvedContext = useResolvedCompetitionContext();
  const { params: timeRangeParams } = useTimeRange();

  const defaultMinSampleInput = rankingDefinition.minSample?.min?.toString() ?? "";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortDirection, setSortDirection] = useState<RankingSortDirection>(
    rankingDefinition.defaultSort,
  );
  const [minSampleInput, setMinSampleInput] = useState(defaultMinSampleInput);

  const deferredSearch = useDeferredValue(search);
  const minSampleValue = useMemo(() => parseMinSample(minSampleInput), [minSampleInput]);

  useEffect(() => {
    setSearch("");
    setPage(1);
    setSortDirection(rankingDefinition.defaultSort);
    setMinSampleInput(defaultMinSampleInput);
  }, [defaultMinSampleInput, rankingDefinition.defaultSort, rankingDefinition.id]);

  useEffect(() => {
    setPage(1);
  }, [
    competitionId,
    seasonId,
    deferredSearch,
    minSampleValue,
    pageSize,
    selectedStageFormat,
    selectedStageId,
    sortDirection,
    timeRangeParams.dateRangeEnd,
    timeRangeParams.dateRangeStart,
    timeRangeParams.lastN,
    timeRangeParams.roundId,
  ]);

  const rankingQuery = useRankingTable(rankingDefinition, {
    localFilters: {
      search: deferredSearch,
      sortDirection,
      minSampleValue,
      stageId: selectedStageId,
      stageFormat: selectedStageFormat,
      page,
      pageSize,
    },
  });

  const rows = rankingQuery.data?.rows ?? [];
  const pagination = rankingQuery.meta?.pagination;
  const totalCount = pagination?.totalCount ?? rows.length;
  const totalPages = Math.max(pagination?.totalPages ?? 1, 1);
  const currentPage = pagination?.page ?? page;
  const currentRangeStart = totalCount === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const currentRangeEnd = totalCount === 0 ? 0 : currentRangeStart + rows.length - 1;
  const scope = rankingQuery.data?.scope;
  const showPer90Column =
    rankingDefinition.metricKey === "goals" &&
    rows.some((row) => typeof row.metricPer90 === "number");
  const entityCopy = resolveEntityCopy(rankingDefinition.entity);

  const fallbackCompetitionName = getCompetitionById(competitionId)?.name ?? null;
  const fallbackSeasonLabel = getSeasonById(seasonId)?.label ?? null;
  const competitionName = scope?.competitionName ?? fallbackCompetitionName;
  const seasonLabel = scope?.seasonLabel ?? fallbackSeasonLabel;
  const sampleFilterLabel = resolveSampleFilterLabel(rankingDefinition, scope?.sample);
  const contextSummary = competitionName && seasonLabel
    ? `${competitionName} · ${seasonLabel}`
    : competitionName ?? seasonLabel ?? "Todas as competições";
  const leaderRow = currentPage === 1 ? rows[0] ?? null : null;
  const leaderMetricValue =
    currentPage === 1 && leaderRow
      ? formatMetricValue(rankingDefinition.metricKey, leaderRow.metricValue)
      : `Página ${currentPage}`;
  const leaderSummary = currentPage === 1 && leaderRow
    ? (leaderRow.entityName ?? leaderRow.entityId)
    : "Primeira página do ranking";
  const updatedAtLabel = formatUpdatedAt(rankingQuery.data?.updatedAt);
  const hasLocalFilters =
    search.trim().length > 0 ||
    sortDirection !== rankingDefinition.defaultSort ||
    minSampleInput.trim() !== defaultMinSampleInput;
  const rankingTabs = useMemo(
    () =>
      RANKING_DEFINITIONS.map((ranking) => ({
        href: buildRankingHref(ranking.id, currentSearch),
        isActive: ranking.id === rankingDefinition.id,
        key: ranking.id,
        label: ranking.label,
      })),
    [currentSearch, rankingDefinition.id],
  );
  const resetLocalFilters = () => {
    setSearch("");
    setPage(1);
    setSortDirection(rankingDefinition.defaultSort);
    setMinSampleInput(defaultMinSampleInput);
  };

  if (!metric) {
    return (
      <ProfileShell className="space-y-6">
        <header className="space-y-2">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
            Rankings
          </p>
          <h1 className="font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-tight text-[#111c2d]">
            {rankingDefinition.label}
          </h1>
        </header>
        <ProfileAlert title="Ranking inválido" tone="critical">
          A métrica configurada para este ranking não foi encontrada.
        </ProfileAlert>
      </ProfileShell>
    );
  }

  if (rankingQuery.isLoading && !rankingQuery.data) {
    return (
      <ProfileShell className="space-y-5">
        <LoadingSkeleton height={220} />
        <LoadingSkeleton height={120} />
        <LoadingSkeleton height={420} />
      </ProfileShell>
    );
  }

  if (rankingQuery.isError && rows.length === 0) {
    return (
      <ProfileShell className="space-y-5">
        <ProfileAlert title="Falha ao carregar ranking" tone="critical">
          <p>{rankingQuery.error?.message}</p>
        </ProfileAlert>
      </ProfileShell>
    );
  }

  return (
    <ProfileShell className="space-y-5" variant="plain">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2 text-[0.78rem] font-semibold text-[#7d889e]">
          <Link className="transition-colors hover:text-[#003526]" href="/">
            Início
          </Link>
          <span className="text-[#b1bccf]">/</span>
          <span className="text-[#0b6a56]">Rankings</span>
        </div>

        <div className="grid gap-4 md:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] md:items-start">
          <div className="max-w-3xl space-y-3">
            <p className="text-[0.68rem] font-bold uppercase leading-none tracking-[0.2em] text-[#69778d]">
              Ranking atual
            </p>
            <h1 className="font-[family:var(--font-profile-headline)] text-[2.35rem] font-extrabold leading-[0.98] tracking-[-0.055em] text-[#003526] md:text-[3.05rem]">
              {rankingDefinition.label} de {entityCopy.plural}
            </h1>
            <p className="max-w-2xl text-base/7 text-[#57657a]">
              {rankingDefinition.description} Use os filtros para ajustar competição, temporada e
              janela.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <RankingSummaryCard
              detail={`${entityCopy.plural} no recorte`}
              label="Resultados"
              value={formatInteger(totalCount)}
            />
            <RankingSummaryCard
              detail={leaderSummary}
              highlight
              label={currentPage === 1 ? "Líder" : "Página"}
              value={leaderMetricValue}
            />
            <RankingSummaryCard
              detail={competitionName ?? "Todas as competições"}
              label="Competição"
              value={competitionName ?? "Competição"}
            />
            <RankingSummaryCard
              detail={scope?.window.label ?? "Todos os jogos"}
              label="Temporada"
              value={seasonLabel ?? "Todas"}
            />
          </div>
        </div>
      </section>

      <ProfileTabs
        ariaLabel="Tipos de ranking"
        className="mx-auto w-full max-w-6xl"
        density="compact"
        items={rankingTabs}
        navClassName="w-full justify-center md:flex-1 md:justify-center"
        aside={<ProfileTag>{contextSummary}</ProfileTag>}
      />

      <section className="mx-auto grid w-full max-w-6xl gap-3 rounded-[1.35rem] bg-[linear-gradient(180deg,rgba(240,243,255,0.82),rgba(248,251,255,0.92))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.84),0_16px_36px_-34px_rgba(17,28,45,0.18)] lg:grid-cols-[minmax(18rem,1.2fr)_220px_220px_auto] lg:items-end">
        <label className="flex flex-col gap-2 text-sm font-semibold text-[#1f2d40]">
          <span className="text-[0.68rem] font-bold uppercase leading-none tracking-[0.2em] text-[#69778d]">
            Buscar
          </span>
          <div className="relative flex min-h-[3.35rem] items-center rounded-[1rem] bg-white/94 shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)]">
            <SearchIcon className="pointer-events-none absolute left-4 text-[#8d9ab0]" />
            <input
              className="w-full border-0 bg-transparent py-3 pl-11 pr-4 text-[0.96rem] text-[#162235] outline-none placeholder:text-[#97a4b7]"
              onChange={(event) => {
                setSearch(event.target.value);
              }}
              placeholder={`Buscar ${entityCopy.singular}`}
              type="search"
              value={search}
            />
          </div>
        </label>

        <label className="flex flex-col gap-2 text-sm font-semibold text-[#1f2d40]">
          <span className="text-[0.68rem] font-bold uppercase leading-none tracking-[0.2em] text-[#69778d]">
            Ordenar
          </span>
          <select
            className="min-h-[3.35rem] rounded-[1rem] border-0 bg-white/94 px-4 text-[0.92rem] font-semibold text-[#162235] shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)] outline-none"
            onChange={(event) => {
              setSortDirection(event.target.value as RankingSortDirection);
            }}
            value={sortDirection}
          >
            <option value="desc">Maior para menor</option>
            <option value="asc">Menor para maior</option>
          </select>
        </label>

        <label className="flex flex-col gap-2 text-sm font-semibold text-[#1f2d40]">
          <span className="text-[0.68rem] font-bold uppercase leading-none tracking-[0.2em] text-[#69778d]">
            {sampleFilterLabel}
          </span>
          <input
            className="min-h-[3.35rem] rounded-[1rem] border-0 bg-white/94 px-4 text-[0.92rem] font-semibold text-[#162235] shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_-30px_rgba(17,28,45,0.2)] outline-none placeholder:text-[#97a4b7]"
            min={0}
            onChange={(event) => {
              setMinSampleInput(event.target.value);
            }}
            placeholder={defaultMinSampleInput || "Opcional"}
            type="number"
            value={minSampleInput}
          />
        </label>

        <button
          className={joinClasses("button-pill", hasLocalFilters ? "button-pill-primary" : "button-pill-secondary")}
          disabled={!hasLocalFilters}
          onClick={resetLocalFilters}
          type="button"
        >
          Limpar filtros
        </button>
      </section>

      <ProfilePanel className="mx-auto w-full max-w-6xl overflow-hidden p-0">
        <div className="flex flex-col gap-3 px-5 py-5 md:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Ranking atual
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
              {rankingDefinition.label}
            </h2>
            <p className="mt-2 text-sm/6 text-[#57657a]">
              Mostrando {formatInteger(currentRangeStart)}-{formatInteger(currentRangeEnd)} de{" "}
              {formatInteger(totalCount)} {entityCopy.plural}. {contextSummary}.
              {updatedAtLabel !== "-" ? ` Atualização: ${updatedAtLabel}.` : ""}
              {rankingDefinition.entity === "player"
                ? " Quando um jogador aparece por mais de um time, o detalhe indica o vínculo exibido."
                : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProfileTag>{metric.label}</ProfileTag>
            {showPer90Column ? <ProfileTag>Gols por 90</ProfileTag> : null}
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="px-5 pb-5 md:px-6">
            <EmptyState
              description={
                search.trim().length > 0
                  ? `Nenhum ${entityCopy.singular} encontrado para "${search.trim()}" no recorte atual.`
                  : `Não há ${entityCopy.plural} suficientes para os filtros atuais.`
              }
              title="Ranking vazio"
            />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto border-t border-[rgba(222,228,237,0.86)]">
              <table className="min-w-full border-collapse text-left text-sm text-[#1f2d40]">
                <thead className="bg-[rgba(240,243,255,0.92)] text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                  <tr>
                    <th className="w-16 px-4 py-3 font-semibold">#</th>
                    <th className="min-w-[280px] px-4 py-3 font-semibold">{entityCopy.singularTitle}</th>
                    {rankingDefinition.entity === "player" ? (
                      <th className="min-w-[240px] px-4 py-3 font-semibold">Time</th>
                    ) : null}
                    <th className="w-24 px-4 py-3 text-right font-semibold">Jogos</th>
                    {rankingDefinition.entity === "player" ? (
                      <th className="w-28 px-4 py-3 text-right font-semibold">Minutos</th>
                    ) : null}
                    <th className="w-24 px-4 py-3 text-right font-semibold whitespace-nowrap">{metric.label}</th>
                    {showPer90Column ? (
                      <th className="w-24 px-4 py-3 text-right font-semibold">Gols/90</th>
                    ) : null}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgba(191,201,195,0.38)]">
                  {rows.map((row) => {
                    const entityName = row.entityName ?? row.entityId;
                    const entityHref = resolveEntityHref(
                      rankingDefinition.entity,
                      row.entityId,
                      resolvedContext,
                      competitionId,
                      seasonId,
                    );
                    const recentTeams = resolveRecentTeams(row);

                    return (
                      <tr className="align-top hover:bg-[rgba(240,243,255,0.42)]" key={row.entityId}>
                        <td className="px-4 py-3">
                          <span className="inline-flex min-w-10 items-center justify-center rounded-full bg-[rgba(216,227,251,0.72)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#003526]">
                            {row.rank ?? "-"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <ProfileMedia
                              alt={entityName}
                              assetId={row.entityId}
                              category={resolveEntityMediaCategory(rankingDefinition.entity) ?? "players"}
                              className="h-11 w-11 border-0 bg-[rgba(216,227,251,0.82)]"
                              fallback={getEntityMonogram(entityName)}
                              imageClassName="p-1.5"
                              shape="circle"
                            />
                            <div className="min-w-0">
                              {entityHref ? (
                                <Link
                                  className="block truncate font-semibold text-[#111c2d] transition-colors hover:text-[#003526]"
                                  href={entityHref}
                                >
                                  {entityName}
                                </Link>
                              ) : (
                                <p className="truncate font-semibold text-[#111c2d]">{entityName}</p>
                              )}
                              <p className="mt-1 text-xs text-[#57657a]">
                                {row.rank === 1 ? "Líder" : "Posição no ranking"}
                              </p>
                            </div>
                          </div>
                        </td>
                        {rankingDefinition.entity === "player" ? (
                          <td className="px-4 py-3">
                            <div className="flex min-h-[2.5rem] items-center gap-1.5 whitespace-nowrap">
                              {recentTeams.length > 0 ? (
                                recentTeams.map((team, index) => {
                                  const teamHref = resolveTeamHref(
                                    team.teamId,
                                    resolvedContext,
                                    competitionId,
                                    seasonId,
                                  );
                                  const teamAsset = (
                                    <ProfileMedia
                                      alt={team.teamName ?? "Time"}
                                      assetId={team.teamId}
                                      category="clubs"
                                      className="h-10 w-10 border border-white/70 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.86),0_12px_24px_-20px_rgba(17,28,45,0.24)]"
                                      fallback={getEntityMonogram(team.teamName ?? "Time")}
                                      fallbackClassName="text-[0.62rem]"
                                      imageClassName="p-1.25"
                                      shape="rounded"
                                    />
                                  );

                                  if (teamHref) {
                                    return (
                                      <Link
                                        aria-label={team.teamName ?? "Time"}
                                        className="transition-transform duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5"
                                        href={teamHref}
                                        key={`${row.entityId}-${team.teamId}-${index}`}
                                        title={team.teamName ?? "Time"}
                                      >
                                        {teamAsset}
                                      </Link>
                                    );
                                  }

                                  return (
                                    <div
                                      aria-label={team.teamName ?? "Time"}
                                      key={`${row.entityId}-${team.teamId}-${index}`}
                                      title={team.teamName ?? "Time"}
                                    >
                                      {teamAsset}
                                    </div>
                                  );
                                })
                              ) : (
                                <span className="text-sm text-[#93a0b4]">-</span>
                              )}
                            </div>
                          </td>
                        ) : null}
                        <td className="px-4 py-3 text-right font-medium tabular-nums text-[#1f2d40]">
                          {formatInteger(row.matchesPlayed)}
                        </td>
                        {rankingDefinition.entity === "player" ? (
                          <td className="px-4 py-3 text-right font-medium tabular-nums text-[#1f2d40]">
                            {formatMetricValue("minutes_played", row.minutesPlayed)}
                          </td>
                        ) : null}
                        <td className="px-4 py-3 text-right">
                          <p className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
                            {formatMetricValue(rankingDefinition.metricKey, row.metricValue)}
                          </p>
                          <p className="mt-1 whitespace-nowrap text-[0.68rem] uppercase tracking-[0.16em] text-[#57657a]">
                            {metric.label}
                          </p>
                        </td>
                        {showPer90Column ? (
                          <td className="px-4 py-3 text-right font-medium tabular-nums text-[#1f2d40]">
                            {formatDecimal(row.metricPer90)}
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 border-t border-[rgba(191,201,195,0.4)] bg-[rgba(240,243,255,0.52)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-[#57657a]">
                Página {formatInteger(currentPage)} de {formatInteger(totalPages)}.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-[#57657a]">
                  Linhas
                  <select
                    className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/88 px-3 py-1.5 text-[#1f2d40]"
                    onChange={(event) => {
                      const nextSize = Number(event.target.value);
                      setPageSize(nextSize);
                    }}
                    value={pageSize}
                  >
                    {[10, 25, 50, 100].map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-1.5 font-medium text-[#1f2d40] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage <= 1}
                  onClick={() => {
                    setPage((currentValue) => Math.max(currentValue - 1, 1));
                  }}
                  type="button"
                >
                  Anterior
                </button>
                <button
                  className="rounded-full border border-[rgba(112,121,116,0.22)] bg-white/92 px-3 py-1.5 font-medium text-[#1f2d40] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage >= totalPages}
                  onClick={() => {
                    setPage((currentValue) => Math.min(currentValue + 1, totalPages));
                  }}
                  type="button"
                >
                  Próxima
                </button>
              </div>
            </div>
          </>
        )}
      </ProfilePanel>

      {rankingQuery.isError ? (
        <ProfileAlert className="mx-auto w-full max-w-6xl" title="Dados carregados com alerta" tone="warning">
          <p>{rankingQuery.error?.message}</p>
        </ProfileAlert>
      ) : null}

      {shouldShowCoverageNotice(
        rankingQuery.coverage.status,
        rankingQuery.coverage.percentage,
      ) ? (
        <PartialDataBanner
          className="mx-auto w-full max-w-6xl"
          coverage={rankingQuery.coverage}
          message={resolveCoverageMessage(rankingQuery.coverage.percentage)}
        />
      ) : null}
    </ProfileShell>
  );
}
