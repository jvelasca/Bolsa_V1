/**
 * F1 — render del semáforo de realidad monetaria.
 *
 * Invariante: con una cuenta demo, la UI declara `DINERO VIRTUAL · AUTO DEMO` y no
 * reclama dinero real. El capital se rotula `NO MEDIDO` mientras no hay respuesta y se
 * presenta como medido cuando llega (nunca `0` por defecto).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSummary: vi.fn(async () => ({
      data: { totalEquity: 12345.67 },
    })),
    getRiskKillSwitch: vi.fn(async () => ({
      effective: false,
      env: false,
      runtimeMemory: false,
      redis: null,
      paperDExecuteEnv: false,
    })),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    account: { id: "acc-1", type: "simulated" },
    effectiveAccountId: "acc-1",
    isLoading: false,
    accounts: [],
  }),
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
