import Link from "next/link";

const PRODUCT_PILLARS = [
  {
    title: "Temporadas canônicas",
    description:
      "Competição, temporada, rankings, tabela e calendário operam como a espinha dorsal do produto.",
  },
  {
    title: "Profundidade por partida",
    description:
      "Central da partida, escalações, linha do tempo e estatísticas dão continuidade operacional sem quebrar o recorte.",
  },
  {
    title: "Perfis contextuais",
    description:
      "Times e jogadores já navegam dentro de um contexto de temporada consistente, com links profundos e descoberta real.",
  },
] as const;

const PRODUCT_ENTRIES = [
  {
    href: "/",
    title: "Página inicial executiva",
    description:
      "Entrada operacional do produto para abrir competições, rankings, times e jogadores.",
  },
  {
    href: "/competitions",
    title: "Competições",
    description: "Catálogo principal do acervo e ponto de entrada para hubs de temporada.",
  },
  {
    href: "/teams",
    title: "Times",
    description: "Descoberta e aprofundamento em perfis contextuais de time.",
  },
  {
    href: "/players",
    title: "Jogadores",
    description: "Exploração individual, comparação e entrada para perfis canônicos.",
  },
  {
    href: "/rankings",
    title: "Rankings",
    description: "Família viva de rankings com entrada pública clara no produto atual.",
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
              Plataforma editorial e analítica
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link
              className="button-pill button-pill-secondary"
              href="/competitions"
            >
              Explorar acervo
            </Link>
            <Link
              className="button-pill button-pill-primary"
              href="/"
            >
              Abrir página inicial
            </Link>
          </div>
        </header>

        <section className="grid gap-8 py-12 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)] lg:py-16">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-[rgba(216,227,251,0.78)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#404944]">
                Página institucional
              </span>
              <span className="inline-flex items-center rounded-full bg-[rgba(139,214,182,0.22)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[#00513b]">
                Papel editorial
              </span>
            </div>

            <div className="space-y-4">
              <h2 className="font-[family:var(--font-profile-headline)] text-5xl font-extrabold tracking-[-0.06em] text-[#003526] md:text-6xl">
                Um produto de exploração futebolística com arquitetura de temporada, não um mosaico
                de telas.
              </h2>
              <p className="max-w-3xl text-base/8 text-[#57657a] md:text-[1.05rem]/8">
                Esta página apresenta o produto, deixa explícito seu papel institucional e aponta
                para as entradas operacionais certas. A exploração diária continua na página
                inicial, no catálogo de competições, na central da partida e nos perfis contextuais.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="button-pill button-pill-primary"
                href="/"
              >
                Entrar no produto
              </Link>
              <Link
                className="button-pill button-pill-secondary"
                href="/competitions"
              >
                Ver competições
              </Link>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-[rgba(17,28,45,0.08)] bg-[linear-gradient(135deg,#082319_0%,#0d3b2b_58%,#14543e_100%)] p-6 text-white shadow-[0_32px_80px_-56px_rgba(0,53,38,0.8)]">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-white/62">
              Papel desta página
            </p>
            <h3 className="mt-4 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em]">
              Institucional por fora, operacional por dentro
            </h3>
            <p className="mt-4 text-sm/7 text-white/78">
              A página organiza narrativa, posicionamento e portas de entrada. Ela não duplica a
              página inicial nem tenta substituir a navegação principal do produto em operação.
            </p>

            <div className="mt-6 grid gap-3">
              <div className="rounded-[1.3rem] border border-white/10 bg-white/10 px-4 py-4">
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-white/62">Página institucional</p>
                <p className="mt-2 text-sm/6 text-white/82">
                  Explica o produto, sintetiza sua proposta e envia para a entrada correta.
                </p>
              </div>
              <div className="rounded-[1.3rem] border border-white/10 bg-white/10 px-4 py-4">
                <p className="text-[0.72rem] uppercase tracking-[0.16em] text-white/62">
                  Página inicial executiva
                </p>
                <p className="mt-2 text-sm/6 text-white/82">
                  Funciona como painel operacional para acervo, recortes e descoberta analítica.
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
                Pilar
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
                Entradas do produto
              </p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                Rotas públicas que já definem a experiência real
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
                Arquitetura pública
              </p>
              <h2 className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold tracking-[-0.04em] text-[#111c2d]">
                A narrativa aponta para o núcleo vivo
              </h2>
            </div>
            <p className="text-sm/7 text-[#57657a]">
              A página institucional não apresenta aliases legados como destino principal e não desloca a
              navegação pública para rotas secundárias ainda em transição. O produto principal
              continua organizado em competições, rankings, times e jogadores, com partidas abertas
              dentro dos contextos de competição e temporada.
            </p>
            <Link
              className="button-pill button-pill-primary"
              href="/competitions"
            >
              Começar por competições
            </Link>
          </aside>
        </section>
      </div>
    </main>
  );
}
