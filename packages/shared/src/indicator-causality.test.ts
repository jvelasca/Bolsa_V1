import { describe, expect, it } from "vitest";
import {
  INDICATOR_UNIVERSE,
  indicatorUniverseByCanonicalId,
} from "./indicator-universe.js";

const READY_STATES = new Set(["implemented", "validated", "production"]);

describe("indicator-causality-metadata (F-IND-1)", () => {
  it("IND-FR declares non-causal metadata", () => {
    const fr = indicatorUniverseByCanonicalId("IND-FR");
    expect(fr).toBeDefined();
    expect(fr!.causal).toBe(false);
    expect(fr!.confirmationLag).toBe(2);
    expect(fr!.visualizationOffset).toBe(0);
  });

  it("IND-ICH family is causal but chikou is marked non-causal", () => {
    const ich = indicatorUniverseByCanonicalId("IND-ICH");
    expect(ich).toBeDefined();
    // La familia es causal: spanA/spanB se dibujan desplazados (offset 26) pero
    // usan datos de i-26 (ya disponibles) → no implican look-ahead.
    expect(ich!.causal).toBe(true);
    expect(ich!.confirmationLag).toBe(0);
    expect(ich!.visualizationOffset).toBe(26);
    expect(ich!.outputKeys).toContain("chikou");
    // Solo la salida `chikou` es no causal.
    expect(ich!.nonCausalOutputKeys).toEqual(["chikou"]);
  });

  it("every implemented/production indicator declares causality metadata", () => {
    for (const item of INDICATOR_UNIVERSE) {
      if (!READY_STATES.has(item.status)) continue;
      expect(typeof item.causal, `${item.canonicalId}.causal`).toBe("boolean");
      expect(
        typeof item.confirmationLag,
        `${item.canonicalId}.confirmationLag`,
      ).toBe("number");
      expect(
        typeof item.visualizationOffset,
        `${item.canonicalId}.visualizationOffset`,
      ).toBe("number");
    }
  });

  it("implemented/production indicators are causal (default) with no confirmation lag", () => {
    for (const item of INDICATOR_UNIVERSE) {
      if (!READY_STATES.has(item.status)) continue;
      if (item.canonicalId === "IND-FR") continue;
      // chikou es la única salida no causal de ICH; la familia sigue siendo causal.
      expect(item.causal, `${item.canonicalId} should be causal`).toBe(true);
      expect(item.confirmationLag, `${item.canonicalId}.confirmationLag`).toBe(
        0,
      );
    }
  });

  it("non-causal output keys are consistent with outputKeys of ICH", () => {
    const ich = indicatorUniverseByCanonicalId("IND-ICH");
    const nonCausal = ich?.nonCausalOutputKeys ?? [];
    for (const key of nonCausal) {
      expect(ich!.outputKeys).toContain(key);
    }
  });
});
