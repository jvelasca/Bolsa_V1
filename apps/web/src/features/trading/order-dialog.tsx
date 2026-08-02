import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogTabs,
  FieldRow,
  checkboxClassName,
  inputClassName,
} from '@/components/ui/dialog';
import { ExpiryDateTimeField } from '@/components/ui/expiry-datetime-field';
import { defaultExpiryFromNow } from '@/lib/datetime-input';
import { formatPrice } from '@/features/charts/chart-utils';
import { useActiveAccount, useActiveAccountSettings } from '@/features/accounts/use-active-account';
import { TradeConfirmPanel } from '@/features/trading/trade-confirm-panel';
import { TradeFeeBreakdown } from '@/features/trading/trade-fee-breakdown';
import { useTradeNotional } from '@/features/trading/use-trade-notional';
import { linkTradeToMandate } from '@/features/platform/operating-mandate';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useTradePreferencesStore } from '@/stores/trade-preferences-store';
import { useTradingUiStore } from '@/stores/trading-ui-store';

type OrderMode = 'market' | 'stop_limit';
type SizeMode = 'volume' | 'value';
type PendingConfirm =
  | { kind: 'market'; side: 'buy' | 'sell' }
  | { kind: 'pending'; side: 'buy' | 'sell' };

function parseNumber(value: string) {
  return Number.parseFloat(value.replace(',', '.'));
}

export function OrderDialog() {
  const instrument = useTradingUiStore((s) => s.orderInstrument);
  const close = useTradingUiStore((s) => s.closeOrderDialog);
  const addPendingOrder = usePendingOrders().addPendingOrder;
  const queryClient = useQueryClient();
  const confirmBeforeTrade = useTradePreferencesStore((s) => s.confirmBeforeTrade);
  const { settings, currency: accountCurrency, accountName } = useActiveAccountSettings();
  const { effectiveAccountId } = useActiveAccount();
  const [mode, setMode] = useState<OrderMode>('market');
  const [sizeMode, setSizeMode] = useState<SizeMode>('volume');
  const [volume, setVolume] = useState('10');
  const [value, setValue] = useState('1000');
  const [limitPrice, setLimitPrice] = useState('');
  const [useExpiry, setUseExpiry] = useState(false);
  const [expiryDate, setExpiryDate] = useState('');
  const [expiryTime, setExpiryTime] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);

  const lastPrice = instrument?.meta.lastClose ?? 0;
  const instrumentCurrency = instrument?.currency ?? accountCurrency;

  function resolveQuantity() {
    if (sizeMode === 'volume') {
      return parseNumber(volume);
    }
    const amount = parseNumber(value);
    return lastPrice > 0 ? Math.floor(amount / lastPrice) : 0;
  }

  const qty = resolveQuantity();
  const executionPrice =
    pendingConfirm?.kind === 'pending' ? parseNumber(limitPrice) || lastPrice : lastPrice;

  const { needsFx, fxLabel, notionalAccount, isFxLoading, yahooSymbol } = useTradeNotional(
    instrumentCurrency,
    accountCurrency,
    qty,
    executionPrice,
  );

  const tradeMutation = useMutation({
    mutationFn: (body: {
      instrumentId: string;
      type: 'buy' | 'sell';
      quantity: number;
      price: number;
    }) => api.executeTrade(body),
    onSuccess: async (res, vars) => {
      const txId = res?.data?.transaction?.id;
      if (txId && effectiveAccountId) {
        linkTradeToMandate({
          transactionId: txId,
          instrumentId: vars.instrumentId,
          accountId: effectiveAccountId,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      await queryClient.invalidateQueries({ queryKey: ['transactions'] });
      await queryClient.invalidateQueries({ queryKey: ['ledger'] });
      await queryClient.invalidateQueries({ queryKey: ['account-summary'] });
      setPendingConfirm(null);
      close();
    },
    onError: (err: Error) => setError(err.message),
  });

  if (!instrument) return null;

  const activeInstrument = instrument;
  const estValueInstrument = sizeMode === 'volume' ? qty * lastPrice : parseNumber(value);
  const feeNotional =
    notionalAccount != null && Number.isFinite(notionalAccount)
      ? notionalAccount
      : qty * lastPrice;

  function validateOrder(): string | null {
    if (!Number.isFinite(qty) || qty <= 0) return 'Indica un volumen válido.';
    if (mode === 'market' && lastPrice <= 0) return 'No hay precio de referencia para ejecutar.';
    if (mode === 'stop_limit') {
      const limit = parseNumber(limitPrice);
      if (!Number.isFinite(limit) || limit <= 0) return 'Indica un precio límite válido.';
    }
    if (needsFx && isFxLoading) return 'Espera el tipo de cambio para confirmar.';
    if (needsFx && notionalAccount == null) return 'No se pudo obtener el tipo de cambio.';
    return null;
  }

  function executeMarket(side: 'buy' | 'sell') {
    tradeMutation.mutate({
      instrumentId: activeInstrument.id,
      type: side,
      quantity: qty,
      price: lastPrice,
    });
  }

  async function executePending(side: 'buy' | 'sell') {
    const limit = parseNumber(limitPrice);
    const expiryAt =
      useExpiry && expiryDate
        ? new Date(`${expiryDate}T${expiryTime || '23:59'}:00`).toISOString()
        : null;

    try {
      await addPendingOrder({
        instrumentId: activeInstrument.id,
        symbol: activeInstrument.symbol,
        side,
        quantity: qty,
        limitPrice: limit,
        expiryAt,
      });
      setPendingConfirm(null);
      close();
    } catch {
      setError('No se pudo registrar la orden pendiente.');
    }
  }

  function requestAction(side: 'buy' | 'sell') {
    setError(null);
    const validationError = validateOrder();
    if (validationError) {
      setError(validationError);
      return;
    }

    const action: PendingConfirm =
      mode === 'market' ? { kind: 'market', side } : { kind: 'pending', side };

    if (confirmBeforeTrade) {
      setPendingConfirm(action);
      return;
    }

    if (mode === 'market') {
      executeMarket(side);
    } else {
      void executePending(side);
    }
  }

  function confirmPendingAction() {
    if (!pendingConfirm) return;
    if (pendingConfirm.kind === 'market') {
      executeMarket(pendingConfirm.side);
    } else {
      void executePending(pendingConfirm.side);
    }
  }

  const busy = tradeMutation.isPending;

  if (pendingConfirm) {
    return (
      <Dialog
        open
        onClose={() => {
          if (!busy) setPendingConfirm(null);
        }}
        title={`Confirmar — ${activeInstrument.symbol}`}
        description={activeInstrument.name}
        className="max-w-md"
      >
        <TradeConfirmPanel
          details={{
            symbol: activeInstrument.symbol,
            name: activeInstrument.name,
            side: pendingConfirm.side,
            quantity: qty,
            price: executionPrice,
            instrumentCurrency,
            accountCurrency,
            accountName,
            notional: feeNotional,
            settings,
            isFxConversion: needsFx,
            orderLabel:
              pendingConfirm.kind === 'pending'
                ? `${pendingConfirm.side === 'buy' ? 'Compra' : 'Venta'} limitada`
                : undefined,
          }}
          error={error}
          isPending={busy}
          onConfirm={confirmPendingAction}
          onCancel={() => setPendingConfirm(null)}
        />
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onClose={close}
      title={`Operar — ${activeInstrument.symbol}`}
      description={activeInstrument.name}
      className="max-w-lg"
    >
      <p className="mb-3 text-xs text-muted-foreground">
        Último: {lastPrice ? formatPrice(lastPrice) : '—'} · {instrumentCurrency}
      </p>

      <DialogTabs
        tabs={[
          { id: 'market', label: 'Orden de mercado' },
          { id: 'stop_limit', label: 'Orden Stop/Limitada' },
        ]}
        active={mode}
        onChange={(id) => setMode(id as OrderMode)}
      />

      {mode === 'stop_limit' && (
        <div className="mb-4 space-y-3">
          <FieldRow label="Precio límite / stop">
            <input
              className={inputClassName}
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              placeholder="0,00"
            />
          </FieldRow>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={useExpiry}
              onChange={(e) => {
                const checked = e.target.checked;
                setUseExpiry(checked);
                if (checked) {
                  const defaults = defaultExpiryFromNow();
                  setExpiryDate(defaults.date);
                  setExpiryTime(defaults.time);
                }
              }}
            />
            Fecha de vencimiento
          </label>
          {useExpiry && (
            <ExpiryDateTimeField
              date={expiryDate}
              time={expiryTime}
              onDateChange={setExpiryDate}
              onTimeChange={setExpiryTime}
            />
          )}
        </div>
      )}

      <div className="mb-4 space-y-3">
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => setSizeMode('volume')}
            className={cn(
              'rounded px-2 py-1',
              sizeMode === 'volume' ? 'bg-primary text-primary-foreground' : 'bg-muted',
            )}
          >
            Volumen (acciones)
          </button>
          <button
            type="button"
            onClick={() => setSizeMode('value')}
            className={cn(
              'rounded px-2 py-1',
              sizeMode === 'value' ? 'bg-primary text-primary-foreground' : 'bg-muted',
            )}
          >
            Valor mercado ({accountCurrency})
          </button>
        </div>
        {sizeMode === 'volume' ? (
          <FieldRow
            label="Volumen"
            hint={`Valor estimado: ${Number.isFinite(estValueInstrument) ? formatPrice(estValueInstrument) : '—'} ${instrumentCurrency}${notionalAccount != null ? ` ≈ ${formatPrice(notionalAccount)} ${accountCurrency}` : ''}`}
          >
            <input className={inputClassName} value={volume} onChange={(e) => setVolume(e.target.value)} />
          </FieldRow>
        ) : (
          <FieldRow
            label={`Valor mercado (${accountCurrency})`}
            hint={`Acciones aprox.: ${lastPrice > 0 && Number.isFinite(estValueInstrument) ? Math.floor(estValueInstrument / lastPrice) : '—'}`}
          >
            <input className={inputClassName} value={value} onChange={(e) => setValue(e.target.value)} />
          </FieldRow>
        )}
      </div>

      <div className="mb-4 space-y-2 rounded border border-border bg-muted/20 p-3">
        {accountName && (
          <p className="text-[10px] text-muted-foreground">
            Cuenta: <span className="text-foreground">{accountName}</span> ({accountCurrency})
          </p>
        )}
        <TradeFeeBreakdown
          notional={feeNotional}
          settings={settings}
          currency={accountCurrency}
          isFxConversion={needsFx}
        />
        <p className="text-[10px] text-muted-foreground">
          Divisa instrumento: {instrumentCurrency}
          {' · '}
          Tipo de cambio: {needsFx ? fxLabel : `1,00 (${accountCurrency})`}
          {needsFx && yahooSymbol && <span className="ml-1 opacity-60">· {yahooSymbol}</span>}
        </p>
        {!confirmBeforeTrade && (
          <p className="text-[10px] text-amber-600/90">
            Confirmación desactivada — la orden se ejecutará al pulsar Compra/Venta.
          </p>
        )}
      </div>

      {error && <p className="mb-3 text-xs text-destructive">{error}</p>}

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={busy}
          className="rounded-lg bg-red-600/90 py-3 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
          onClick={() => requestAction('sell')}
        >
          VENTA {lastPrice ? formatPrice(lastPrice) : ''}
        </button>
        <button
          type="button"
          disabled={busy}
          className="rounded-lg bg-emerald-600/90 py-3 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
          onClick={() => requestAction('buy')}
        >
          {mode === 'market' ? 'COMPRA' : 'COMPRA LIMITADA'}{' '}
          {lastPrice ? formatPrice(lastPrice) : ''}
        </button>
      </div>
    </Dialog>
  );
}
