/**
 * F1 — render del semáforo de realidad monetaria.
 *
 * Invariante: con una cuenta demo, la UI declara `DINERO VIRTUAL · AUTO DEMO` y no
 * reclama dinero real. El capital se rotula `NO MEDIDO` mientras no hay respuesta y se
 * presenta como medido cuando llega (nunca `0` por defecto).
 *
 * Honestidad de telemetría: el banner de AUTO sigue en dinero virtual aunque la cuenta
 * sea `live` o aún no haya llegado. La cuenta ausente se declara `NO MEDIDO` en su línea.
 * Un `PAPER_D_EXECUTE` pendiente se declara `NO MEDIDO` en vez de colapsarse a `false`.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

type ActiveAccountState = {
  account: { id: string; type: string } | null;
  effectiveAccountId: string | null;
  isLoading: boolean;
  accounts: unknown[];
};

type KillSwitchData = {
  effective: boolean;
  env: boolean;
  runtimeMemory: boolean;
  redis: null;
  paperDExecuteEnv: boolean;
};

const mocks = vi.hoisted(() => ({
  getAccountSummary: vi.fn<() => Promise<{ data: { totalEquity: number } }>>(),
  getRiskKillSwitch: vi.fn<() => Promise<KillSwitchData>>(),
  useActiveAccount: vi.fn<() => ActiveAccountState>(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSummary: mocks.getAccountSummary,
    getRiskKillSwitch: mocks.getRiskKillSwitch,
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: mocks.useActiveAccount,
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({
    mode: "semi",
    maxOpenPositions: 10,
    defaultSizePctOfCash: 10,
    countryPrefer: "home_first",
  }),
}));

vi.mock("@/features/trading/demo-book-auto-arm", () => ({
  loadAutoArm: () => ({ armed: false, armedAt: null, confirmPhrase: null }),
}));

import { AutoRealityStrip } from "@/features/auto/auto-reality-strip";

function renderStrip() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AutoRealityStrip />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.useActiveAccount.mockReturnValue({
    account: { id: "acc-1", type: "simulated" },
    effectiveAccountId: "acc-1",
    isLoading: false,
    accounts: [],
  });
  mocks.getAccountSummary.mockResolvedValue({
    data: { totalEquity: 12345.67 },
  });
  mocks.getRiskKillSwitch.mockResolvedValue({
    effective: false,
    env: false,
    runtimeMemory: false,
    redis: null,
    paperDExecuteEnv: false,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AutoRealityStrip", () => {
  it("declara DINERO VIRTUAL · AUTO DEMO y no genera órdenes al broker", () => {
    renderStrip();
    expect(
      screen.getByTestId("auto-reality-strip").getAttribute("data-tone"),
    ).toBe("virtual");
    expect(screen.getByTestId("auto-reality-banner").textContent).toBe(
      "SIMULACIÓN — DINERO VIRTUAL",
    );
    expect(screen.getByTestId("auto-reality-money").textContent).toBe(
      "DINERO VIRTUAL",
    );
    expect(screen.getByTestId("auto-reality-mode").textContent).toBe(
      "AUTO DEMO",
    );
    expect(screen.getByTestId("auto-reality-broker").textContent).toContain(
      "No envía órdenes a XTB",
    );
    expect(screen.getByTestId("auto-reality-auto").textContent).toContain(
      "Inactivo",
    );
  });

  it("con un tipo de cuenta aún no cargado mantiene el banner virtual y declara la cuenta", () => {
    mocks.useActiveAccount.mockReturnValue({
      account: null,
      effectiveAccountId: null,
      isLoading: true,
      accounts: [],
    });
    renderStrip();
    expect(
      screen.getByTestId("auto-reality-strip").getAttribute("data-tone"),
    ).toBe("virtual");
    expect(screen.getByTestId("auto-reality-money").textContent).toBe(
      "DINERO VIRTUAL",
    );
    expect(screen.getByTestId("auto-reality-mode").textContent).toBe(
      "AUTO DEMO",
    );
    expect(screen.getByTestId("auto-reality-broker").textContent).toContain(
      "No envía órdenes a XTB",
    );
    expect(screen.getByTestId("auto-reality-account").textContent).toBe(
      "NO MEDIDO",
    );
    expect(screen.getByTestId("auto-reality-notes").textContent).toContain(
      "Tipo de cuenta NO MEDIDO",
    );
  });

  it("una cuenta live no pinta DINERO REAL ni Broker LIVE dentro de AUTO", () => {
    mocks.useActiveAccount.mockReturnValue({
      account: { id: "acc-live", type: "live" },
      effectiveAccountId: "acc-live",
      isLoading: false,
      accounts: [],
    });
    renderStrip();
    const strip = screen.getByTestId("auto-reality-strip");
    expect(strip.getAttribute("data-tone")).toBe("virtual");
    expect(screen.getByTestId("auto-reality-banner").textContent).toBe(
      "SIMULACIÓN — DINERO VIRTUAL",
    );
    expect(screen.getByTestId("auto-reality-money").textContent).toBe(
      "DINERO VIRTUAL",
    );
    expect(screen.getByTestId("auto-reality-mode").textContent).toBe(
      "AUTO DEMO",
    );
    expect(screen.getByTestId("auto-reality-broker").textContent).toContain(
      "No envía órdenes a XTB",
    );
    expect(screen.getByTestId("auto-reality-account").textContent).toBe(
      "Cuenta conectada: XTB LIVE",
    );
    expect(strip.textContent).not.toContain("DINERO REAL");
    expect(strip.textContent).not.toContain("Broker LIVE");
  });

  it("conserva PAPER_D_EXECUTE como NO MEDIDO mientras la consulta no responde", () => {
    mocks.getRiskKillSwitch.mockImplementation(
      () => new Promise<never>(() => {}),
    );
    renderStrip();
    expect(screen.getByTestId("auto-reality-notes").textContent).toContain(
      "Ejecución paper NO MEDIDA",
    );
  });

  it("presenta el capital como medido cuando llega la respuesta", async () => {
    renderStrip();
    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-reality-capital")
          .getAttribute("data-measurement"),
      ).toBe("COMPLETE"),
    );
  });
});
