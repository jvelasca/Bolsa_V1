import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * OR-Obs — atrapa errores de render en el shell autenticado.
 * AuthGate queda fuera para no perder el flujo de login.
 */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[AppErrorBoundary]', error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div
          role="alert"
          style={{
            minHeight: '100vh',
            display: 'grid',
            placeContent: 'center',
            gap: '0.75rem',
            padding: '2rem',
            fontFamily: 'Georgia, "Times New Roman", serif',
            background: 'linear-gradient(160deg, #0f1419 0%, #1a2332 55%, #0f1419 100%)',
            color: '#e8eef5',
          }}
        >
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>Algo falló en la interfaz</h1>
          <p style={{ margin: 0, maxWidth: '28rem', opacity: 0.85, fontFamily: 'ui-sans-serif, system-ui' }}>
            {this.state.error.message || 'Error inesperado'}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            style={{
              justifySelf: 'start',
              marginTop: '0.5rem',
              padding: '0.5rem 1rem',
              border: '1px solid #6b8499',
              background: '#243447',
              color: '#e8eef5',
              cursor: 'pointer',
              fontFamily: 'ui-sans-serif, system-ui',
            }}
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
