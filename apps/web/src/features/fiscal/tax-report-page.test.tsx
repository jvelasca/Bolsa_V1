/**
 * `/fiscal` — revisión UI de comisiones y fiscal (2026-10-30).
 *
 * Fija los hallazgos del documento `seguimiento-ui-fiscal-comisiones-2026-10-30`:
 * - COM-D2: el impuesto estimado que el backend YA calcula se pinta (y solo cuando existe).
 * - COM-D3: la card de comisiones dice «del ejercicio · sin custodia», no «histórico».
 * - COM-D7: el selector declara que cambia la cuenta activa de TODA la app.
 * - COM-D9: importes con su moneda y el error de API con su detalle.
 * - COM-D10: «editar perfil fiscal» enlaza a la ficha con la pestaña Fiscal enfocada.
 */

import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InvestmentAccountDto, TaxReportSummaryDto } from "@bolsa/shared";
import { defaultAccountSettings } from "@bolsa/shared";

let accounts: InvestmentAccountDto[] = [];
let report: TaxReportSummaryDto | null = null;
let reportError: Error | null = null;

const getAccounts = vi.fn(async () => ({ data: accounts }));
const getTaxReport = vi.fn(async () => {
  if (reportError) throw reportError;
  return { data: report as TaxReportSummaryDto };
});

vi.mock("@/lib/api", () => ({
  api: {
    getAccounts: () => getAccounts(),
    getTaxReport: (accountId: string, year?: number) =>
      getTaxReport(accountId, year),
  },
}));

import { TaxReportPage } from "@/features/fiscal/tax-report-page";
import { useActiveAccountStore } from "@/stores/active-account-store";

function makeAccount(
  overrides: Partial<InvestmentAccountDto> = {},
): InvestmentAccountDto {
  return {
    id: "acc-fiscal",
    userId: null,
    name: "Demo fiscal",
    description: null,
    type: "simulated",
    status: "active",
    currency: "USD",
    baseCurrency: "USD",
    initialDeposit: 100_000,
    leverage: 1,
    marginCallLevelPct: null,
    isDefault: true,
    settings: defaultAccountSettings("standard_es", "ES"),
    activeProfileId: "moderate",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    lastActivityAt: null,
    ...overrides,
  };
}

function makeReport(
  overrides: Partial<TaxReportSummaryDto> = {},
): TaxReportSummaryDto {
  return {
    accountId: "acc-fiscal",
    currency: "USD",
    method: "fifo",
    jurisdiction: "ES",
    year: new Date().getFullYear(),
    periodLabel: `Año natural ${new Date().getFullYear()}`,
    realizedLines: [
      {
        id: "line-1",
        instrumentId: "inst-1",
        symbol: "AAPL",
        sellTransactionId: "tx-sell",
        executedAt: "2026-06-01T10:00:00Z",
        quantity: 5,
        sellPrice: 120,
        proceeds: 600,
        costBasis: 500,
        realizedGain: 100,
        method: "fifo",
        acquisitionDates: ["2026-01-01T00:00:00Z"],
      },
    ],
    totalGains: 100,
    totalLosses: 0,
    netRealizedGain: 100,
    estimatedTaxLiability: 19,
    unrealizedLines: [],
    totalUnrealizedGain: null,
    feesPaidTotal: 3.963,
    dividendWithholdingPct: 19,
    openPositionCount: 0,
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/fiscal"]}>
        <TaxReportPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  accounts = [makeAccount()];
  report = makeReport();
  reportError = null;
  useActiveAccountStore.setState({ activeAccountId: "acc-fiscal" });
  getAccounts.mockImplementation(async () => ({ data: accounts }));
  getTaxReport.mockImplementation(async () => {
    if (reportError) throw reportError;
    return { data: report as TaxReportSummaryDto };
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TaxReportPage · resumen", () => {
  it("pinta el impuesto estimado con el tipo aplicado y el aviso de proyección", async () => {
    renderPage();

    const taxCard = await screen.findByTestId("fiscal-estimated-tax-card");
    expect(
      within(taxCard).getByTestId("fiscal-estimated-tax"),
    ).toHaveTextContent("$19.00");
    expect(taxCard).toHaveTextContent("tipo 19 % sobre el neto realizado");
    expect(taxCard).toHaveTextContent("proyección, no retención");
    // La simplificación del IRPF progresivo se declara en la propia card.
    expect(taxCard).toHaveTextContent(
      "IRPF del ahorro en España es progresivo",
    );
  });

  it("no inventa la card de impuesto cuando el backend no devuelve estimación", async () => {
    report = makeReport({ estimatedTaxLiability: null });
    renderPage();

    await screen.findByTestId("fiscal-net-realized");
    expect(
      screen.queryByTestId("fiscal-estimated-tax-card"),
    ).not.toBeInTheDocument();
  });

  it("etiqueta las comisiones como del ejercicio y sin custodia (COM-D3)", async () => {
    renderPage();

    const fees = await screen.findByTestId("fiscal-fees");
    expect(fees).toHaveTextContent("Comisiones de operaciones");
    expect(fees).toHaveTextContent("sin custodia");
    expect(fees).toHaveTextContent("$3.96");
    expect(screen.queryByText(/Histórico acumulado/)).not.toBeInTheDocument();
  });

  it("usa la moneda del informe en todos los importes (COM-D9)", async () => {
    renderPage();

    const net = await screen.findByTestId("fiscal-net-realized");
    expect(net).toHaveTextContent("$100.00");
    expect(screen.getByText("$600.00")).toBeInTheDocument(); // ingresos
    expect(screen.getByText("$500.00")).toBeInTheDocument(); // coste
  });

  it("muestra el estado vacío cuando no hay ventas en el ejercicio", async () => {
    report = makeReport({
      realizedLines: [],
      totalGains: 0,
      netRealizedGain: 0,
      estimatedTaxLiability: null,
    });
    renderPage();

    expect(
      await screen.findByText(/Sin ventas con plusvalía\/minusvalía en/),
    ).toBeInTheDocument();
  });
});

describe("TaxReportPage · errores y navegación", () => {
  it("muestra el detalle del error de API en vez de un texto genérico (COM-D9)", async () => {
    reportError = new Error("422 — el perfil fiscal no tiene método de coste");
    renderPage();

    const error = await screen.findByTestId("fiscal-error");
    expect(error).toHaveTextContent("No se pudo generar el informe fiscal");
    expect(error).toHaveTextContent(
      "422 — el perfil fiscal no tiene método de coste",
    );
  });

  it("declara que el selector cambia la cuenta activa de la app (COM-D7)", async () => {
    renderPage();

    expect(
      await screen.findByText("Cuenta activa de la app"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Cambiar de cuenta aquí cambia también la cuenta con la que opera/,
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("fiscal-account-select")).toHaveValue(
        "acc-fiscal",
      ),
    );
  });
  it("enlaza a la ficha de cuenta con la pestaña Fiscal enfocada (COM-D10)", async () => {
    renderPage();

    const link = await screen.findByTestId("fiscal-edit-profile-link");
    expect(link).toHaveAttribute(
      "href",
      "/accounts?selected=acc-fiscal&tab=config&focus=fiscal",
    );
  });

  it("resume el perfil fiscal que aplica el backend", async () => {
    renderPage();

    const profile = await screen.findByText(/Perfil fiscal aplicado/);
    expect(profile.parentElement).toHaveTextContent("FIFO");
    expect(screen.getByText(/plusvalías 19 %/)).toBeInTheDocument();
  });
});
