/**
 * V1.70 — Abrir valor en Mercado: panel DECISIÓN + gráfico + ruta /trading.
 */

import type { NavigateFunction } from "react-router-dom";
import { ensureChartRoute } from "@/components/layout/chart-tab-bar";
import { requestChartReflow } from "@/features/charts/chart-utils";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";

export function ensureMercadoActionPanelsOpen(): void {
  const layout = useTradingLayoutStore.getState();
  layout.ensureOperativaOpen();
  layout.ensureChartsOpen();
  layout.ensureListsOpen();
}

export function focusInstrumentInMercado(
  navigate: NavigateFunction,
  deps: {
    openChartTab: (instrumentId: string, label: string) => string;
    focusInstrumentFromList?: (
      listId: string,
      instrumentId: string,
      label: string,
    ) => string;
  },
  hit: { instrumentId: string; symbol: string },
  options?: { listId?: string | null },
): string {
  ensureMercadoActionPanelsOpen();

  const listId = options?.listId?.trim();
  const tabId =
    listId && deps.focusInstrumentFromList
      ? deps.focusInstrumentFromList(listId, hit.instrumentId, hit.symbol)
      : deps.openChartTab(hit.instrumentId, hit.symbol);

  ensureChartRoute(navigate);
  requestChartReflow();
  return tabId;
}

export function focusInstrumentsInMercado(
  navigate: NavigateFunction,
  deps: {
    focusInstrumentsFromList: (
      listId: string,
      items: Array<{ instrumentId: string; label: string }>,
    ) => void;
  },
  listId: string,
  items: Array<{ instrumentId: string; label: string }>,
): void {
  if (items.length === 0) return;
  ensureMercadoActionPanelsOpen();
  deps.focusInstrumentsFromList(listId, items);
  ensureChartRoute(navigate);
  requestChartReflow();
}
