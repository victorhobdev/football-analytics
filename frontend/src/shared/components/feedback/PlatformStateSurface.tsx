import Link from "next/link";
import type { ReactNode } from "react";

import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import { ProfilePanel, ProfileShell } from "@/shared/components/profile/ProfilePrimitives";

type PlatformStateSurfaceProps = {
  title: string;
  description: string;
  kicker?: string;
  tone?: "critical" | "warning" | "info";
  actionHref?: string;
  actionLabel?: string;
  secondaryAction?: ReactNode;
  detail?: ReactNode;
  loading?: boolean;
};

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

const STATE_BADGE_LABELS = {
  critical: "Recuperação",
  warning: "Transição",
  info: "Continuidade",
} as const;

const STATE_SUMMARY_TITLES = {
  critical: "Esta área saiu do fluxo esperado",
  warning: "Esta área ainda não entrou no fluxo principal",
  info: "A navegação principal continua disponível",
} as const;

const STATE_SUMMARY_DESCRIPTIONS = {
  critical: "Use os atalhos estáveis abaixo enquanto esta superfície é recuperada.",
  warning: "Os atalhos abaixo levam para as rotas mais próximas já integradas ao produto.",
  info: "Escolha o próximo caminho para retomar a exploração sem perder o enquadramento atual.",
} as const;

export function PlatformStateSurface({
  title,
  description,
  kicker = "Shell global",
  tone = "info",
  actionHref,
  actionLabel,
  secondaryAction = null,
  detail = null,
  loading = false,
}: PlatformStateSurfaceProps) {
  const contextPanelClasses =
    tone === "critical"
      ? "border-[#ffdad6] bg-[#fff1ef]"
      : tone === "warning"
        ? "border-[#ffdcc3] bg-[#fff3e8]"
        : "border-[rgba(191,201,195,0.55)] bg-white/82";

  const heroAsideClasses =
    tone === "critical"
      ? "border-white/12 bg-white/10 text-white"
      : tone === "warning"
        ? "border-[rgba(255,255,255,0.18)] bg-white/12 text-white"
        : "border-[rgba(255,255,255,0.2)] bg-white/10 text-white";

  const contextDescription = loading
    ? "Estamos montando os blocos desta página e preservando o enquadramento da navegação."
    : tone === "critical"
      ? "Esta superfície não conseguiu concluir a abertura. Os atalhos abaixo levam para caminhos estáveis do produto."
      : tone === "warning"
        ? "Esta superfície ainda não participa da experiência principal. Continue a exploração pelas áreas já consolidadas."
        : "A página continua dentro da mesma base visual e a navegação principal segue disponível.";

  return (
    <ProfileShell className="space-y-6">
      <ProfilePanel className="overflow-hidden" tone="accent">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(16rem,0.9fr)] lg:items-end">
          <header className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-white/16 bg-white/12 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-white/88">
                {kicker}
              </span>
              <span className="inline-flex items-center rounded-full border border-white/16 bg-[rgba(255,255,255,0.08)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-white/72">
                {loading ? "Preparando" : STATE_BADGE_LABELS[tone]}
              </span>
            </div>
            <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-4xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
              {title}
            </h1>
            <p className="max-w-3xl text-sm/6 text-white/78 md:text-[0.95rem]/7">{description}</p>
          </header>

          <aside
            className={joinClasses(
              "rounded-[1.45rem] border px-4 py-4 shadow-[0_24px_54px_-42px_rgba(2,12,9,0.55)] backdrop-blur-xl",
              heroAsideClasses,
            )}
          >
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-white/64">
              Continuidade do fluxo
            </p>
            <p className="mt-3 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.03em] text-white">
              {loading ? "Preparando a próxima etapa" : STATE_SUMMARY_TITLES[tone]}
            </p>
            <p className="mt-3 text-sm/6 text-white/74">
              {loading
                ? "A estrutura principal da página está sendo montada antes da renderização final."
                : STATE_SUMMARY_DESCRIPTIONS[tone]}
            </p>
          </aside>
        </div>
      </ProfilePanel>

      {loading ? (
        <section aria-label="Estado da página" className="grid gap-4">
          <ProfilePanel className="space-y-4" tone="soft">
            <LoadingSkeleton height={12} rounded="full" width="22%" />
            <LoadingSkeleton height={22} rounded="md" width="58%" />
            <LoadingSkeleton height={16} rounded="md" width="92%" />
            <LoadingSkeleton height={16} rounded="md" width="86%" />
          </ProfilePanel>
          <div className="grid gap-4 md:grid-cols-2">
            <ProfilePanel className="space-y-4" tone="soft">
              <LoadingSkeleton height={12} rounded="full" width="26%" />
              <LoadingSkeleton height={72} rounded="md" />
            </ProfilePanel>
            <ProfilePanel className="space-y-4" tone="soft">
              <LoadingSkeleton height={12} rounded="full" width="30%" />
              <LoadingSkeleton height={72} rounded="md" />
            </ProfilePanel>
          </div>
        </section>
      ) : (
        <section aria-label="Estado da página">
          <ProfilePanel className={joinClasses("space-y-3 border", contextPanelClasses)} tone="soft">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-[#57657a]">
              Contexto da página
            </p>
            <p className="text-sm/6 text-[#404944]">{contextDescription}</p>
            {detail ? <div className="text-sm/6 text-[#404944]">{detail}</div> : null}
          </ProfilePanel>
        </section>
      )}

      {!loading && (actionHref || secondaryAction) ? (
        <ProfilePanel className="flex flex-wrap items-center gap-3" tone="soft">
          {actionHref && actionLabel ? (
            <Link
              className="button-pill button-pill-primary"
              href={actionHref}
            >
              {actionLabel}
            </Link>
          ) : null}
          {secondaryAction}
        </ProfilePanel>
      ) : null}
    </ProfileShell>
  );
}
