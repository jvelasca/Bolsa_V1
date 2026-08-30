/**
 * V1.34 — commit G4 del drag de stop (orquestación testeable).
 * No llama APIs de protect/execute: solo cola Confirm + prefill `signedStop`.
 */

import type { PositionDto, SupervisedProposePayloadDto } from "@bolsa/shared";
import {
  canDragOperationalStop,
  evaluateChartStopDragGeometry,
} from "@/features/charts/chart-stop-drag-policy";
import { setChartSignedStopPrefill } from "@/features/charts/chart-signed-stop-prefill";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { buildPositionExitPayload } from "@/features/operations/propose-position-exit";
import type { MercadoCockpitPhase } from "@/features/trading/operativa-cockpit-phase";

export type ChartStopDragCommitResult =
  | { ok: true; signedStop: number; enqueuedProtect: boolean }
  | { ok: false; reason: string };

export type ChartStopDragCommitDeps = {
  enqueue: (
    payload: SupervisedProposePayloadDto,
    meta?: { origin?: "chart"; symbol?: string },
  ) => string;
  setActive: (id: string) => void;
  findQueueItemIdForInstrument: (instrumentId: string) => string | null;
};

export function commitChartStopDrag(input: {
  phase: MercadoCockpitPhase;
  showsPlanLevels: boolean;
  direction: unknown;
  entry: unknown;
  ghostStop: number;
  target1?: unknown;
  target2?: unknown;
  instrumentId: string;
  accountId: string | null;
  position: PositionDto | null;
  symbol?: string | null;
  deps: ChartStopDragCommitDeps;
}): ChartStopDragCommitResult {
  if (
    !canDragOperationalStop({
      phase: input.phase,
      showsPlanLevels: input.showsPlanLevels,
      stopPrice: input.ghostStop,
    })
  ) {
    return { ok: false, reason: "drag_not_allowed" };
  }

  const geometry = evaluateChartStopDragGeometry({
    direction: input.direction,
    entry: input.entry,
    ghostStop: input.ghostStop,
    target1: input.target1,
    target2: input.target2,
  });
  if (!geometry.ok) {
    return {
      ok: false,
      reason: geometry.reason ?? "geometry_invalid",
    };
  }

  setChartSignedStopPrefill({
    instrumentId: input.instrumentId,
    signedStop: input.ghostStop,
  });

  let enqueuedProtect = false;
  if (input.phase === "posicion" && input.position && input.accountId) {
    try {
      const payload = buildPositionExitPayload({
        position: input.position,
        accountId: input.accountId,
        intent: "protect",
        suggestedStopOverride: input.ghostStop,
        allowPendingOverride: true,
      });
      const id = input.deps.enqueue(payload, {
        origin: "chart",
        symbol: input.symbol ?? input.position.symbol,
      });
      input.deps.setActive(id);
      enqueuedProtect = true;
    } catch {
      // Sin plan persistido / libro MANUAL: igual abrimos Confirm con prefill.
    }
  } else if (input.phase === "preparada") {
    const existing = input.deps.findQueueItemIdForInstrument(
      input.instrumentId,
    );
    if (existing) input.deps.setActive(existing);
  }

  openConfirmDrawer({
    signedStop: input.ghostStop,
    instrumentId: input.instrumentId,
  });

  return { ok: true, signedStop: input.ghostStop, enqueuedProtect };
}
