/**
 * V1.34 B-γ — política de drag del stop vigente (pura, sin DOM).
 *
 * G3 = ghost; G4 = commit → Confirm `signedStop`. El gráfico no autoriza.
 *
 * @see docs/engineering/diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md
 */

import {
  validateOperationalLevels,
  type OperationalLevelsReasonV1,
} from "@bolsa/shared";
import type { MercadoCockpitPhase } from "@/features/trading/operativa-cockpit-phase";

/** Fases con drag de stop (nunca disparada). */
export const CHART_STOP_DRAG_PHASES = ["preparada", "posicion"] as const;

export type ChartStopDragPhase = (typeof CHART_STOP_DRAG_PHASES)[number];

export const CHART_STOP_HIT_THRESHOLD_PX = 8;

export function isChartStopDragPhase(
  phase: MercadoCockpitPhase,
): phase is ChartStopDragPhase {
  return (CHART_STOP_DRAG_PHASES as readonly string[]).includes(phase);
}

/**
 * ¿Se permite iniciar drag de stop?
 * Requiere niveles visibles + fase allowlist + stop finito.
 */
export function canDragOperationalStop(input: {
  phase: MercadoCockpitPhase;
  showsPlanLevels: boolean;
  stopPrice: number | null | undefined;
}): boolean {
  if (!input.showsPlanLevels) return false;
  if (!isChartStopDragPhase(input.phase)) return false;
  return (
    typeof input.stopPrice === "number" &&
    Number.isFinite(input.stopPrice) &&
    input.stopPrice > 0
  );
}

export type ChartStopDragGeometryVerdict = {
  ok: boolean;
  reason: OperationalLevelsReasonV1 | null;
  riskDistance: number | null;
};

/**
 * Geometría del ghost = misma `validateOperationalLevels` que Confirm / V1.26.
 * Targets opcionales: si el plan los tiene, se revalidan al mover el stop.
 */
export function evaluateChartStopDragGeometry(input: {
  direction: unknown;
  entry: unknown;
  ghostStop: unknown;
  target1?: unknown;
  target2?: unknown;
}): ChartStopDragGeometryVerdict {
  const verdict = validateOperationalLevels({
    direction: input.direction,
    entry: input.entry,
    stop: input.ghostStop,
    target1: input.target1,
    target2: input.target2,
  });
  return {
    ok: verdict.ok,
    reason: verdict.reason,
    riskDistance: verdict.riskDistance,
  };
}

/** Hit-test vertical: ¿el puntero está cerca del stop? */
export function isPointerNearStopLine(input: {
  pointerY: number;
  stopY: number | null;
  thresholdPx?: number;
}): boolean {
  if (input.stopY == null || !Number.isFinite(input.stopY)) return false;
  const thr = input.thresholdPx ?? CHART_STOP_HIT_THRESHOLD_PX;
  return Math.abs(input.pointerY - input.stopY) <= thr;
}

/** ¿El kind de nivel es el único draggable (stop vigente)? */
export function isDraggablePlanLevelKind(kind: string): boolean {
  return kind === "stopVigente";
}
