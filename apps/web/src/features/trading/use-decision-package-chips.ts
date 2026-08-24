/**
 * U4 — resuelve chips acción+Fit para el instrumento activo (cola F3 + dictamen).
 */

import {
  extractPackageChipFields,
  pickQueueItemForInstrument,
  resolveDecisionActionChip,
  resolveFitChip,
  type DecisionActionChipView,
  type FitChipView,
} from "@/features/trading/decision-package-chips";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";

export function useDecisionPackageChips(opts: {
  instrumentId: string | null | undefined;
  /** gateStatus del dictamen diario (PASS/VETO/WARNING) si existe. */
  opinionGateStatus?: string | null;
}): {
  action: DecisionActionChipView | null;
  fit: FitChipView | null;
  hasQueuePackage: boolean;
} {
  const items = useSupervisedF3QueueStore((s) => s.items);
  const activeId = useSupervisedF3QueueStore((s) => s.activeId);

  const item = pickQueueItemForInstrument(items, opts.instrumentId, activeId);
  const fields = item
    ? extractPackageChipFields(item.payload)
    : {
        packageAction: undefined,
        recommendationAction: undefined,
        compliancePassed: null as boolean | null,
        executionAllowed: null as boolean | null,
        hasComplianceCheck: false,
        policyGateStatus: null as unknown,
      };

  const action = resolveDecisionActionChip({
    packageAction: fields.packageAction,
    recommendationAction: fields.recommendationAction,
  });

  const fit = resolveFitChip({
    compliancePassed: fields.compliancePassed,
    executionAllowed: fields.executionAllowed,
    hasComplianceCheck: fields.hasComplianceCheck,
    policyGateStatus: fields.policyGateStatus,
    opinionGateStatus: opts.opinionGateStatus,
  });

  return {
    action,
    fit,
    hasQueuePackage: Boolean(item),
  };
}
