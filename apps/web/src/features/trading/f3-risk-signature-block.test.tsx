/**
 * P2 — bloque firma de riesgo en Confirm.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { RiskSignatureV1 } from "@bolsa/shared";
import { F3RiskSignatureBlock } from "@/features/trading/f3-risk-signature-block";

afterEach(() => cleanup());

const noPlan: RiskSignatureV1 = {
  mode: "no_plan",
  suggestedQty: null,
  maxQty: null,
  stop: null,
  plannedRiskAmount: null,
  initialRiskR: null,
  signedLossAtStop: null,
  signedR: null,
  overrideRequired: false,
  allowed: true,
  excess: null,
  blockReason: null,
};

const overQty: RiskSignatureV1 = {
  ...noPlan,
  mode: "plan",
  suggestedQty: 10,
  maxQty: 10,
  stop: 95,
  plannedRiskAmount: 50,
  signedLossAtStop: 100,
  signedR: 2,
  overrideRequired: true,
  allowed: false,
  excess: "qty_above_plan",
  blockReason: "override_missing",
};

describe("F3RiskSignatureBlock", () => {
  it("is honest when there is no plan", () => {
    render(
      <MemoryRouter>
        <F3RiskSignatureBlock
          signature={noPlan}
          currency="EUR"
          overrideReason=""
          onOverrideReasonChange={() => undefined}
        />
      </MemoryRouter>,
    );
    const text = screen.getByTestId("f3-risk-signature").textContent ?? "";
    expect(text).toMatch(/Sin TradePlan TRIGGERED/i);
    expect(text).toMatch(/% caja/i);
  });

  it("asks for override reason when qty exceeds plan", () => {
    render(
      <MemoryRouter>
        <F3RiskSignatureBlock
          signature={overQty}
          currency="EUR"
          overrideReason=""
          onOverrideReasonChange={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("f3-risk-override-reason")).toBeTruthy();
    expect(screen.getByTestId("f3-risk-signature").textContent).toMatch(
      /supera el plan/i,
    );
  });

  it("shows no_tradeplan block copy when SEMI opening lacks TRIGGERED", () => {
    render(
      <MemoryRouter>
        <F3RiskSignatureBlock
          signature={{
            ...noPlan,
            allowed: false,
            blockReason: "no_tradeplan",
          }}
          currency="EUR"
          overrideReason=""
          onOverrideReasonChange={() => undefined}
        />
      </MemoryRouter>,
    );
    const text = screen.getByTestId("f3-risk-signature").textContent ?? "";
    expect(text).toMatch(/bloqueado/i);
    expect(text).toMatch(/TRIGGERED/i);
  });
});
