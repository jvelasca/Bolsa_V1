/**
 * Abre un instrumento en Mercado (/trading) desde toast u otra superficie.
 */

import type { NavigateFunction } from "react-router-dom";
import { ensureChartRoute } from "@/components/layout/chart-tab-bar";
import { requestChartReflow } from "@/features/charts/chart-utils";

export function openInstrumentInTrading(
  navigate: NavigateFunction,
  deps: {
    openChartTab: (instrumentId: string, label: string) => string;
  },
  hit: { instrumentId: string; symbol: string },
): void {
  deps.openChartTab(hit.instrumentId, hit.symbol);
  ensureChartRoute(navigate);
  requestChartReflow();
}
