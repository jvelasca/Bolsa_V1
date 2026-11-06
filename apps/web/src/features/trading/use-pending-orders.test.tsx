/**
 * P1-01 — `useInstrumentOrderPending` es tri-estado: `null` = la cola no se pudo leer.
 *
 * Falsable: devolver `false` con la consulta caída afirmaba «sin orden pendiente»
 * sobre un dato inexistente, y el estado de ejecución de la posición se pintaba
 * limpio.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  useInstrumentOrderPending,
  usePendingOrders,
} from "@/features/trading/use-pending-orders";

const getPendingOrders = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getPendingOrders: (...args: unknown[]) => getPendingOrders(...args),
    createPendingOrder: vi.fn(),
    deletePendingOrder: vi.fn(),
  },
}));

vi.mock("@/stores/active-account-store", () => ({
  useActiveAccountQueryKey: () => "acc-1",
}));

vi.mock("@/lib/legacy-storage-metrics", () => ({
  reportLegacyStorageMetric: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("Órdenes pendientes — tri-estado de lectura", () => {
  it("con la cola caída devuelve null (no se puede afirmar «sin pendientes»)", async () => {
    getPendingOrders.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useInstrumentOrderPending("inst-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current).toBeNull());
  });

  it("con la cola leída y vacía devuelve false", async () => {
    getPendingOrders.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useInstrumentOrderPending("inst-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current).toBe(false));
  });

  it("con una orden del instrumento devuelve true", async () => {
    getPendingOrders.mockResolvedValue({
      data: [
        {
          id: "o1",
          instrumentId: "inst-1",
          symbol: "SAN",
          side: "buy",
          quantity: 1,
          limitPrice: 10,
          expiryAt: null,
        },
      ],
    });

    const { result } = renderHook(() => useInstrumentOrderPending("inst-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current).toBe(true));
  });

  it("expone isError al consumidor", async () => {
    getPendingOrders.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePendingOrders(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.pendingOrders).toEqual([]);
  });
});
