import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

export default function PlatformHomeLoading() {
  return (
    <PlatformStateSurface
      description="Estamos carregando a página inicial e os principais atalhos."
      kicker="Início"
      loading
      title="Preparando o início"
    />
  );
}
