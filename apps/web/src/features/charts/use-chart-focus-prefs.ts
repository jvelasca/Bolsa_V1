/**
 * V2.30 — Preferencia Chart Focus (Simple / Completo), reactiva.
 */

import { useSyncExternalStore } from "react";
import {
  getChartFocusPrefsServerSnapshot,
  getChartFocusPrefsSnapshot,
  patchChartFocusPrefs,
  subscribeChartFocusPrefs,
  type ChartFocusModeV1,
  type ChartFocusPrefs,
} from "@/features/charts/chart-focus-prefs";

export function useChartFocusPrefs(): ChartFocusPrefs {
  return useSyncExternalStore(
    subscribeChartFocusPrefs,
    getChartFocusPrefsSnapshot,
    getChartFocusPrefsServerSnapshot,
  );
}

export function useSetChartFocusMode(): (mode: ChartFocusModeV1) => void {
  return (mode) => {
    patchChartFocusPrefs({ mode });
  };
}
