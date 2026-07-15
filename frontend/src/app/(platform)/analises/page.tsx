import Link from "next/link";

import { resolveCompetitionSeasonContextFromSearchParams } from "@/shared/utils/context-routing";

const powerBiReportUrl =
  process.env.NEXT_PUBLIC_POWER_BI_EMBED_URL?.trim() ||
  "https://app.powerbi.com/view?r=eyJrIjoiZjI0MzhlOTMtMzE0Mi00NmY2LWJlNmMtMDRiZTc2YmNmZjBhIiwidCI6IjE0MDAyMTc4LWEwZDAtNGYxNC1iZGQ2LTJiMjNiYTJiNThkYyJ9";
const powerBiEmbedUrl = `${powerBiReportUrl}${powerBiReportUrl.includes("?") ? "&" : "?"}pageName=4742e1e6937d814ce78f`;

type AnalisesPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AnalisesPage({ searchParams }: AnalisesPageProps) {
  const params = (await searchParams) ?? {};
  const context = resolveCompetitionSeasonContextFromSearchParams(params);
  const requestedFilters = [
    context ? { label: "Competição", value: context.competitionName } : null,
    context ? { label: "Temporada", value: context.seasonLabel } : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  return (
    <div className="space-y-3">
      {requestedFilters.length > 0 ? (
        <section className="rounded-[1.25rem] border border-[#8bd6b6]/60 bg-[#eff8f3] px-5 py-4 text-[#17382d]">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#00513b]">
            Contexto solicitado
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {requestedFilters.map((item) => (
              <span className="rounded-full bg-white px-3 py-1.5 text-sm" key={item.label}>
                <strong>{item.label}:</strong> {item.value}
              </span>
            ))}
          </div>
          <p className="mt-3 text-sm/6">
            Selecione esses valores nos filtros do relatório. A publicação pública do Power BI não
            aceita pré-filtros por URL.
          </p>
        </section>
      ) : null}

      <section className="rounded-[1.35rem] border border-[rgba(17,28,45,0.1)] bg-[linear-gradient(145deg,#073c2e_0%,#0b5a45_100%)] p-5 text-white shadow-[0_24px_56px_-38px_rgba(0,53,38,0.7)] md:hidden">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-200">
          Análises competitivas
        </p>
        <h1 className="mt-3 font-[family:var(--font-app-headline)] text-3xl font-extrabold leading-[0.98] tracking-[-0.045em]">
          Abra o relatório em tela cheia
        </h1>
        <p className="mt-3 text-sm/6 text-emerald-50/82">
          O relatório interativo é hospedado pelo Power BI e funciona melhor no modo de tela
          cheia do celular.
        </p>
        <Link
          className="mt-5 inline-flex min-h-11 w-full items-center justify-center rounded-full bg-white px-5 py-3 text-sm font-bold text-[#003526] active:scale-[0.98]"
          href={powerBiEmbedUrl}
          rel="noreferrer"
          target="_blank"
        >
          Abrir relatório completo
        </Link>
      </section>

      <section className="hidden overflow-hidden rounded-[1.5rem] border border-[rgba(17,28,45,0.1)] bg-white shadow-[0_20px_48px_-40px_rgba(17,28,45,0.35)] md:block">
        <iframe
          allowFullScreen
          className="h-[calc(100dvh-8rem)] min-h-[34rem] w-full border-0 lg:h-[calc(100dvh-10rem)]"
          loading="lazy"
          src={powerBiEmbedUrl}
          title="Football Analytics — Análises Competitivas"
        />
      </section>

      <p className="hidden px-2 text-sm text-[#57657a] md:block">
        Se o relatório não carregar, abra o{" "}
        <Link
          className="font-semibold text-[#00513b] underline underline-offset-4"
          href={powerBiEmbedUrl}
          rel="noreferrer"
          target="_blank"
        >
          Power BI em uma nova guia
        </Link>
        .
      </p>
    </div>
  );
}
