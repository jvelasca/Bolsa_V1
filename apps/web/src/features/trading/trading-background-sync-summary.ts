/**
 * Resumen compacto de procesos en segundo plano (auto-sync OHLCV) para la barra Trading.
 */

import type { SyncQueueItemDto, SyncSettingsDto } from '@bolsa/shared';

export type BackgroundSyncTone = 'off' | 'idle' | 'active' | 'warn';

export type BackgroundSyncSummary = {
  label: string;
  detail: string;
  tone: BackgroundSyncTone;
};

function scopeLabel(scope: string): string {
  if (scope === 'lists') return 'solo listas';
  if (scope === 'all') return 'toda la BD';
  return scope;
}

export function summarizeBackgroundSync(opts: {
  settings: SyncSettingsDto | null | undefined;
  queue: SyncQueueItemDto[] | null | undefined;
  loading?: boolean;
}): BackgroundSyncSummary {
  if (opts.loading && !opts.settings) {
    return {
      label: 'Velas · …',
      detail: 'Consultando cola de sincronización…',
      tone: 'idle',
    };
  }
  const settings = opts.settings;
  const queue = opts.queue ?? [];
  if (!settings) {
    return {
      label: 'Velas · —',
      detail: 'Sin datos de auto-sync',
      tone: 'off',
    };
  }
  if (!settings.autoSyncEnabled) {
    return {
      label: 'Velas · off',
      detail: `Auto-sync desactivado · ámbito ${scopeLabel(settings.scope)}. Actívalo en Configuración → Sincronización.`,
      tone: 'off',
    };
  }
  const pending = queue.filter((i) => i.status === 'pending');
  const processing = queue.filter((i) => i.status === 'processing');
  const failed = queue.filter((i) => i.status === 'failed');
  const current = processing[0] ?? pending[0];
  const baseDetail = [
    `Auto-sync activo · ámbito ${scopeLabel(settings.scope)}`,
    `escaneo cada ${settings.scanIntervalMinutes} min`,
    `pausa ${settings.minDelaySeconds}s entre valores`,
    settings.postMarketOnly ? 'solo post-mercado' : null,
  ]
    .filter(Boolean)
    .join(' · ');
  if (processing.length > 0 || pending.length > 0) {
    const n = processing.length + pending.length;
    const sym = current?.symbol ? current.symbol.slice(0, 6) : '';
    return {
      // Labels cortos + truncado en slot fijo (barra no redimensiona).
      label:
        processing.length > 0
          ? sym
            ? `Velas · ${sym}`
            : 'Velas · sync'
          : `Velas · ${n}`,
      detail: [
        baseDetail,
        processing.length ? `${processing.length} procesando` : null,
        pending.length ? `${pending.length} en cola` : null,
        failed.length ? `${failed.length} con error (reintento)` : null,
        current?.symbol
          ? `siguiente/actual: ${current.symbol}`
          : null,
      ]
        .filter(Boolean)
        .join('\n'),
      tone: 'active',
    };
  }
  if (failed.length > 0) {
    return {
      label: `Velas · ${Math.min(failed.length, 99)} err`,
      detail: `${baseDetail}\n${failed.length} ítem(s) fallidos pendientes de reintento`,
      tone: 'warn',
    };
  }
  return {
    label: 'Velas · ok',
    detail: `${baseDetail}\nCola vacía: sin valores pendientes de actualizar.`,
    tone: 'idle',
  };
}
