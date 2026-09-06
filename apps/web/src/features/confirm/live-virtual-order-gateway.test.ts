/**
 * LIVE VIRTUAL ladder + why honesty (Confirm híbrido).
 */

import { describe, expect, it } from "vitest";
import {
  LIVE_VIRTUAL_LADDER_COPY,
  liveVirtualStepFromFillStatus,
  resolveLiveVirtualLadderStep,
} from "@/features/confirm/live-virtual-ladder";
import { buildLiveVirtualWhyBlocks } from "@/features/confirm/live-virtual-why";
import {
  LIVE_VIRTUAL_BADGE_LABEL,
  LIVE_VIRTUAL_BANNER_TEXT,
} from "@/features/confirm/live-virtual-banner";
import { executeCtaLabel } from "@bolsa/shared";

describe("live-virtual-ladder", () => {
  it("maps adapter fillStatus to honest steps", () => {
    expect(liveVirtualStepFromFillStatus("submitted")).toBe("submitted");
    expect(liveVirtualStepFromFillStatus("not_wired")).toBe("not_wired");
    expect(liveVirtualStepFromFillStatus("rejected")).toBe("rejected");
    expect(liveVirtualStepFromFillStatus("executed")).toBe("filled");
    expect(liveVirtualStepFromFillStatus("unknown")).toBe("unknown");
  });

  it("keeps proposed until firma; Intent → signed; execute uses fill", () => {
    expect(resolveLiveVirtualLadderStep({ hasPending: true })).toBe("proposed");
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        intentStatus: "authorized",
        execute: false,
      }),
    ).toBe("signed");
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        execute: true,
        fillStatus: "submitted",
      }),
    ).toBe("submitted");
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        execute: true,
        fillStatus: "executed",
      }),
    ).toBe("filled");
  });

  it("filled* copy never claims real settlement", () => {
    expect(LIVE_VIRTUAL_LADDER_COPY.filled).toMatch(/SIMULADO/i);
    expect(LIVE_VIRTUAL_LADDER_COPY.filled).toMatch(/settlement/i);
    expect(LIVE_VIRTUAL_LADDER_COPY.submitted).toMatch(/simulado/i);
  });
});

describe("live-virtual-why", () => {
  it("shows honest gaps and anti-implications", () => {
    const blocks = buildLiveVirtualWhyBlocks({});
    expect(blocks.find((b) => b.id === "valor")?.bullets[0]).toMatch(
      /Sin explicación disponible/,
    );
    const anti = blocks.find((b) => b.id === "anti");
    expect(anti?.bullets.join(" ")).toMatch(/Ranking ≠ BUY/);
    expect(anti?.bullets.join(" ")).toMatch(/Arm ≠ Execute/);
    expect(anti?.bullets.join(" ")).toMatch(/VIRTUAL/);
  });

  it("reuses weight rationale and trade plan without inventing PASS", () => {
    const blocks = buildLiveVirtualWhyBlocks({
      action: "recommend_long",
      weightContext: {
        horizon: "swing",
        regime: "risk_on",
        ruleVersion: "1",
        weights: { ta: 0.4, fund: 0.2, macro: 0.2, news: 0.2 },
        rationale: "Tendencia alineada con régimen.",
      },
      tradePlan: {
        decisionId: "d1",
        instrumentId: "i1",
        direction: "long",
        status: "TRIGGERED",
        quantity: 10,
        riskPct: 0.7,
        whyNot: [],
        executionAllowed: true,
      },
    });
    const valor = blocks.find((b) => b.id === "valor")?.bullets.join(" ") ?? "";
    expect(valor).toMatch(/LONG/);
    expect(valor).toMatch(/Tendencia alineada/);
    expect(valor).toMatch(/TRIGGERED/);
    expect(valor).not.toMatch(/\bPASS\b/);
  });
});

describe("live-virtual copy surfaces", () => {
  it("banner / badge / CTA stay VIRTUAL · SIMULADO", () => {
    expect(LIVE_VIRTUAL_BANNER_TEXT).toMatch(/LIVE VIRTUAL/);
    expect(LIVE_VIRTUAL_BANNER_TEXT).toMatch(/SIMULADO/);
    expect(LIVE_VIRTUAL_BANNER_TEXT).toMatch(/no capital real/);
    expect(LIVE_VIRTUAL_BADGE_LABEL).toMatch(/LIVE VIRTUAL/);
    expect(executeCtaLabel("live")).toBe(
      "Firmar · Ejecutar en LIVE VIRTUAL (simulado)",
    );
    expect(executeCtaLabel("paper")).toBe("Ejecutar en PAPER");
  });
});
