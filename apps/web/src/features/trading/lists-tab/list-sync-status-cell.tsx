import { AlertTriangle, Check, Minus, RefreshCw, X } from 'lucide-react';
import type { InstrumentWithMetaDto, ListDataFreshnessStatus } from '@bolsa/shared';
import { cn } from '@/lib/utils';

type SyncVisualState = 'current' | 'stale' | 'empty' | 'error' | 'partial';

function resolveFreshness(item: InstrumentWithMetaDto): ListDataFreshnessStatus {
  if (item.meta.freshnessStatus) return item.meta.freshnessStatus;
  if (item.meta.barCount <= 0) return 'empty';
  const status = item.meta.lastSync?.status;
  if (status === 'failed') return 'error';
  if (status === 'partial') return 'stale';
  if (status === 'success' || item.meta.barCount > 0) return 'current';
  return 'empty';
}

function resolveVisualState(item: InstrumentWithMetaDto): SyncVisualState {
  const freshness = resolveFreshness(item);
  if (freshness === 'current' && item.meta.lastSync?.status === 'partial') return 'partial';
  return freshness;
}

function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatSyncAt(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildTooltip(item: InstrumentWithMetaDto, state: SyncVisualState): string {
  const lines = [
    state === 'current'
      ? 'Histórico diario al día'
      : state === 'stale'
        ? 'Histórico desfasado — en cola o pendiente de sync'
        : state === 'empty'
          ? 'Sin velas diarias en BD'
          : state === 'error'
            ? 'Error de sincronización'
            : 'Sincronización parcial',
    `Última vela: ${formatShortDate(item.meta.lastBarDate)}`,
    `Esperada: ${formatShortDate(item.meta.expectedLastBarDate)}`,
    `Barras 1D: ${item.meta.barCount.toLocaleString('es-ES')}`,
    `Último sync: ${formatSyncAt(item.meta.lastSync?.syncedAt)} (${item.meta.lastSync?.status ?? '—'})`,
  ];
  if (item.meta.lastSync?.error) {
    lines.push(item.meta.lastSync.error);
  }
  return lines.join('\n');
}

type ListSyncStatusCellProps = {
  item: InstrumentWithMetaDto;
  className?: string;
};

/**
 * Icono Sincro: solo histórico de velas diarias (OHLCV).
 * Capas Lab/CORE-R → columna «Procesos» (`ListProcessStatusCell`).
 */
export function ListSyncStatusCell({ item, className }: ListSyncStatusCellProps) {
  const state = resolveVisualState(item);
  const title = buildTooltip(item, state);

  if (state === 'current') {
    return (
      <span className={cn('inline-flex justify-center', className)} title={title}>
        <Check className="h-3.5 w-3.5 text-emerald-500" strokeWidth={2.5} aria-label="Datos al día" />
      </span>
    );
  }

  if (state === 'error') {
    return (
      <span className={cn('inline-flex justify-center', className)} title={title}>
        <X className="h-3.5 w-3.5 text-red-500" strokeWidth={2.5} aria-label="Error de sincronización" />
      </span>
    );
  }

  if (state === 'stale' || state === 'partial') {
    return (
      <span className={cn('inline-flex justify-center', className)} title={title}>
        <RefreshCw
          className={cn(
            'h-3.5 w-3.5',
            state === 'partial' ? 'text-amber-500' : 'text-sky-400',
          )}
          strokeWidth={2.5}
          aria-label={state === 'partial' ? 'Sincronización parcial' : 'Datos desfasados'}
        />
      </span>
    );
  }

  if (state === 'empty') {
    return (
      <span className={cn('inline-flex justify-center', className)} title={title}>
        <Minus className="h-3.5 w-3.5 text-muted-foreground/60" strokeWidth={2.5} aria-label="Sin datos" />
      </span>
    );
  }

  return (
    <span className={cn('inline-flex justify-center', className)} title={title}>
      <AlertTriangle className="h-3.5 w-3.5 text-amber-500" strokeWidth={2.5} aria-label="Revisar datos" />
    </span>
  );
}
