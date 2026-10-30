import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InvestmentAccountDto, InvestorProfileV1 } from "@bolsa/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountInvestorProfileSelect } from "@/features/accounts/account-investor-profile-select";

const mocks = vi.hoisted(() => ({
  listInvestorProfiles: vi.fn(),
  getAccounts: vi.fn(),
  assignAccountProfile: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listInvestorProfiles: mocks.listInvestorProfiles,
    getAccounts: mocks.getAccounts,
    assignAccountProfile: mocks.assignAccountProfile,
  },
}));

function profile(profileId: string, name: string): InvestorProfileV1 {
  return {
    profileId,
    name,
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
}

const profiles = [
  profile("prof-moderate", "Moderado"),
  profile("prof-other", "Otro"),
];

function account(
  id: string,
  name: string,
  activeProfileId: string | null,
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
    activeProfileId,
    createdAt: "2026-10-30T00:00:00.000Z",
    updatedAt: "2026-10-30T00:00:00.000Z",
    lastActivityAt: null,
  };
}

function renderSelect(activeProfileId: string | null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AccountInvestorProfileSelect
        accountId="acc-a"
        activeProfileId={activeProfileId}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.listInvestorProfiles.mockResolvedValue({ data: profiles });
  mocks.getAccounts.mockResolvedValue({
    data: [account("acc-a", "Cuenta A", "prof-moderate")],
  });
  mocks.assignAccountProfile.mockResolvedValue({
    data: { accountId: "acc-a", activeProfileId: "prof-other" },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountInvestorProfileSelect — única asignación (CU-D2/CU-D7)", () => {
  it("no crea perfiles al montarse y muestra el perfil activo", async () => {
    renderSelect("prof-moderate");

    const active = await screen.findByTestId("account-profile-active");
    expect(active.textContent).toContain("Moderado · Moderado");
    expect(screen.queryByTestId("account-profile-missing")).toBeNull();
    // El mock no define `ensureDefaultInvestorProfiles`: una llamada habría reventado.
    expect(mocks.assignAccountProfile).not.toHaveBeenCalled();
  });

  it("sin perfil avisa del fallback moderate", async () => {
    renderSelect(null);

    const missing = await screen.findByTestId("account-profile-missing");
    expect(missing.textContent).toContain("moderate");
  });

  it("asigna solo al pulsar «Aplicar a esta cuenta»", async () => {
    renderSelect("prof-moderate");

    const option = await screen.findByRole("option", { name: /Otro/ });
    fireEvent.click(option);

    // Elegir no persiste: hace falta el botón explícito.
    expect(mocks.assignAccountProfile).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("account-profile-apply"));

    await waitFor(() => {
      expect(mocks.assignAccountProfile).toHaveBeenCalledWith(
        "acc-a",
        "prof-other",
      );
    });
  });

  it("avisa cuando el perfil elegido ya lo usan otras cuentas", async () => {
    mocks.getAccounts.mockResolvedValue({
      data: [
        account("acc-a", "Cuenta A", "prof-moderate"),
        account("acc-b", "Cuenta B", "prof-other"),
      ],
    });
    renderSelect("prof-moderate");

    const option = await screen.findByRole("option", { name: /Otro/ });
    fireEvent.click(option);

    const warning = await screen.findByTestId("account-profile-shared-warning");
    expect(warning.textContent).toContain("Cuenta B");
    expect(warning.textContent).toContain(
      "Compartirán la misma Trading Policy",
    );
  });
});

describe("AccountInvestorProfileSelect — desasignación explícita «Quitar perfil» (AUD-01)", () => {
  it("pide confirmación y no escribe hasta confirmar", async () => {
    renderSelect("prof-moderate");

    fireEvent.click(await screen.findByTestId("account-profile-clear"));

    expect(
      await screen.findByTestId("account-profile-clear-confirm-block"),
    ).toBeTruthy();
    expect(mocks.assignAccountProfile).not.toHaveBeenCalled();
    // La operación es DISTINTA de cambiar el perfil: el selector no viaja en el PUT.
    expect(screen.getByTestId("account-profile-apply")).toBeTruthy();
  });

  it("«Cancelar» cierra la confirmación sin tocar la asignación", async () => {
    renderSelect("prof-moderate");

    fireEvent.click(await screen.findByTestId("account-profile-clear"));
    fireEvent.click(await screen.findByTestId("account-profile-clear-cancel"));

    await waitFor(() => {
      expect(
        screen.queryByTestId("account-profile-clear-confirm-block"),
      ).toBeNull();
    });
    expect(mocks.assignAccountProfile).not.toHaveBeenCalled();
    expect(screen.getByTestId("account-profile-clear")).toBeTruthy();
  });

  it("al confirmar envía un único PUT con profileId null (sin perfil por defecto)", async () => {
    mocks.assignAccountProfile.mockResolvedValue({
      data: { accountId: "acc-a", activeProfileId: null },
    });
    renderSelect("prof-moderate");

    fireEvent.click(await screen.findByTestId("account-profile-clear"));
    fireEvent.click(await screen.findByTestId("account-profile-clear-confirm"));

    await waitFor(() => {
      expect(mocks.assignAccountProfile).toHaveBeenCalledTimes(1);
    });
    expect(mocks.assignAccountProfile).toHaveBeenCalledWith("acc-a", null);
    // Ni bootstrap ni reasignación: el mock no define `ensureDefaultInvestorProfiles`,
    // así que cualquier llamada habría reventado el test. El resultado en servidor es
    // `active_profile_id = NULL` (la UI refleja el nuevo estado al refrescar la cuenta).
  });

  it("sin perfil activo no ofrece «Quitar perfil»", async () => {
    renderSelect(null);

    await screen.findByTestId("account-profile-missing");
    expect(screen.queryByTestId("account-profile-clear")).toBeNull();
  });
});
