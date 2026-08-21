/**
 * Protects the one-shot localStorage → API migrator in usePendingOrders.
 * Do not delete readLegacyPendingOrders or its useEffect until E8 (purge storage).
 */
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { usePendingOrders } from "./use-pending-orders";

vi.mock("@/lib/api", () => ({
  api: {
    getPendingOrders: vi.fn(),
    createPendingOrder: vi.fn(),
    deletePendingOrder: vi.fn(),
  },
}));

const TRADING_UI_KEY = "bolsa-trading-ui";

const legacyOrder = {
  id: "legacy-1",
  instrumentId: "inst-san",
  symbol: "SAN",
  side: "buy" as const,
  orderType: "stop_limit",
  quantity: 10,
  limitPrice: 4.5,
  expiryAt: null,
  createdAt: "2026-01-01T00:00:00.000Z",
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

function seedLegacyBlob(pendingOrders: unknown[]) {
  localStorage.setItem(
    TRADING_UI_KEY,
    JSON.stringify({ state: { pendingOrders } }),
  );
}

describe("usePendingOrders legacy migrator", () => {
  beforeEach(() => {
    localStorage.removeItem(TRADING_UI_KEY);
    vi.mocked(api.getPendingOrders).mockResolvedValue({ data: [] });
    vi.mocked(api.createPendingOrder).mockResolvedValue({ data: [] });
  });

  afterEach(() => {
    localStorage.removeItem(TRADING_UI_KEY);
    vi.clearAllMocks();
  });

  it("reads bolsa-trading-ui state.pendingOrders, POSTs each, then removeItem", async () => {
    seedLegacyBlob([legacyOrder]);

    renderHook(() => usePendingOrders(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(api.createPendingOrder).toHaveBeenCalledTimes(1);
    });

    expect(api.createPendingOrder).toHaveBeenCalledWith({
      instrumentId: "inst-san",
      symbol: "SAN",
      side: "buy",
      orderType: "stop_limit",
      quantity: 10,
      limitPrice: 4.5,
      expiryAt: null,
    });
    expect(localStorage.getItem(TRADING_UI_KEY)).toBeNull();
    expect(api.getPendingOrders).toHaveBeenCalled();
  });

  it("does not POST or wipe storage when the server already has orders", async () => {
    seedLegacyBlob([legacyOrder]);
    vi.mocked(api.getPendingOrders).mockResolvedValue({
      data: [{ ...legacyOrder, id: "server-1" }],
    });

    const { result } = renderHook(() => usePendingOrders(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.pendingOrders).toHaveLength(1);
    });

    expect(api.createPendingOrder).not.toHaveBeenCalled();
    expect(localStorage.getItem(TRADING_UI_KEY)).not.toBeNull();
  });

  it("does not POST when the blob has no pendingOrders", async () => {
    localStorage.setItem(TRADING_UI_KEY, JSON.stringify({ state: {} }));

    const { result } = renderHook(() => usePendingOrders(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.createPendingOrder).not.toHaveBeenCalled();
  });

  it("does not throw or POST when the blob is malformed JSON", async () => {
    localStorage.setItem(TRADING_UI_KEY, "{not-json");

    const { result } = renderHook(() => usePendingOrders(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.createPendingOrder).not.toHaveBeenCalled();
  });
});
