import { useEffect, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuthStore, getApiBaseUrl } from '@/stores/auth-store';
import { LoginPage } from '@/features/auth/login-page';

function BootstrapError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-lg space-y-4 rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <div className="space-y-2">
            <h1 className="text-lg font-semibold">No se pudo conectar con la API</h1>
            <p className="text-sm text-muted-foreground">{message}</p>
            <p className="text-xs text-muted-foreground">
              URL configurada: <code className="rounded bg-muted px-1">{getApiBaseUrl()}</code>
            </p>
          </div>
        </div>
        <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Arranque recomendado</p>
          <ol className="mt-2 list-decimal space-y-1 pl-4">
            <li>Desde la raíz del repo: <code className="rounded bg-muted px-1">pnpm dev</code></li>
            <li>Comprueba <code className="rounded bg-muted px-1">/api/health</code> en el puerto 8000</li>
            <li>
              Si usas F5 en Cursor, elige <strong>Bolsa: F5 Dev (recomendado)</strong>, no la config
              legacy TS (:3001)
            </li>
          </ol>
        </div>
        <Button type="button" variant="outline" className="w-full" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Reintentar
        </Button>
      </div>
    </div>
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { token, authEnabled, isHydrated, bootstrapError, checkAuthRequired, setSession, clearBootstrapError } =
    useAuthStore();
  const [ready, setReady] = useState(false);
  const [bootAttempt, setBootAttempt] = useState(0);

  useEffect(() => {
    const fallback = setTimeout(() => {
      useAuthStore.getState().setHydrated();
    }, 2_000);
    return () => clearTimeout(fallback);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    clearBootstrapError();

    (async () => {
      try {
        const required = await checkAuthRequired();
        if (cancelled) return;
        if (!required) {
          setSession('', false);
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [bootAttempt, checkAuthRequired, setSession, clearBootstrapError]);

  if (!isHydrated || !ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }

  if (bootstrapError) {
    return (
      <BootstrapError
        message={bootstrapError}
        onRetry={() => {
          setBootAttempt((n) => n + 1);
        }}
      />
    );
  }

  if (authEnabled && !token) {
    return <LoginPage />;
  }

  return <>{children}</>;
}
