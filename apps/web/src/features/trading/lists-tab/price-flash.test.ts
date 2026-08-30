import { describe, expect, it } from "vitest";
import {
  PRICE_FLASH_MS,
  priceFlashClassName,
  resolvePriceFlashDirection,
} from "./price-flash";

describe("resolvePriceFlashDirection", () => {
  it("returns up / down / null", () => {
    expect(resolvePriceFlashDirection(10, 10.5)).toBe("up");
    expect(resolvePriceFlashDirection(10, 9.5)).toBe("down");
    expect(resolvePriceFlashDirection(10, 10)).toBe(null);
  });

  it("ignores null / non-finite", () => {
    expect(resolvePriceFlashDirection(null, 10)).toBe(null);
    expect(resolvePriceFlashDirection(10, null)).toBe(null);
    expect(resolvePriceFlashDirection(NaN, 10)).toBe(null);
    expect(resolvePriceFlashDirection(undefined, undefined)).toBe(null);
  });
});

describe("priceFlashClassName", () => {
  it("maps direction to CSS class", () => {
    expect(priceFlashClassName("up")).toBe("bolsa-price-flash-up");
    expect(priceFlashClassName("down")).toBe("bolsa-price-flash-down");
    expect(priceFlashClassName(null)).toBeUndefined();
  });
});

describe("PRICE_FLASH_MS", () => {
  it("is a short tick duration", () => {
    expect(PRICE_FLASH_MS).toBeGreaterThanOrEqual(300);
    expect(PRICE_FLASH_MS).toBeLessThanOrEqual(800);
  });
});
