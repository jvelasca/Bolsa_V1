/**
 * Panel «Configuración → Comisiones y fiscal» (2026-10-30).
 *
 * Fija:
 * - COM-D1: cambiar de jurisdicción y volver a ES aplica el 19 % canónico del dominio.
 * - COM-D4: el tipo de plusvalías es visible y editable (y vacío = no estimar).
 * - COM-D6: la validación de cliente bloquea el guardado SIN petición.
 * - COM-D8: la vista previa usa el mismo cálculo (y redondeo) que el servidor.
 * - COM-D11: los hints del preset salen del catálogo compartido, no de una copia.
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
import type { AccountSettings } from "@bolsa/shared";
import {
  TAX_PRESETS,
  calculateTradeFees,
  defaultAccountSettings,
} from "@bolsa/shared";

const updateAccountSettings = vi.fn(
  async (accountId: string, settings: AccountSettings) => ({
    data: { id: accountId, settings } as unknown,
  }),
);

vi.mock("@/lib/api", () => ({
  api: {
    updateAccountSettings: (accountId: string, settings: AccountSettings) =>
      updateAccountSettings(accountId, settings),
  },
}));

// El panel cuelga el selector de preferencia de mercado, que habla con la API por su
// cuenta: aquí se aísla la superficie de comisiones/fiscal, que es lo que se prueba.
// El selector de perfil ya NO vive en este panel (se asigna en la ficha de la cuenta),
// así que no hay nada que mockear para él.
vi.mock("@/features/accounts/account-venue-preference", () => ({
  AccountVenuePreference: () => null,
}));

import {
  AccountSettingsPanel,
  validateAccountSettings,
} from "@/features/accounts/account-settings-panel";

function renderPanel(
  settings: AccountSettings = defaultAccountSettings("standard_es", "ES"),
  initialTab: "commissions" | "tax" = "commissions",
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountSettingsPanel
        accountId="acc-1"
        currency="EUR"
        settings={settings}
        initialTab={initialTab}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  updateAccountSettings.mockClear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountSettingsPanel · presets y hints", () => {
  it("usa el catálogo compartido para describir cada preset", () => {
    renderPanel();
    expect(
      screen.getByText(/0,1 % comisión · mín\. 1,00 EUR · máx\. 29,00 EUR/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Sin comisión de operación · los impuestos dependen/),
    ).toBeInTheDocument();
  });

  it("marca el preset como personalizado al editar un número", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("settings-preset-custom"));
    const commissionInput = screen.getAllByRole("spinbutton")[0];
    fireEvent.change(commissionInput, { target: { value: "0.25" } });
    expect(commissionInput).toHaveValue(0.25);
    expect(screen.getByTestId("settings-preset-custom")).toBeChecked();
  });
});

describe("AccountSettingsPanel · fiscal", () => {
  it("aplica el 19 % canónico al volver a la jurisdicción ES (COM-D1)", () => {
    renderPanel(defaultAccountSettings("standard_es", "US"), "tax");
    const capitalGains = screen.getByTestId("settings-tax-capital-gains");
    // US no proyecta plusvalías: el campo arranca vacío («no estimar»).
    expect((capitalGains as HTMLInputElement).value).toBe("");

    fireEvent.change(screen.getByTestId("settings-tax-jurisdiction"), {
      target: { value: "ES" },
    });

    expect(capitalGains).toHaveValue(19);
    expect(screen.getByLabelText("Retención dividendos (%)")).toHaveValue(19);
  });

  it("permite dejar el tipo de plusvalías vacío para no estimar (COM-D4)", async () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("settings-tab-tax"));

    const capitalGains = screen.getByTestId("settings-tax-capital-gains");
    fireEvent.change(capitalGains, { target: { value: "" } });

    fireEvent.click(screen.getByRole("button", { name: /Guardar comisiones/ }));

    await waitFor(() => expect(updateAccountSettings).toHaveBeenCalledTimes(1));
    const settings = updateAccountSettings.mock.calls[0][1];
    expect(settings.tax.capitalGainsTaxPct).toBeNull();
  });
});

describe("AccountSettingsPanel · validación cliente (COM-D6)", () => {
  it("bloquea el guardado si el máximo es menor que el mínimo y no llama a la API", async () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("settings-preset-custom"));
    const [, minInput, maxInput] = screen.getAllByRole("spinbutton");
    fireEvent.change(minInput, { target: { value: "5" } });
    fireEvent.change(maxInput, { target: { value: "2" } });

    expect(screen.getByTestId("settings-validation-error")).toHaveTextContent(
      "El máximo por operación no puede ser menor que el mínimo.",
    );
    const save = screen.getByRole("button", { name: /Guardar comisiones/ });
    expect(save).toBeDisabled();

    fireEvent.click(save);
    await Promise.resolve();
    expect(updateAccountSettings).not.toHaveBeenCalled();
  });

  it("rechaza un inicio de ejercicio fuera de 1..12", () => {
    expect(
      validateAccountSettings({
        ...defaultAccountSettings(),
        tax: { ...defaultAccountSettings().tax, fiscalYearStartMonth: 13 },
      }),
    ).toBe("El inicio del año fiscal debe ser un mes entre 1 y 12.");
    expect(
      validateAccountSettings({
        ...defaultAccountSettings(),
        tax: { ...defaultAccountSettings().tax, fiscalYearStartMonth: 0 },
      }),
    ).not.toBeNull();
    expect(validateAccountSettings(defaultAccountSettings())).toBeNull();
  });
});

describe("AccountSettingsPanel · notas internas (CTA-D3)", () => {
  it("conserva los espacios mientras se escribe y recorta solo al guardar", async () => {
    renderPanel(defaultAccountSettings(), "tax");
    const notes = screen.getByLabelText(
      "Notas internas",
    ) as HTMLTextAreaElement;

    // Escritura incremental: antes cada pulsación recortaba el borrador y era
    // imposible separar palabras.
    for (const value of [
      "n",
      "no",
      "nota",
      "nota ",
      "nota c",
      "nota con espacios ",
    ]) {
      fireEvent.change(notes, { target: { value } });
    }
    expect(notes).toHaveValue("nota con espacios ");

    fireEvent.click(screen.getByRole("button", { name: /Guardar comisiones/ }));

    await waitFor(() => expect(updateAccountSettings).toHaveBeenCalledTimes(1));
    expect(updateAccountSettings.mock.calls[0][1].notes).toBe(
      "nota con espacios",
    );
  });

  it("un borrador de solo espacios se guarda como sin notas (null)", async () => {
    renderPanel(defaultAccountSettings(), "tax");
    const notes = screen.getByLabelText(
      "Notas internas",
    ) as HTMLTextAreaElement;

    fireEvent.change(notes, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar comisiones/ }));

    await waitFor(() => expect(updateAccountSettings).toHaveBeenCalledTimes(1));
    expect(updateAccountSettings.mock.calls[0][1].notes).toBeNull();
  });
});

describe("AccountSettingsPanel · guardado y vista previa", () => {
  it("manda el borrador completo con el PATCH", async () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("settings-tab-tax"));
    fireEvent.change(screen.getByTestId("settings-tax-jurisdiction"), {
      target: { value: "EU_OTHER" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Guardar comisiones/ }));

    await waitFor(() => expect(updateAccountSettings).toHaveBeenCalledTimes(1));
    const [accountId, settings] = updateAccountSettings.mock.calls[0];
    expect(accountId).toBe("acc-1");
    expect(settings.tax).toEqual(TAX_PRESETS.EU_OTHER);
  });

  it("la vista previa es el mismo cálculo que el servidor (COM-D8)", () => {
    const settings = defaultAccountSettings("standard_es", "ES");
    renderPanel(settings);

    const expected = calculateTradeFees(5000, "buy", settings, {
      currency: "EUR",
    });
    expect(expected.total).toBe(16.05);
    expect(screen.getByText(/Total 16\.05 €/)).toBeInTheDocument();
    expect(
      screen.getByText(/misma fórmula y redondeo \(4 decimales\)/),
    ).toBeInTheDocument();
  });
});

// Fusión de la integración: este caso venía del bloque Cuentas / Perfil inversor. El
// panel dejó de duplicar la asignación de perfil, así que aquí se fija esa retirada sin
// perder ninguno de los casos fiscales de arriba.
describe("AccountSettingsPanel — solo comisiones y fiscal (CU-D2)", () => {
  it("no repite la asignación de perfil dentro de comisiones/fiscal", () => {
    renderPanel();

    expect(screen.queryByTestId("account-investor-profile-select")).toBeNull();
    expect(screen.queryByText(/Perfil inversor/i)).toBeNull();
    expect(screen.getByText("Guardar comisiones y fiscal")).toBeTruthy();
  });
});
