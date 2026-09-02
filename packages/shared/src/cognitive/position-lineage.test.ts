import { describe, expect, it } from "vitest";
import { resolvePositionOriginLineage } from "./position-lineage.js";

describe("resolvePositionOriginLineage", () => {
  it("orphans when tradePlanId missing", () => {
    const ref = resolvePositionOriginLineage({
      originStudy: { decisionId: "D1", instrumentId: "i1" },
      positionInstrumentId: "i1",
    });
    expect(ref.originDecisionId).toBeNull();
    expect(ref.packageAvailable).toBe(false);
    expect(ref.orphanReason).toBe("missing_decision_id");
  });

  it("resolves when study decisionId matches tradePlanId", () => {
    const ref = resolvePositionOriginLineage({
      tradePlanId: "D1",
      originStudy: { decisionId: "D1", instrumentId: "i1" },
      positionInstrumentId: "i1",
    });
    expect(ref.originDecisionId).toBe("D1");
    expect(ref.thesisId).toBe("D1");
    expect(ref.packageAvailable).toBe(true);
    expect(ref.orphanReason).toBeNull();
  });

  it("does not adopt same-instrument study with other decisionId", () => {
    const ref = resolvePositionOriginLineage({
      tradePlanId: "D1",
      originStudy: { decisionId: "D-OTHER", instrumentId: "i1" },
      positionInstrumentId: "i1",
    });
    expect(ref.originDecisionId).toBe("D1");
    expect(ref.packageAvailable).toBe(false);
    expect(ref.orphanReason).toBe("package_missing");
  });

  it("orphans session_not_found when no study candidate", () => {
    const ref = resolvePositionOriginLineage({
      tradePlanId: "D1",
      originStudy: null,
      positionInstrumentId: "i1",
    });
    expect(ref.packageAvailable).toBe(false);
    expect(ref.orphanReason).toBe("session_not_found");
  });

  it("flags instrument_mismatch", () => {
    const ref = resolvePositionOriginLineage({
      tradePlanId: "D1",
      originStudy: { decisionId: "D1", instrumentId: "OTHER" },
      positionInstrumentId: "i1",
    });
    expect(ref.packageAvailable).toBe(false);
    expect(ref.orphanReason).toBe("instrument_mismatch");
  });

  it("GP-V165-03: positionDecisionId wins over tradePlanId", () => {
    const ref = resolvePositionOriginLineage({
      positionDecisionId: "DEC-1",
      tradePlanId: "TP-1",
      originStudy: { decisionId: "DEC-1", instrumentId: "i1" },
      positionInstrumentId: "i1",
    });
    expect(ref.originDecisionId).toBe("DEC-1");
    expect(ref.originDecisionId).not.toBe("TP-1");
    expect(ref.packageAvailable).toBe(true);
  });
});
