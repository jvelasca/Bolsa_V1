/**
 * S3 · Cartera del Asesor — el memo de estructura no se paga al refrescar cotizaciones.
 *
 * La estructura de mercado (ATR, pivotes, niveles) se calcula por la identidad del array
 * de velas. Un refresco de COTIZACIONES no trae velas nuevas: si el memo no se ejerce, el
 * `rows` vuelve a calcular la estructura de toda la lista en cada refresco de precio.
 *
 * Este test renderiza el hook REAL (no se mockea `useAsesorCarteraData`, como sí hace
 * `asesor-cartera-panel.test.tsx`) con un mock PARCIAL de `@bolsa/shared` que cuenta las
 * invocaciones de `computeMarketStructure` y sigue delegando en la implementación real.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 */

import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OhlcvBarDto } from "@bolsa/shared";

// `vi.hoisted` evita la TDZ: `vi.mock` se eleva por encima de los `const` del módulo.
const structure = vi.hoisted(() => ({ calls: 0 }));

const apiMocks = vi.hoisted(() => ({
  getPortfolio: vi.fn(),
  getDecisionStudies: vi.fn(),
  getInstrumentQuotes: vi.fn(),
  getOhlcv: vi.fn(),
  queryInstrumentDailyOpinions: vi.fn(),
  getPendingOrders: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: apiMocks }));

// Mock PARCIAL: solo se instrumenta `computeMarketStructure`; el resto de @bolsa/shared
// (buildAsesorCarteraRow, chunkIds, summarizeAsesorCartera…) sigue siendo el real.
vi.mock("@bolsa/shared", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@bolsa/shared")>();
  return {
    ...actual,
    computeMarketStructure: (
      input: Parameters<typeof actual.computeMarketStructure>[0],
    ) => {
      structure.calls += 1;
      return actual.computeMarketStructure(input);
    },
  };
});

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/stores/active-account-store", () => ({
  useActiveAccountQueryKey: () => "acc-1",
}));

vi.mock("@/stores/estudio-membership-store", () => ({
  useEstudioMembershipStore: (selector: (state: unknown) => unknown) =>
    selector({
      members: [{ instrumentId: "inst-1", symbol: "AAA", name: "AAA SA" }],
    }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (selector: (state: unknown) => unknown) =>
    selector({ items: [] }),
}));

vi.mock("@/features/trading/use-pending-orders", () => ({
  usePendingOrders: () => ({ pendingOrders: [] }),
}));

import { useAsesorCarteraData } from "./use-asesor-cartera-data";

const INSTRUMENT_ID = "inst-1";

function bars(count = 220): OhlcvBarDto[] {
  return Array.from({ length: count }, (_, index) => {
    const close = 10 + Math.sin(index / 5) * 1.5 + index * 0.01;
    return {
      timestamp: new Date(Date.UTC(2025, 0, 1 + index)).toISOString(),
      open: close - 0.05,
      high: close + 0.2,
      low: close - 0.2,
      close,
      volume: 1_000,
      adjClose: null,
      source: "yahoo",
    };
  });
}

function quote(lastClose: number, changePct: number) {
  return {
    id: INSTRUMENT_ID,
    symbol: "AAA",
    name: "AAA SA",
    meta: {
      lastClose,
      changePct,
      lastBarDate: "2026-11-11",
      expectedLastBarDate: "2026-11-12",
      freshnessStatus: "current",
    },
  };
}

function wrapperWith(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

afterEach(() => {
  structure.calls = 0;
  for (const mock of Object.values(apiMocks)) mock.mockReset();
});

describe("useAsesorCarteraData · memo de estructura", () => {
  it("un refresco que solo cambia cotizaciones NO recalcula la estructura", async () => {
    apiMocks.getPortfolio.mockResolvedValue({ data: { positions: [] } });
    apiMocks.getDecisionStudies.mockResolvedValue({
      data: { studies: [], total: 0 },
    });
    apiMocks.getInstrumentQuotes.mockResolvedValue({
      data: [quote(10.5, 1.2)],
    });
    apiMocks.getOhlcv.mockResolvedValue({ data: bars() });
    apiMocks.queryInstrumentDailyOpinions.mockResolvedValue({ data: [] });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { result } = renderHook(() => useAsesorCarteraData(), {
      wrapper: wrapperWith(queryClient),
    });

    // 1) Velas cargadas ⇒ la estructura se mide UNA vez y la fila la publica.
    await waitFor(() => expect(result.current.rows).toHaveLength(1));
    await waitFor(() =>
      expect(result.current.rows[0]?.quote.price).toBe(10.5),
    );
    expect(result.current.rows[0]?.structureProvenance).not.toBeNull();

    const callsAfterLoad = structure.calls;
    expect(callsAfterLoad).toBeGreaterThan(0);

    // 2) Refresco de SOLO cotizaciones: mismas velas (misma identidad de array).
    queryClient.setQueryData(["asesor-cartera-quotes", INSTRUMENT_ID], [
      quote(99, 2.5),
    ]);

    await waitFor(() => expect(result.current.rows[0]?.quote.price).toBe(99));

    // El precio se refrescó…
    expect(apiMocks.getOhlcv).toHaveBeenCalledTimes(1);
    // …y la estructura NO se volvió a calcular.
    expect(structure.calls).toBe(callsAfterLoad);
    expect(result.current.rows[0]?.structureProvenance).not.toBeNull();
  });
});
