/**
 * U4 — tests de mappers acción package + Fit (sin inventar PASS).
 */

import { describe, expect, it } from "vitest";
import {
  extractPackageChipFields,
  parseDecisionAction,
  pickQueueItemForInstrument,
  resolveDecisionActionChip,
  resolveFitChip,
} from "@/features/trading/decision-package-chips";

describe("parseDecisionAction", () => {
  it("accepts known DecisionAction values", () => {
    expect(parseDecisionAction("recommend_long")).toBe("recommend_long");
    expect(parseDecisionAction("exit_hint")).toBe("exit_hint");
  });

  it("rejects unknown / empty", () => {
    expect(parseDecisionAction("BUY")).toBeNull();
    expect(parseDecisionAction(null)).toBeNull();
    expect(parseDecisionAction(undefined)).toBeNull();
  });
});

describe("resolveDecisionActionChip", () => {
  it("prefers package action over recommendation", () => {
    const chip = resolveDecisionActionChip({
      packageAction: "wait",
      recommendationAction: "recommend_long",
    });
    expect(chip?.label).toBe("WAIT");
    expect(chip?.action).toBe("wait");
  });

  it("falls back to recommendation action", () => {
    const chip = resolveDecisionActionChip({
      recommendationAction: "recommend_long",
    });
    expect(chip?.label).toBe("LONG");
  });

  it("returns null without action", () => {
    expect(resolveDecisionActionChip({})).toBeNull();
  });
});

describe("resolveFitChip", () => {
  it("maps compliance passed → PASS", () => {
    expect(resolveFitChip({ compliancePassed: true })?.status).toBe("PASS");
  });

  it("maps compliance failed → VETO", () => {
    expect(resolveFitChip({ compliancePassed: false })?.label).toBe(
      "Fit · VETO",
    );
  });

  it("does not invent PASS from missing data", () => {
    expect(resolveFitChip({})).toBeNull();
    expect(
      resolveFitChip({
        executionAllowed: true,
        hasComplianceCheck: false,
      }),
    ).toBeNull();
    expect(resolveFitChip({ policyGateStatus: "SKIPPED" })).toBeNull();
  });

  it("uses executionAllowed only when complianceCheck present", () => {
    expect(
      resolveFitChip({
        hasComplianceCheck: true,
        executionAllowed: false,
      })?.status,
    ).toBe("VETO");
  });

  it("maps policyGate and opinion gate tokens", () => {
    expect(resolveFitChip({ policyGateStatus: "PASS" })?.status).toBe("PASS");
    expect(resolveFitChip({ policyGateStatus: "DENY" })?.status).toBe("VETO");
    expect(resolveFitChip({ opinionGateStatus: "WARNING" })?.status).toBe(
      "WARNING",
    );
  });

  it("prefers compliance over opinion", () => {
    expect(
      resolveFitChip({
        compliancePassed: false,
        opinionGateStatus: "PASS",
      })?.status,
    ).toBe("VETO");
  });
});

describe("extractPackageChipFields + pickQueueItemForInstrument", () => {
  it("reads package blob fields", () => {
    const fields = extractPackageChipFields({
      action: "recommend_long",
      decisionPackage: {
        action: "exit_hint",
        executionAllowed: false,
        complianceCheck: { passed: false },
      },
      policyGate: { status: "SKIPPED" },
    });
    expect(fields.packageAction).toBe("exit_hint");
    expect(fields.hasComplianceCheck).toBe(true);
    expect(fields.compliancePassed).toBe(false);
    expect(fields.executionAllowed).toBe(false);
  });

  it("picks active queue item for instrument", () => {
    const items = [
      { id: "a", payload: { instrumentId: "i1" } },
      { id: "b", payload: { instrumentId: "i2" } },
      { id: "c", payload: { instrumentId: "i1" } },
    ];
    expect(pickQueueItemForInstrument(items, "i1", "c")?.id).toBe("c");
    expect(pickQueueItemForInstrument(items, "i1")?.id).toBe("a");
    expect(pickQueueItemForInstrument(items, "missing")).toBeNull();
  });
});
