import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { defaultAccountSettings } from "@bolsa/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountSettingsPanel } from "@/features/accounts/account-settings-panel";

const mocks = vi.hoisted(() => ({
  getAccountBrokerVenue: vi.fn(),
  updateAccountSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAccountBrokerVenue: mocks.getAccountBrokerVenue,
    updateAccountSettings: mocks.updateAccountSettings,
  },
}));

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AccountSettingsPanel
        accountId="acc-a"
        currency="EUR"
        settings={defaultAccountSettings()}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.getAccountBrokerVenue.mockResolvedValue({
    accountId: "acc-a",
    preference: null,
    effective: "paper",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountSettingsPanel — solo comisiones y fiscal (CU-D2)", () => {
  it("no repite la asignación de perfil dentro de comisiones/fiscal", () => {
    renderPanel();

    expect(screen.queryByTestId("account-investor-profile-select")).toBeNull();
    expect(screen.queryByText(/Perfil inversor/i)).toBeNull();
    expect(screen.getByText("Guardar comisiones y fiscal")).toBeTruthy();
  });
});
