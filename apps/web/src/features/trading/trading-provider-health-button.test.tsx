/**
 * Icono de servidores de datos: el color es un veredicto medido, no una suposición.
 *
 * Verde = todos los proveedores HABILITADOS medidos y OK · rojo = alguno ha caído ·
 * ámbar = falta medir (o sonda en curso) · gris = ninguno habilitado.
 * Un proveedor deshabilitado a propósito no pinta rojo: se declara en el tooltip.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProviderHealthSummaryDto } from "@bolsa/shared";

const getProviderHealth = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getProviderHealth: () => getProviderHealth(),
  },
}));

const openPlatformConfig = vi.fn();
vi.mock("@/stores/ui-store", () => ({
  useUiStore: (
    selector: (state: {
      openPlatformConfig: typeof openPlatformConfig;
    }) => unknown,
  ) => selector({ openPlatformConfig }),
}));

import {
  PROVIDER_HEALTH_POLL_OFF_MS,
  TradingProviderHealthButton,
  healthPollIntervalMs,
} from "@/features/trading/trading-provider-health-button";

function summary(overrides: Partial<ProviderHealthSummaryDto> = {}): {
  data: ProviderHealthSummaryDto;
} {
  return {
    data: {
      status: "ok",
      ok: true,
      measuredAt: "2026-10-29T10:00:00+00:00",
      probing: false,
      providers: [
        {
          id: "yahoo",
          label: "Yahoo Finance",
          enabled: true,
          healthy: true,
          verified: true,
          message: "Yahoo respondió 11.2345 (ref. ^IBEX)",
          lastCheckAt: "2026-10-29T10:00:00+00:00",
          lastCheckOk: true,
        },
        {
          id: "xtb",
          label: "XTB Bridge",
          enabled: true,
          healthy: true,
          verified: true,
          message: "Bridge mock listo",
          lastCheckAt: "2026-10-29T10:00:00+00:00",
          lastCheckOk: true,
        },
      ],
      ...overrides,
    },
  };
}

function renderButton() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TradingProviderHealthButton />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TradingProviderHealthButton", () => {
  beforeEach(() => {
    getProviderHealth.mockReset();
    openPlatformConfig.mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("verde cuando todos los proveedores habilitados están medidos y OK", async () => {
    getProviderHealth.mockResolvedValue(summary());
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() => expect(icon.getAttribute("data-tone")).toBe("ok"));
    expect(icon.getAttribute("title")).toContain(
      "Servidores de datos verificados",
    );
    expect(icon.getAttribute("title")).toContain(
      "Yahoo Finance: Yahoo respondió",
    );
  });

  it("rojo cuando un proveedor habilitado ha caído", async () => {
    getProviderHealth.mockResolvedValue(
      summary({
        status: "degraded",
        ok: false,
        providers: [
          {
            id: "xtb",
            label: "XTB Bridge",
            enabled: true,
            healthy: false,
            verified: true,
            message: "Bridge no responde",
            lastCheckAt: "2026-10-29T10:00:00+00:00",
            lastCheckOk: false,
          },
        ],
      }),
    );
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() =>
      expect(icon.getAttribute("data-tone")).toBe("degraded"),
    );
    const title = icon.getAttribute("title") ?? "";
    expect(title).toContain("Algún servidor de datos ha caído");
    expect(title).toContain("XTB Bridge: Bridge no responde");
  });

  it("ámbar si falta medir; nunca verde por optimismo", async () => {
    getProviderHealth.mockResolvedValue(
      summary({
        status: "unverified",
        ok: false,
        measuredAt: null,
        providers: [
          {
            id: "yahoo",
            label: "Yahoo Finance",
            enabled: true,
            healthy: false,
            verified: false,
            message: "Sin verificar (usa «Probar conexión»)",
            lastCheckAt: null,
            lastCheckOk: null,
          },
        ],
      }),
    );
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() =>
      expect(icon.getAttribute("data-tone")).toBe("unverified"),
    );
    expect(icon.getAttribute("title")).toContain("Sin medición reciente");
  });

  it("gris si no hay proveedores habilitados y lo declara", async () => {
    getProviderHealth.mockResolvedValue(
      summary({
        status: "none",
        ok: false,
        providers: [
          {
            id: "yahoo",
            label: "Yahoo Finance",
            enabled: false,
            healthy: false,
            verified: false,
            message: "Deshabilitado en Configuración",
          },
        ],
      }),
    );
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() => expect(icon.getAttribute("data-tone")).toBe("none"));
    expect(icon.getAttribute("title")).toContain(
      "Yahoo Finance: deshabilitado (no cuenta para el veredicto)",
    );
  });

  it("el clic abre Configuración en la pestaña Sync / proveedores", async () => {
    getProviderHealth.mockResolvedValue(summary());
    renderButton();

    screen.getByTestId("status-bar-provider-health").click();
    expect(openPlatformConfig).toHaveBeenCalledWith("other");
  });

  it("ámbar stale cuando hay medición pero el bucle no la refresca", async () => {
    getProviderHealth.mockResolvedValue(
      summary({
        status: "stale",
        ok: false,
        autoCheckEnabled: true,
        checkIntervalSeconds: 300,
        measuredAt: "2020-01-01T00:00:00+00:00",
      }),
    );
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() => expect(icon.getAttribute("data-tone")).toBe("stale"));
    const title = icon.getAttribute("title") ?? "";
    expect(title).toContain("no está refrescando");
    expect(title).toContain("Se comprueba cada 300 s");
  });

  it("con la automática OFF declara la cadencia desactivada", async () => {
    getProviderHealth.mockResolvedValue(
      summary({ autoCheckEnabled: false, nextCheckAt: null }),
    );
    renderButton();

    const icon = screen.getByTestId("status-bar-provider-health");
    await waitFor(() => expect(icon.getAttribute("data-tone")).toBe("ok"));
    expect(icon.getAttribute("title")).toContain(
      "Comprobación automática desactivada",
    );
  });
});

describe("healthPollIntervalMs · cadencia derivada de la política", () => {
  it("con 300 s consulta a 60 s (techo) y nunca menos de 15 s", () => {
    expect(
      healthPollIntervalMs({
        status: "ok",
        ok: true,
        checkIntervalSeconds: 300,
        providers: [],
      }),
    ).toBe(60_000);
    expect(
      healthPollIntervalMs({
        status: "ok",
        ok: true,
        checkIntervalSeconds: 20,
        providers: [],
      }),
    ).toBe(15_000);
  });

  it("OFF consulta despacio: no hay nada que refrescar solo", () => {
    expect(
      healthPollIntervalMs({
        status: "ok",
        ok: true,
        autoCheckEnabled: false,
        checkIntervalSeconds: 60,
        providers: [],
      }),
    ).toBe(PROVIDER_HEALTH_POLL_OFF_MS);
  });
});
