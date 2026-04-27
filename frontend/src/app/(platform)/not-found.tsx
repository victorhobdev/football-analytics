import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

export default function PlatformNotFound() {
  return (
    <PlatformStateSurface
      actionHref="/"
      actionLabel="Voltar ao início"
      description="Esse caminho não existe ou não está disponível com os filtros atuais."
      detail="Confira o endereço ou retome a navegação pelas áreas principais."
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
      title="Área não encontrada"
      tone="warning"
    />
  );
}
