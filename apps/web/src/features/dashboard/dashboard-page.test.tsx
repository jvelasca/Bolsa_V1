/**
 * Overview — guarda de la simplificación (2026-11-01).
 *
 * Falsable: la pantalla vuelve a llenarse de documentación de arquitectura
 * interna (`Score_FUND`, `PAPER_D_EXECUTE`, `whitelist`), tutoriales que repiten
 * los accesos o el estado de sync que ya vive en Configuración.
 *
 * Se fija lo que la pantalla **sí** responde — cuenta activa + patrimonio,
 * accesos rápidos y últimos movimientos — y lo que **no** debe volver al primer
 * nivel (`RT-01` / `R-G1` / `UI5-20`).
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §2
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type {
  AccountSummaryDto,
  InvestmentAccountDto,
  LedgerEntryDto,
} from "@bolsa/shared";

const apiMock = vi.hoisted(() => ({
  getHealth: vi.fn(),
  getAccountSummary: vi.fn(),
  getAccountLedger: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
  ApiError: class ApiError extends Error {},
}));

const accountsMock = vi.hoisted(() => ({
  accounts: [] as InvestmentAccountDto[],
  account: null as InvestmentAccountDto | null,
  isLoading: false,
}));

vi.mock("@/features/accounts/use-active-account", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/features/accounts/use-active-account")
    >();
  return {
    ...actual,
    useActiveAccount: () => ({
      account: accountsMock.account,
      effectiveAccountId: accountsMock.account?.id ?? null,
      isLoading: accountsMock.isLoading,
      accounts: accountsMock.accounts,
    }),
  };
});

import { OverviewPage } from "@/features/dashboard/dashboard-page";

const ACCOUNT: InvestmentAccountDto = {
  id: "acc-overview",
  userId: "user-overview",
  name: "Cuenta demo EUR",
  description: null,
  type: "simulated",
  status: "active",
  currency: "EUR",
  baseCurrency: "EUR",
  initialDeposit: 100_000,
  leverage: 1,
  marginCallLevelPct: null,
  isDefault: true,
  settings: null,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
  lastActivityAt: null,
};

const SUMMARY = {
  account: ACCOUNT,
  defaultPortfolio: {
    id: "pf-1",
    accountId: ACCOUNT.id,
    name: "Cartera",
    isDefault: true,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  },
  cash: 99_800,
  totalMarketValue: 0,
  totalCost: 0,
  totalUnrealizedPnl: 0,
  totalRealizedPnl: null,
  totalEquity: 99_800,
  marginUsed: 0,
  freeMargin: 99_800,
  marginLevelPct: null,
  positionsCount: 0,
} as unknown as AccountSummaryDto;

const LEDGER: LedgerEntryDto[] = [
  {
    id: "led-1",
    accountId: ACCOUNT.id,
    portfolioId: null,
    type: "fee",
    amount: -200,
    currency: "EUR",
    balanceAfter: 99_800,
    instrumentId: null,
    symbol: null,
    quantity: null,
    price: null,
    referenceType: "custody",
    referenceId: null,
    description: null,
    executedAt: "2026-10-01T00:00:00.000Z",
  },
  {
    id: "led-2",
    accountId: ACCOUNT.id,
    portfolioId: null,
    type: "deposit",
    amount: 100_000,
    currency: "EUR",
    balanceAfter: 100_000,
    instrumentId: null,
    symbol: null,
    quantity: null,
    price: null,
    referenceType: "manual",
    referenceId: null,
    description: null,
    executedAt: "2026-09-30T00:00:00.000Z",
  },
];

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/overview"]}>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  accountsMock.accounts = [];
  accountsMock.account = null;
  accountsMock.isLoading = false;
});

function seedHappyPath() {
  accountsMock.account = ACCOUNT;
  accountsMock.accounts = [ACCOUNT];
  apiMock.getHealth.mockResolvedValue({ status: "ok" });
  apiMock.getAccountSummary.mockResolvedValue({ data: SUMMARY });
  apiMock.getAccountLedger.mockResolvedValue({ data: LEDGER });
}

describe("Overview · estructura", () => {
  it("tiene un solo h1 y no salta de nivel", async () => {
    seedHappyPath();
    renderPage();

    const headings = screen.getAllByRole("heading") as HTMLElement[];
    const levels = headings.map((h) => Number(h.tagName.slice(1)));

    expect(levels.filter((level) => level === 1)).toHaveLength(1);
    expect(headings[0]?.textContent?.trim()).toBe("Overview");
    for (let i = 1; i < levels.length; i += 1) {
      expect(levels[i]! - levels[i - 1]!).toBeLessThanOrEqual(1);
    }
  });

  it("responde con la cuenta activa y sus cuatro métricas", async () => {
    seedHappyPath();
    renderPage();

    const accountSection = screen
      .getByRole("heading", { level: 2, name: "Cuenta activa" })
      .closest("section");
    expect(accountSection).not.toBeNull();
    const section = within(accountSection as HTMLElement);

    expect(section.getByText("Cuenta demo EUR")).toBeTruthy();
    // El resumen llega de forma asíncrona: sin dato todavía → valor medido.
    expect(await section.findByText("Patrimonio")).toBeTruthy();
    const metrics = () => {
      const value = (label: string) => {
        const card = section.getByText(label).parentElement;
        return card?.querySelectorAll("p")[1]?.textContent?.trim() ?? "";
      };
      return {
        patrimonio: value("Patrimonio"),
        disponible: value("Capital disponible"),
        noRealizado: value("Beneficio no realizado"),
        posiciones: value("Posiciones abiertas"),
      };
    };
    await vi.waitFor(() =>
      expect(metrics()).toEqual({
        patrimonio: "99800.00",
        disponible: "99800.00",
        noRealizado: "0.00",
        posiciones: "0",
      }),
    );
    expect(section.getByText("Margen libre 99800.00")).toBeTruthy();
  });

  it("sin cuenta activa declara el hueco en vez de ceros fabricados", () => {
    apiMock.getHealth.mockResolvedValue({ status: "ok" });
    renderPage();

    expect(
      screen.getByText(/No hay cuenta activa\. Crea una demo/),
    ).toBeTruthy();
    expect(screen.queryByText("Patrimonio")).toBeNull();
  });

  it("avisa cuando la API no responde", async () => {
    seedHappyPath();
    apiMock.getHealth.mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findByText(/API no disponible/)).toBeTruthy();
  });
});

describe("Overview · accesos rápidos", () => {
  it("resume la navegación en cuatro enlaces con su destino", () => {
    seedHappyPath();
    renderPage();

    const nav = screen.getByRole("navigation", { name: "Accesos rápidos" });
    const links = within(nav).getAllByRole("link");

    expect(links).toHaveLength(4);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/trading",
      "/operations",
      "/history",
      "/accounts",
    ]);
    expect(within(nav).getByText("Trading")).toBeTruthy();
    expect(within(nav).getByText("Operaciones")).toBeTruthy();
    expect(within(nav).getByText("Historial")).toBeTruthy();
    expect(within(nav).getByText("Cuentas")).toBeTruthy();
  });

  it("señala cuántas otras cuentas activas hay", () => {
    seedHappyPath();
    const second = { ...ACCOUNT, id: "acc-2", name: "Cuenta demo USD" };
    accountsMock.accounts = [ACCOUNT, second];
    renderPage();

    expect(screen.getByTestId("overview-other-accounts-link")).toBeTruthy();
    expect(screen.getByText(/1 otra cuenta activa/)).toBeTruthy();
  });
});

describe("Overview · últimos movimientos", () => {
  it("pinta los asientos de la cuenta activa con su importe", async () => {
    seedHappyPath();
    renderPage();

    const card = screen
      .getByRole("heading", { level: 2, name: "Últimos movimientos" })
      .closest("div.rounded-xl") as HTMLElement;
    const scope = within(card);

    expect(await scope.findByText("Custodia anual")).toBeTruthy();
    expect(scope.getByText("Depósito inicial")).toBeTruthy();
    expect(scope.getByText("-200.00")).toBeTruthy();
    expect(scope.getByText("100000.00")).toBeTruthy();
  });

  it("declara el vacío cuando no hay movimientos", async () => {
    seedHappyPath();
    apiMock.getAccountLedger.mockResolvedValue({ data: [] });
    renderPage();

    expect(
      await screen.findByText(/Sin movimientos\. Cuando operes o deposites/),
    ).toBeTruthy();
  });
});

describe("Overview · nada de jerga ni duplicidades en primer nivel", () => {
  it("no vuelve a mostrar investigación, tutorial ni estado de sync", async () => {
    seedHappyPath();
    renderPage();

    // Espera a que las queries resuelvan antes de auditar el texto.
    await screen.findByText("Custodia anual");

    const text = document.body.textContent ?? "";
    for (const removed of [
      "Investigación",
      "Por dónde seguir",
      "Datos de mercado",
      "Backtesting",
    ]) {
      expect(text, `«${removed}» no debe volver a Overview`).not.toContain(
        removed,
      );
    }

    for (const jargon of [
      "Score_FUND",
      "PAPER_D_EXECUTE",
      "whitelist",
      "FIE",
      "Paper D",
    ]) {
      expect(text, `jerga «${jargon}» en nivel 1`).not.toContain(jargon);
    }
  });
});
