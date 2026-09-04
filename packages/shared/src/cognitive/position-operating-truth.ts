/**
 * PositionOperatingTruth — proyección canónica de posición abierta (V1.42 F3).
 * Compone OperationalTruth + ExecutionState + protect/route facts.
 * No sustituye OperationalTruth. No motor. No tabla.
 *
 * Spec: docs/engineering/spec-v142-operating-excellence-2026-08-31.md §A.5 + §A.8
 */

import type { PositionDto } from "../types.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildExecutionState,
  formatExecutionStateCopy,
  type BuildExecutionStateInputV1,
  type ExecutionStateV1,
  type PaperAutoLedgerFactV1,
} from "./execution-state.js";
import type { ExecutionRecordV1 } from "./execution-record.js";
import { buildExitRouteView, type ExitRouteViewV1 } from "./exit-route-view.js";
import { buildInvestmentPositionAggregate } from "./investment-position-aggregate.js";
import {
  MESA_NEXT_ACTION_LABELS,
  mapMesaNextAction,
  type MesaNextActionV1,
} from "./mesa-next-action.js";
import {
  buildOperationalTruth,
  formatExecutionHintCopy,
  formatOperationalAsOf,
  mesaNextActionFromOperationalTruth,
  type OperationalTruthV1,
} from "./operational-truth.js";
import type { PaperOrderV1 } from "./paper-order.js";
import {
  formatPositionDecisionPhrase,
  type PositionOperatingCtaV1,
} from "./position-decision-copy.js";
import type { PositionAttentionV1 } from "./position-decision.js";
import type { ProtectPlanV1 } from "./protect-plan.js";
import type { DurableSubmitIntentV1 } from "./submit-intent.js";
import {
  buildPositionOperationalView,
  type PositionOperationalViewV1,
} from "./position-operational-view.js";
import { positionStateFromPositionDto } from "./position-state-from-dto.js";
import type { PaperDeskNextActionV1 } from "./operational-context.js";
import { mapPortfolioReconToPovRecon } from "./reconciliation-opening-veto.js";
import {
  buildOperatorDecision,
  mesaNextActionFromOperatorDecision,
  type OperatorCabinTruthV1,
} from "./operator-cabin-view.js";

export type PositionSecondaryConditionKindV1 =
  | "protection_discrepancy"
  | "trail_hint_not_applied"
  | "recon_attention"
  | "recommended_not_executed";

export type PositionSecondaryConditionV1 = {
  kind: PositionSecondaryConditionKindV1;
  label: string;
};

const SECONDARY_LABELS: Record<PositionSecondaryConditionKindV1, string> = {
  protection_discrepancy: "⚠️ Protección discrepante",
  /** GP-08 / §A.9 — hint ≠ currentStop; never auto-promotes. */
  trail_hint_not_applied: "Trail no aplicado · requiere Confirm",
  recon_attention: "Reconciliación requiere atención",
  recommended_not_executed: "Acción recomendada · aún no ejecutada",
};

export type PositionOperatingTruthV1 = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  asOf: string | null;
  operational: OperationalTruthV1;
  execution: ExecutionStateV1;
  exitRoute: ExitRouteViewV1 | null;
  protectPlan: ProtectPlanV1 | null;
  protectionDiscrepancy: boolean;
  /** V1.55 — canonical operational projection (backend-derived when available). */
  operationalView: PositionOperationalViewV1 | null;
  primaryCta: MesaNextActionV1;
  phrase: string;
  secondaryConditions: PositionSecondaryConditionV1[];
  attention: PositionAttentionV1;
};

export type BuildPositionOperatingTruthInputV1 = {
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  portfolioReconStatus?: string | null;
  asOf?: string | null;
  orderPending?: boolean;
  submitIntent?: DurableSubmitIntentV1 | null;
  paperOrder?: PaperOrderV1 | null;
  executionRecord?: ExecutionRecordV1 | null;
  paperAutoLedger?: PaperAutoLedgerFactV1 | null;
  orderReconciled?: boolean;
  hasOpenIncident?: boolean;
  reconLookupFailed?: boolean;
  protectPlan?: ProtectPlanV1 | null;
  /** Override; si falta, se deriva del aggregate / mesa protection. */
  protectionDiscrepancy?: boolean;
  includeExitRoute?: boolean;
};

export type PositionOperatingTruthSurfaceSnapshotV1 = {
  ctaKind: MesaNextActionV1["kind"];
  ctaLabel: string;
  phrase: string;
  protectionDiscrepancy: boolean;
  secondaryKinds: PositionSecondaryConditionKindV1[];
  executionLifecycle: ExecutionStateV1["lifecycle"];
  executionOrderState: ExecutionStateV1["orderState"];
  attention: PositionAttentionV1;
  asOf: string | null;
};

function secondary(
  kind: PositionSecondaryConditionKindV1,
): PositionSecondaryConditionV1 {
  return { kind, label: SECONDARY_LABELS[kind] };
}

/**
 * §A.8 overlay on OperationalTruth CTA:
 * exit|reduce keep primary; discrepancy alone → protect; review stays review.
 */
export function applyProtectionDiscrepancyToCta(
  base: MesaNextActionV1,
  protectionDiscrepancy: boolean,
): {
  primaryCta: MesaNextActionV1;
  discrepancyIsSecondary: boolean;
} {
  if (!protectionDiscrepancy) {
    return { primaryCta: base, discrepancyIsSecondary: false };
  }
  if (base.kind === "exit" || base.kind === "reduce") {
    return { primaryCta: base, discrepancyIsSecondary: true };
  }
  if (base.kind === "review") {
    return { primaryCta: base, discrepancyIsSecondary: true };
  }
  return {
    primaryCta: {
      kind: "protect",
      label: MESA_NEXT_ACTION_LABELS.protect,
      allowsEntry: false,
    },
    discrepancyIsSecondary: false,
  };
}

function resolveProtectionDiscrepancy(
  input: BuildPositionOperatingTruthInputV1,
): boolean {
  if (typeof input.protectionDiscrepancy === "boolean") {
    return input.protectionDiscrepancy;
  }
  const aggregate = buildInvestmentPositionAggregate({
    position: input.position,
    study: input.study,
    originStudy: input.originStudy,
    protectPlan: input.protectPlan,
  });
  return aggregate.currentState.protectionDiscrepancy;
}

/** Wire exitPlan (Mesa/aggregate parity) — OT may recompute from mark. */
function wireExitSuggestedAction(
  position: PositionDto,
): "hold" | "protect" | "reduce" | "full_exit" | null {
  const raw = position.operational?.exitPlan?.suggestedAction;
  if (
    raw === "hold" ||
    raw === "protect" ||
    raw === "reduce" ||
    raw === "full_exit"
  ) {
    return raw;
  }
  return null;
}

/**
 * CTA base: REVIEW (recon) gana; si no, wire full_exit/reduce (§A.8);
 * si no, OT + overlay discrepancia.
 */
function resolveBaseCta(input: {
  operational: OperationalTruthV1;
  position: PositionDto;
  protectionDiscrepancy: boolean;
  protectPlan: ProtectPlanV1 | null | undefined;
}): {
  primaryCta: MesaNextActionV1;
  discrepancyIsSecondary: boolean;
} {
  const otCta = mesaNextActionFromOperationalTruth(input.operational);
  if (otCta.kind === "review") {
    return applyProtectionDiscrepancyToCta(otCta, input.protectionDiscrepancy);
  }
  const wireExit = wireExitSuggestedAction(input.position);
  if (wireExit === "full_exit" || wireExit === "reduce") {
    const mapped = mapMesaNextAction({
      exitSuggestedAction: wireExit,
      protectPlan: input.protectPlan ?? null,
      hasOpenPosition: true,
      protectionDiscrepancy: input.protectionDiscrepancy,
    });
    return {
      primaryCta: mapped,
      discrepancyIsSecondary: input.protectionDiscrepancy,
    };
  }
  return applyProtectionDiscrepancyToCta(otCta, input.protectionDiscrepancy);
}

function buildSecondaryConditions(input: {
  discrepancyIsSecondary: boolean;
  operational: OperationalTruthV1;
}): PositionSecondaryConditionV1[] {
  const out: PositionSecondaryConditionV1[] = [];
  // §A.8: discrepancy is secondary only when primary stayed exit|reduce|review.
  if (input.discrepancyIsSecondary) {
    out.push(secondary("protection_discrepancy"));
  }
  if (
    input.operational.trailing.hint != null &&
    !input.operational.trailing.applied
  ) {
    out.push(secondary("trail_hint_not_applied"));
  }
  if (input.operational.reconHealth === "ATTENTION") {
    out.push(secondary("recon_attention"));
  }
  if (input.operational.executionHint === "recommended_not_executed") {
    out.push(secondary("recommended_not_executed"));
  }
  return out;
}

export function buildPositionOperatingTruth(
  input: BuildPositionOperatingTruthInputV1,
): PositionOperatingTruthV1 | null {
  const operational = buildOperationalTruth({
    position: input.position,
    study: input.study,
    originStudy: input.originStudy,
    portfolioReconStatus: input.portfolioReconStatus,
    asOf: input.asOf,
    orderPending: input.orderPending,
  });
  if (!operational) return null;

  const protectionDiscrepancy = resolveProtectionDiscrepancy(input);
  const { primaryCta: baseCta, discrepancyIsSecondary } = resolveBaseCta({
    operational,
    position: input.position,
    protectionDiscrepancy,
    protectPlan: input.protectPlan,
  });

  const executionInput: BuildExecutionStateInputV1 = {
    instrumentId: operational.instrumentId,
    asOf: operational.asOf,
    pendingOrder: input.orderPending ?? false,
    submitIntent: input.submitIntent ?? null,
    paperOrder: input.paperOrder ?? null,
    executionRecord: input.executionRecord ?? null,
    paperAutoLedger: input.paperAutoLedger ?? null,
    orderReconciled: input.orderReconciled,
    portfolioReconStatus: input.portfolioReconStatus,
    hasOpenIncident: input.hasOpenIncident,
    reconLookupFailed: input.reconLookupFailed,
    protectionActive: operational.protection === "ACTIVE",
    trailingHint:
      Boolean(operational.trailing.hint) && !operational.trailing.applied,
    trailingApplied: operational.trailing.applied,
    nextAction: baseCta,
  };
  const execution = buildExecutionState(executionInput);
  const primaryCta = execution.nextAction ?? baseCta;

  const secondaryConditions = buildSecondaryConditions({
    discrepancyIsSecondary,
    operational,
  });

  const exitRoute =
    input.includeExitRoute === false
      ? null
      : buildExitRouteView({
          truth: operational,
          position: input.position,
          study: input.study,
          originStudy: input.originStudy,
        });

  const stateFromDto = positionStateFromPositionDto(input.position);
  const operationalView = stateFromDto
    ? buildPositionOperationalView({
        position: stateFromDto,
        reconStatus: mapPortfolioReconToPovRecon(input.portfolioReconStatus),
        deskStatus: mapOperatingStateToDeskStatusFromCta(primaryCta),
        decisionVerdict: operational.decision.action,
        templateId: null,
      })
    : null;

  return {
    instrumentId: operational.instrumentId,
    symbol: operational.symbol,
    positionId: operational.positionId,
    asOf: operational.asOf,
    operational,
    execution,
    exitRoute,
    protectPlan: input.protectPlan ?? null,
    protectionDiscrepancy,
    operationalView,
    primaryCta,
    phrase: formatPositionDecisionPhrase(operational.decision),
    secondaryConditions,
    attention: operational.attention,
  };
}

export function positionOperatingTruthSurfaceSnapshot(
  truth: PositionOperatingTruthV1,
): PositionOperatingTruthSurfaceSnapshotV1 {
  return {
    ctaKind: truth.primaryCta.kind,
    ctaLabel: truth.primaryCta.label,
    phrase: truth.phrase,
    protectionDiscrepancy: truth.protectionDiscrepancy,
    secondaryKinds: truth.secondaryConditions.map((c) => c.kind),
    executionLifecycle: truth.execution.lifecycle,
    executionOrderState: truth.execution.orderState,
    attention: truth.attention,
    asOf: truth.asOf,
  };
}

export function operatorCabinTruthFromPot(
  truth: PositionOperatingTruthV1,
): OperatorCabinTruthV1 {
  const view = truth.operationalView;
  const executedStop =
    view?.levels.currentStop ?? truth.operational.levels.stopOperativo ?? null;
  const primaryAction: PaperDeskNextActionV1 =
    view?.primaryAction ??
    (truth.primaryCta.kind === "exit"
      ? "SALIR"
      : truth.primaryCta.kind === "reduce"
        ? "REDUCIR"
        : truth.primaryCta.kind === "protect"
          ? "SUBIR_STOP"
          : truth.primaryCta.kind === "review"
            ? "REVISAR_DATOS_NO_FRESCOS"
            : "MANTENER");
  return {
    kind: "position",
    primaryAction,
    persistSkipped: truth.protectionDiscrepancy,
    protectionDiscrepancy: truth.protectionDiscrepancy,
    currentStop: executedStop,
    entry: view?.levels.entry ?? truth.operational.levels.entry,
    birthQuantity: view?.quantity ?? null,
    remainingQuantity: view?.remainingQuantity ?? null,
    closed: view?.operatingState === "CLOSED",
    templateId: view?.templateId ?? null,
  };
}

export function mesaNextActionFromPositionOperatingTruth(
  truth: PositionOperatingTruthV1,
): MesaNextActionV1 {
  const cta = truth.primaryCta;
  if (cta.kind === "exit" || cta.kind === "reduce") {
    return {
      kind: cta.kind,
      label: cta.label,
      allowsEntry: false,
    };
  }
  const decision = buildOperatorDecision(operatorCabinTruthFromPot(truth));
  const mesa = mesaNextActionFromOperatorDecision(decision);
  if (mesa.kind === "protect") return mesa;
  if (cta.kind === "review") {
    return { kind: cta.kind, label: cta.label, allowsEntry: false };
  }
  return mesa;
}

/** Compat: PositionOperatingCta from POT primary (subset of mesa kinds). */
export function positionOperatingCtaFromPot(
  truth: PositionOperatingTruthV1,
): PositionOperatingCtaV1 | null {
  const kind = truth.primaryCta.kind;
  if (
    kind === "maintain" ||
    kind === "protect" ||
    kind === "reduce" ||
    kind === "exit" ||
    kind === "review"
  ) {
    return { kind, label: truth.primaryCta.label };
  }
  return null;
}

export function formatPositionOperatingAsOf(
  asOf: string | null,
): string | null {
  return formatOperationalAsOf(asOf);
}

/**
 * Copy de ciclo: ExecutionState gana a recommended_not_executed.
 */
export function formatPositionOperatingExecutionCopy(
  truth: PositionOperatingTruthV1,
): string | null {
  return (
    formatExecutionStateCopy(truth.execution) ??
    formatExecutionHintCopy(truth.operational)
  );
}

function mapOperatingStateToDeskStatusFromCta(cta: MesaNextActionV1): string {
  switch (cta.kind) {
    case "protect":
      return "protected";
    case "reduce":
      return "reduced";
    case "exit":
      return "exited";
    case "review":
      return "denied";
    default:
      return "held";
  }
}
