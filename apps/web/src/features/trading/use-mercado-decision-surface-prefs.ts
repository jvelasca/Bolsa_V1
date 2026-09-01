/**
 * V1.63 — Preferencia panel vs gráfico para Decision Surface (reactiva).
 */

import { useSyncExternalStore } from "react";
import {
  getMercadoDecisionSurfacePrefsServerSnapshot,
  getMercadoDecisionSurfacePrefsSnapshot,
  patchMercadoDecisionSurfacePrefs,
  subscribeMercadoDecisionSurfacePrefs,
  type DecisionSurfacePlacementV1,
  type MercadoDecisionSurfacePrefs,
} from "@/features/trading/mercado-decision-surface-prefs";

export function useMercadoDecisionSurfacePrefs(): MercadoDecisionSurfacePrefs {
  return useSyncExternalStore(
    subscribeMercadoDecisionSurfacePrefs,
    getMercadoDecisionSurfacePrefsSnapshot,
    getMercadoDecisionSurfacePrefsServerSnapshot,
  );
}

export function useSetDecisionSurfacePlacement(): (
  placement: DecisionSurfacePlacementV1,
) => void {
  return (placement) => {
    patchMercadoDecisionSurfacePrefs({ placement });
  };
}
