"use client";

import { useEffect } from "react";
import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

type PlatformErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function PlatformError({ error, reset }: PlatformErrorProps) {
  useEffect(() => {
    // TODO: integrar com tracking central de erro.
    console.error(error);
  }, [error]);

  return (
    <PlatformStateSurface
      actionHref="/"
      actionLabel="Voltar ao início"
      description="Não foi possível abrir esta área agora. Tente novamente ou siga para uma página principal."
      detail="O problema ficou restrito a esta página. Os atalhos principais seguem disponíveis."
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
      title="Não foi possível abrir esta área"
      tone="critical"
    />
  );
}
