"use client";

import Link from "next/link";

import { getCompetitionByKey, type CompetitionDef } from "@/config/competitions.registry";
import {
  getLatestSeasonForCompetition,
  resolveSeasonForCompetition,
  type SeasonDef,
} from "@/config/seasons.registry";
import {
  profileHeadlineVariableClassName,
  profileTypographyClassName,
} from "@/shared/components/profile/ProfilePrimitives";
import { buildMatchesPath } from "@/shared/utils/context-routing";

type MatchCollectionConfig = {
  competitionKey: string;
  description: string;
  eyebrow: string;
  meta: string[];
  roundId?: string;
  seasonLabel?: string;
  title: string;
};

type MatchCollection = MatchCollectionConfig & {
  competition: CompetitionDef;
  href: string;
  season: SeasonDef;
};

const MATCH_COLLECTIONS: MatchCollectionConfig[] = [
  {
    competitionKey: "fifa_world_cup_mens",
    description:
      "A edição completa abre em uma lista de partidas com grupos, oitavas, semifinais e final.",
    eyebrow: "Copa do Mundo 2022",
    meta: ["64 partidas", "fase por fase", "seleções"],
    seasonLabel: "2022",
    title: "Mata-mata e final em uma edição fechada",
  },
  {
    competitionKey: "copa_do_brasil",
    description:
      "Um recorte de copa para navegar por final, semifinais e rodadas eliminatórias sem procurar no catálogo.",
    eyebrow: "Copa do Brasil 2024",
    meta: ["122 partidas", "mata-mata", "ida e volta"],
    seasonLabel: "2024",
    title: "Fases decisivas da copa nacional",
  },
  {
    competitionKey: "brasileirao_a",
    description:
      "Uma rodada fechada de liga, útil para comparar jogos do mesmo momento competitivo.",
    eyebrow: "Brasileirão 2024",
    meta: ["10 partidas", "Rodada 38", "liga"],
    roundId: "38",
    seasonLabel: "2024",
    title: "Rodada final do campeonato",
  },
  {
    competitionKey: "champions_league",
    description:
      "Temporada continental com grupos e eliminatórias para abrir direto na página de partidas.",
    eyebrow: "Champions League 2024/2025",
    meta: ["279 partidas", "Europa", "copa"],
    seasonLabel: "2024/2025",
    title: "Campanha europeia por fases",
  },
  {
    competitionKey: "libertadores",
    description:
      "Arquivo continental sul-americano para entrar em jogos de fase de grupos e mata-mata.",
    eyebrow: "Libertadores 2024",
    meta: ["155 partidas", "América do Sul", "copa"],
    seasonLabel: "2024",
    title: "Edição continental completa",
  },
  {
    competitionKey: "premier_league",
    description:
      "Temporada de liga para explorar rodadas, mandos e partidas de clubes em sequência.",
    eyebrow: "Premier League 2024/2025",
    meta: ["380 partidas", "rodadas", "liga"],
    seasonLabel: "2024/2025",
    title: "Rodadas de uma liga europeia",
  },
];

function buildCompetitionFallbackLabel(competition: CompetitionDef): string {
  const compactShortName = competition.shortName.replace(/[^A-Za-z0-9]/g, "");

  if (compactShortName.length > 1 && compactShortName.length <= 4) {
    return compactShortName.toUpperCase();
  }

  return competition.shortName
    .split(/\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => chunk[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);
}

function resolveCollectionSeason(
  competition: CompetitionDef,
  seasonLabel: string | undefined,
): SeasonDef | null {
  if (seasonLabel) {
    return resolveSeasonForCompetition(competition, { seasonLabel });
  }

  return getLatestSeasonForCompetition(competition) ?? null;
}

function buildCollectionHref(collection: MatchCollection): string {
  return buildMatchesPath({
    competitionId: collection.competition.id,
    roundId: collection.roundId,
    seasonId: collection.season.queryId,
  });
}

function buildMatchCollection(config: MatchCollectionConfig): MatchCollection | null {
  const competition = getCompetitionByKey(config.competitionKey);

  if (!competition) {
    return null;
  }

  const season = resolveCollectionSeason(competition, config.seasonLabel);

  if (!season) {
    return null;
  }

  const collection = {
    ...config,
    competition,
    href: "",
    season,
  };

  return {
    ...collection,
    href: buildCollectionHref(collection),
  };
}

function isMatchCollection(collection: MatchCollection | null): collection is MatchCollection {
  return collection !== null;
}

export function MatchesEntrySurface() {
  const matchCollections = MATCH_COLLECTIONS.map(buildMatchCollection).filter(isMatchCollection);
  const featuredCollection = matchCollections[0];
  const secondaryCollections = matchCollections.slice(1);

  return (
    <main
      className={`${profileTypographyClassName} ${profileHeadlineVariableClassName} mx-auto max-w-7xl space-y-5 text-[#111c2d]`}
    >
      <section className="rounded-[2rem] border border-white/60 bg-[rgba(255,255,255,0.86)] p-6 shadow-[0_24px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl md:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.18em] text-[#57657a]">
              Acervo de partidas
            </p>
            <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-[#111c2d] md:text-5xl">
              Partidas
            </h1>
            <p className="mt-3 max-w-2xl text-sm/6 text-[#57657a]">
              Comece por recortes concretos de jogos: edições, rodadas e fases que abrem direto na
              lista de partidas.
            </p>
          </div>

          <div className="rounded-[1.45rem] border border-[rgba(191,201,195,0.48)] bg-[rgba(249,251,255,0.78)] p-4">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#6b7890]">
              Como a página funciona
            </p>
            <div className="mt-3 space-y-2 text-sm/6 text-[#1f2d40]">
              <p>1. Abra um recorte fechado de competição e temporada.</p>
              <p>2. Refine por busca, rodada ou janela dentro da lista.</p>
              <p>3. Entre na central da partida para o detalhe completo.</p>
            </div>
          </div>
        </div>
      </section>

      {featuredCollection ? (
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <Link
            className="group overflow-hidden rounded-[2rem] border border-[rgba(0,81,59,0.16)] bg-[linear-gradient(135deg,#003526_0%,#00513b_100%)] p-6 text-white shadow-[0_30px_80px_-52px_rgba(0,53,38,0.75)] transition-transform hover:-translate-y-0.5"
            href={featuredCollection.href}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/12 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/76">
                Recorte pronto
              </span>
              <span className="rounded-full bg-white/12 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-white/76">
                {featuredCollection.eyebrow}
              </span>
            </div>
            <h2 className="mt-6 max-w-2xl font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {featuredCollection.title}
            </h2>
            <p className="mt-4 max-w-2xl text-sm/6 text-white/76">
              {featuredCollection.description}
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {featuredCollection.meta.map((item) => (
                <span
                  className="rounded-full border border-white/12 bg-white/10 px-3 py-1 text-[0.72rem] font-semibold text-white/82"
                  key={item}
                >
                  {item}
                </span>
              ))}
            </div>
            <span className="mt-8 inline-flex text-sm font-semibold text-white transition-colors group-hover:text-white/82">
              Abrir partidas deste recorte
            </span>
          </Link>

          <section className="rounded-[2rem] border border-white/60 bg-[rgba(255,255,255,0.86)] p-5 shadow-[0_24px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl">
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              O que fica visível depois
            </p>
            <div className="mt-4 space-y-3">
              <div className="rounded-[1.25rem] bg-[rgba(240,243,255,0.92)] p-4">
                <p className="text-sm font-semibold text-[#111c2d]">Lista de partidas do recorte</p>
                <p className="mt-1 text-sm/6 text-[#57657a]">
                  A página abre com paginação real e somente os jogos da edição selecionada.
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-[rgba(240,243,255,0.92)] p-4">
                <p className="text-sm font-semibold text-[#111c2d]">Agrupamento por competição</p>
                <p className="mt-1 text-sm/6 text-[#57657a]">
                  Liga aparece por rodada; copa aparece por fase, sem tratar o acervo como agenda.
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-[rgba(240,243,255,0.92)] p-4">
                <p className="text-sm font-semibold text-[#111c2d]">Central da partida</p>
                <p className="mt-1 text-sm/6 text-[#57657a]">
                  Cada jogo leva para escalações, eventos e estatísticas quando disponíveis.
                </p>
              </div>
            </div>
          </section>
        </section>
      ) : null}

      <section className="rounded-[2rem] border border-white/60 bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_24px_60px_-48px_rgba(17,28,45,0.32)] backdrop-blur-xl md:p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">
              Entradas diretas em partidas
            </p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
              Recortes para abrir agora
            </h2>
          </div>
          <p className="max-w-xl text-sm/6 text-[#57657a]">
            Nenhum desses caminhos consulta o arquivo inteiro. Todos já chegam com competição e
            temporada definidos.
          </p>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {secondaryCollections.map((collection) => (
            <Link
              className="group flex min-h-[230px] flex-col rounded-[1.45rem] border border-[rgba(191,201,195,0.48)] bg-[rgba(249,251,255,0.82)] p-4 transition-colors hover:border-[rgba(0,81,59,0.25)] hover:bg-white"
              href={collection.href}
              key={`${collection.competition.key}-${collection.season.id}-${collection.roundId ?? "all"}`}
            >
              <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-[#003526] text-xs font-extrabold text-white">
                  {buildCompetitionFallbackLabel(collection.competition)}
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7890]">
                    {collection.eyebrow}
                  </p>
                  <h3 className="mt-1 font-[family:var(--font-profile-headline)] text-xl font-extrabold tracking-[-0.03em] text-[#111c2d]">
                    {collection.title}
                  </h3>
                </div>
              </div>
              <p className="mt-4 text-sm/6 text-[#57657a]">{collection.description}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {collection.meta.map((item) => (
                  <span
                    className="rounded-full bg-[rgba(216,227,251,0.7)] px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[#27415f]"
                    key={item}
                  >
                    {item}
                  </span>
                ))}
              </div>
              <span className="mt-auto pt-5 text-sm font-semibold text-[#00513b] transition-colors group-hover:text-[#003526]">
                Ver partidas
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
