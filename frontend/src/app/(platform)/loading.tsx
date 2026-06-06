import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

export default function PlatformLoading() {
  return (
    <PlatformStateSurface
      description="Estamos abrindo a próxima página e preservando seus filtros."
      loading
      title="Preparando a próxima área"
    />
  );
}
