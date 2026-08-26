/**
 * OperationalIncident DEX-3 — review → resolve → clear (ADR-035).
 */

import { describe, expect, it } from "vitest";
import {
  canClear,
  clearIncident,
  incidentBlocksOpening,
  incidentOpeningVetoReason,
  kindsFromRecon,
  markInReview,
  openIncident,
  operationalIncidentStatusCopy,
  resolveIncident,
} from "./cognitive/operational-incident.js";

function opened() {
  return openIncident({
    incidentId: "inc-1",
    accountId: "acc-1",
    kind: "portfolio_drift",
    snapshot: "cash_ledger mismatch",
    now: "2026-08-26T12:00:00.000Z",
  });
}

describe("DEX-3 OperationalIncident", () => {
  it("open starts active and blocks opening", () => {
    const inc = opened();
    expect(inc.status).toBe("open");
    expect(incidentBlocksOpening(inc.status)).toBe(true);
    expect(inc.incidentId).toBe("inc-1");
  });

  it("open → review → resolve → clear", () => {
    const reviewed = markInReview(opened(), {
      reviewedBy: "op",
      now: "2026-08-26T12:01:00.000Z",
    });
    expect(reviewed.status).toBe("in_review");
    const resolved = resolveIncident(reviewed, {
      resolutionNote: "cash aligned after manual deposit",
      resolvedBy: "op",
      now: "2026-08-26T12:02:00.000Z",
    });
    expect(resolved.status).toBe("resolved");
    expect(canClear(resolved, "clean")).toBe(true);
    const cleared = clearIncident(resolved, {
      reconStatus: "clean",
      now: "2026-08-26T12:03:00.000Z",
    });
    expect(cleared.status).toBe("cleared");
    expect(incidentBlocksOpening(cleared.status)).toBe(false);
  });

  it("resolve requires a note", () => {
    expect(() => resolveIncident(opened(), { resolutionNote: "  " })).toThrow(
      /resolution_note_required/,
    );
  });

  it("clear while drift fails; no auto-heal", () => {
    const resolved = resolveIncident(opened(), { resolutionNote: "looking" });
    expect(canClear(resolved, "drift")).toBe(false);
    expect(() => clearIncident(resolved, { reconStatus: "drift" })).toThrow(
      /recon_not_clean/,
    );
    expect(operationalIncidentStatusCopy("resolved")).toMatch(/auto-heal/i);
  });

  it("kindsFromRecon: paper ignores live unavailable", () => {
    expect(
      kindsFromRecon({
        portfolioReconStatus: "drift",
        liveReconStatus: "unavailable",
        brokerVenue: "paper",
      }),
    ).toEqual(["portfolio_drift"]);
    expect(
      kindsFromRecon({
        liveReconStatus: "unavailable",
        brokerVenue: "live",
      }),
    ).toEqual(["live_unavailable"]);
  });

  it("opening veto gate-off without require", () => {
    expect(incidentOpeningVetoReason()).toBeNull();
    expect(incidentOpeningVetoReason({ incidentStatus: "unresolved" })).toBe(
      "incident:unresolved",
    );
  });
});
