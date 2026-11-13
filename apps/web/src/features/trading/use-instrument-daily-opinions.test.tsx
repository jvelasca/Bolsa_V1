/**
 * Fase 1.3 / 1.4 — el cliente manda `accountId` y NO fabrica hints.
 *
 * La postura del dictamen depende de las posiciones de la cuenta y de los scores de
 * los chips: ambos los mide el servidor. Si el cliente enviara `hints` (o un
 * `hasEodBar` inventado), la caché quedaría envenenada. Este test fija el contrato:
 * el body lleva ids + forceRefresh + accountId y nada más.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const queryInstrumentDailyOpinions = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    queryInstrumentDailyOpinions: (...args: unknown[]) =>
      queryInstrumentDailyOpinions(...args),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-active",
    account: { id: "acc-active" },
    isLoading: false,
  }),
}));

import { useInstrumentDailyOpinions } from "@/features/trading/use-instrument-daily-opinions";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

afterEach(() => {
  queryInstrumentDailyOpinions.mockReset();
});

describe("useInstrumentDailyOpinions — contrato de servidor", () => {
  it("envía la cuenta activa y no envía hints fabricados", async () => {
    queryInstrumentDailyOpinions.mockResolvedValue({
      data: [
        {
          instrumentId: "inst-1",
          asOfBarDate: "2026-11-10",
          stance: "neutral",
        },
      ],
    });

    const { result } = renderHook(
      () => useInstrumentDailyOpinions(["inst-1", "inst-1"]),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(queryInstrumentDailyOpinions).toHaveBeenCalledTimes(1);
    const body = queryInstrumentDailyOpinions.mock.calls[0]?.[0];
    expect(body).toEqual({
      instrumentIds: ["inst-1"],
      forceRefresh: false,
      accountId: "acc-active",
    });
    expect(body).not.toHaveProperty("hints");
  });

  it("respeta el accountId explícito (scope por cuenta) y lo separa en la queryKey", async () => {
    queryInstrumentDailyOpinions.mockResolvedValue({ data: [] });

    const { result } = renderHook(
      () =>
        useInstrumentDailyOpinions(["inst-2"], { accountId: "acc-other" }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryInstrumentDailyOpinions.mock.calls[0]?.[0]).toEqual({
      instrumentIds: ["inst-2"],
      forceRefresh: false,
      accountId: "acc-other",
    });
    expect(result.current.data).toEqual([]);
  });

  it("sin cuenta (null) viaja accountId null, no inventado", async () => {
    queryInstrumentDailyOpinions.mockResolvedValue({ data: [] });

    const { result } = renderHook(
      () => useInstrumentDailyOpinions(["inst-3"], { accountId: null }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryInstrumentDailyOpinions.mock.calls[0]?.[0].accountId).toBeNull();
  });
});
