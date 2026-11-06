/**
 * Asistente «Nueva cuenta demo» — pasos Comisiones/Fiscal/Revisión (2026-10-30).
 *
 * Fija:
 * - COM-D1: una cuenta ES nace con `capitalGainsTaxPct = 19` en el payload real del alta.
 * - COM-D5: el paso Fiscal enseña lo que el backend aplicará y la Revisión resume
 *   comisión, coste de ejemplo y perfil fiscal (antes solo «ES · FIFO»).
 * - COM-D11: los hints de los presets salen del catálogo compartido.
 * - COM-D12: «sin comisiones» no promete «sin impuestos».
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  CreateInvestmentAccountRequestDto,
  InvestorProfileV1,
} from "@bolsa/shared";

const createAccount = vi.fn(
  async (payload: CreateInvestmentAccountRequestDto) => ({
    data: { id: "acc-wizard", ...payload },
  }),
);
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
    createAccount: (payload: CreateInvestmentAccountRequestDto) =>
      createAccount(payload),
    setDefaultAccount: () => setDefaultAccount(),
    listInvestorProfiles: () => listInvestorProfiles(),
  },
}));

import { CreateAccountWizardDialog } from "@/features/accounts/create-account-wizard-dialog";
import { useUiStore } from "@/stores/ui-store";

function renderWizard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateAccountWizardDialog />
    </QueryClientProvider>,
  );
}

function clickNext() {
  fireEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
}

/**
 * Avanza hasta el paso indicado esperando a que el catálogo de perfiles esté cargado:
 * el paso «Perfil» valida que haya un `existingProfileId`, que el orquestador
 * preselecciona en un efecto cuando la query resuelve.
 */
async function goToStep(step: "commissions" | "tax" | "review") {
  clickNext(); // identity → capital
  clickNext(); // capital → profile
  fireEvent.click(await screen.findByRole("option", { name: /Moderado/ }));
  clickNext(); // profile → commissions
  await screen.findByTestId("wizard-preset-standard_es");
  if (step === "commissions") return;
  clickNext(); // commissions → tax
  await screen.findByTestId("wizard-tax-summary");
  if (step === "tax") return;
  clickNext(); // tax → review
  await screen.findByText("Coste de una compra de 5.000");
}

beforeEach(() => {
  createAccount.mockClear();
  setDefaultAccount.mockClear();
  listInvestorProfiles.mockClear();
  useUiStore.setState({ createAccountWizardOpen: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useUiStore.setState({ createAccountWizardOpen: false });
});

describe("CreateAccountWizardDialog · comisiones y fiscal", () => {
  it("llena el paso de comisiones desde el catálogo compartido (COM-D11)", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta fiscal test" },
    });
    await goToStep("commissions");

    expect(
      screen.getByText(/0,1 % comisión · mín\. 1,00 EUR/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Sin comisión de operación · los impuestos dependen/),
    ).toBeInTheDocument();
    // No se ofrece «Personalizado» aquí: se afina después en Configuración.
    expect(
      screen.queryByTestId("wizard-preset-custom"),
    ).not.toBeInTheDocument();
  });

  it("resume en Fiscal lo que aplicará el backend (COM-D5)", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta fiscal test" },
    });
    await goToStep("tax");

    const summary = screen.getByTestId("wizard-tax-summary");
    expect(summary).toHaveTextContent("Tipo sobre plusvalías");
    expect(summary).toHaveTextContent("19 % · proyección del informe");
    expect(summary).toHaveTextContent("Retención de dividendos");
    expect(summary).toHaveTextContent("Transmisiones (solo compras)");
    expect(summary).toHaveTextContent("Desde el 1 de enero");
  });

  it("declara que US no proyecta impuesto de plusvalías", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta US" },
    });
    await goToStep("tax");

    fireEvent.change(screen.getByTestId("wizard-tax-jurisdiction"), {
      target: { value: "US" },
    });
    const summary = screen.getByTestId("wizard-tax-summary");
    expect(summary).toHaveTextContent("No se estima");
    expect(summary).toHaveTextContent("30 %"); // retención dividendos US
  });

  it("la Revisión enseña comisión, coste de ejemplo y perfil fiscal (COM-D5)", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta revisión" },
    });
    await goToStep("review");

    const review = within(screen.getByTestId("wizard-review"));
    const reviewRow = (label: string) =>
      review.getByText(label).closest("div")!;

    expect(reviewRow("Comisiones")).toHaveTextContent("Broker estándar ES");

    const costRow = reviewRow("Coste de una compra de 5.000");
    expect(costRow).toHaveTextContent("16.05 €");
    expect(costRow).toHaveTextContent("comisión 5.00 €");
    expect(costRow).toHaveTextContent("IVA 1.05 €");
    expect(costRow).toHaveTextContent("transmisiones 10.00 €");

    const fiscalRow = reviewRow("Fiscal");
    expect(fiscalRow).toHaveTextContent("España (ES) · FIFO");
    expect(fiscalRow).toHaveTextContent("plusvalías 19 %");
  });

  it("crea la cuenta ES con el 19 % canónico en el payload (COM-D1)", async () => {
    renderWizard();
    fireEvent.change(screen.getByPlaceholderText("Cuenta demo EUR"), {
      target: { value: "Cuenta ES" },
    });
    await goToStep("review");
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() => expect(createAccount).toHaveBeenCalledTimes(1));
    const payload = createAccount.mock.calls[0][0];
    expect(payload.name).toBe("Cuenta ES");
    expect(payload.settings?.tax.capitalGainsTaxPct).toBe(19);
    expect(payload.settings?.tax.dividendWithholdingPct).toBe(19);
    expect(payload.settings?.commission.presetId).toBe("standard_es");
  });
});
