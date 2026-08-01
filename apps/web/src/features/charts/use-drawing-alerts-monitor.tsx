import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { drawingAlertPrice } from '@bolsa/shared';
import { api } from '@/lib/api';
import { formatPrice } from '@/features/charts/chart-utils';
import { useAlertsStore } from '@/stores/alerts-store';
import { useActiveChartTab } from '@/stores/workspace-store';

const INTRADAY_INTERVAL_MS = 15_000;
const DAILY_INTERVAL_MS = 30_000;

export function DrawingAlertsMonitor() {
  const pushToast = useAlertsStore((s) => s.pushToast);
  const activeTab = useActiveChartTab();
  const prevSideRef = useRef<Map<string, 'above' | 'below'>>(new Map());

  const instrumentId = activeTab?.instrumentId;
  const timeframe = activeTab?.timeframe ?? '1d';
  const alertDrawings =
    activeTab?.drawings.filter((drawing) => drawing.alertOnCross && drawingAlertPrice(drawing) != null) ??
    [];

  const ohlcvQuery = useQuery({
    queryKey: ['ohlcv-alerts', instrumentId, timeframe],
    queryFn: () => api.getOhlcv(instrumentId!, 120, timeframe),
    enabled: Boolean(instrumentId) && alertDrawings.length > 0,
    staleTime: 10_000,
    refetchInterval: timeframe === '1d' ? DAILY_INTERVAL_MS : INTRADAY_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  const bars = ohlcvQuery.data?.data ?? [];
  const lastClose = bars.at(-1)?.close;

  useEffect(() => {
    if (!activeTab || lastClose == null || alertDrawings.length === 0) return;

    for (const drawing of alertDrawings) {
      const level = drawingAlertPrice(drawing);
      if (level == null) continue;
      const side: 'above' | 'below' = lastClose >= level ? 'above' : 'below';
      const prev = prevSideRef.current.get(drawing.id);
      if (prev && prev !== side) {
        const verb = side === 'above' ? 'por encima' : 'por debajo';
        pushToast(
          `${activeTab.label}: precio pasó ${verb} de ${formatPrice(level)} (${drawing.type})`,
        );
      }
      prevSideRef.current.set(drawing.id, side);
    }
  }, [activeTab, alertDrawings, lastClose, pushToast]);

  useEffect(() => {
    const activeIds = new Set(alertDrawings.map((drawing) => drawing.id));
    for (const id of prevSideRef.current.keys()) {
      if (!activeIds.has(id)) {
        prevSideRef.current.delete(id);
      }
    }
  }, [alertDrawings]);

  return null;
}
