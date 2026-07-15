import Link from "next/link";

const PIPELINE = [
  ["01", "Aquisição e qualidade", "Dados públicos são consolidados por fonte, competição e temporada sem transformar ausência em zero."],
  ["02", "Modelagem analítica", "Fatos de partidas, times e jogadores se relacionam a dimensões conformadas de data, escopo e identidade."],
  ["03", "SQL e reconciliação", "Consultas independentes validam placares, pontos, eficiência e métricas por 90 antes da publicação."],
  ["04", "Power BI", "Power Query, modelo TMDL, medidas DAX, cobertura explícita e relatório PBIR versionável compõem a entrega."],
] as const;

const FINDINGS = [
  ["2,3158", "PPG do Barcelona", "La Liga 2024/25 · 88 pontos em 38 jogos"],
  ["15,07%", "Conversão do Barcelona", "102 gols em 677 finalizações no recorte coberto"],
  ["1,1546", "Gols por 90 de Sørloth", "20 gols em 1.559 minutos"],
] as const;

const STATISTICAL_FINDING = {
  scope: "207.770 partidas · 38 competições · 2000–2025",
  result: "-0,095 ponto de vantagem de mando por década",
  evidence: "IC95% bootstrap: -0,126 a -0,064; controle por competição",
} as const;

const COVERAGE = [
  ["259.872", "partidas"],
  ["1.004", "escopos fonte–competição–temporada"],
  ["67,63%", "cobertura de notas de jogadores"],
  ["5,43%", "cobertura de estatísticas de times"],
] as const;

export default function MarketingLandingPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.9),transparent_34%),radial-gradient(circle_at_top_right,rgba(139,214,182,0.22),transparent_28%),linear-gradient(180deg,#f6f8f4_0%,#fbfcff_48%,#f4f8f3_100%)] text-[#111c2d]">
      <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 md:px-10 lg:py-12">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgba(17,28,45,0.08)] pb-5 sm:items-center sm:pb-6">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
              Case de portfólio · Análise de dados
            </p>
            <h1 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#003526]">
              Football Analytics
            </h1>
          </div>
          <div className="flex w-full gap-2 sm:w-auto sm:flex-wrap">
            <Link className="button-pill button-pill-secondary flex-1 sm:flex-none" href="/competitions">
              Explorar dados
            </Link>
            <Link className="button-pill button-pill-primary flex-1 sm:flex-none" href="/analises">
              Abrir Power BI
            </Link>
          </div>
        </header>

        <section className="grid gap-7 py-9 sm:py-12 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)] lg:py-16">
          <div>
            <p className="text-[0.72rem] font-bold uppercase tracking-[0.2em] text-[#00513b]">
              Problema
            </p>
            <h2 className="mt-4 max-w-4xl font-[family:var(--font-profile-headline)] text-[2.5rem] font-extrabold leading-[0.98] tracking-[-0.055em] text-[#003526] md:text-6xl">
              Transformar um acervo heterogêneo de futebol em análises comparáveis e auditáveis.
            </h2>
            <p className="mt-6 max-w-3xl text-base/8 text-[#57657a] md:text-[1.05rem]/8">
              O projeto integra resultados históricos e estatísticas de diferentes fontes. O desafio
              não é apenas criar gráficos: é respeitar o grão dos dados, declarar a cobertura e
              impedir que métricas incompletas produzam conclusões falsas.
            </p>
          </div>

          <aside className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(135deg,#082319_0%,#0d3b2b_58%,#14543e_100%)] p-5 text-white shadow-[0_32px_80px_-56px_rgba(0,53,38,0.8)] sm:rounded-[2rem] sm:p-6">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-white/62">
              Entrega
            </p>
            <h3 className="mt-4 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]">
              Do dado bruto ao produto analítico
            </h3>
            <ul className="mt-6 space-y-3 text-sm/6 text-white/82">
              <li>Modelo estrela com três fatos e dimensões conformadas.</li>
              <li>SQL de seleção de recorte, validação e reconciliação.</li>
              <li>Power Query, DAX e PBIR versionados junto à aplicação.</li>
              <li>Power BI público integrado ao produto web.</li>
            </ul>
          </aside>
        </section>

        <section aria-labelledby="cobertura-title" className="py-4">
          <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
            Snapshot validado
          </p>
          <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]" id="cobertura-title">
            Escala e cobertura real
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {COVERAGE.map(([value, label]) => (
              <article className="rounded-[1.4rem] border border-[rgba(17,28,45,0.08)] bg-white/85 p-5" key={label}>
                <p className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#003526]">{value}</p>
                <p className="mt-2 text-sm/6 text-[#57657a]">{label}</p>
              </article>
            ))}
          </div>
          <p className="mt-4 text-sm/6 text-[#57657a]">
            Cobertura parcial é uma característica do dado, não um valor a ser preenchido. O
            relatório oculta medidas quando a amostra não atende aos limites documentados.
          </p>
        </section>

        <section aria-labelledby="metodo-title" className="py-10 sm:py-14">
          <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">Método</p>
          <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]" id="metodo-title">
            Processo analítico reproduzível
          </h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {PIPELINE.map(([step, title, description]) => (
              <article className="rounded-[1.6rem] border border-[rgba(17,28,45,0.08)] bg-white/82 p-6" key={step}>
                <p className="text-xs font-bold tracking-[0.2em] text-[#00513b]">{step}</p>
                <h3 className="mt-3 text-xl font-bold">{title}</h3>
                <p className="mt-2 text-sm/7 text-[#57657a]">{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="achados-title" className="rounded-[1.5rem] bg-[#eef3ff] p-5 sm:rounded-[2rem] md:p-8">
          <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">Achados reconciliados</p>
          <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]" id="achados-title">
            Exemplo: La Liga 2024/25
          </h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {FINDINGS.map(([value, label, evidence]) => (
              <article className="rounded-[1.4rem] bg-white p-5" key={label}>
                <p className="text-3xl font-extrabold text-[#003526]">{value}</p>
                <h3 className="mt-2 font-bold">{label}</h3>
                <p className="mt-2 text-sm/6 text-[#57657a]">{evidence}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="estatistica-title" className="py-10 sm:py-14">
          <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
            Investigação em Python
          </p>
          <div className="mt-3 grid gap-5 rounded-[1.5rem] bg-[#082319] p-5 text-white sm:rounded-[2rem] sm:p-7 md:grid-cols-[1fr_1.2fr] md:p-9">
            <div>
              <h2 className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]" id="estatistica-title">
                A vantagem de jogar em casa diminuiu?
              </h2>
              <p className="mt-3 text-sm/7 text-white/70">{STATISTICAL_FINDING.scope}</p>
            </div>
            <div>
              <p className="text-2xl font-extrabold text-[#8bd6b6]">{STATISTICAL_FINDING.result}</p>
              <p className="mt-3 text-sm/7 text-white/78">{STATISTICAL_FINDING.evidence}</p>
              <p className="mt-3 text-sm/7 text-white/62">
                Associação observacional, não causal: o estudo declara limites de força dos times,
                público, viagens e estádios neutros.
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-8 py-10 sm:py-14 lg:grid-cols-[1fr_0.8fr]">
          <div>
            <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">Limitações</p>
            <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]">
              O que o projeto não afirma
            </h2>
            <ul className="mt-5 space-y-3 text-sm/7 text-[#57657a]">
              <li>Não há xG na fonte; conversão de finalizações não é tratada como qualidade de chance.</li>
              <li>A classificação DAX não substitui regras oficiais de desempate ou dedução de pontos.</li>
              <li>Notas de provedores diferentes não são comparadas como se usassem a mesma escala.</li>
              <li>Associação entre mando e resultado não demonstra causalidade.</li>
            </ul>
          </div>

          <aside className="rounded-[1.8rem] border border-[rgba(17,28,45,0.08)] bg-white/82 p-6">
            <p className="text-[0.72rem] font-bold uppercase tracking-[0.18em] text-[#00513b]">Resultado</p>
            <h2 className="mt-3 text-2xl font-extrabold">Uma entrega verificável, não apenas visual.</h2>
            <p className="mt-3 text-sm/7 text-[#57657a]">
              Explore o relatório, confira a página de cobertura e use os perfis e catálogos para
              navegar pelo mesmo domínio fora do BI.
            </p>
            <Link className="button-pill button-pill-primary mt-6 w-full sm:w-auto" href="/analises">
              Ver análises no Power BI
            </Link>
          </aside>
        </section>
      </div>
    </main>
  );
}
