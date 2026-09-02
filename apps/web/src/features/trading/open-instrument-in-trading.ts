/**
 * Abre un instrumento en Mercado (/trading) desde toast u otra superficie.
 */

import type { NavigateFunction } from "react-router-dom";
import { focusInstrumentInMercado } from "@/features/trading/focus-instrument-in-mercado";

export function openInstrumentInTrading(
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
): void {
  focusInstrumentInMercado(navigate, deps, hit, options);
}
