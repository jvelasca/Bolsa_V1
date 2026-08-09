import { useEffect, useMemo, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { formatPrice } from '@/features/charts/chart-utils';
import {
  liveQuotesMap,
  useInstrumentLiveQuotesBatch,
} from '@/features/instruments/use-instrument-live-quotes-batch';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useAlertsStore } from '@/stores/alerts-store';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { linkTradeToMandate } from '@/features/platform/operating-mandate';
import { api } from '@/lib/api';

const EVALUATE_INTERVAL_MS = 15_000;

function resolveQuotePrice(
  data: import('@bolsa/shared').InstrumentLiveQuoteDto,
): number | null {
  return data.xtb?.last ?? data.reference?.price ?? null;
}

function shouldExecuteOrder(
  side: 'buy' | 'sell',
  marketPrice: number,
  limitPrice: number,
) {
  if (side === 'buy') {
    return marketPrice <= limitPrice;
  }
  return marketPrice >= limitPrice;
}

export function PendingOrdersMonitor() {
  const { pendingOrders, removePendingOrder } = usePendingOrders();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const queryClient = useQueryClient();
  const { effectiveAccountId } = useActiveAccount();
  const processing = useRef<Set<string>>(new Set());
  const errorNotified = useRef<Set<string>>(new Set());
  const orderSignature = pendingOrders.map((order) => order.id).join(',');

  const instrumentIds = useMemo(
    () => [...new Set(pendingOrders.map((order) => order.instrumentId))],
    // orderSignature es el fingerprint estable de pendingOrders; evita recalcular
    // este index en cada render por identidad de array (ya se recalcula al cambiar órdenes).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [orderSignature],
  );

  const quotesQuery = useInstrumentLiveQuotesBatch(instrumentIds, {
    enabled: instrumentIds.length > 0,
    refetchInterval: EVALUATE_INTERVAL_MS,
    staleTime: EVALUATE_INTERVAL_MS,
  });

  useEffect(() => {
    if (pendingOrders.length === 0) {
      return;
    }

    async function evaluate() {
      const now = Date.now();
      const activeOrders = pendingOrders.filter((order) => {
        if (order.expiryAt && new Date(order.expiryAt).getTime() < now) {
          return false;
        }
        return !processing.current.has(order.id);
      });

      for (const order of pendingOrders) {
        if (order.expiryAt && new Date(order.expiryAt).getTime() < now) {
          await removePendingOrder(order.id);
          pushToast(`Orden ${order.symbol} cancelada — vencida`);
        }
      }

      if (activeOrders.length === 0 || !quotesQuery.data) {
        return;
      }

      const quotesByInstrument = liveQuotesMap(quotesQuery.data);

      for (const order of activeOrders) {
        const quote = quotesByInstrument.get(order.instrumentId);
        const marketPrice = quote ? resolveQuotePrice(quote) : null;
        if (marketPrice == null) {
          continue;
        }

        if (!shouldExecuteOrder(order.side, marketPrice, order.limitPrice)) {
          continue;
        }

        processing.current.add(order.id);
        try {
          const res = await api.executeTrade({
            instrumentId: order.instrumentId,
            type: order.side,
            quantity: order.quantity,
            price: order.limitPrice,
          });
          const txId = res?.data?.transaction?.id;
          if (txId && effectiveAccountId) {
            linkTradeToMandate({
              transactionId: txId,
              instrumentId: order.instrumentId,
              accountId: effectiveAccountId,
            });
          }
          await removePendingOrder(order.id);
          errorNotified.current.delete(order.id);
          pushToast(
            `Orden ${order.side === 'buy' ? 'compra' : 'venta'} ${order.symbol} ejecutada @ ${formatPrice(order.limitPrice)}`,
          );
          void queryClient.invalidateQueries({ queryKey: ['portfolio'] });
          void queryClient.invalidateQueries({ queryKey: ['transactions'] });
          void queryClient.invalidateQueries({ queryKey: ['ledger'] });
          void queryClient.invalidateQueries({ queryKey: ['account-summary'] });
        } catch (error) {
          if (!errorNotified.current.has(order.id)) {
            errorNotified.current.add(order.id);
            const message = error instanceof Error ? error.message : 'Error al ejecutar orden';
            pushToast(`Orden ${order.symbol}: ${message}`);
          }
        } finally {
          processing.current.delete(order.id);
        }
      }
    }

    void evaluate();
  }, [
    orderSignature,
    pendingOrders,
    pushToast,
    queryClient,
    quotesQuery.data,
    quotesQuery.dataUpdatedAt,
    removePendingOrder,
    effectiveAccountId,
  ]);

  return null;
}
