/**
 * LIVE VIRTUAL ladder + why honesty (Confirm híbrido).
 */

import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  LIVE_VIRTUAL_LADDER_COPY,
  liveVirtualStepFromFillStatus,
  resolveLiveVirtualLadderStep,
} from "@/features/confirm/live-virtual-ladder";
import { LiveVirtualOrderGateway } from "@/features/confirm/live-virtual-order-gateway";
import { buildLiveVirtualWhyBlocks } from "@/features/confirm/live-virtual-why";
import {
  LIVE_VIRTUAL_BADGE_LABEL,
  LIVE_VIRTUAL_BANNER_TEXT,
} from "@/features/confirm/live-virtual-banner";
import { executeCtaLabel } from "@bolsa/shared";

/** Tokens ingleses que `UI5-09`/`UI5-20` prohíben en el DOM de la escalera. */
const RAW_ENGLISH_LADDER_TOKENS =
  /proposed|signed|submitted|filled\*|filled\b|rejected|not_wired/;

describe("live-virtual-ladder", () => {
  it("maps adapter fillStatus to honest Spanish steps", () => {
    expect(liveVirtualStepFromFillStatus("submitted")).toBe("enviada");
    expect(liveVirtualStepFromFillStatus("not_wired")).toBe("no_cableado");
    expect(liveVirtualStepFromFillStatus("rejected")).toBe("rechazada");
    expect(liveVirtualStepFromFillStatus("executed")).toBe("completada");
    expect(liveVirtualStepFromFillStatus("unknown")).toBe("desconocida");
  });

  it("keeps preparada until firma; Intent → firmada; execute uses fill", () => {
    expect(resolveLiveVirtualLadderStep({ hasPending: true })).toBe(
      "preparada",
    );
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        intentStatus: "authorized",
        execute: false,
      }),
    ).toBe("firmada");
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        execute: true,
        fillStatus: "submitted",
      }),
    ).toBe("enviada");
    expect(
      resolveLiveVirtualLadderStep({
        hasPending: true,
        execute: true,
        fillStatus: "executed",
      }),
    ).toBe("completada");
  });

  it("completada copy never claims real settlement", () => {
    expect(LIVE_VIRTUAL_LADDER_COPY.completada).toMatch(/SIMULADO/i);
    expect(LIVE_VIRTUAL_LADDER_COPY.completada).toMatch(/liquidación/i);
    expect(LIVE_VIRTUAL_LADDER_COPY.enviada).toMatch(/simulado/i);
  });
});

describe("live-virtual-why", () => {
  it("shows honest gaps and anti-implications", () => {
    const blocks = buildLiveVirtualWhyBlocks({});
    expect(blocks.find((b) => b.id === "valor")?.bullets[0]).toMatch(
      /Sin explicación disponible/,
    );
    const anti = blocks.find((b) => b.id === "anti");
    expect(anti?.bullets.join(" ")).toMatch(
      /Estar arriba en la lista no es una orden de compra/,
    );
    expect(anti?.bullets.join(" ")).toMatch(/Preparar una orden no la ejecuta/);
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

describe("LiveVirtualOrderGateway DOM (UI5-09 / UI5-20)", () => {
  afterEach(() => cleanup());

  it("renderiza la escalera en español y sin tokens ingleses", () => {
    const { container } = render(
      createElement(LiveVirtualOrderGateway, {
        symbol: "AAPL",
        proposalRef: "rec-1",
        ticket: null,
        ladderStep: "enviada",
        whyBlocks: [],
      }),
    );

    const ladder = container.querySelector(
      '[data-testid="live-virtual-ladder"]',
    );
    expect(ladder).not.toBeNull();
    expect(ladder?.textContent).toContain(
      "Enviada (simulado) · sin ejecución real",
    );

    const text = container.textContent ?? "";
    expect(text).not.toMatch(RAW_ENGLISH_LADDER_TOKENS);
    expect(text).toContain("Sin dato todavía");
  });

  it("un peldaño terminal declara el desenlace en español", () => {
    const { container } = render(
      createElement(LiveVirtualOrderGateway, {
        symbol: "AAPL",
        proposalRef: "rec-2",
        ticket: null,
        ladderStep: "rechazada",
        whyBlocks: [],
      }),
    );

    const terminal = container.querySelector(
      '[data-testid="live-virtual-ladder-terminal"]',
    );
    expect(terminal?.textContent).toContain(LIVE_VIRTUAL_LADDER_COPY.rechazada);
    expect(container.textContent ?? "").not.toMatch(RAW_ENGLISH_LADDER_TOKENS);
  });
});
