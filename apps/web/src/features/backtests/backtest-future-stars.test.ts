import { describe, expect, it } from "vitest";
import { normalizeFutureStars } from "@/features/backtests/backtest-future-stars";

describe("normalizeFutureStars", () => {
  it("rounds to half-star steps", () => {
    expect(normalizeFutureStars(3.2)).toBe(3);
    expect(normalizeFutureStars(3.4)).toBe(3.5);
    expect(normalizeFutureStars(4.75)).toBe(5);
    expect(normalizeFutureStars(0)).toBe(0);
    expect(normalizeFutureStars(6)).toBe(5);
  });
});
