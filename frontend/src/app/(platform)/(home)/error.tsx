"use client";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

type PlatformHomeErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function PlatformHomeError({ reset }: PlatformHomeErrorProps) {
  return (
    <PlatformStateSurface
      actionHref="/"
      actionLabel="Voltar ao início"
      description="Não foi possível carregar a visão inicial agora. Tente novamente ou siga por outra área já estável do produto."
      detail="A falha ficou restrita à abertura da página inicial. O restante da navegação principal continua disponível."
      kicker="Início"
      secondaryAction={
        <>
          <button
            className="button-pill button-pill-secondary"
            onClick={reset}
            type="button"
          >
            Tentar novamente
          </button>
          <Link
            className="button-pill button-pill-secondary"
            href="/competitions"
          >
            Abrir competições
          </Link>
        </>
      }
      title="Não foi possível carregar o início"
      tone="critical"
    />
  );
}
