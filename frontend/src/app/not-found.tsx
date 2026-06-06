import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

export default function RootNotFound() {
  return (
    <PlatformStateSurface
      actionHref="/"
      actionLabel="Voltar ao início"
      description="Este endereço não está disponível na aplicação."
      detail="Retome a navegação pelo início ou por uma das áreas principais."
      kicker="Aplicação"
      secondaryAction={
        <>
          <Link
            className="button-pill button-pill-secondary"
            href="/competitions"
          >
            Abrir competições
          </Link>
        </>
      }
      title="Página não encontrada"
      tone="warning"
    />
  );
}
