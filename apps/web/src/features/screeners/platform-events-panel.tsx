import { useQuery } from '@tanstack/react-query';
import { Activity } from 'lucide-react';
import type { PlatformEventType } from '@bolsa/shared';
import { api } from '@/lib/api';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';

const EVENT_LABELS: Record<PlatformEventType, string> = {
  'signal.emitted': 'Señal',
  'scan.completed': 'Rastreo',
  'backtest.completed': 'Backtest',
  'execution.order_requested': 'Orden solicitada',
  'execution.order_filled': 'Orden ejecutada',
};

function formatPayloadSummary(type: PlatformEventType, payload: Record<string, unknown>): string {
  if (type === 'scan.completed') {
    return `${payload.hitCount ?? 0} coincidencias / ${payload.scannedCount ?? 0} escaneados`;
  }
  if (type === 'signal.emitted') {
    return `${String(payload.kind ?? '?')} · ${String(payload.instrumentId ?? '').slice(0, 8)}`;
  }
  if (type.startsWith('execution.')) {
    return `${payload.tradeType ?? '?'} · ${String(payload.instrumentId ?? '').slice(0, 8)}`;
  }
  return JSON.stringify(payload).slice(0, 60);
}

export function PlatformEventsPanel({ embedded }: { embedded?: boolean } = {}) {
  const eventsQuery = useQuery({
    queryKey: ['platform-events'],
    queryFn: () => api.getPlatformEvents({ limit: 25 }),
    refetchInterval: 8000,
  });

  const events = eventsQuery.data?.data ?? [];

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Bus de eventos"
      description={
        embedded
          ? undefined
          : 'Registro de auditoría — rastreos, señales y ejecución (platform_events).'
      }
      icon={Activity}
    >
        {eventsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Cargando eventos…</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sin eventos aún. Ejecuta un rastreo o una política para ver actividad.
          </p>
        ) : (
          <ul className="max-h-48 space-y-1.5 overflow-y-auto text-xs">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded border border-border px-2 py-1.5"
              >
                <span className="font-medium">
                  {EVENT_LABELS[event.type as PlatformEventType] ?? event.type}
                </span>
                <span className="text-muted-foreground">
                  {new Date(event.timestamp).toLocaleTimeString('es-ES')}
                </span>
                <span className="w-full text-muted-foreground">
                  {formatPayloadSummary(event.type as PlatformEventType, event.payload)}
                </span>
              </li>
            ))}
          </ul>
        )}
    </ScreenerPanelShell>
  );
}
