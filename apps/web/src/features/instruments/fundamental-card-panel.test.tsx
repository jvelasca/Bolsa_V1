/**
 * Regresión del panel FA — **forma del wire**.
 *
 * Un payload que NO cumple `FundamentalCardDto` (el fallback genérico `{ data: [] }` de los mocks
 * E2E, o una versión antigua del API) hacía *truthy* al `card`, pasaba el `if (!card)` y el panel
 * blanqueaba la página entera en «Cannot read properties of undefined (reading 'forwardPe')» (y con
 * ella el verificador DÍA-D). Ahora se declara el hueco y el panel sigue siendo usable.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { FundamentalCardDto } from "@bolsa/shared";

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    getInstrumentFundamentals: vi.fn(async () => ({ data: [] })),
    syncInstrument: vi.fn(async () => ({ data: { synced: true } })),
  },
}));

import { api } from "@/lib/api";
import { FundamentalCardPanel } from "./fundamental-card-panel";

const VALID_CARD = {
  schemaVersion: "fundamental_card_v1",
  instrumentId: "inst-x",
  ticker: "AAPL",
  scoreDisplay100: 62,
  distress: false,
  facts: {
    forwardPe: 28.4,
    trailingPe: 30.1,
    sector: "Technology",
    roe: 0.31,
    debtToEquity: 1.4,
    marketCap: 2.5e12,
  },
  derived: { altmanZ: 5.2, piotroski: 7, beneishM: null, roic: null },
  metadata: {
    fetchedAt: "2026-10-01T00:00:00.000Z",
    confidence: "HIGH",
  },
} as unknown as FundamentalCardDto;

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FundamentalCardPanel instrumentId="inst-x" compact asOf="2026-08-01" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FundamentalCardPanel — forma del wire", () => {
  it("un payload malformado declara el hueco en vez de blanquear la página", async () => {
    renderPanel();

    expect(await screen.findByText(/Sin datos FA/)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Reintentar Yahoo/ }),
    ).toBeTruthy();
    expect(api.getInstrumentFundamentals).toHaveBeenCalled();
  });

  it("una tarjeta válida sigue pintando la franja FA (sin regresión)", async () => {
    vi.mocked(api.getInstrumentFundamentals).mockResolvedValueOnce({
      data: VALID_CARD,
    } as never);

    renderPanel();

    expect(await screen.findByText("FA")).toBeTruthy();
    expect(screen.getByText("62")).toBeTruthy();
    expect(screen.getByText("HIGH")).toBeTruthy();
  });
});
