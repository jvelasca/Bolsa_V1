import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  featureName: string;
  fallbackMessage?: string;
};

type State = { error: Error | null };

/**
 * V1.16 — boundary por feature crítica (Mesa, Confirm, F3).
 * No tumba el shell completo; las posiciones siguen intactas en backend.
 */
export class FeatureErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(
      `[FeatureErrorBoundary:${this.props.featureName}]`,
      error,
      info.componentStack,
    );
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-6 text-sm"
          data-testid={`feature-error-${this.props.featureName}`}
        >
          <p className="font-semibold text-rose-900 dark:text-rose-100">
            No se pudo mostrar {this.props.featureName}
          </p>
          <p className="mt-2 text-muted-foreground">
            {this.props.fallbackMessage ??
              "Tus posiciones y el libro siguen intactos. Recarga la página o vuelve más tarde."}
          </p>
          <button
            type="button"
            className="mt-3 rounded border border-border px-3 py-1.5 text-xs hover:bg-accent"
            onClick={() => this.setState({ error: null })}
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
