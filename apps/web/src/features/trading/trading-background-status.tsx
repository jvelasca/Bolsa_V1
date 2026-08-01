/**
 * Indicador derecha de la barra Trading: auto-sync OHLCV en segundo plano.
 */

import { useQuery } from '@tanstack/react-query';

import { RefreshCw } from 'lucide-react';

import { api } from '@/lib/api';

import { useUiStore } from '@/stores/ui-store';

import { cn } from '@/lib/utils';

import {
  summarizeBackgroundSync,
  type BackgroundSyncTone,
} from '@/features/trading/trading-background-sync-summary';

function toneDotClass(tone: BackgroundSyncTone): string {
  if (tone === 'active') return 'animate-pulse bg-sky-500';
  if (tone === 'warn') return 'bg-amber-500';
  if (tone === 'off') return 'bg-muted-foreground/40';
  return 'bg-emerald-500/80';
}

export function TradingBackgroundStatus() {
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);
  const settingsQuery = useQuery({
    queryKey: ['sync-settings'],
    queryFn: async () => (await api.getSyncSettings()).data,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  const queueQuery = useQuery({
    queryKey: ['sync-queue'],
    queryFn: async () => (await api.getSyncQueue()).data,
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      const busy = data.some((i) => i.status === 'pending' || i.status === 'processing');
      return busy ? 8_000 : 30_000;
    },
  });
  const summary = summarizeBackgroundSync({
    settings: settingsQuery.data,
    queue: queueQuery.data,
    loading: settingsQuery.isLoading || queueQuery.isLoading,
  });
  return (
    <button
      type="button"
      className={cn(
        'flex max-w-[min(14rem,32vw)] items-center gap-1 truncate rounded px-1 py-0.5 text-left hover:bg-accent',
        summary.tone === 'active' && 'text-sky-800 dark:text-sky-200',
        summary.tone === 'warn' && 'text-amber-800 dark:text-amber-200',
      )}
      title={`${summary.detail}\n\nClic → Configuración de sincronización`}
      onClick={() => openPlatformConfig('other')}
    >
      <RefreshCw
        className={cn(
          'h-3 w-3 shrink-0 opacity-80',
          summary.tone === 'active' && 'animate-spin',
        )}
        aria-hidden
      />
      <span
        className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-full', toneDotClass(summary.tone))}
        aria-hidden
      />
      <span className="truncate tabular-nums font-medium text-foreground">{summary.label}</span>
    </button>
  );
}