/**
 * S2 — Preferencia reactiva de visibilidad de niveles calculados.
 */

import { useSyncExternalStore } from "react";
import {
  getMarketStructurePrefsServerSnapshot,
  getMarketStructurePrefsSnapshot,
  patchMarketStructurePrefs,
  subscribeMarketStructurePrefs,
  type MarketStructurePrefs,
} from "@/features/charts/market-structure-prefs";

export function useMarketStructurePrefs(): MarketStructurePrefs {
  return useSyncExternalStore(
    subscribeMarketStructurePrefs,
    getMarketStructurePrefsSnapshot,
    getMarketStructurePrefsServerSnapshot,
  );
}

export function useToggleMarketStructureLevels(): (visible: boolean) => void {
  return (visible) => {
    patchMarketStructurePrefs({ showChartLevels: visible });
  };
}
