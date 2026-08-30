import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PRICE_FLASH_MS } from "./price-flash";
import { usePriceFlash } from "./use-price-flash";

describe("usePriceFlash", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not flash on first price", () => {
    const { result } = renderHook(() => usePriceFlash(10));
    expect(result.current).toBe(null);
  });

  it("flashes up then clears", () => {
    const { result, rerender } = renderHook(
      ({ price }: { price: number }) => usePriceFlash(price),
      { initialProps: { price: 10 } },
    );
    expect(result.current).toBe(null);

    rerender({ price: 11 });
    expect(result.current).toBe("up");

    act(() => {
      vi.advanceTimersByTime(PRICE_FLASH_MS);
    });
    expect(result.current).toBe(null);
  });

  it("flashes down on decrease", () => {
    const { result, rerender } = renderHook(
      ({ price }: { price: number }) => usePriceFlash(price),
      { initialProps: { price: 10 } },
    );
    rerender({ price: 9 });
    expect(result.current).toBe("down");
  });
});
