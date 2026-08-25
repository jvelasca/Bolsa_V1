/**
 * P4 — encolar cierre/reducción/proteger desde posición operativa → Confirm (no ejecuta).
 */

import type {
  DecisionAction,
  PositionDto,
  ProtectPlanV1,
  RecommendationV1,
} from "@bolsa/shared";
import { doesStopWorsen } from "@bolsa/shared";
import type { SupervisedProposePayload } from "@/stores/supervised-f3-queue-store";
import {
  demoBookAllowsEnqueueConfirm,
  loadDemoBookPrefs,
} from "@/features/trading/demo-book-prefs";

export type PositionExitIntent = "review" | "reduce" | "exit_hint" | "protect";

export type OperativaProtectMetaV1 = {
  operativaIntent: "protect";
  suggestedStop: number;
  currentStop: number | null;
  direction: string;
  stopOverrideRequired: boolean;
};

function defaultMetrics(): RecommendationV1["metrics"] {
  return {
    confidence: 0.5,
    consensus: 0.5,
    evidenceStrength: 0.5,
    stability: 0.5,
    conviction: 0.5,
  };
}

function resolveExitQuantity(
  pos: PositionDto,
  intent: PositionExitIntent,
): number {
  const qty = pos.quantity;
  if (!(qty > 0)) return 0;
  if (intent === "exit_hint") return qty;
  if (intent === "reduce") return Math.max(1, Math.ceil(qty / 2));
  if (intent === "protect") return qty;
  return qty;
}

export function resolveProtectSuggestedStop(
  position: PositionDto,
  protectPlan?: ProtectPlanV1 | null,
): number | null {
  const exitPlan = position.operational?.exitPlan;
  const fromExit = exitPlan?.suggestedStop;
  if (fromExit != null && fromExit > 0) return fromExit;
  const fromProtect = protectPlan?.suggestedProtectStop;
  if (fromProtect != null && fromProtect > 0) return fromProtect;
  return null;
}

export function positionShowsProtectHint(
  position: PositionDto,
  protectPlan?: ProtectPlanV1 | null,
): boolean {
  const action = position.operational?.exitPlan?.suggestedAction;
  if (action === "protect") return true;
  if (protectPlan?.status === "protect_hint") return true;
  return false;
}

export function evaluateProtectStopOverride(opts: {
  direction: string;
  currentStop: number | null | undefined;
  suggestedStop: number;
  overrideReason?: string;
}): { overrideRequired: boolean; allowed: boolean } {
  const overrideRequired = doesStopWorsen(
    opts.direction,
    opts.currentStop,
    opts.suggestedStop,
  );
  const override = Boolean(opts.overrideReason?.trim());
  return { overrideRequired, allowed: !overrideRequired || override };
}

export function asOperativaProtectMeta(
  payload: SupervisedProposePayload | null | undefined,
): OperativaProtectMetaV1 | null {
  const pkg = payload?.decisionPackage as OperativaProtectMetaV1 | undefined;
  if (pkg?.operativaIntent === "protect" && pkg.suggestedStop > 0) return pkg;
  return null;
}

export function buildPositionExitPayload(opts: {
  position: PositionDto;
  accountId: string;
  intent: PositionExitIntent;
  protectPlan?: ProtectPlanV1 | null;
  stopOverrideReason?: string;
}): SupervisedProposePayload {
  const { position, accountId, intent, protectPlan, stopOverrideReason } = opts;
  const operational = position.operational;
  if (!operational?.tradePlanId) {
    throw new Error("Sin plan persistido: no se puede encolar desriesgo.");
  }
  const book = loadDemoBookPrefs();
  if (!demoBookAllowsEnqueueConfirm(book.mode)) {
    throw new Error(
      "Libro en MANUAL: cambia a SEMI en Operativa → Configuración para encolar Confirm.",
    );
  }

  const price =
    position.lastPrice != null && position.lastPrice > 0
      ? position.lastPrice
      : position.avgCost > 0
        ? position.avgCost
        : null;
  if (price == null && intent !== "protect") {
    throw new Error("Sin precio de referencia para el ticket de salida.");
  }

  if (intent === "protect") {
    const suggestedStop = resolveProtectSuggestedStop(position, protectPlan);
    if (suggestedStop == null) {
      throw new Error("Sin stop sugerido para proteger la posición.");
    }
    const { overrideRequired, allowed } = evaluateProtectStopOverride({
      direction: operational.direction,
      currentStop: operational.currentStop,
      suggestedStop,
      overrideReason: stopOverrideReason,
    });
    if (!allowed) {
      throw new Error(
        "El stop empeoraría el actual: escribe un motivo de override.",
      );
    }

    const now = new Date().toISOString();
    const protectMeta: OperativaProtectMetaV1 = {
      operativaIntent: "protect",
      suggestedStop,
      currentStop: operational.currentStop ?? null,
      direction: operational.direction,
      stopOverrideRequired: overrideRequired,
    };

    return {
      artifactType: "ART-RECOMMENDATION",
      schemaVersion: "1.0.0",
      recommendationId: `REC-PROTECT-${position.instrumentId}-${Date.now()}`,
      decisionId: operational.tradePlanId,
      instrumentId: position.instrumentId,
      symbol: position.symbol,
      accountId,
      action: "wait",
      suggestedQuantity: position.quantity,
      suggestedPrice: suggestedStop,
      metrics: defaultMetrics(),
      status: "awaiting_human",
      createdAt: now,
      source: "operativa",
      notes: ["Proteger (stop amend) desde Consola de Mesa (P4.2)"],
      decisionPackage: protectMeta,
    };
  }

  const action: DecisionAction =
    intent === "review" ? "wait" : intent === "reduce" ? "reduce" : "exit_hint";
  const qty = resolveExitQuantity(position, intent);
  if (qty <= 0) {
    throw new Error("Cantidad inválida para la salida.");
  }
  if (price == null) {
    throw new Error("Sin precio de referencia para el ticket de salida.");
  }

  const now = new Date().toISOString();
  const decisionId = operational.tradePlanId;

  return {
    artifactType: "ART-RECOMMENDATION",
    schemaVersion: "1.0.0",
    recommendationId: `REC-EXIT-${position.instrumentId}-${Date.now()}`,
    decisionId,
    instrumentId: position.instrumentId,
    symbol: position.symbol,
    accountId,
    action,
    suggestedQuantity: qty,
    suggestedPrice: price,
    metrics: defaultMetrics(),
    status: "awaiting_human",
    createdAt: now,
    source: "operativa",
    notes: [
      intent === "review"
        ? "Revisión de posición desde Operaciones"
        : `CTA ${intent} desde Consola de Mesa (P4)`,
    ],
  };
}
