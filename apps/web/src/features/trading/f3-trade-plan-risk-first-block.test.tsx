/**
 * V1.17 — trade plan block stale copy.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { defaultAccountSettings } from "@bolsa/shared";
import { F3TradePlanRiskFirstBlock } from "@/features/trading/f3-trade-plan-risk-first-block";
import type { F3TicketPreviewView } from "@/features/trading/f3-ticket-preview";

afterEach(() => cleanup());

const ticket: F3TicketPreviewView = {
  side: "buy",
  sideLabel: "Compra",
  actionLabel: "Long",
  quantity: 12,
  price: 100,
  notional: 1200,
  currency: "EUR",
  fees: {
    commission: 3,
    exchange: 0,
    stamp: 0,
    total: 3,
    currency: "EUR",
  },
  cashImpact: 1203,
  cashImpactLabel: "Total a debitar (est.)",
  commissionProfileLabel: defaultAccountSettings("standard_es", "ES").commission
    .label,
  marginRequired: 1200,
  marginUsed: null,
  freeMargin: null,
  freeMarginAfter: null,
};

describe("F3TradePlanRiskFirstBlock", () => {
  it("shows stale warning when inputs differ from plan", () => {
    render(<F3TradePlanRiskFirstBlock ticket={ticket} stop={95} inputsStale />);
    expect(screen.getByTestId("f3-trade-plan-inputs-stale")).toBeTruthy();
    expect(
      screen.getByTestId("f3-trade-plan-inputs-stale").textContent,
    ).toMatch(/modificados/i);
  });

  it("shows loss at stop not cashImpact (T-SIZE-03)", () => {
    render(
      <F3TradePlanRiskFirstBlock
        ticket={ticket}
        stop={95}
        signedLossAtStop={50}
        riskPct={0.72}
        signedR={1}
        inputsStale={false}
      />,
    );
    const lossRow = screen.getByTestId("f3-trade-plan-loss-at-stop");
    expect(lossRow.textContent).toMatch(/50/);
    expect(lossRow.textContent).not.toMatch(/1\.203/);
    expect(screen.getByTestId("f3-trade-plan-risk-pct").textContent).toMatch(
      /0\.72/,
    );
  });
});
