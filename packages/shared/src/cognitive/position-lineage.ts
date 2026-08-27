/**
 * V1.18 L1 — Position → DecisionPackage lineage (proyección, fail-closed).
 * Origen = decisionId / tradePlanId. Soft-join por instrumento ≠ autoridad.
 */

export type PositionLineageOrphanReasonV1 =
  | "missing_decision_id"
  | "session_not_found"
  | "package_missing"
  | "instrument_mismatch";

export type PositionLineageRefV1 = {
  originDecisionId: string | null;
  thesisId: string | null;
  packageAvailable: boolean;
  orphanReason: PositionLineageOrphanReasonV1 | null;
};

export type ResolvePositionOriginLineageInput = {
  /** Explicit override; otherwise tradePlanId. */
  originDecisionId?: string | null;
  tradePlanId?: string | null;
  /** Optional thesis id from TradePlan snapshot (defaults to originDecisionId). */
  thesisId?: string | null;
  positionInstrumentId?: string | null;
  /**
   * Candidate origin study/package view. Matching is by decisionId only.
   * Latest study of the same instrument does NOT count unless ids match.
   */
  originStudy?: {
    decisionId?: string | null;
    instrumentId?: string | null;
  } | null;
};

function trimId(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const t = value.trim();
  return t.length > 0 ? t : null;
}

/**
 * Resolve lineage of a live position to its origin decision.
 * Never invents BUY / DecisionPackage. Orphan = fail-closed.
 */
export function resolvePositionOriginLineage(
  input: ResolvePositionOriginLineageInput,
): PositionLineageRefV1 {
  const originDecisionId =
    trimId(input.originDecisionId) ?? trimId(input.tradePlanId);
  const thesisId = trimId(input.thesisId) ?? originDecisionId;

  if (!originDecisionId) {
    return {
      originDecisionId: null,
      thesisId: null,
      packageAvailable: false,
      orphanReason: "missing_decision_id",
    };
  }

  const study = input.originStudy;
  if (!study) {
    return {
      originDecisionId,
      thesisId,
      packageAvailable: false,
      orphanReason: "session_not_found",
    };
  }

  const studyDecisionId = trimId(study.decisionId);
  if (!studyDecisionId || studyDecisionId !== originDecisionId) {
    return {
      originDecisionId,
      thesisId,
      packageAvailable: false,
      orphanReason: "package_missing",
    };
  }

  const positionInstrumentId = trimId(input.positionInstrumentId);
  const studyInstrumentId = trimId(study.instrumentId);
  if (
    positionInstrumentId &&
    studyInstrumentId &&
    positionInstrumentId !== studyInstrumentId
  ) {
    return {
      originDecisionId,
      thesisId,
      packageAvailable: false,
      orphanReason: "instrument_mismatch",
    };
  }

  return {
    originDecisionId,
    thesisId,
    packageAvailable: true,
    orphanReason: null,
  };
}
