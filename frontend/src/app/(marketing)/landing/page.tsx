import Link from "next/link";

const PRODUCT_PILLARS = [
  {
    title: "Dados confiáveis",
    description:
      "Cada análise nasce de um acervo consistente, com contexto claro de competição e temporada para reduzir ruído e aumentar confiança.",
  },
  {
    title: "Leitura completa do jogo",
    description:
      "Da visão geral ao detalhe da partida, você encontra performance, tendências e comparativos sem perder o fio da análise.",
  },
  {
    title: "Decisão mais rápida",
    description:
      "Rankings, times e jogadores em uma experiência integrada para transformar informação em ação com mais velocidade.",
  },
] as const;

const PRODUCT_ENTRIES = [
  {
    href: "/",
    title: "Visão geral do produto",
    description:
      "Painel principal para acompanhar o cenário atual e abrir as análises mais relevantes em poucos cliques.",
  },
  {
    href: "/competitions",
    title: "Competições",
    description: "Explore ligas e torneios com contexto histórico e recorte por temporada.",
  },
  {
    href: "/teams",
    title: "Times",
    description: "Avalie desempenho, consistência e evolução de cada equipe com profundidade.",
  },
  {
    href: "/players",
    title: "Jogadores",
    description: "Compare atletas, encontre destaques e identifique impacto real em campo.",
  },
  {
    href: "/rankings",
    title: "Rankings",
    description: "Monitore líderes por métrica e descubra oportunidades com leitura objetiva.",
  },
] as const;

export default function MarketingLandingPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.9),transparent_34%),radial-gradient(circle_at_top_right,rgba(139,214,182,0.22),transparent_28%),linear-gradient(180deg,#f6f8f4_0%,#fbfcff_48%,#f4f8f3_100%)] text-[#111c2d]">
      <div className="mx-auto max-w-6xl px-6 py-8 md:px-10 lg:py-12">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[rgba(17,28,45,0.08)] pb-6">
          <div>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.22em] text-[#57657a]">
              Football Analytics
            </p>
            <h1 className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.04em] text-[#003526]">
              Inteligência de futebol para decidir melhor
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link
              className="button-pill button-pill-secondary"
              href="/competitions"
            >
              Ver produto
            </Link>
            <Link
              className="button-pill button-pill-primary"
              href="/"
            >
              Começar agora
            </Link>
          </div>
        </header>

        <section className="grid gap-8 py-12 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)] lg:py-16">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-[rgba(216,227,251,0.78)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#404944]">
                Plataforma profissional
              </span>
              <span className="inline-flex items-center rounded-full bg-[rgba(139,214,182,0.22)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#00513b]">
                Pronta para operação
              </span>
            </div>

            <div className="space-y-4">
              <h2 className="font-[family:var(--font-profile-headline)] text-5xl font-extrabold tracking-[-0.06em] text-[#003526] md:text-6xl">
                Transforme dados de futebol em vantagem competitiva.
              </h2>
              <p className="max-w-3xl text-base/8 text-[#57657a] md:text-[1.05rem]/8">
                O Football Analytics conecta competições, partidas, times e jogadores em uma única
                experiência. Você ganha clareza para comparar cenários, identificar tendências e
                agir com segurança em decisões esportivas e editoriais.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="button-pill button-pill-primary"
                href="/"
              >
                Experimentar plataforma
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href="/competitions"
              >
                Explorar competições
              </Link>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-[rgba(17,28,45,0.08)] bg-[linear-gradient(135deg,#082319_0%,#0d3b2b_58%,#14543e_100%)] p-6 text-white shadow-[0_32px_80px_-56px_rgba(0,53,38,0.8)]">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-white/62">
              Por que escolher
            </p>
            <h3 className="mt-4 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]">
              Qualidade, velocidade e profundidade
            </h3>
            <p className="mt-4 text-sm/7 text-white/78">
              Desenvolvido para quem precisa confiar no dado e ganhar tempo na análise: scouting,
              conteúdo, inteligência de mercado e acompanhamento de performance.
            </p>

            <div className="mt-6 grid gap-3">
              <div className="rounded-[1.3rem] border border-white/10 bg-white/10 px-4 py-4">
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-white/62">Cobertura rica</p>
                <p className="mt-2 text-sm/6 text-white/82">
                  Métricas, rankings e contexto para enxergar o jogo além do placar.
                </p>
              </div>
              <div className="rounded-[1.3rem] border border-white/10 bg-white/10 px-4 py-4">
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-white/62">
                  Fluxo integrado
                </p>
                <p className="mt-2 text-sm/6 text-white/82">
                  Navegue entre competição, partida, time e jogador sem quebrar o contexto.
                </p>
              </div>
            </div>
          </aside>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {PRODUCT_PILLARS.map((pillar) => (
            <article
              className="rounded-[1.6rem] border border-[rgba(17,28,45,0.08)] bg-white/82 p-6 shadow-[0_24px_60px_-50px_rgba(17,28,45,0.18)]"
              key={pillar.title}
            >
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                Diferencial
              </p>
              <h3 className="mt-3 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
                {pillar.title}
              </h3>
              <p className="mt-3 text-sm/7 text-[#57657a]">{pillar.description}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-8 py-14 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <div className="space-y-5">
            <div>
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                Onde você gera valor
              </p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                Módulos desenhados para uso real
              </h2>
            </div>

            <div className="grid gap-3">
              {PRODUCT_ENTRIES.map((entry) => (
                <Link
                  className="rounded-[1.35rem] border border-[rgba(17,28,45,0.08)] bg-white/82 px-5 py-4 transition-colors hover:border-[#8bd6b6] hover:bg-white"
                  href={entry.href}
                  key={entry.href}
                >
                  <p className="font-semibold text-[#111c2d]">{entry.title}</p>
                  <p className="mt-1 text-sm/6 text-[#57657a]">{entry.description}</p>
                </Link>
              ))}
            </div>
          </div>

          <aside className="space-y-4 rounded-[1.8rem] border border-[rgba(17,28,45,0.08)] bg-[rgba(240,243,255,0.7)] p-6">
            <div>
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
                Potencial de uso
              </p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                Da análise diária à estratégia
              </h2>
            </div>
            <p className="text-sm/7 text-[#57657a]">
              Use a plataforma para monitorar desempenho, antecipar narrativas, encontrar padrões de
              evolução e comparar cenários com precisão. Tudo em um ambiente pronto para apoiar
              decisões de negócio e de campo.
            </p>
            <Link
              className="button-pill button-pill-primary"
              href="/competitions"
            >
              Acessar plataforma
            </Link>
          </aside>
        </section>
      </div>
    </main>
  );
}
