/**
 * Hook de órdenes pendientes — servidor como fuente de verdad.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import type { PendingOrderDto } from '@bolsa/shared';
import { api } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';

export type PendingOrder = PendingOrderDto & { type: 'stop_limit' };

function mapOrder(dto: PendingOrderDto): PendingOrder {
  return { ...dto, type: 'stop_limit' };
}

function readLegacyPendingOrders(): Array<Omit<PendingOrder, 'type'>> {
  const raw = localStorage.getItem('bolsa-trading-ui');
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as { state?: { pendingOrders?: PendingOrder[] } };
    return parsed.state?.pendingOrders ?? [];
  } catch {
    return [];
  }
}

export function usePendingOrders() {
  const queryClient = useQueryClient();
  const migratedRef = useRef(false);
  const accountScope = useActiveAccountQueryKey();

  const query = useQuery({
    queryKey: ['pending-orders', accountScope],
    queryFn: async () => {
      const response = await api.getPendingOrders();
      return response.data.map(mapOrder);
    },
  });

  useEffect(() => {
    if (migratedRef.current || query.isLoading) return;
    if ((query.data?.length ?? 0) > 0) {
      migratedRef.current = true;
      return;
    }
    const legacy = readLegacyPendingOrders();
    if (!legacy.length) {
      migratedRef.current = true;
      return;
    }
    migratedRef.current = true;
    void (async () => {
      for (const order of legacy) {
        await api.createPendingOrder({
          instrumentId: order.instrumentId,
          symbol: order.symbol,
          side: order.side,
          orderType: 'stop_limit',
          quantity: order.quantity,
          limitPrice: order.limitPrice,
          expiryAt: order.expiryAt,
        });
      }
      localStorage.removeItem('bolsa-trading-ui');
      await queryClient.invalidateQueries({ queryKey: ['pending-orders'] });
    })();
  }, [query.data, query.isLoading, queryClient]);

  const createMutation = useMutation({
    mutationFn: (body: {
      instrumentId: string;
      symbol: string;
      side: 'buy' | 'sell';
      quantity: number;
      limitPrice: number;
      expiryAt: string | null;
    }) => api.createPendingOrder({ ...body, orderType: 'stop_limit' }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['pending-orders'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deletePendingOrder(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['pending-orders'] }),
  });

  return {
    pendingOrders: query.data ?? [],
    isLoading: query.isLoading,
    addPendingOrder: createMutation.mutateAsync,
    removePendingOrder: deleteMutation.mutateAsync,
  };
}
