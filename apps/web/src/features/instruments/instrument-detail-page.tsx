import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Bell, RefreshCw, Settings2 } from 'lucide-react';
import { DEFAULT_CHART_CONFIG } from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, inputClassName } from '@/components/ui/dialog';
import { useActiveAccountSettings } from '@/features/accounts/use-active-account';
import { InstrumentStrategyTopPanel } from '@/features/backtests/instrument-strategy-top-panel';
import { OhlcvChart } from '@/features/charts/ohlcv-chart';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { TradeConfirmPanel } from '@/features/trading/trade-confirm-panel';
import { TradeFeeBreakdown } from '@/features/trading/trade-fee-breakdown';
import { useTradeNotional } from '@/features/trading/use-trade-notional';
import { cn } from '@/lib/utils';
import { invalidateInstrumentMarketData } from '@/lib/query-invalidation';
import { useTradePreferencesStore } from '@/stores/trade-preferences-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function InstrumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tradeQty, setTradeQty] = useState('10');
  const [pendingSide, setPendingSide] = useState<'buy' | 'sell' | null>(null);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const confirmBeforeTrade = useTradePreferencesStore((s) => s.confirmBeforeTrade);
  const { settings, currency: accountCurrency, accountName } = useActiveAccountSettings();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const openChartInspector = useWorkspaceStore((s) => s.openChartInspector);

  const instrumentQuery = useQuery({
    queryKey: ['instrument', id],
    queryFn: () => api.getInstrument(id!),
    enabled: Boolean(id),
  });

  const instrument = instrumentQuery.data?.data;
  const summary = instrumentQuery.data?.meta.priceSummary;
  const lastSync = instrumentQuery.data?.meta.lastSync;
  const lastPrice = summary?.lastClose ?? 0;
  const instrumentCurrency = instrument?.currency ?? accountCurrency;
  const quantity = Number(tradeQty) || 0;

  const { needsFx, fxLabel, notionalAccount, isFxLoading, yahooSymbol } = useTradeNotional(
    instrumentCurrency,
    accountCurrency,
    quantity,
    lastPrice,
  );

  const feeNotional =
    notionalAccount != null && Number.isFinite(notionalAccount)
      ? notionalAccount
      : quantity * lastPrice;

  useEffect(() => {
    if (id && instrument?.symbol) {
      openChartTab(id, instrument.symbol);
    }
  }, [id, instrument?.symbol, openChartTab]);

  const ohlcvQuery = useQuery({
    queryKey: ['ohlcv', id],
    queryFn: () => api.getOhlcv(id!, 500),
    enabled: Boolean(id),
  });

  const indicatorsQuery = useQuery({
    queryKey: ['indicators', id],
    queryFn: () => api.getIndicators(id!, 500),
    enabled: Boolean(id),
  });

  const liveQuoteQuery = useQuery({
    queryKey: ['live-quote', id],
    queryFn: () => api.getLiveQuote(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data?.data.xtbAvailable ? 30_000 : false),
  });

  const syncMutation = useMutation({
    mutationFn: () => api.syncInstrument(id!, 5),
    onSettled: async () => {
      if (id) await invalidateInstrumentMarketData(queryClient, id);
    },
  });

  const tradeMutation = useMutation({
    mutationFn: (type: 'buy' | 'sell') =>
      api.executeTrade({
        instrumentId: id!,
        type,
        quantity,
        price: lastPrice,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      await queryClient.invalidateQueries({ queryKey: ['transactions'] });
      await queryClient.invalidateQueries({ queryKey: ['ledger'] });
      await queryClient.invalidateQueries({ queryKey: ['account-summary'] });
      setPendingSide(null);
      setTradeError(null);
    },
    onError: (err: Error) => setTradeError(err.message),
  });

  function validateTrade(): string | null {
    if (!Number.isFinite(quantity) || quantity <= 0) return 'Indica una cantidad válida.';
    if (lastPrice <= 0) return 'No hay precio de referencia.';
    if (needsFx && isFxLoading) return 'Espera el tipo de cambio.';
    if (needsFx && notionalAccount == null) return 'No se pudo obtener el tipo de cambio.';
    return null;
  }

  function requestTrade(side: 'buy' | 'sell') {
    setTradeError(null);
    const validationError = validateTrade();
    if (validationError) {
      setTradeError(validationError);
      return;
    }
    if (confirmBeforeTrade) {
      setPendingSide(side);
      return;
    }
    tradeMutation.mutate(side);
  }

  if (instrumentQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Cargando instrumento…</p>;
  }

  if (instrumentQuery.isError || !instrument) {
    return (
      <div className="space-y-4">
        <Link
          to="/instruments"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver
        </Link>
        <p className="text-destructive">No se encontró el instrumento.</p>
      </div>
    );
  }

  const bars = ohlcvQuery.data?.data ?? [];
  const indicators = indicatorsQuery.data?.data ?? [];
  const liveQuote = liveQuoteQuery.data?.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/instruments"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Instrumentos
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">
            {instrument.symbol}
            <span className="ml-2 text-base font-normal text-muted-foreground">{instrument.name}</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {instrument.exchange} · {instrument.yahooSymbol}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              openChartTab(id!, instrument.symbol);
              navigate('/trading');
              openChartInspector({ mode: 'config', configSection: 'styles' });
            }}
            title="Estilos del gráfico en el workspace"
          >
            <Settings2 className="mr-1 h-4 w-4" />
            Estilos
          </Button>
          <Link
            to={`/alerts?instrumentId=${id}`}
            className="inline-flex h-8 items-center justify-center gap-1 rounded-md border border-border bg-transparent px-3 text-xs font-medium hover:bg-accent"
          >
            <Bell className="h-4 w-4" />
            Alerta
          </Link>
          <Button variant="outline" size="sm" disabled={syncMutation.isPending} onClick={() => syncMutation.mutate()}>
            <RefreshCw className={cn('mr-1 h-4 w-4', syncMutation.isPending && 'animate-spin')} />
            Sincronizar
          </Button>
        </div>
      </div>

      {id && (
        <InstrumentStrategyTopPanel
          instrumentId={id}
          symbol={instrument.symbol}
          timeframe="1d"
        />
      )}

      {syncMutation.isError && (
        <p className="text-sm text-destructive">
          Error de sincronización:{' '}
          {syncMutation.error instanceof ApiError ? syncMutation.error.message : 'Error desconocido'}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Último cierre</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">
              {summary?.lastClose != null ? formatPrice(summary.lastClose) : '—'}
            </p>
            {summary?.changePct != null && (
              <p
                className={cn(
                  'text-sm tabular-nums',
                  summary.changePct >= 0 ? 'text-success' : 'text-destructive',
                )}
              >
                {formatPct(summary.changePct)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Barras en BD</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{summary?.barCount ?? 0}</p>
            {lastSync && (
              <p className="text-xs text-muted-foreground">
                Sync: {lastSync.status} ({lastSync.barsAdded} añadidas)
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Cotización XTB</CardTitle>
            <CardDescription>{liveQuote?.xtbAvailable ? 'Bridge activo' : 'No disponible'}</CardDescription>
          </CardHeader>
          <CardContent>
            {liveQuote?.xtbAvailable && liveQuote.xtb ? (
              <p className="text-lg font-semibold tabular-nums">{formatPrice(liveQuote.xtb.last)}</p>
            ) : (
              <p className="text-sm text-muted-foreground">—</p>
            )}
          </CardContent>
        </Card>
      </div>

      <OhlcvChart bars={bars} indicators={indicators} config={DEFAULT_CHART_CONFIG} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Operar (simulado)</CardTitle>
          <CardDescription>
            {accountName ? `Cuenta ${accountName} (${accountCurrency})` : 'Cuenta activa'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Cantidad
              <input
                type="number"
                min={1}
                value={tradeQty}
                onChange={(e) => setTradeQty(e.target.value)}
                className={cn(inputClassName, 'ml-2 w-24')}
              />
            </label>
            <Button
              size="sm"
              disabled={tradeMutation.isPending || !summary?.lastClose}
              onClick={() => requestTrade('buy')}
            >
              Comprar
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={tradeMutation.isPending || !summary?.lastClose}
              onClick={() => requestTrade('sell')}
            >
              Vender
            </Button>
          </div>

          <div className="rounded-md border border-border bg-muted/20 p-3">
            <TradeFeeBreakdown
              notional={feeNotional}
              settings={settings}
              currency={accountCurrency}
              isFxConversion={needsFx}
            />
            <p className="mt-2 text-[10px] text-muted-foreground">
              {instrumentCurrency !== accountCurrency && (
                <>
                  FX: {fxLabel}
                  {yahooSymbol && <span className="ml-1 opacity-60">· {yahooSymbol}</span>}
                  {' · '}
                </>
              )}
              {!confirmBeforeTrade && 'Confirmación desactivada en Configuración → Confirmaciones.'}
            </p>
          </div>

          {tradeError && <p className="text-sm text-destructive">{tradeError}</p>}
        </CardContent>
      </Card>

      {pendingSide && (
        <Dialog
          open
          onClose={() => {
            if (!tradeMutation.isPending) setPendingSide(null);
          }}
          title={`Confirmar — ${instrument.symbol}`}
          description={instrument.name}
          className="max-w-md"
        >
          <TradeConfirmPanel
            details={{
              symbol: instrument.symbol,
              name: instrument.name,
              side: pendingSide,
              quantity,
              price: lastPrice,
              instrumentCurrency,
              accountCurrency,
              accountName,
              notional: feeNotional,
              settings,
              isFxConversion: needsFx,
            }}
            error={tradeError}
            isPending={tradeMutation.isPending}
            onConfirm={() => tradeMutation.mutate(pendingSide)}
            onCancel={() => setPendingSide(null)}
          />
        </Dialog>
      )}
    </div>
  );
}
