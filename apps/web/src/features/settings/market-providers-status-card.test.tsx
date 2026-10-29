/**
 * Tarjetas de proveedor — configuración explícita y estado honesto.
 *
 * Cubre `UI-1`, `UI-4`, `UI-5` y `UI-7` del documento
 * `docs/engineering/seguimiento-ui-proveedores-2026-10-29.md`.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
  MarketProviderStatusDto,
  ProviderTestResultDto,
  UpdateMarketProviderDto,
} from "@bolsa/shared";

let providers: MarketProviderStatusDto[] = [];
let probeResult: ProviderTestResultDto = {
  providerId: "xtb",
  ok: true,
  message: "Bridge mock listo",
  checkedAt: "2026-10-29T10:05:00Z",
};

const getMarketProviders = vi.fn(async () => ({ data: providers }));
const updateMarketProvider = vi.fn(
  async (providerId: string, body: UpdateMarketProviderDto) => ({
    data: {
      ...(providers.find(
        (provider) => provider.id === providerId,
      ) as MarketProviderStatusDto),
      ...body,
    },
  }),
);
const testMarketProvider = vi.fn(async () => ({ data: probeResult }));

vi.mock("@/lib/api", () => ({
  api: {
    getMarketProviders: () => getMarketProviders(),
    updateMarketProvider: (providerId: string, body: UpdateMarketProviderDto) =>
      updateMarketProvider(providerId, body),
    testMarketProvider: (providerId: string) => testMarketProvider(providerId),
  },
}));

import { MarketProvidersStatusCard } from "@/features/settings/market-providers-status-card";

function makeProvider(
  overrides: Partial<MarketProviderStatusDto> = {},
): MarketProviderStatusDto {
  return {
    id: "yahoo",
    label: "Yahoo Finance",
    enabled: true,
    healthy: false,
    message: "Sin verificar (usa «Probar conexión»)",
    priority: 10,
    minIntervalSeconds: 2,
    baseUrl: null,
    capabilities: ["ohlcv", "fundamentals"],
    description: "Histórico diario, fundamentales y tipos de cambio.",
    verified: false,
    ...overrides,
  };
}

function makeXtb(
  overrides: Partial<MarketProviderStatusDto> = {},
): MarketProviderStatusDto {
  return makeProvider({
    id: "xtb",
    label: "XTB Bridge",
    priority: 20,
    minIntervalSeconds: 0,
    capabilities: ["live_quote"],
    description: "Cotización en vivo vía bridge HTTP local (opcional).",
    ...overrides,
  });
}

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MarketProvidersStatusCard />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  providers = [makeProvider(), makeXtb()];
  probeResult = {
    providerId: "xtb",
    ok: true,
    message: "Bridge mock listo",
    checkedAt: "2026-10-29T10:05:00Z",
  };
  getMarketProviders.mockImplementation(async () => ({ data: providers }));
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("MarketProvidersStatusCard · estado honesto", () => {
  it("no declara disponible un proveedor sin verificar y publica su configuración", async () => {
    renderCard();

    expect(await screen.findByTestId("provider-state-yahoo")).toHaveTextContent(
      "Sin verificar",
    );
    expect(screen.getByText("ohlcv")).toBeInTheDocument();
    expect(screen.getByLabelText("Prioridad de Yahoo Finance")).toHaveValue(10);
    expect(screen.getByLabelText("Intervalo de Yahoo Finance")).toHaveValue(2);
    expect(screen.getAllByText(/Sin verificación registrada/)).toHaveLength(2);
  });

  it("marca XTB sin URL como no configurado", async () => {
    renderCard();
    expect(await screen.findByTestId("provider-state-xtb")).toHaveTextContent(
      "Sin URL de bridge",
    );
  });
});

describe("MarketProvidersStatusCard · acciones", () => {
  it("deshabilitar manda un único PATCH con enabled", async () => {
    renderCard();

    const toggle = await screen.findByLabelText("Habilitar Yahoo Finance");
    fireEvent.click(toggle);

    await waitFor(() => expect(updateMarketProvider).toHaveBeenCalledTimes(1));
    expect(updateMarketProvider).toHaveBeenCalledWith("yahoo", {
      enabled: false,
    });
  });

  it("guardar manda prioridad e intervalo y, en XTB, la URL", async () => {
    renderCard();

    const priority = await screen.findByLabelText("Prioridad de XTB Bridge");
    fireEvent.change(priority, { target: { value: "5" } });
    const url = screen.getByLabelText("URL del bridge XTB");
    fireEvent.change(url, { target: { value: "http://127.0.0.1:3002" } });

    fireEvent.click(screen.getAllByRole("button", { name: /Guardar/ })[1]);

    await waitFor(() => expect(updateMarketProvider).toHaveBeenCalledTimes(1));
    expect(updateMarketProvider).toHaveBeenCalledWith("xtb", {
      priority: 5,
      minIntervalSeconds: 0,
      baseUrl: "http://127.0.0.1:3002",
    });
  });

  it("rechaza una URL que no es http(s) sin llamar a la API", async () => {
    renderCard();

    const url = await screen.findByLabelText("URL del bridge XTB");
    fireEvent.change(url, { target: { value: "ftp://bridge" } });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /http:\/\/ o https/,
    );
    const saveButtons = screen.getAllByRole("button", { name: /Guardar/ });
    expect(saveButtons[1]).toBeDisabled();
    fireEvent.click(saveButtons[1]);
    expect(updateMarketProvider).not.toHaveBeenCalled();
  });

  it("probar conexión muestra el resultado sin recargar", async () => {
    renderCard();

    const probeButtons = await screen.findAllByRole("button", {
      name: /Probar conexión/,
    });
    fireEvent.click(probeButtons[1]);

    await waitFor(() => expect(testMarketProvider).toHaveBeenCalledWith("xtb"));
    expect(await screen.findByTestId("provider-probe-xtb")).toHaveTextContent(
      /Conexión OK: Bridge mock listo/,
    );
  });

  it("un fallo de la API se declara en la tarjeta", async () => {
    updateMarketProvider.mockRejectedValueOnce(
      new Error("500: base de datos caída"),
    );
    renderCard();

    const toggle = await screen.findByLabelText("Habilitar Yahoo Finance");
    fireEvent.click(toggle);

    expect(
      await screen.findByText(/500: base de datos caída/),
    ).toBeInTheDocument();
  });
});
