import type { NavigateFunction } from "react-router-dom";
import type { ChartTimeframe } from "@bolsa/shared";
import { isKernelTimeframe } from "@bolsa/shared";
import { requestChartReflow } from "@/features/charts/chart-utils";
import { focusInstrumentInMercado } from "@/features/trading/focus-instrument-in-mercado";

interface OpenHitInTradingDeps {
  openChartTab: (instrumentId: string, label: string) => string;
  updateChartTimeframe: (timeframe: ChartTimeframe, chartId?: string) => void;
  focusInstrumentFromList?: (
    listId: string,
    instrumentId: string,
    label: string,
  ) => string;
}

interface ScanHitLike {
  instrumentId: string;
  symbol: string;
}

interface OpenHitInTradingOptions {
  timeframe?: string;
  listId?: string;
}

/** Abre el instrumento en /trading; opcionalmente con contexto de lista del scan. */
export function openHitInTrading(
  navigate: NavigateFunction,
  deps: OpenHitInTradingDeps,
  hit: ScanHitLike,
  options?: OpenHitInTradingOptions,
) {
  const tabId = focusInstrumentInMercado(navigate, deps, hit, {
    listId: options?.listId,
  });

  if (options?.timeframe && isKernelTimeframe(options.timeframe)) {
    deps.updateChartTimeframe(options.timeframe, tabId);
    requestChartReflow();
  }
}
