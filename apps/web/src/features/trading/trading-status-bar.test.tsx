/**
 * UI 5.0 · A3 — la barra de estado no expone abreviaturas crípticas ni tokens de ingeniería
 * en el primer nivel (`RT-01`/`UI5-20`) y el tooltip de OPERATIVA está en español humano.
 *
 * Falsable: si vuelven `Pat.`/`Disp.`/`Ops.`/`Pos.`/`P&L` o `PAPER_D_EXECUTE` al DOM, el test falla.
 *
 * @see docs/engineering/auditoria-ui-5-0-mapa-problemas-2026-10-08.md §2.3, §8
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (§RT-01, UI5-20)
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
import { MemoryRouter } from "react-router-dom";

import { STATUS_BAR_PREFS_KEY } from "@/features/trading/status-bar-prefs";

vi.mock("@/lib/api", () => ({
  api: {
    getHealth: vi.fn(async () => ({ status: "ok" })),
    getProviderHealth: vi.fn(async () => ({
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
            message: "Yahoo respondió 11.2345",
            lastCheckAt: "2026-10-29T10:00:00+00:00",
            lastCheckOk: true,
          },
        ],
      },
    })),
    getPortfolio: vi.fn(async () => ({
      data: {
        totalEquity: 1000,
        totalMarketValue: 400,
        totalUnrealizedPnl: 25,
        portfolio: { cash: 500 },
        positions: [],
      },
    })),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    account: {
      id: "acc-1",
      name: "Cuenta Demo",
      type: "demo",
      currency: "EUR",
    },
    effectiveAccountId: "acc-1",
    isLoading: false,
  }),
  accountTypeShortLabel: () => "DEMO",
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: "semi" }),
}));

vi.mock("@/features/accounts/account-scope-selector", () => ({
  AccountScopeSelector: () => null,
}));
vi.mock("@/features/trading/trading-app-threads", () => ({
  TradingAppThreads: () => null,
}));
vi.mock("@/features/trading/trading-alarm-inbox-button", () => ({
  TradingAlarmInboxButton: () => null,
}));

import { TradingStatusBar } from "@/features/trading/trading-status-bar";

function renderBar() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TradingStatusBar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TradingStatusBar · UI 5.0 lenguaje de primer nivel", () => {
  beforeEach(() => {
    localStorage.removeItem(STATUS_BAR_PREFS_KEY);
  });
  afterEach(() => {
    cleanup();
    localStorage.removeItem(STATUS_BAR_PREFS_KEY);
  });

  it("no pinta abreviaturas crípticas ni `P&L` en el DOM", () => {
    const { container } = renderBar();
    const text = container.textContent ?? "";
    for (const cryptic of ["Pat.", "Disp.", "Ops.", "Pos.", "P&L"]) {
      expect(text).not.toContain(cryptic);
    }
  });

  it("usa palabras reales para las métricas", () => {
    const { container } = renderBar();
    const text = container.textContent ?? "";
    for (const readable of [
      "Patrimonio",
      "Disponible",
      "En mercado",
      "No realizado",
    ]) {
      expect(text).toContain(readable);
    }
  });

  it("expone el nombre completo en el tooltip de cada indicador", () => {
    const { container } = renderBar();
    const titles = Array.from(container.querySelectorAll("[title]")).map(
      (el) => el.getAttribute("title") ?? "",
    );
    expect(titles).toContain("Patrimonio");
    expect(titles).toContain("Capital disponible");
    expect(titles).toContain("Beneficio no realizado");
  });

  it("el tooltip de OPERATIVA usa lenguaje de resultado (sin jerga de mecanismo)", () => {
    const { container } = renderBar();
    const operativa = container.querySelector(
      '[data-testid="status-bar-operativa-mode"]',
    );
    expect(operativa).toBeTruthy();
    const title = operativa?.getAttribute("title") ?? "";
    expect(title).not.toContain("PAPER_D_EXECUTE");
    // Lenguaje de resultado, no de mecanismo (`armado`/`≠`).
    expect(title).toContain("cada operación espera tu confirmación");
    expect(title).toMatch(/se ejecuta sin confirmación/i);
    expect(title).not.toMatch(/armado/i);
    expect(container.textContent ?? "").not.toContain("PAPER_D_EXECUTE");
  });

  it("muestra el icono de servidores de datos verificado y su clic abre Config Sync", async () => {
    const { container } = renderBar();
    const icon = container.querySelector(
      '[data-testid="status-bar-provider-health"]',
    );
    expect(icon).toBeTruthy();
    await waitFor(() => expect(icon?.getAttribute("data-tone")).toBe("ok"));
    const title = icon?.getAttribute("title") ?? "";
    expect(title).toContain("Servidores de datos verificados");
    expect(title).toContain("Yahoo Finance: Yahoo respondió 11.2345");
    expect(title).toContain("Clic → Configuración · Sync / proveedores");
  });

  it("el diálogo de la barra enciende y apaga el icono de servidores (persistido)", async () => {
    const { container } = renderBar();
    fireEvent.click(screen.getByTitle("Configurar barra de estado"));

    const toggle = await screen.findByTestId(
      "status-bar-provider-health-toggle",
    );
    expect((toggle as HTMLInputElement).checked).toBe(true);
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(
        container.querySelector('[data-testid="status-bar-provider-health"]'),
      ).toBeNull(),
    );
    const stored = JSON.parse(
      localStorage.getItem(STATUS_BAR_PREFS_KEY) ?? "{}",
    );
    expect(stored.showProviderHealth).toBe(false);
  });
});
