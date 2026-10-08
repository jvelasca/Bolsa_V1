/**
 * UI 5.0 · A3 — la barra de estado no expone abreviaturas crípticas ni tokens de ingeniería
 * en el primer nivel (`RT-01`/`UI5-20`) y el tooltip de OPERATIVA está en español humano.
 *
 * Falsable: si vuelven `Pat.`/`Disp.`/`Ops.`/`Pos.`/`P&L` o `PAPER_D_EXECUTE` al DOM, el test falla.
 *
 * @see docs/engineering/auditoria-ui-5-0-mapa-problemas-2026-10-08.md §2.3, §8
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (§RT-01, UI5-20)
 */

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/lib/api", () => ({
  api: {
    getHealth: vi.fn(async () => ({ status: "ok" })),
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
  afterEach(() => {
    cleanup();
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

  it("el tooltip de OPERATIVA no contiene el token prohibido `PAPER_D_EXECUTE`", () => {
    const { container } = renderBar();
    const operativa = container.querySelector(
      '[data-testid="status-bar-operativa-mode"]',
    );
    expect(operativa).toBeTruthy();
    const title = operativa?.getAttribute("title") ?? "";
    expect(title).not.toContain("PAPER_D_EXECUTE");
    expect(title).toContain("armado ≠ ejecutado");
    expect(container.textContent ?? "").not.toContain("PAPER_D_EXECUTE");
  });
});
