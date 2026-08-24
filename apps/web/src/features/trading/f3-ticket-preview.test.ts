/**
 * U6 — tests de resolvers de ticket preview (margen / comisión).
 */

import { describe, expect, it } from "vitest";
import { defaultAccountSettings } from "@bolsa/shared";
import {
  coercePositiveQuantity,
  resolveF3TicketFreeMarginAfter,
  resolveF3TicketMarginRequired,
  resolveF3TicketNotional,
  resolveF3TicketPreview,
  resolveF3TicketSide,
} from "@/features/trading/f3-ticket-preview";

const settings = defaultAccountSettings("standard_es", "ES");

describe("resolveF3TicketSide", () => {
  it("maps openings long/short", () => {
    expect(resolveF3TicketSide({ action: "recommend_long" })).toBe("buy");
    expect(resolveF3TicketSide({ action: "recommend_short" })).toBe("sell");
  });

  it("maps closes from package thesis", () => {
    expect(
      resolveF3TicketSide({
        action: "exit_hint",
        packageAction: "recommend_long",
      }),
    ).toBe("sell");
    expect(
      resolveF3TicketSide({
        action: "reduce",
        packageAction: "recommend_short",
      }),
    ).toBe("buy");
  });

  it("returns null for wait / indeterminate close", () => {
    expect(resolveF3TicketSide({ action: "wait" })).toBeNull();
    expect(resolveF3TicketSide({ action: "exit_hint" })).toBeNull();
    expect(resolveF3TicketSide({})).toBeNull();
  });
});

describe("coercePositiveQuantity / notional", () => {
  it("parses quantity strings", () => {
    expect(coercePositiveQuantity("12,5")).toBe(12.5);
    expect(coercePositiveQuantity(0)).toBeNull();
  });

  it("prefers payload notional then qty×price", () => {
    expect(
      resolveF3TicketNotional({ notional: 500, quantity: 10, price: 2 }),
    ).toBe(500);
    expect(resolveF3TicketNotional({ quantity: 10, price: 2 })).toBe(20);
  });
});

describe("margin helpers", () => {
  it("divides notional by leverage", () => {
    expect(resolveF3TicketMarginRequired(1000, 2)).toBe(500);
    expect(resolveF3TicketMarginRequired(1000, null)).toBe(1000);
  });

  it("estimates free margin after buy/sell", () => {
    expect(
      resolveF3TicketFreeMarginAfter({
        side: "buy",
        freeMargin: 2000,
        marginRequired: 500,
      }),
    ).toBe(1500);
    expect(
      resolveF3TicketFreeMarginAfter({
        side: "sell",
        freeMargin: 2000,
        marginRequired: 500,
      }),
    ).toBe(2500);
  });
});

describe("resolveF3TicketPreview", () => {
  it("surfaces commission and margin for a long open", () => {
    const view = resolveF3TicketPreview({
      action: "recommend_long",
      quantity: 10,
      price: 100,
      settings,
      currency: "EUR",
      leverage: 1,
      freeMargin: 5000,
      marginUsed: 1000,
    });
    expect(view).not.toBeNull();
    expect(view!.side).toBe("buy");
    expect(view!.sideLabel).toBe("Compra");
    expect(view!.actionLabel).toBe("LONG");
    expect(view!.notional).toBe(1000);
    expect(view!.fees.commission).toBeGreaterThan(0);
    expect(view!.fees.total).toBeGreaterThan(0);
    expect(view!.cashImpact).toBe(view!.notional + view!.fees.total);
    expect(view!.marginRequired).toBe(1000);
    expect(view!.freeMargin).toBe(5000);
    expect(view!.freeMarginAfter).toBe(4000);
    expect(view!.commissionProfileLabel).toMatch(/estándar|Broker/i);
  });

  it("fails soft without price or tradeable action", () => {
    expect(
      resolveF3TicketPreview({
        action: "wait",
        quantity: 1,
        price: 10,
        settings,
        currency: "EUR",
      }),
    ).toBeNull();
    expect(
      resolveF3TicketPreview({
        action: "recommend_long",
        quantity: 1,
        price: "",
        settings,
        currency: "EUR",
      }),
    ).toBeNull();
  });
});
