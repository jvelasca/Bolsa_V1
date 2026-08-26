/**
 * OR-4 — reconciliationOpeningVetoReason mirror tests.
 */

import { describe, expect, it } from "vitest";
import { reconciliationOpeningVetoReason } from "./cognitive/reconciliation-opening-veto.js";

describe("OR-4 reconciliationOpeningVetoReason", () => {
  it("gate off without require or status", () => {
    expect(reconciliationOpeningVetoReason()).toBeNull();
  });

  it("portfolio drift denies", () => {
    expect(
      reconciliationOpeningVetoReason({ portfolioReconStatus: "drift" }),
    ).toBe("reconciliation:portfolio_drift");
  });

  it("live unavailable denies only on live venue", () => {
    expect(
      reconciliationOpeningVetoReason({
        liveReconStatus: "unavailable",
        brokerVenue: "live",
        require: true,
      }),
    ).toBe("reconciliation:live_unavailable");
    expect(
      reconciliationOpeningVetoReason({
        liveReconStatus: "unavailable",
        brokerVenue: "paper",
        require: true,
      }),
    ).toBeNull();
  });

  it("live drift denies on live", () => {
    expect(
      reconciliationOpeningVetoReason({
        liveReconStatus: "drift",
        brokerVenue: "live",
      }),
    ).toBe("reconciliation:live_drift");
  });
});
