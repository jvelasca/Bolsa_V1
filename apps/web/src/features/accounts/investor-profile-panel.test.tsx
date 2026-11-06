import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InvestmentAccountDto, InvestorProfileV1 } from "@bolsa/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InvestorProfilePanel } from "@/features/accounts/investor-profile-panel";

const mocks = vi.hoisted(() => ({
  listInvestorProfiles: vi.fn(),
  createInvestorProfile: vi.fn(),
  updateInvestorProfile: vi.fn(),
  deleteInvestorProfile: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listInvestorProfiles: mocks.listInvestorProfiles,
    createInvestorProfile: mocks.createInvestorProfile,
    updateInvestorProfile: mocks.updateInvestorProfile,
    deleteInvestorProfile: mocks.deleteInvestorProfile,
  },
}));

function profile(
  profileId: string,
  name: string,
  template: "conservative" | "moderate" | "aggressive_swing",
): InvestorProfileV1 {
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
    suggestedPolicyTemplateId: template,
    selectedPolicyTemplateId: template,
    observed: null,
    updatedBy: "user",
    createdAt: "2026-10-30T00:00:00.000Z",
    updatedAt: "2026-10-30T00:00:00.000Z",
  };
}

const profiles: InvestorProfileV1[] = [
  profile("prof-shared", "Moderado compartido", "moderate"),
  profile("prof-free", "Libre", "conservative"),
];

mocks.listInvestorProfiles.mockImplementation(async () => ({ data: profiles }));
mocks.createInvestorProfile.mockImplementation(async () => ({
  data: profiles[1],
}));
mocks.updateInvestorProfile.mockImplementation(async () => ({
  data: profiles[0],
}));
mocks.deleteInvestorProfile.mockImplementation(async () => ({ ok: true }));

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

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <InvestorProfilePanel
        accounts={[
          account("acc-1", "Cuenta A", "prof-shared"),
          account("acc-2", "Cuenta B", "prof-shared"),
          account("acc-3", "Cuenta C", null),
        ]}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvestorProfilePanel — catálogo puro (CU-D1/CU-D4/CU-D7)", () => {
  it("no pide cuenta, no asigna y no crea perfiles al montarse", async () => {
    renderPanel();

    await screen.findByText("Moderado compartido");

    // Sin selector de cuenta ni botón de aplicar.
    expect(screen.queryByText(/Asignar a una cuenta/i)).toBeNull();
    expect(screen.queryByText(/Aplicar perfil a la cuenta/i)).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    // Sin auto-bootstrap: `ensureDefaultInvestorProfiles` ni existe en el mock, así que una
    // llamada habría reventado el render.
    expect(screen.queryByText(/Preparando perfiles por defecto/i)).toBeNull();
    expect(mocks.createInvestorProfile).not.toHaveBeenCalled();
  });

  it("muestra el uso por perfil y bloquea el borrado de un perfil en uso", async () => {
    renderPanel();

    const sharedUsage = await screen.findByTestId("profile-usage-prof-shared");
    expect(sharedUsage.textContent).toContain("En uso en: Cuenta A, Cuenta B");
    expect(screen.getByTestId("profile-usage-prof-free").textContent).toContain(
      "Sin uso",
    );

    const deleteButtons = screen.getAllByRole("button", { name: "Eliminar" });
    expect(deleteButtons).toHaveLength(2);
    expect((deleteButtons[0] as HTMLButtonElement).disabled).toBe(true);
    expect((deleteButtons[1] as HTMLButtonElement).disabled).toBe(false);
  });

  it("avisa al editar un perfil compartido de cuántas cuentas cambian", async () => {
    renderPanel();
    await screen.findByText("Moderado compartido");
    const editButtons = screen.getAllByRole("button", { name: "Editar" });
    fireEvent.click(editButtons[0]);

    const warning = await screen.findByTestId("profile-shared-warning");
    expect(warning.textContent).toContain("2 cuentas");
    expect(warning.textContent).toContain("Cuenta A, Cuenta B");

    // Un perfil sin uso no muestra el aviso.
    fireEvent.click(editButtons[1]);
    await waitFor(() => {
      expect(screen.queryByTestId("profile-shared-warning")).toBeNull();
    });
  });
});
