import { describe, expect, it } from "vitest";
import {
  buildFinalistsLabEvidenceSnapshot,
  finalistsStabilityWarnTitle,
  formatFinalistsStabilityBadge,
  mergeLabEvidenceIntoCoachFacts,
  readLabEvidenceFromCoachFacts,
} from "@/features/backtests/finalists-stability-summary";

describe("finalists-stability-summary (Q3.2)", () => {
  it("reads labEvidence from coachFacts", () => {
    expect(
      readLabEvidenceFromCoachFacts({
        labEvidence: { kind: "walkforward", walkForwardEfficiency: 0.72 },
      })?.kind,
    ).toBe("walkforward");
    expect(readLabEvidenceFromCoachFacts({})).toBeNull();
  });

  it("formats badge with Lab vocabulary", () => {
    const badge = formatFinalistsStabilityBadge({
      kind: "walkforward",
      walkForwardEfficiency: 0.72,
    });
    expect(badge).toMatch(/WF/);
    expect(badge).toMatch(/WFE/);
    expect(formatFinalistsStabilityBadge({ kind: "none" })).toBeNull();
  });

  it("warns on weak WFE", () => {
    expect(
      finalistsStabilityWarnTitle({
        kind: "walkforward",
        walkForwardEfficiency: 0.2,
      }),
    ).toMatch(/WFE débil/);
  });

  it("merges snapshot into facts", () => {
    const snap = buildFinalistsLabEvidenceSnapshot({
      kind: "holdout",
      oosScore: 6.5,
    });
    const facts = mergeLabEvidenceIntoCoachFacts(
      { coachPass: "post_lab" },
      snap,
    );
    expect(facts.labEvidence).toMatchObject({ kind: "holdout", oosScore: 6.5 });
    expect(formatFinalistsStabilityBadge(snap)).toMatch(/Hold-out/);
  });
});
