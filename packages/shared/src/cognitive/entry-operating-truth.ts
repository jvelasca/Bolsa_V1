/**
 * EntryOperatingTruth — proyección canónica pre-posición (V1.38).
 * Composición: fase cockpit + OperationalPlanView + sizing del study.
 * Mercado / Hoy / Journal leen la misma fase, CTA y frase. No BUY.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  JOURNAL_STUDY_VIGENCIA_LABELS,
  type JournalStudyVigencia,
} from "./decision-journal-study.js";
import {
  entryOperatingCtaFromPhase,
  formatEntryOperatingPhrase,
  formatEntryTriggerLabel,
  isEntryOperatingPhase,
  mesaNextActionFromEntryTruth,
  type EntryOperatingCtaV1,
  type EntryOperatingPhaseV1,
} from "./entry-operating-copy.js";
import type { MesaNextActionV1 } from "./mesa-next-action.js";
import {
  MERCADO_COCKPIT_PHASE_LABEL,
  resolveMercadoCockpitPhase,
} from "./mercado-cockpit-phase.js";
import {
  buildOperationalPlanFromStudy,
  type OperationalPlanViewV1,
} from "./operational-plan-view.js";
import { formatOperationalAsOf } from "./operational-truth.js";

export type EntryOperatingSizingV1 = {
  riskAmount: number | null;
  riskR: number | null;
  expectedRR: number | null;
  positionValue: number | null;
  quantity: number | null;
};

export type EntryOperatingTruthV1 = {
  instrumentId: string;
  symbol: string;
  phase: EntryOperatingPhaseV1;
  phaseLabel: string;
  plan: OperationalPlanViewV1;
  primaryCta: EntryOperatingCtaV1;
  phrase: string;
  triggerLabel: string;
  sizing: EntryOperatingSizingV1;
  asOf: string | null;
  expiryLabel: string | null;
  entriesBlocked: boolean;
  gateStatus: string | null;
};

export type BuildEntryOperatingTruthInputV1 = {
  study: DecisionJournalStudyViewV1;
  hasOpenPosition?: boolean;
  inConfirmQueue?: boolean;
  orderPendingFill?: boolean;
  inEstudio?: boolean;
  entriesBlocked?: boolean;
  gateStatus?: string | null;
  asOf?: string | null;
};

export type EntryOperatingSurfaceSnapshotV1 = {
  phase: EntryOperatingPhaseV1;
  phaseLabel: string;
  ctaLabel: string;
  ctaKind: EntryOperatingCtaV1["kind"];
  phrase: string;
  triggerLabel: string;
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
  expectedRR: number | null;
  riskAmount: number | null;
  asOf: string | null;
};

function expiryLabelFromStudy(
  study: DecisionJournalStudyViewV1,
): string | null {
  if (study.nextReviewAt?.trim()) {
    return `Revisión ${study.nextReviewAt.trim()}`;
  }
  const vigencia = study.vigencia as JournalStudyVigencia | null;
  if (vigencia && vigencia in JOURNAL_STUDY_VIGENCIA_LABELS) {
    return JOURNAL_STUDY_VIGENCIA_LABELS[vigencia];
  }
  return null;
}

export function buildEntryOperatingTruth(
  input: BuildEntryOperatingTruthInputV1,
): EntryOperatingTruthV1 | null {
  const { study } = input;
  if (input.hasOpenPosition) return null;

  const plan = buildOperationalPlanFromStudy(study);
  const phase = resolveMercadoCockpitPhase({
    instrumentId: study.instrumentId,
    inEstudio: input.inEstudio ?? true,
    hasOpenPosition: false,
    inConfirmQueue: input.inConfirmQueue ?? false,
    orderPendingFill: input.orderPendingFill ?? false,
    tradePlanStatus: study.tradePlanStatus,
    hasOperationalPlan: study.hasOperationalPlan === true || plan.hasPlan,
  });

  if (!isEntryOperatingPhase(phase)) return null;
  if (!plan.hasPlan && phase !== "confirmada") return null;

  const entriesBlocked = input.entriesBlocked === true;
  const gateStatus = input.gateStatus ?? null;
  const primaryCta = entryOperatingCtaFromPhase(phase, {
    entriesBlocked,
    gateStatus,
  });

  const asOf =
    typeof input.asOf === "string" && input.asOf.trim()
      ? input.asOf.trim()
      : study.studiedAt?.trim() || null;

  return {
    instrumentId: study.instrumentId,
    symbol: study.symbol ?? study.instrumentId,
    phase,
    phaseLabel: MERCADO_COCKPIT_PHASE_LABEL[phase],
    plan,
    primaryCta,
    phrase: formatEntryOperatingPhrase(phase, { entriesBlocked, gateStatus }),
    triggerLabel: formatEntryTriggerLabel(phase),
    sizing: {
      riskAmount: study.riskAmount,
      riskR: study.initialRiskR ?? plan.riskR,
      expectedRR: study.expectedRR ?? plan.expectedRR,
      positionValue: study.positionValue,
      quantity: study.quantity,
    },
    asOf,
    expiryLabel: expiryLabelFromStudy(study),
    entriesBlocked,
    gateStatus,
  };
}

export function entryOperatingSurfaceSnapshot(
  truth: EntryOperatingTruthV1,
): EntryOperatingSurfaceSnapshotV1 {
  return {
    phase: truth.phase,
    phaseLabel: truth.phaseLabel,
    ctaLabel: truth.primaryCta.label,
    ctaKind: truth.primaryCta.kind,
    phrase: truth.phrase,
    triggerLabel: truth.triggerLabel,
    entry: truth.plan.entry,
    stop: truth.plan.stopVigente,
    target1: truth.plan.target1,
    target2: truth.plan.target2,
    expectedRR: truth.sizing.expectedRR,
    riskAmount: truth.sizing.riskAmount,
    asOf: truth.asOf,
  };
}

export function mesaNextActionFromEntryOperatingTruth(
  truth: EntryOperatingTruthV1,
): MesaNextActionV1 {
  return mesaNextActionFromEntryTruth({
    phase: truth.phase,
    primaryCta: truth.primaryCta,
  });
}

export function formatEntryOperatingAsOf(asOf: string | null): string | null {
  return formatOperationalAsOf(asOf);
}
