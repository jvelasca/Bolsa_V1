import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { InvestmentAccountDto, InvestorProfileV1 } from "@bolsa/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountsPage } from "@/features/accounts/accounts-page";
import { useActiveAccountStore } from "@/stores/active-account-store";

const mocks = vi.hoisted(() => ({
  getAccounts: vi.fn(),
  getAccountSummaries: vi.fn(),
  listInvestorProfiles: vi.fn(),
  getAccountSummary: vi.fn(),
  getPortfolio: vi.fn(),
  getAccountLedger: vi.fn(),
  setDefaultAccount: vi.fn(),
  closeAccount: vi.fn(),
  updateAccount: vi.fn(),
  deleteAccount: vi.fn(),
  assignAccountProfile: vi.fn(),
  getAccountBrokerVenue: vi.fn(),
  updateAccountSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAccounts: mocks.getAccounts,
    getAccountSummaries: mocks.getAccountSummaries,
    listInvestorProfiles: mocks.listInvestorProfiles,
    getAccountSummary: mocks.getAccountSummary,
    getPortfolio: mocks.getPortfolio,
    getAccountLedger: mocks.getAccountLedger,
    setDefaultAccount: mocks.setDefaultAccount,
    closeAccount: mocks.closeAccount,
    updateAccount: mocks.updateAccount,
    deleteAccount: mocks.deleteAccount,
    assignAccountProfile: mocks.assignAccountProfile,
    getAccountBrokerVenue: mocks.getAccountBrokerVenue,
    updateAccountSettings: mocks.updateAccountSettings,
  },
}));

vi.mock("@/features/trading/demo-book-mode-panel", () => ({
  DemoBookModePanel: () => null,
}));

function account(
  id: string,
  name: string,
  overrides: Partial<InvestmentAccountDto> = {},
): InvestmentAccountDto {
  return {
    id,
    userId: "user-a",
    name,
    description: null,
    type: "simulated",
    status: "active",
    currency: "EUR",
    baseCurrency: "EUR",
    initialDeposit: 100_000,
    leverage: 1,
    marginCallLevelPct: null,
    isDefault: false,
    settings: null,
    activeProfileId: null,
    createdAt: "2026-10-30T00:00:00.000Z",
    updatedAt: "2026-10-30T00:00:00.000Z",
    lastActivityAt: null,
    ...overrides,
  };
}

const profileModerate: InvestorProfileV1 = {
  profileId: "prof-moderate",
  name: "Moderado",
  version: "1.0.0",
  userId: "user-a",
  declared: {
    horizon: "swing",
    objectives: ["growth"],
    riskTolerance: "moderate",
    experience: "intermediate",
    maxAcceptableLossPct: null,
    notes: null,
  },
  suggestedPolicyTemplateId: "moderate",
  selectedPolicyTemplateId: "moderate",
  observed: null,
  updatedBy: "user",
  createdAt: "2026-10-30T00:00:00.000Z",
  updatedAt: "2026-10-30T00:00:00.000Z",
};

const demoA = account("acc-a", "Demo A", { activeProfileId: "prof-moderate" });
const demoB = account("acc-b", "Demo B");
const paperP = account("acc-p", "Paper P", { type: "paper" });

function summary(accountRow: InvestmentAccountDto) {
  return {
    account: accountRow,
    totalEquity: 100_000,
    cash: 100_000,
    totalUnrealizedPnl: 0,
    totalRealizedPnl: 1250.5,
    positionsCount: 0,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function renderPage(initialEntry = "/accounts") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AccountsPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useActiveAccountStore.setState({ activeAccountId: "acc-a" });
  mocks.getAccounts.mockResolvedValue({ data: [demoA, demoB, paperP] });
  mocks.getAccountSummaries.mockResolvedValue({
    data: [summary(demoA), summary(demoB), summary(paperP)],
  });
  mocks.listInvestorProfiles.mockResolvedValue({ data: [profileModerate] });
  mocks.getAccountSummary.mockResolvedValue({ data: summary(demoA) });
  mocks.getPortfolio.mockResolvedValue({ data: { positions: [] } });
  mocks.getAccountLedger.mockResolvedValue({ data: [] });
  mocks.setDefaultAccount.mockResolvedValue({ data: demoB });
  mocks.getAccountBrokerVenue.mockResolvedValue({
    accountId: "acc-a",
    preference: null,
    effective: "paper",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useActiveAccountStore.setState({ activeAccountId: null });
});

describe("AccountsPage — selección ≠ cuenta activa (CU-D3)", () => {
  it("seleccionar una cuenta no la activa, solo navega y persiste ?selected=", async () => {
    renderPage();

    const row = await screen.findByTestId("account-list-item-acc-b");
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByTestId("location-search").textContent).toContain(
        "selected=acc-b",
      );
    });
    // La cuenta activa de la app no cambia sin acción explícita.
    expect(mocks.setDefaultAccount).not.toHaveBeenCalled();
    expect(useActiveAccountStore.getState().activeAccountId).toBe("acc-a");
  });

  it("«Usar ahora» sí activa la cuenta y refleja en servidor", async () => {
    renderPage("/accounts?selected=acc-b");

    const activate = await screen.findByTestId("account-activate");
    fireEvent.click(activate);

    await waitFor(() => {
      expect(mocks.setDefaultAccount).toHaveBeenCalledWith("acc-b");
    });
    expect(useActiveAccountStore.getState().activeAccountId).toBe("acc-b");
  });

  it("muestra el perfil de cada cuenta o «Sin perfil»", async () => {
    renderPage();

    const withProfile = await screen.findByTestId("account-list-profile-acc-a");
    expect(withProfile.textContent).toContain("Perfil: Moderado · Moderado");

    const withoutProfile = screen.getByTestId("account-list-profile-acc-b");
    expect(withoutProfile.textContent?.trim()).toBe("Sin perfil");
  });

  it("avisa cuando la cuenta activa queda fuera del filtro y no mezcla detalle", async () => {
    useActiveAccountStore.setState({ activeAccountId: "acc-p" });
    renderPage();

    const notice = await screen.findByTestId("accounts-active-outside-filter");
    expect(notice.textContent).toContain("Paper P");
    // El detalle sigue mostrando una cuenta del filtro (demo), no la activa.
    expect(screen.getByTestId("account-list-item-acc-a")).toBeTruthy();
    expect(mocks.setDefaultAccount).not.toHaveBeenCalled();
  });

  it("un fallo de carga se muestra como error, no como «no hay cuentas»", async () => {
    mocks.getAccounts.mockRejectedValue(new Error("API caída"));
    renderPage();

    const alert = await screen.findByTestId("accounts-load-error");
    expect(alert.textContent).toContain("API caída");
    expect(screen.queryByText("No hay cuentas demo activas.")).toBeNull();
  });
});
