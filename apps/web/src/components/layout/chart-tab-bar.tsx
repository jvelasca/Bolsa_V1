/**
 * Navegación de gráficos — abrir instrumento y asegurar ruta /workspace.
 *
 * Las pestañas de gráficos se renderizan en charts-zone.tsx (TradingLayout).
 */
import type { NavigateFunction } from 'react-router-dom';
import { requestChartReflow } from '@/features/charts/chart-utils';
import { isTradingRoute } from '@/lib/routes';

export function ensureChartRoute(navigate: NavigateFunction) {
  if (!isTradingRoute(window.location.pathname)) {
    navigate('/trading');
  }
}

export function openInstrumentChart(
  navigate: NavigateFunction,
  openChartTab: (instrumentId: string, label: string) => string,
  instrumentId: string,
  symbol: string,
) {
  openChartTab(instrumentId, symbol);
  ensureChartRoute(navigate);
  requestChartReflow();
}
