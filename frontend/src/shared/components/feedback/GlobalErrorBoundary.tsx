"use client";

import { Component, type ReactNode } from "react";

import Link from "next/link";

import { PlatformStateSurface } from "@/shared/components/feedback/PlatformStateSurface";

type GlobalErrorBoundaryProps = {
  children: ReactNode;
};

type GlobalErrorBoundaryState = {
  hasError: boolean;
};

export class GlobalErrorBoundary extends Component<
  GlobalErrorBoundaryProps,
  GlobalErrorBoundaryState
> {
  public constructor(props: GlobalErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  public static getDerivedStateFromError(): GlobalErrorBoundaryState {
    return { hasError: true };
  }

  private readonly handleReset = (): void => {
    this.setState({ hasError: false });
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <PlatformStateSurface
          actionHref="/"
          actionLabel="Voltar ao início"
          description="Encontramos um problema inesperado nesta área. Use um dos atalhos para continuar pela navegação estável."
          detail="A falha ficou restrita a esta renderização. Você pode tentar novamente ou seguir para uma área consolidada do produto."
          kicker="Aplicação"
          secondaryAction={
            <>
              <button
                className="button-pill button-pill-primary"
                onClick={this.handleReset}
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
          title="Ocorreu um erro inesperado"
          tone="critical"
        />
      );
    }

    return this.props.children;
  }
}
