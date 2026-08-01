import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export function SyncSettingsPanel({ embedded = false }: { embedded?: boolean }) {
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: ['sync-settings'],
    queryFn: async () => (await api.getSyncSettings()).data,
  });

  const queueQuery = useQuery({
    queryKey: ['sync-queue'],
    queryFn: async () => (await api.getSyncQueue()).data,
    refetchInterval: 30_000,
  });

  const updateMutation = useMutation({
    mutationFn: (patch: Parameters<typeof api.updateSyncSettings>[0]) => api.updateSyncSettings(patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['sync-settings'] });
      void queryClient.invalidateQueries({ queryKey: ['sync-queue'] });
    },
  });

  const enqueueMutation = useMutation({
    mutationFn: () => api.enqueueStaleInstruments(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['sync-queue'] }),
  });

  const settings = settingsQuery.data;
  const queue = queueQuery.data ?? [];
  const pendingCount = queue.filter((item) => item.status === 'pending').length;

  if (!settings) {
    const loading = (
      <p className="text-sm text-muted-foreground">Cargando configuración…</p>
    );
    if (embedded) return loading;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Actualización automática</CardTitle>
        </CardHeader>
        <CardContent>{loading}</CardContent>
      </Card>
    );
  }

  const body = (
    <>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={settings.autoSyncEnabled}
          onChange={(e) =>
            updateMutation.mutate({ autoSyncEnabled: e.target.checked })
          }
        />
        Activar auto-actualización en segundo plano
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Escanear cada (min)</span>
          <input
            type="number"
            min={5}
            max={1440}
            className="rounded border border-border bg-background px-2 py-1"
            value={settings.scanIntervalMinutes}
            onChange={(e) =>
              updateMutation.mutate({ scanIntervalMinutes: Number(e.target.value) })
            }
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Pausa entre peticiones (s)</span>
          <input
            type="number"
            min={1}
            max={120}
            className="rounded border border-border bg-background px-2 py-1"
            value={settings.minDelaySeconds}
            onChange={(e) =>
              updateMutation.mutate({ minDelaySeconds: Number(e.target.value) })
            }
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Reintentos máx.</span>
          <input
            type="number"
            min={1}
            max={20}
            className="rounded border border-border bg-background px-2 py-1"
            value={settings.maxRetries}
            onChange={(e) => updateMutation.mutate({ maxRetries: Number(e.target.value) })}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Backoff reintentos (min)</span>
          <input
            type="number"
            min={5}
            max={1440}
            className="rounded border border-border bg-background px-2 py-1"
            value={settings.retryBackoffMinutes}
            onChange={(e) =>
              updateMutation.mutate({ retryBackoffMinutes: Number(e.target.value) })
            }
          />
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-muted-foreground">Universo a mantener fresco</span>
        <select
          className="rounded border border-border bg-background px-2 py-1"
          value={settings.scope === 'all' ? 'stale' : settings.scope}
          onChange={(e) => updateMutation.mutate({ scope: e.target.value })}
        >
          <option value="lists">Solo valores en listas (recomendado / defecto)</option>
          <option value="stale">Todos los instrumentos activos desfasados</option>
        </select>
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={settings.postMarketOnly}
          onChange={(e) => updateMutation.mutate({ postMarketOnly: e.target.checked })}
        />
        Solo procesar cola tras cierre de mercado (17:35 Madrid)
      </label>

      <p className="text-xs text-muted-foreground">
        Por defecto solo se encolan valores que estánén en alguna lista (universo de rastreadores). El worker
        procesa ~1 valor cada 15 s + la pausa entre peticiones, y Yahoo lleva su propio throttle — no satura
        el proveedor. Si falla un sync, el ítem reintenta con backoff. XTB no escribe histórico; solo cotización
        live / validación.
      </p>

      <button
        type="button"
        disabled={enqueueMutation.isPending}
        className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent"
        onClick={() => void enqueueMutation.mutateAsync()}
      >
        <RefreshCw className={cn('h-4 w-4', enqueueMutation.isPending && 'animate-spin')} />
        Encolar valores desactualizados ahora
      </button>

      {queue.length > 0 && (
        <div className="max-h-48 overflow-auto rounded border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-left">
              <tr>
                <th className="px-2 py-1">Símbolo</th>
                <th className="px-2 py-1">Estado</th>
                <th className="px-2 py-1">Intentos</th>
                <th className="hidden px-2 py-1 sm:table-cell">Programado</th>
              </tr>
            </thead>
            <tbody>
              {queue.slice(0, 30).map((item) => (
                <tr key={item.id} className="border-t border-border">
                  <td className="px-2 py-1">{item.symbol}</td>
                  <td className="px-2 py-1">{item.status}</td>
                  <td className="px-2 py-1">{item.attempts}</td>
                  <td className="hidden px-2 py-1 sm:table-cell">
                    {new Date(item.scheduledAt).toLocaleString('es-ES')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  if (embedded) {
    return <div className="space-y-4 text-sm">{body}</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actualización automática de datos</CardTitle>
        <CardDescription>
          Cola con reintentos espaciados para evitar límites de Yahoo. {pendingCount} en cola.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">{body}</CardContent>
    </Card>
  );
}
