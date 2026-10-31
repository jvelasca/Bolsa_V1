/**
 * CTA-D9 — «Nueva demo» activa la cuenta recién creada de verdad.
 *
 * El asistente fijaba la Activa local ANTES de refrescar la lista de cuentas. Como el
 * `useActiveAccount` global compara el id guardado con su caché de `["accounts"]`, la
 * cuenta recién creada aún no estaba en la caché, se consideraba «inexistente» y el
 * efecto devolvía la Activa al fallback (la semilla). Resultado: la API quedaba con
 * `isDefault` en la cuenta nueva y la app seguía operando con la semilla, sin badge
 * «Activa» en la fila recién creada.
 *
 * La corrección es de orden: esperar el refresco de `["accounts"]` y solo después fijar
 * la Activa local. Este test reproduce el ciclo completo (asistente + consumidor global).
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InvestmentAccountDto, InvestorProfileV1 } from "@bolsa/shared";

const SEED_ID = "default-account-seed";
const NEW_ID = "acc-wizard";

const seedAccount = {
  id: SEED_ID,
  name: "Cuenta demo EUR",
  type: "simulated",
  status: "active",
  currency: "EUR",
  baseCurrency: "EUR",
  isDefault: true,
  activeProfileId: "profile-moderate",
} as unknown as InvestmentAccountDto;

const createdAccount = {
  id: NEW_ID,
  name: "Cuenta nueva",
  type: "simulated",
  status: "active",
  currency: "EUR",
  baseCurrency: "EUR",
  isDefault: false,
  activeProfileId: "profile-moderate",
} as unknown as InvestmentAccountDto;

let accounts: InvestmentAccountDto[] = [seedAccount];

const getAccounts = vi.fn(async () => ({ data: accounts }));
const createAccount = vi.fn(async () => {
  accounts = [...accounts, createdAccount];
  return { data: createdAccount };
});
const setDefaultAccount = vi.fn(async () => ({ data: undefined }));
const listInvestorProfiles = vi.fn(async () => ({
  data: [makeCatalogProfile()],
}));

function makeCatalogProfile(): InvestorProfileV1 {
  return {
    profileId: "profile-moderate",
    version: "1.0.0",
    name: "Moderado",
    declared: {} as InvestorProfileV1["declared"],
    suggestedPolicyTemplateId: "moderate",
    selectedPolicyTemplateId: "moderate",
    updatedBy: "test",
    updatedAt: "2026-01-01T00:00:00Z",
    createdAt: "2026-01-01T00:00:00Z",
  };
}

vi.mock("@/lib/api", () => ({
  api: {
    getAccounts: () => getAccounts(),
    createAccount: () => createAccount(),
    setDefaultAccount: () => setDefaultAccount(),
    listInvestorProfiles: () => listInvestorProfiles(),
  },
}));

import { CreateAccountWizardDialog } from "@/features/accounts/create-account-wizard-dialog";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountStore } from "@/stores/active-account-store";
import { useUiStore } from "@/stores/ui-store";

function ActiveAccountProbe() {
  const { account } = useActiveAccount();
  return <p data-testid="active-account-probe">{account?.id ?? "none"}</p>;
}

function renderWizard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateAccountWizardDialog />
      <ActiveAccountProbe />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  accounts = [seedAccount];
  getAccounts.mockClear();
  createAccount.mockClear();
  setDefaultAccount.mockClear();
  listInvestorProfiles.mockClear();
  useActiveAccountStore.setState({ activeAccountId: SEED_ID });
  useUiStore.setState({ createAccountWizardOpen: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useUiStore.setState({ createAccountWizardOpen: false });
  useActiveAccountStore.setState({ activeAccountId: null });
});

describe("CreateAccountWizardDialog · activación de la cuenta creada", () => {
  it("deja la Activa en la cuenta nueva sin que el refresco la revierta (CTA-D9)", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta nueva" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // identidad → capital
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // capital → perfil
    fireEvent.click(await screen.findByRole("option", { name: /Moderado/ }));
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // perfil → comisiones
    await screen.findByTestId("wizard-preset-standard_es");
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // comisiones → fiscal
    await screen.findByTestId("wizard-tax-summary");
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // fiscal → revisión
    await screen.findByTestId("wizard-review");

    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() => expect(createAccount).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(useActiveAccountStore.getState().activeAccountId).toBe(NEW_ID),
    );
    await waitFor(() =>
      expect(screen.getByTestId("active-account-probe")).toHaveTextContent(
        NEW_ID,
      ),
    );
    // El espejo en servidor sigue siendo best-effort y se pidió una vez.
    await waitFor(() => expect(setDefaultAccount).toHaveBeenCalledTimes(1));
  });
});
