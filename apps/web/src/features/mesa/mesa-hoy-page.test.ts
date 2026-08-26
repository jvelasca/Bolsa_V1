import { describe, expect, it } from "vitest";
import { buildMesaSessionState, mesaEntriesBlocked } from "@bolsa/shared";

describe("mesa-hoy-page invariants", () => {
  it("incident state blocks entries before candidates can show ready", () => {
    expect(
      mesaEntriesBlocked({
        incidents: [
          {
            incidentId: "i1",
            accountId: "a",
            kind: "live_drift",
            status: "open",
            snapshot: null,
            openedAt: "",
            reviewedAt: null,
            reviewedBy: null,
            resolvedAt: null,
            resolvedBy: null,
            resolutionNote: null,
            clearedAt: null,
          },
        ],
      }),
    ).toBe(true);
    const session = buildMesaSessionState(null, {
      entriesBlocked: true,
      incidentCount: 1,
    });
    expect(session.tone).toBe("blocked");
    expect(session.detail).toContain("BLOQUEADAS");
  });
});
