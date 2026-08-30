import { describe, expect, it } from "vitest";
import { evaluateExitRiskSignature } from "./exit-risk-signature.js";

describe("evaluateExitRiskSignature", () => {
  it("allows when signed qty ≤ planned", () => {
    const v = evaluateExitRiskSignature({ plannedQty: 5, signedQty: 5 });
    expect(v.allowed).toBe(true);
    expect(v.overrideRequired).toBe(false);
    expect(v.blockReason).toBeNull();
  });

  it("requires override when signed exceeds planned", () => {
    const denied = evaluateExitRiskSignature({
      plannedQty: 3,
      signedQty: 5,
    });
    expect(denied.allowed).toBe(false);
    expect(denied.overrideRequired).toBe(true);
    expect(denied.blockReason).toBe("qty_exceeds_plan");

    const ok = evaluateExitRiskSignature({
      plannedQty: 3,
      signedQty: 5,
      overrideReason: "tomar más beneficio",
    });
    expect(ok.allowed).toBe(true);
  });

  it("no_plan allows when planned qty missing", () => {
    const v = evaluateExitRiskSignature({ plannedQty: null, signedQty: 2 });
    expect(v.mode).toBe("no_plan");
    expect(v.allowed).toBe(true);
  });

  it("denies invalid signed qty", () => {
    const v = evaluateExitRiskSignature({ plannedQty: 2, signedQty: 0 });
    expect(v.allowed).toBe(false);
    expect(v.blockReason).toBe("qty_invalid");
  });
});
