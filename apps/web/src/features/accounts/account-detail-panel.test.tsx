import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { InvestmentAccountDto, InvestorProfileV1 } from "@bolsa/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountDetailPanel } from "@/features/accounts/account-detail-panel";
import { useActiveAccountStore } from "@/stores/active-account-store";

const mocks = vi.hoisted(() => ({
  getAccountSummary: vi.fn(),
  listInvestorProfiles: vi.fn(),
  getPortfolio: vi.fn(),
  getAccountLedger: vi.fn(),
  getAccounts: vi.fn(),
  setDefaultAccount: vi.fn(),
  updateAccount: vi.fn(),
  closeAccount: vi.fn(),
  deleteAccount: vi.fn(),
  depositCash: vi.fn(),
  withdrawCash: vi.fn(),
  assignAccountProfile: vi.fn(),
  getAccountBrokerVenue: vi.fn(),
  updateAccountSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSummary: mocks.getAccountSummary,
    listInvestorProfiles: mocks.listInvestorProfiles,
    getPortfolio: mocks.getPortfolio,
    getAccountLedger: mocks.getAccountLedger,
    getAccounts: mocks.getAccounts,
    setDefaultAccount: mocks.setDefaultAccount,
    updateAccount: mocks.updateAccount,
    closeAccount: mocks.closeAccount,
    deleteAccount: mocks.deleteAccount,
    depositCash: mocks.depositCash,
    withdrawCash: mocks.withdrawCash,
    assignAccountProfile: mocks.assignAccountProfile,
    getAccountBrokerVenue: mocks.getAccountBrokerVenue,
    updateAccountSettings: mocks.updateAccountSettings,
  },
}));

vi.mock("@/features/trading/demo-book-mode-panel", () => ({
  DemoBookModePanel: () => null,
}));

const profile: InvestorProfileV1 = {
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

function account(
  overrides: Partial<InvestmentAccountDto> = {},
): InvestmentAccountDto {
  return {
    id: "acc-a",
    userId: "user-a",
    name: "Demo A",
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
    activeProfileId: "prof-moderate",
    createdAt: "2026-10-30T00:00:00.000Z",
    updatedAt: "2026-10-30T00:00:00.000Z",
    lastActivityAt: null,
    ...overrides,
  };
}

function renderPanel(
  props: {
    account?: InvestmentAccountDto;
    initialTab?: "config";
    focus?: string;
  } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AccountDetailPanel
          account={props.account ?? account()}
          onDelete={() => {}}
          initialTab={props.initialTab}
          focus={props.focus}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  // jsdom no implementa scrollIntoView; el foco de deep-link lo usa.
  Element.prototype.scrollIntoView = vi.fn();
  useActiveAccountStore.setState({ activeAccountId: "acc-other" });
  mocks.getAccountSummary.mockResolvedValue({
    data: {
      account: account(),
      totalEquity: 100_000,
      cash: 90_000,
      totalUnrealizedPnl: 120,
      totalRealizedPnl: 1250.5,
      positionsCount: 2,
    },
  });
  mocks.listInvestorProfiles.mockResolvedValue({ data: [profile] });
  mocks.getPortfolio.mockResolvedValue({ data: { positions: [] } });
  mocks.getAccountLedger.mockResolvedValue({ data: [] });
  mocks.getAccounts.mockResolvedValue({ data: [account()] });
  mocks.setDefaultAccount.mockResolvedValue({ data: account() });
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

describe("AccountDetailPanel — perfil visible y una sola asignación (CU-D2/CU-D9)", () => {
  it("muestra el perfil activo en la cabecera", async () => {
    renderPanel();

    const header = await screen.findByTestId("account-detail-profile");
    await waitFor(() => {
      expect(header.textContent).toContain("Moderado · Moderado");
    });
  });

  it("avisa si la cuenta apunta a un perfil fuera del catálogo", async () => {
    mocks.listInvestorProfiles.mockResolvedValue({ data: [] });
    renderPanel({ account: account({ activeProfileId: "prof-legacy" }) });

    const header = await screen.findByTestId("account-detail-profile");
    await waitFor(() => {
      expect(header.textContent).toContain("fuera del catálogo");
    });
  });

  it("la cabecera muestra «Sin perfil» cuando la cuenta no tiene perfil", async () => {
    renderPanel({ account: account({ activeProfileId: null }) });

    const header = await screen.findByTestId("account-detail-profile");
    await waitFor(() => {
      expect(header.textContent).toContain("Sin perfil");
    });
    expect(header.textContent).not.toContain("se aplica moderate");
  });

  it("pinta el P&L realizado del resumen", async () => {
    renderPanel();

    expect(await screen.findByText("P&L realizado")).toBeTruthy();
    expect(await screen.findByText("1250.50")).toBeTruthy();
  });

  it("«Usar ahora» es la acción explícita de activación", async () => {
    renderPanel();

    fireEvent.click(await screen.findByTestId("account-activate"));

    await waitFor(() => {
      expect(mocks.setDefaultAccount).toHaveBeenCalledWith("acc-a");
    });
  });

  it("?focus=perfil abre Configuración y deja una única superficie de asignación", async () => {
    renderPanel({ focus: "perfil" });

    expect(await screen.findByTestId("account-profile-block")).toBeTruthy();
    expect(
      screen.getAllByTestId("account-investor-profile-select"),
    ).toHaveLength(1);
    // El panel de comisiones/fiscal ya no incluye el selector de perfil.
    expect(screen.getByText("Editar comisiones y fiscal →")).toBeTruthy();
    expect(
      screen.queryByText("Editar perfil, comisiones y fiscal →"),
    ).toBeNull();
  });
});
