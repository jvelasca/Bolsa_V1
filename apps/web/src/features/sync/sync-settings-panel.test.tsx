/**
 * Panel de sincronización — guardado explícito, validación y cola legible.
 *
 * Cubre `UI-2`, `UI-3`, `UI-4`, `UI-6` y `UI-7` del documento
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
  EnqueueStaleResultDto,
  MarketProviderStatusDto,
  SyncQueueItemDto,
  SyncSettingsDto,
} from "@bolsa/shared";

let settings: SyncSettingsDto = {
  autoSyncEnabled: true,
  scanIntervalMinutes: 30,
  minDelaySeconds: 5,
  postMarketOnly: false,
  maxRetries: 3,
  retryBackoffMinutes: 30,
  scope: "lists",
  providerCheckEnabled: true,
  providerCheckIntervalSeconds: 60,
  updatedAt: "2026-10-29T09:00:00Z",
};
let providers: MarketProviderStatusDto[] = [];
let queue: SyncQueueItemDto[] = [];

const getSyncSettings = vi.fn(async () => ({ data: settings }));
const getSyncQueue = vi.fn(async () => ({ data: queue }));
const getMarketProviders = vi.fn(async () => ({ data: providers }));
const updateSyncSettings = vi.fn(async (patch: Partial<SyncSettingsDto>) => ({
  data: { ...settings, ...patch },
}));
const enqueueStaleInstruments = vi.fn<
  () => Promise<{ data: EnqueueStaleResultDto }>
>(async () => ({ data: { scanned: 12, enqueued: 3, skippedReason: null } }));
const checkProviderHealth = vi.fn(async () => ({
  data: {
    status: "ok" as const,
    ok: true,
    measuredAt: "2026-10-29T09:00:00Z",
    probing: false,
    autoCheckEnabled: true,
    checkIntervalSeconds: 60,
    nextCheckAt: "2026-10-29T09:01:00Z",
    providers: [],
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    getSyncSettings: () => getSyncSettings(),
    getSyncQueue: () => getSyncQueue(),
    getMarketProviders: () => getMarketProviders(),
    updateSyncSettings: (patch: Partial<SyncSettingsDto>) =>
      updateSyncSettings(patch),
    enqueueStaleInstruments: () => enqueueStaleInstruments(),
    checkProviderHealth: () => checkProviderHealth(),
  },
}));

import { SyncSettingsPanel } from "@/features/sync/sync-settings-panel";

function makeSettings(
  overrides: Partial<SyncSettingsDto> = {},
): SyncSettingsDto {
  return {
    autoSyncEnabled: true,
    scanIntervalMinutes: 30,
    minDelaySeconds: 5,
    postMarketOnly: false,
    maxRetries: 3,
    retryBackoffMinutes: 30,
    scope: "lists",
    providerCheckEnabled: true,
    providerCheckIntervalSeconds: 60,
    updatedAt: "2026-10-29T09:00:00Z",
    ...overrides,
  };
}

function makeProvider(
  overrides: Partial<MarketProviderStatusDto> = {},
): MarketProviderStatusDto {
  return {
    id: "yahoo",
    label: "Yahoo Finance",
    enabled: true,
    healthy: false,
    message: "Sin verificar",
    priority: 10,
    minIntervalSeconds: 2,
    baseUrl: null,
    capabilities: ["ohlcv"],
    verified: false,
    ...overrides,
  };
}

function makeQueueItem(
  overrides: Partial<SyncQueueItemDto> = {},
): SyncQueueItemDto {
  return {
    id: "q-1",
    instrumentId: "inst-1",
    symbol: "ITX",
    status: "pending",
    priority: 1,
    scheduledAt: "2026-10-29T09:00:00Z",
    attempts: 0,
    lastError: null,
    createdAt: "2026-10-29T09:00:00Z",
    updatedAt: "2026-10-29T09:00:00Z",
    ...overrides,
  };
}

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SyncSettingsPanel embedded />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  settings = makeSettings();
  providers = [makeProvider()];
  queue = [];
  getSyncSettings.mockImplementation(async () => ({ data: settings }));
  getSyncQueue.mockImplementation(async () => ({ data: queue }));
  getMarketProviders.mockImplementation(async () => ({ data: providers }));
  updateSyncSettings.mockImplementation(
    async (patch: Partial<SyncSettingsDto>) => ({
      data: { ...settings, ...patch },
    }),
  );
  enqueueStaleInstruments.mockImplementation(async () => ({
    data: { scanned: 12, enqueued: 3, skippedReason: null },
  }));
  checkProviderHealth.mockReset();
  checkProviderHealth.mockResolvedValue({
    data: {
      status: "ok",
      ok: true,
      measuredAt: "2026-10-29T09:00:00Z",
      probing: false,
      autoCheckEnabled: true,
      checkIntervalSeconds: 60,
      nextCheckAt: "2026-10-29T09:01:00Z",
      providers: [],
    },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SyncSettingsPanel · guardado explícito", () => {
  it("envía UN PATCH solo con los campos cambiados", async () => {
    settings = makeSettings();
    renderPanel();

    const interval = await screen.findByLabelText("Escanear cada (min)");
    fireEvent.change(interval, { target: { value: "45" } });

    // Sin guardar no hay ninguna petición: no hay PATCH por tecla.
    expect(updateSyncSettings).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(updateSyncSettings).toHaveBeenCalledTimes(1));
    expect(updateSyncSettings).toHaveBeenCalledWith({
      scanIntervalMinutes: 45,
    });
  });

  it("bloquea el guardado con un valor fuera de rango y no llama a la API", async () => {
    renderPanel();

    const delay = await screen.findByLabelText("Pausa entre peticiones (s)");
    fireEvent.change(delay, { target: { value: "0" } });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /fuera de rango/,
    );
    const save = screen.getByRole("button", { name: /Guardar cambios/ });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(updateSyncSettings).not.toHaveBeenCalled();
  });

  it("muestra el error de la API sin fingir que guardó", async () => {
    updateSyncSettings.mockRejectedValueOnce(new Error("422: scope inválido"));
    renderPanel();

    const scope = await screen.findByLabelText("Universo a mantener fresco");
    fireEvent.change(scope, { target: { value: "stale" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    expect(await screen.findByText(/422: scope inválido/)).toBeInTheDocument();
  });

  it("avisa cuando el proveedor de histórico está deshabilitado", async () => {
    providers = [makeProvider({ enabled: false })];
    renderPanel();

    expect(
      await screen.findByTestId("sync-provider-disabled"),
    ).toHaveTextContent(/Yahoo Finance está deshabilitado/);
  });
});

describe("SyncSettingsPanel · comprobación de servidores (060)", () => {
  it("separa velas y servidores en dos bloques rotulados", async () => {
    renderPanel();

    expect(
      await screen.findByRole("heading", { name: "Velas (histórico)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Comprobación de servidores" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Solo prueba la conexión: no/)).toBeInTheDocument();
  });

  it("guardar solo el ON/OFF de servidores manda un PATCH con ese campo", async () => {
    renderPanel();

    const toggle = await screen.findByLabelText(
      "Comprobar servidores automáticamente",
    );
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(updateSyncSettings).toHaveBeenCalledTimes(1));
    expect(updateSyncSettings).toHaveBeenCalledWith({
      providerCheckEnabled: false,
    });
  });

  it("valida el intervalo de servidores con el rango del dominio (15–3600)", async () => {
    renderPanel();

    const interval = await screen.findByLabelText("Comprobar cada (s)");
    fireEvent.change(interval, { target: { value: "5" } });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /fuera de rango/,
    );
    expect(
      screen.getByRole("button", { name: /Guardar cambios/ }),
    ).toBeDisabled();
  });

  it("«Comprobar ahora» mide de verdad y sin exigir guardar antes", async () => {
    renderPanel();

    fireEvent.click(
      await screen.findByRole("button", { name: /Comprobar ahora/ }),
    );

    await waitFor(() => expect(checkProviderHealth).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId("provider-check-note")).toHaveTextContent(
      /proveedores medidos/,
    );
  });

  it("declara que OFF deja el icono con la última medición guardada", async () => {
    settings = makeSettings({ providerCheckEnabled: false });
    renderPanel();

    expect(
      await screen.findByText(/no hay comprobaciones automáticas/),
    ).toBeInTheDocument();
  });
});

describe("SyncSettingsPanel · cola legible", () => {
  it("traduce estados, muestra lastError y contadores", async () => {
    queue = [
      makeQueueItem({ id: "q-1", symbol: "ITX", status: "pending" }),
      makeQueueItem({
        id: "q-2",
        symbol: "SAN",
        status: "failed",
        attempts: 3,
        lastError: "Yahoo 404: no historical data",
      }),
    ];
    renderPanel();

    expect(await screen.findByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText("Fallido")).toBeInTheDocument();
    expect(
      screen.getByText("Yahoo 404: no historical data"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Pendientes: 1 · Procesando: 0 · Fallidos: 1/),
    ).toBeInTheDocument();
  });

  it("declara el motivo cuando no se encoló nada", async () => {
    enqueueStaleInstruments.mockResolvedValueOnce({
      data: {
        scanned: 0,
        enqueued: 0,
        skippedReason: "provider_disabled:yahoo",
      },
    });
    renderPanel();

    fireEvent.click(
      await screen.findByRole("button", {
        name: /Encolar valores desactualizados/,
      }),
    );

    expect(await screen.findByTestId("enqueue-note")).toHaveTextContent(
      /provider_disabled:yahoo/,
    );
  });
});
