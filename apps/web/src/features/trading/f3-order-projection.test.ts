/**
 * U5 — tests de resolvers de proyección F3 (precio / etiqueta).
 */

import { describe, expect, it } from "vitest";
import {
  coercePositivePrice,
  formatF3ProjectionLabel,
  resolveF3OrderProjection,
  resolveF3OrderProjectionForInstrument,
  resolveF3ProjectionPrice,
} from "@/features/trading/f3-order-projection";

describe("coercePositivePrice", () => {
  it("accepts finite > 0", () => {
    expect(coercePositivePrice(12.5)).toBe(12.5);
    expect(coercePositivePrice("9,75")).toBe(9.75);
  });

  it("rejects zero / negative / junk", () => {
    expect(coercePositivePrice(0)).toBeNull();
    expect(coercePositivePrice(-1)).toBeNull();
    expect(coercePositivePrice("")).toBeNull();
    expect(coercePositivePrice(null)).toBeNull();
    expect(coercePositivePrice(Number.NaN)).toBeNull();
  });
});

describe("resolveF3ProjectionPrice", () => {
  it("prefers suggestedPrice over lastClose", () => {
    expect(
      resolveF3ProjectionPrice({
        suggestedPrice: 10,
        lastClose: 9,
      }),
    ).toBe(10);
  });

  it("falls back to lastClose then package then session", () => {
    expect(resolveF3ProjectionPrice({ lastClose: 8.2 })).toBe(8.2);
    expect(
      resolveF3ProjectionPrice({
        decisionPackage: { entryPrice: 7.1 },
      }),
    ).toBe(7.1);
    expect(
      resolveF3ProjectionPrice({
        decisionSession: { outcome: { priceAtDecision: 6.5 } },
      }),
    ).toBe(6.5);
  });

  it("fails soft when no price", () => {
    expect(resolveF3ProjectionPrice({})).toBeNull();
    expect(
      resolveF3ProjectionPrice({
        decisionPackage: { action: "recommend_long" },
      }),
    ).toBeNull();
  });
});

describe("formatF3ProjectionLabel", () => {
  it("builds mesa-style label", () => {
    expect(formatF3ProjectionLabel({ actionLabel: "LONG", price: 12.34 })).toBe(
      "F3 · LONG @ 12.34",
    );
    expect(formatF3ProjectionLabel({ price: 5 })).toBe("F3 @ 5.00");
  });
});

describe("resolveF3OrderProjection", () => {
  it("builds view from queue item", () => {
    const view = resolveF3OrderProjection({
      id: "q-1",
      payload: {
        instrumentId: "inst-a",
        action: "recommend_long",
        suggestedPrice: 15.5,
      },
    });
    expect(view).toMatchObject({
      queueItemId: "q-1",
      instrumentId: "inst-a",
      price: 15.5,
      action: "recommend_long",
      actionLabel: "LONG",
      label: "F3 · LONG @ 15.50",
      color: "#059669",
    });
  });

  it("returns null without instrument or price", () => {
    expect(
      resolveF3OrderProjection({
        id: "q",
        payload: { suggestedPrice: 10 },
      }),
    ).toBeNull();
    expect(
      resolveF3OrderProjection({
        id: "q",
        payload: { instrumentId: "i1", action: "wait" },
      }),
    ).toBeNull();
  });

  it("prefers package action for side label", () => {
    const view = resolveF3OrderProjection({
      id: "q",
      payload: {
        instrumentId: "i1",
        action: "recommend_long",
        lastClose: 3,
        decisionPackage: { action: "recommend_short", price: 3 },
      },
    });
    expect(view?.actionLabel).toBe("SHORT");
    expect(view?.color).toBe("#e11d48");
  });
});

describe("resolveF3OrderProjectionForInstrument", () => {
  it("clears when no queue item for symbol", () => {
    expect(
      resolveF3OrderProjectionForInstrument(
        [
          {
            id: "a",
            payload: { instrumentId: "other", suggestedPrice: 1 },
          },
        ],
        "target",
      ),
    ).toBeNull();
  });

  it("picks active item for instrument", () => {
    const view = resolveF3OrderProjectionForInstrument(
      [
        {
          id: "old",
          payload: {
            instrumentId: "i1",
            action: "wait",
            suggestedPrice: 1,
          },
        },
        {
          id: "active",
          payload: {
            instrumentId: "i1",
            action: "recommend_long",
            suggestedPrice: 2,
          },
        },
      ],
      "i1",
      "active",
    );
    expect(view?.queueItemId).toBe("active");
    expect(view?.price).toBe(2);
  });
});
