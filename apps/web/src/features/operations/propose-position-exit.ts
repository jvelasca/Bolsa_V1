/**
 * P4 — encolar cierre/reducción/proteger desde posición operativa → Confirm (no ejecuta).
 * V1.29 — reduce qty desde ExitPolicy; trail/protect clamp no empeora stop vigente.
 */

import type {
  DecisionAction,
  OperationalExitPlanDto,
  PositionDto,
  ProtectPlanV1,
  RecommendationV1,
} from "@bolsa/shared";
import {
  clampStopNotWorsen,
  doesStopWorsen,
  resolveExitPolicy,
  revisionOriginFromExitReason,
  suggestionFromExitPolicy,
} from "@bolsa/shared";
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
  /**
   * V1.43 — trail Confirm → PositionRevision origin=trail.
   * Default/omit = protect (T1 BE / protect_hint).
   */
  revisionOrigin?: "protect" | "trail";
  primaryReason?: string | null;
};

/** V1.32 — snapshot ExitPlan + fuente evento|manual en enqueue reduce/exit. */
export type OperativaExitMetaV1 = {
  operativaIntent: "reduce" | "exit_hint";
  exitSource: "event" | "manual";
  plannedQty: number;
  exitPlan: {
    status: string;
    suggestedAction: string;
    primaryReason: string | null;
    suggestedQty?: number | null;
    suggestedStop?: number | null;
    policyTemplateId?: string | null;
  } | null;
};

function resolveExitSource(
  exitPlan: OperationalExitPlanDto | null | undefined,
): "event" | "manual" {
  if (!exitPlan) return "manual";
  const status = exitPlan.status;
  const reason = exitPlan.primaryReason;
  if (
    (status === "TRIGGERED" || status === "ARMED") &&
    typeof reason === "string" &&
    reason.trim()
  ) {
    return "event";
  }
  return "manual";
}

function defaultMetrics(): RecommendationV1["metrics"] {
  return {
    confidence: 0.5,
    consensus: 0.5,
    evidenceStrength: 0.5,
    stability: 0.5,
    conviction: 0.5,
  };
}

function resolvePolicyTemplateId(
  pos: PositionDto,
  policyTemplateId?: string | null,
): string {
  return (
    policyTemplateId ??
    pos.operational?.exitPlan?.policyTemplateId ??
    "moderate"
  );
}

/**
 * V1.29 — qty de reduce desde ExitPlan.suggestedQty (política) o
 * suggestionFromExitPolicy(primaryReason); legado mitad solo si no hay evento.
 */
export function resolveExitQuantity(
  pos: PositionDto,
  intent: PositionExitIntent,
  policyTemplateId?: string | null,
): number {
  const qty = pos.quantity;
  if (!(qty > 0)) return 0;
  if (intent === "exit_hint") return qty;
  if (intent === "protect") return qty;
  if (intent === "reduce") {
    const exitPlan = pos.operational?.exitPlan;
    const fromPlan = exitPlan?.suggestedQty;
    if (
      typeof fromPlan === "number" &&
      Number.isFinite(fromPlan) &&
      fromPlan > 0
    ) {
      return Math.min(qty, fromPlan);
    }
    const primary = exitPlan?.primaryReason ?? null;
    if (primary === "TARGET_1" || primary === "TARGET_2") {
      const policy = resolveExitPolicy(
        resolvePolicyTemplateId(pos, policyTemplateId),
      );
      const suggestion = suggestionFromExitPolicy(primary, qty, policy);
      if (suggestion.suggestedQty != null && suggestion.suggestedQty > 0) {
        return Math.min(qty, suggestion.suggestedQty);
      }
      if (suggestion.suggestedAction === "hold") return 0;
    }
    // Legado: sin evento de política → mitad (pre-V1.29 CTA manual).
    return Math.max(1, Math.ceil(qty / 2));
  }
  return qty;
}

export function resolveProtectSuggestedStop(
  position: PositionDto,
  protectPlan?: ProtectPlanV1 | null,
): number | null {
  const operational = position.operational;
  const exitPlan = operational?.exitPlan;
  const fromExit = exitPlan?.suggestedStop;
  let raw: number | null = null;
  if (fromExit != null && fromExit > 0) raw = fromExit;
  else {
    const fromProtect = protectPlan?.suggestedProtectStop;
    if (fromProtect != null && fromProtect > 0) raw = fromProtect;
  }
  if (raw == null) return null;
  const direction = operational?.direction ?? "long";
  const current = operational?.currentStop;
  // V1.29 — trail no empeora riesgo: clamp al vigente.
  return clampStopNotWorsen(direction, current, raw);
}

export function positionShowsProtectHint(
  position: PositionDto,
  protectPlan?: ProtectPlanV1 | null,
): boolean {
  const action = position.operational?.exitPlan?.suggestedAction;
  if (action === "protect") {
    const stop = resolveProtectSuggestedStop(position, protectPlan);
    if (stop == null) return false;
    const current = position.operational?.currentStop;
    // Si el clamp dejó el stop igual al vigente, no hay CTA (nada que firmar).
    if (current != null && current > 0 && Math.abs(stop - current) < 1e-9) {
      return false;
    }
    return true;
  }
  if (protectPlan?.status === "protect_hint") {
    const stop = resolveProtectSuggestedStop(position, protectPlan);
    if (stop == null) return false;
    const current = position.operational?.currentStop;
    if (current != null && current > 0 && Math.abs(stop - current) < 1e-9) {
      return false;
    }
    return true;
  }
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

export function asOperativaExitMeta(
  payload: SupervisedProposePayload | null | undefined,
): OperativaExitMetaV1 | null {
  const pkg = payload?.decisionPackage as OperativaExitMetaV1 | undefined;
  if (
    (pkg?.operativaIntent === "reduce" ||
      pkg?.operativaIntent === "exit_hint") &&
    typeof pkg.plannedQty === "number" &&
    pkg.plannedQty > 0
  ) {
    return pkg;
  }
  return null;
}

export function buildPositionExitPayload(opts: {
  position: PositionDto;
  accountId: string;
  intent: PositionExitIntent;
  protectPlan?: ProtectPlanV1 | null;
  stopOverrideReason?: string;
  /** V1.29 — plantilla activa si el wire aún no trae policyTemplateId. */
  policyTemplateId?: string | null;
  /** V1.34 B-γ — stop del ghost chart (salta resolveProtectSuggestedStop). */
  suggestedStopOverride?: number;
  /**
   * V1.34 — permitir encolar protect aunque haga falta motivo de override
   * (el ticket Confirm lo exige al firmar).
   */
  allowPendingOverride?: boolean;
}): SupervisedProposePayload {
  const {
    position,
    accountId,
    intent,
    protectPlan,
    stopOverrideReason,
    policyTemplateId,
    suggestedStopOverride,
    allowPendingOverride,
  } = opts;
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
    const fromOverride =
      typeof suggestedStopOverride === "number" &&
      Number.isFinite(suggestedStopOverride) &&
      suggestedStopOverride > 0
        ? suggestedStopOverride
        : null;
    const suggestedStop =
      fromOverride ?? resolveProtectSuggestedStop(position, protectPlan);
    if (suggestedStop == null) {
      throw new Error("Sin stop sugerido para proteger la posición.");
    }
    const { overrideRequired, allowed } = evaluateProtectStopOverride({
      direction: operational.direction,
      currentStop: operational.currentStop,
      suggestedStop,
      overrideReason: stopOverrideReason,
    });
    if (!allowed && allowPendingOverride !== true) {
      throw new Error(
        "El stop empeoraría el actual: escribe un motivo de override.",
      );
    }

    const now = new Date().toISOString();
    const primaryReason =
      typeof operational.exitPlan?.primaryReason === "string"
        ? operational.exitPlan.primaryReason
        : null;
    const revisionOrigin = revisionOriginFromExitReason(primaryReason);
    const protectMeta: OperativaProtectMetaV1 = {
      operativaIntent: "protect",
      suggestedStop,
      currentStop: operational.currentStop ?? null,
      direction: operational.direction,
      stopOverrideRequired: overrideRequired,
      revisionOrigin,
      primaryReason,
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
      notes: [
        revisionOrigin === "trail"
          ? "Trail → Confirm (stop amend · revision origin=trail · P4.2)"
          : "Proteger (stop amend) desde Consola de Mesa (P4.2)",
      ],
      decisionPackage: protectMeta,
    };
  }

  const action: DecisionAction =
    intent === "review" ? "wait" : intent === "reduce" ? "reduce" : "exit_hint";
  const qty = resolveExitQuantity(position, intent, policyTemplateId);
  if (qty <= 0) {
    throw new Error("Cantidad inválida para la salida.");
  }
  if (price == null) {
    throw new Error("Sin precio de referencia para el ticket de salida.");
  }

  const now = new Date().toISOString();
  const decisionId = operational.tradePlanId;
  const exitPlanDto = operational.exitPlan ?? null;
  const exitMeta: OperativaExitMetaV1 | null =
    intent === "reduce" || intent === "exit_hint"
      ? {
          operativaIntent: intent,
          exitSource: resolveExitSource(exitPlanDto),
          plannedQty: qty,
          exitPlan: exitPlanDto
            ? {
                status: exitPlanDto.status,
                suggestedAction: exitPlanDto.suggestedAction,
                primaryReason: exitPlanDto.primaryReason ?? null,
                suggestedQty: exitPlanDto.suggestedQty ?? null,
                suggestedStop: exitPlanDto.suggestedStop ?? null,
                policyTemplateId: exitPlanDto.policyTemplateId ?? null,
              }
            : null,
        }
      : null;

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
      ...(exitMeta
        ? [
            exitMeta.exitSource === "manual"
              ? "Salida MANUAL (firma humana · sin evento ExitPlan TRIGGERED/ARMED)"
              : `Salida por evento ExitPlan (${exitPlanDto?.primaryReason ?? "—"})`,
          ]
        : []),
    ],
    ...(exitMeta ? { decisionPackage: exitMeta } : {}),
  };
}
