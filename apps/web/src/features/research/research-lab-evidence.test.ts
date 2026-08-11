import { describe, expect, it } from "vitest";
import type { ResearchTrialDto } from "@bolsa/shared";
import { summarizeLabEvidenceFromTrial } from "@/features/research/research-lab-evidence";

function trial(partial: Partial<ResearchTrialDto>): ResearchTrialDto {
  return {
    id: "t1",
    instrumentId: "i1",
    params: {},
    isMetrics: {},
    proposedBy: "grid",
    kContribution: 1,
    createdAt: "2026-07-26T00:00:00Z",
    ...partial,
  };
}

describe("summarizeLabEvidenceFromTrial (Observatory P5)", () => {
  it("returns empty when blocks have no lab validation", () => {
    const s = summarizeLabEvidenceFromTrial(trial({ blocks: { foo: 1 } }));
    expect(s.hasLab).toBe(false);
    expect(s.compact).toBe("—");
    expect(s.modeLabel).toBe("—");
  });

  it("summarizes hold-out OOS", () => {
    const s = summarizeLabEvidenceFromTrial(
      trial({
        blocks: {
          oosMetrics: { score: 4.2, totalReturnPct: 3 },
        },
      }),
    );
    expect(s.hasLab).toBe(true);
    expect(s.kind).toBe("holdout");
    expect(s.compact).toContain("Hold-out");
    expect(s.compact).toContain("OOS 4.2");
  });

  it("summarizes CPCV with WFE, PBO, Edge and persisted EdgeReport id", () => {
    const s = summarizeLabEvidenceFromTrial(
      trial({
        blocks: {
          cpcv: {
            meanOosScore: 2.4,
            pathCount: 10,
            walkForwardEfficiency: 0.65,
          },
          pbo: { pbo: 0.55 },
          edgeReport: {
            credibility: 58,
            band: "uncertain",
            persistedEdgeReportId: "EDGE-persisted-1",
          },
          labEvidence: { wfeSource: "lab_score", mode: "cpcv" },
        },
      }),
    );
    expect(s.kind).toBe("cpcv");
    expect(s.modeLabel).toBe("CPCV");
    expect(s.compact).toMatch(/CPCV/);
    expect(s.compact).toMatch(/WFE 0\.65/);
    expect(s.compact).toMatch(/PBO 0\.55/);
    expect(s.compact).toMatch(/Edge uncertain/);
    expect(s.compact).toMatch(/ER EDGE-pers/);
  });

  it("summarizes walk-forward WFE", () => {
    const s = summarizeLabEvidenceFromTrial(
      trial({
        blocks: {
          walkForward: {
            meanOosScore: 1.5,
            nFolds: 3,
            walkForwardEfficiency: 0.72,
          },
        },
      }),
    );
    expect(s.kind).toBe("walkforward");
    expect(s.compact).toMatch(/WF/);
    expect(s.compact).toMatch(/WFE 0\.72/);
    expect(s.compact).toMatch(/aceptable/);
  });
});
