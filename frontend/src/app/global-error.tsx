"use client";

import { useEffect } from "react";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-[linear-gradient(180deg,#eff4ee_0%,#f6f8fb_48%,#eef4ef_100%)] p-4 text-[#111c2d] md:p-6">
        <PlatformStateSurface
          actionHref="/"
          actionLabel="Voltar ao início"
          description="Encontramos um problema ao abrir a aplicação. Tente novamente ou retome por uma área estável."
          detail="A falha aconteceu antes da renderização completa. Reabrir o início ou as competições costuma ser o caminho mais seguro."
          kicker="Aplicação"
          secondaryAction={
            <>
              <button
                className="button-pill button-pill-primary"
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
          title="Não foi possível abrir a aplicação"
          tone="critical"
        />
      </body>
    </html>
  );
}
