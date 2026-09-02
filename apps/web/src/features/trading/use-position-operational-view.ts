/**
 * V1.60 — PositionOperationalView desde PositionDto wire (tarjeta estrella Mercado).
 * V1.61 — source canonical · recon fail-closed.
 * V1.70 — sin fallback de PositionDto plano: fail-closed si falta wire/blob.
 * V1.71 — source wire vs blob · overlay recon live sobre wire · warn DEV.
 * Proyección cliente; autoridad en backend persistido.
 */

import { useMemo } from "react";
import type {
  PaperDeskNextActionV1,
  PositionDto,
  PositionOperationalViewV1,
} from "@bolsa/shared";
import {
  MESA_NEXT_ACTION_LABELS,
  assertNever,
  mapPortfolioReconToPovRecon,
  positionOperationalViewFromBlob,
} from "@bolsa/shared";

export type PositionOperationalViewSourceV1 = "canonical" | "blob";

export type PositionOperationalViewResultV1 = {
  view: PositionOperationalViewV1;
  source: PositionOperationalViewSourceV1;
};

/** Reconstruye blob PositionState mínimo desde PositionDto + campos extendidos opcionales. */
export function operationalBlobFromPositionDto(
  position: PositionDto,
): Record<string, unknown> | null {
  const op = position.operational;
  if (!op?.tradePlanId) return null;
  const qty = Math.abs(Number(position.quantity ?? 0));
  if (qty <= 0) return null;

  const ext = op as unknown as Record<string, unknown>;
  const remaining =
    typeof ext.remainingQuantity === "number"
      ? Math.abs(ext.remainingQuantity)
      : qty;

  return {
    ...ext,
    positionId: position.id,
    instrumentId: position.instrumentId,
    decisionId: op.decisionId ?? op.originThesis?.decisionId ?? null,
    tradePlanId: op.tradePlanId,
    direction: op.direction === "short" ? "short" : "long",
    status: op.status ?? "OPEN",
    plannedEntry: op.plannedEntry ?? position.avgCost,
    actualEntry: op.actualEntry ?? position.avgCost,
    initialStop: op.initialStop ?? null,
    currentStop: op.currentStop ?? null,
    target1: op.target1 ?? null,
    target2: op.target2 ?? null,
    quantity: qty,
    remainingQuantity: remaining,
    unrealizedR: op.unrealizedR ?? null,
    target1Leg: ext.target1Leg ?? { status: "pending" },
    target2Leg: ext.target2Leg ?? { status: "pending" },
    revisions: ext.revisions ?? [],
  };
}

function isWireOperationalView(
  value: unknown,
): value is PositionOperationalViewV1 {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  return (
    typeof o.positionId === "string" &&
    typeof o.tradePlanId === "string" &&
    "operatingState" in o
  );
}

function applyLiveReconToView(
  view: PositionOperationalViewV1,
  portfolioReconStatus?: string | null,
): PositionOperationalViewV1 {
  const reconStatus = mapPortfolioReconToPovRecon(portfolioReconStatus);
  if (
    reconStatus === "drift" &&
    view.operatingState !== "RECONCILIATION_DRIFT"
  ) {
    return {
      ...view,
      operatingState: "RECONCILIATION_DRIFT",
      primaryAction: "BLOQUEADO",
    };
  }
  if (
    reconStatus === "unavailable" &&
    view.operatingState !== "RECONCILIATION_ERROR" &&
    view.operatingState !== "RECONCILIATION_DRIFT"
  ) {
    return {
      ...view,
      operatingState: "RECONCILIATION_ERROR",
      primaryAction: "BLOQUEADO",
    };
  }
  return view;
}

export function buildPositionOperationalViewFromDto(
  position: PositionDto,
  portfolioReconStatus?: string | null,
): PositionOperationalViewResultV1 | null {
  const reconStatus = mapPortfolioReconToPovRecon(portfolioReconStatus);
  const wireView = position.operational?.operationalView;
  if (isWireOperationalView(wireView)) {
    return {
      view: applyLiveReconToView(wireView, portfolioReconStatus),
      source: "canonical",
    };
  }

  if (position.operational) {
    const blob = operationalBlobFromPositionDto(position);
    if (blob) {
      const fromBlob = positionOperationalViewFromBlob(blob, { reconStatus });
      if (fromBlob) {
        if (import.meta.env?.DEV) {
          console.warn(
            "[POV] blob rebuild — wire operationalView missing",
            position.id,
          );
        }
        return { view: fromBlob, source: "blob" };
      }
    }
  }

  return null;
}

export function usePositionOperationalView(
  position: PositionDto | null | undefined,
  portfolioReconStatus?: string | null,
): PositionOperationalViewResultV1 | null {
  return useMemo(
    () =>
      position
        ? buildPositionOperationalViewFromDto(position, portfolioReconStatus)
        : null,
    [position, portfolioReconStatus],
  );
}

export function formatPovPrimaryActionLabel(
  action: PaperDeskNextActionV1,
): string {
  switch (action) {
    case "SUBIR_STOP":
      return MESA_NEXT_ACTION_LABELS.protect;
    case "REDUCIR":
      return MESA_NEXT_ACTION_LABELS.reduce;
    case "SALIR":
      return MESA_NEXT_ACTION_LABELS.exit;
    case "REVISAR_DATOS_NO_FRESCOS":
    case "BLOQUEADO":
      return MESA_NEXT_ACTION_LABELS.review;
    case "ESPERAR_APERTURA":
      return MESA_NEXT_ACTION_LABELS.watch;
    case "MONITOR":
    case "MANTENER":
      return MESA_NEXT_ACTION_LABELS.maintain;
    default:
      return assertNever(action);
  }
}
