import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { formatSignalAlertToast, SIGNAL_KIND_LABELS, type AlertPriceSource } from '@bolsa/shared';
import { api } from '@/lib/api';
import { useAlertsStore } from '@/stores/alerts-store';
import { formatPrice } from '@/features/charts/chart-utils';

const DAILY_INTERVAL_MS = 20_000;
const XTB_INTERVAL_MS = 10_000;

const priceSourceLabels: Record<AlertPriceSource, string> = {
  daily_close: 'cierre',
  xtb_last: 'XTB',
};

export function AlertsMonitor() {
  const pushToast = useAlertsStore((s) => s.pushToast);
  const queryClient = useQueryClient();
  const seenPriceTriggered = useRef<Set<string>>(new Set());
  const seenSignalTriggered = useRef<Set<string>>(new Set());

  const activeQuery = useQuery({
    queryKey: ['alerts', 'active'],
    queryFn: () => api.getAlerts(true),
  });

  const signalAlertsQuery = useQuery({
    queryKey: ['signal-alerts', 'active'],
    queryFn: () => api.getSignalAlerts(true),
  });

  const activeAlerts = activeQuery.data?.data ?? [];
  const activeSignalAlerts = signalAlertsQuery.data?.data ?? [];
  const hasXtbAlerts = activeAlerts.some((alert) => alert.priceSource === 'xtb_last');
  const evaluateIntervalMs = hasXtbAlerts ? XTB_INTERVAL_MS : DAILY_INTERVAL_MS;

  const evaluateMutation = useMutation({
    mutationFn: api.evaluateAlerts,
    onSuccess: (result) => {
      for (const alert of result.data) {
        if (seenPriceTriggered.current.has(alert.id)) {
          continue;
        }
        seenPriceTriggered.current.add(alert.id);
        const direction = alert.condition === 'above' ? 'superó' : 'cayó por debajo de';
        const source = priceSourceLabels[alert.priceSource];
        pushToast(
          `${alert.symbol} (${source}): ${direction} ${formatPrice(alert.targetPrice)} (precio ${formatPrice(alert.triggeredPrice ?? 0)})`,
        );
      }
      void queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  const evaluateSignalMutation = useMutation({
    mutationFn: api.evaluateSignalAlerts,
    onSuccess: (result) => {
      for (const hit of result.data) {
        const dedupeKey = `${hit.subscription.id}:${hit.signal.timestamp}:${hit.signal.kind}`;
        if (seenSignalTriggered.current.has(dedupeKey)) {
          continue;
        }
        seenSignalTriggered.current.add(dedupeKey);
        if (hit.subscription.channels.includes('toast')) {
          pushToast(formatSignalAlertToast(hit, SIGNAL_KIND_LABELS));
        }
      }
      for (const dispatch of result.dispatches ?? []) {
        if (!dispatch.ok) {
          pushToast(
            `Canal ${dispatch.channel} falló (${dispatch.subscriptionId.slice(0, 8)}): ${dispatch.error ?? 'error'}`,
          );
        }
      }
      void queryClient.invalidateQueries({ queryKey: ['signal-alerts'] });
    },
  });

  const activeCount = activeAlerts.length + activeSignalAlerts.length;

  useEffect(() => {
    if (activeCount === 0) {
      return;
    }
    void activeQuery.refetch();
    void signalAlertsQuery.refetch();
    void evaluateMutation.mutate();
    void evaluateSignalMutation.mutate();
    const timer = window.setInterval(() => {
      void activeQuery.refetch();
      void signalAlertsQuery.refetch();
      void evaluateMutation.mutate();
      void evaluateSignalMutation.mutate();
    }, evaluateIntervalMs);
    return () => window.clearInterval(timer);
  }, [activeCount, evaluateIntervalMs]);

  return null;
}
