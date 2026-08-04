/**
 * Barra de estado Trading: cuenta Activa + métricas (izq.) · rail fijo Colas/Alarmas (der.).
 *
 * Derecha no redimensiona: slots Velas · CORE-R · F3 · Lista AUTO + badge alarmas 2 dígitos.
 */

import { Settings2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { resolveApiBaseUrl } from '@/lib/api-base-url';
import { formatPrice } from '@/features/charts/chart-utils';
import { IconButton } from '@/components/ui/icon-button';
import { cn } from '@/lib/utils';
import { Dialog } from '@/components/ui/dialog';
import { AccountScopeSelector } from '@/features/accounts/account-scope-selector';
import {
  accountTypeShortLabel,
  useActiveAccount,
} from '@/features/accounts/use-active-account';
import { TradingAppThreads } from '@/features/trading/trading-app-threads';
import { TradingAlarmInboxButton } from '@/features/trading/trading-alarm-inbox-button';

type StatusItemId = 'equity' | 'cash' | 'marketValue' | 'pnl' | 'positions';

const STATUS_LABELS: Record<StatusItemId, string> = {
  equity: 'Patrimonio',
  cash: 'Capital disponible',
  marketValue: 'Valor operaciones',
  pnl: 'Beneficio',
  positions: 'Posiciones',
};

const STATUS_LABELS_SHORT: Record<StatusItemId, string> = {
  equity: 'Pat.',
  cash: 'Disp.',
  marketValue: 'Ops.',
  pnl: 'P&L',
  positions: 'Pos.',
};

const DEFAULT_ITEMS: StatusItemId[] = ['marketValue', 'cash', 'pnl', 'equity'];

function StatusSeparator() {
  return (
    <span
      aria-hidden
      className="mx-0.5 h-3.5 w-px shrink-0 bg-border"
    />
  );
}

function connectionLabel(): string {
  if (typeof window === 'undefined') return 'local';
  const host = window.location.hostname;
  const port = window.location.port;
  const apiBase = resolveApiBaseUrl();
  const web = port ? `${host}:${port}` : host;
  if (!apiBase) return `${web} · API proxy`;
  try {
    const apiHost = new URL(apiBase).host;
    return apiHost === web || apiHost.startsWith('localhost')
      ? web
      : `${web} → ${apiHost}`;
  } catch {
    return web;
  }
}

export function TradingStatusBar() {
  const [configOpen, setConfigOpen] = useState(false);
  const [visibleItems, setVisibleItems] = useState<StatusItemId[]>(DEFAULT_ITEMS);
  const { account, effectiveAccountId } = useActiveAccount();
  const endpointLabel = useMemo(() => connectionLabel(), []);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30_000,
    retry: 1,
  });

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', effectiveAccountId],
    queryFn: api.getPortfolio,
    enabled: Boolean(effectiveAccountId),
    refetchInterval: 60_000,
  });

  const summary = portfolioQuery.data?.data;
  const apiOk = healthQuery.isSuccess && !healthQuery.isError;

  const values: Record<StatusItemId, string> = {
    equity: summary ? formatPrice(summary.totalEquity) : '—',
    cash: summary ? formatPrice(summary.portfolio.cash) : '—',
    marketValue: summary ? formatPrice(summary.totalMarketValue) : '—',
    pnl: summary ? formatPrice(summary.totalUnrealizedPnl) : '—',
    positions: summary ? String(summary.positions.length) : '—',
  };

  return (
    <>
      <footer className="scroll-area flex h-7 shrink-0 items-center gap-1.5 overflow-x-auto border-t border-border bg-card/90 px-2 text-[10px] text-muted-foreground">
        {/* Izquierda: sistema + cuenta + métricas (puede truncar/scroll) */}
        <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto">
          <span
            className="flex shrink-0 items-center gap-1.5 whitespace-nowrap"
            title={apiOk ? 'API conectada' : 'API no responde'}
          >
            <span
              className={cn(
                'inline-block h-1.5 w-1.5 rounded-full',
                apiOk ? 'bg-emerald-500' : healthQuery.isLoading ? 'bg-amber-400' : 'bg-red-500',
              )}
            />
            <span className="tabular-nums text-muted-foreground/90">{endpointLabel}</span>
          </span>

          <StatusSeparator />

          <div className="flex min-w-0 shrink-0 items-center gap-1.5">
            <span className="shrink-0 uppercase tracking-wide text-muted-foreground/70">Activa</span>
            {account ? (
              <>
                <span
                  className="max-w-[10rem] truncate font-medium text-foreground sm:max-w-[14rem]"
                  title={`${account.name} · ${accountTypeShortLabel(account.type)} · ${account.currency}`}
                >
                  {account.name}
                </span>
                <span className="shrink-0 rounded border border-border/80 px-1 text-[9px] uppercase tracking-wide text-muted-foreground">
                  {accountTypeShortLabel(account.type)}
                </span>
                <span className="hidden shrink-0 text-muted-foreground/60 sm:inline">
                  {account.currency}
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">Sin cuenta</span>
            )}
            <AccountScopeSelector compact hideLabel className="ml-0.5" />
          </div>

          <StatusSeparator />

          {visibleItems.map((id) => (
            <span key={id} className="flex shrink-0 items-center gap-1 whitespace-nowrap">
              <span className="text-muted-foreground/80">
                <span className="trading-status-label-full">{STATUS_LABELS[id]}:</span>
                <span className="trading-status-label-short">{STATUS_LABELS_SHORT[id]}:</span>
              </span>
              <span
                className={cn(
                  'font-medium tabular-nums text-foreground',
                  id === 'pnl' &&
                    summary &&
                    (summary.totalUnrealizedPnl >= 0 ? 'text-emerald-400' : 'text-red-400'),
                )}
              >
                {values[id]}
              </span>
            </span>
          ))}
        </div>

        {/* Derecha: rail fijo Colas + Alarmas + ajustes (no redimensiona con conteos) */}
        <div
          className="ml-1 flex shrink-0 items-center gap-1 border-l border-border/70 pl-1.5"
          data-testid="trading-status-rail"
        >
          <TradingAppThreads />
          <TradingAlarmInboxButton />
          <IconButton
            icon={Settings2}
            title="Configurar barra de estado"
            onClick={() => setConfigOpen(true)}
          />
        </div>
      </footer>

      <Dialog
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        title="Barra de estado"
        description="Indicadores del resumen de la cuenta Activa (izquierda). Derecha: colas fijas + alarmas Radar."
        className="max-w-md"
      >
        <div className="space-y-2">
          {(Object.keys(STATUS_LABELS) as StatusItemId[]).map((id) => (
            <label key={id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={visibleItems.includes(id)}
                onChange={(e) => {
                  setVisibleItems((prev) =>
                    e.target.checked ? [...prev, id] : prev.filter((item) => item !== id),
                  );
                }}
                className="h-3.5 w-3.5 accent-primary"
              />
              {STATUS_LABELS[id]}
            </label>
          ))}
          <p className="pt-2 text-[11px] leading-snug text-muted-foreground">
            La zona derecha reserva espacio fijo para Colas (Velas · CORE-R · F3 · Lista AUTO) y el
            panel de Alarmas Radar (nº sin leer), para que la barra no salte al cambiar conteos.
          </p>
        </div>
      </Dialog>
    </>
  );
}
