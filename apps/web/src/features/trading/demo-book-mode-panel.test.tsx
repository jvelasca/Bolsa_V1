import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  api: {
    getRiskKillSwitch: vi.fn(async () => ({
      effective: false,
      env: false,
      runtimeMemory: false,
      redis: null,
    })),
    setRiskKillSwitch: vi.fn(),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "default-account-seed",
    account: { id: "default-account-seed", name: "Seed DEMO" },
    isLoading: false,
  }),
}));

import { AUTO_ARM_CONFIRM_PHRASE } from "@/features/trading/demo-book-auto-arm";
import { loadDemoBookPrefs } from "@/features/trading/demo-book-prefs";
import { DemoBookModePanel } from "@/features/trading/demo-book-mode-panel";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DemoBookModePanel />
    </QueryClientProvider>,
  );
}

describe("DemoBookModePanel A3-wire", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    localStorage.clear();
  });

  it("Auto click without arm opens form and does not persist auto", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("demo-book-auto-pill"));
    expect(screen.getByTestId("demo-book-auto-arm-form")).toBeTruthy();
    expect(loadDemoBookPrefs().mode).toBe("semi");
  });

  it("wrong phrase keeps semi; exact phrase sets auto", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("demo-book-auto-pill"));
    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: "activar auto" },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(screen.getByTestId("demo-book-auto-arm-error")).toBeTruthy();
    expect(loadDemoBookPrefs().mode).toBe("semi");

    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: AUTO_ARM_CONFIRM_PHRASE },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(loadDemoBookPrefs().mode).toBe("auto");
    expect(screen.queryByTestId("demo-book-auto-arm-form")).toBeNull();
  });

  it("leaving Auto to Semi clears arm so Auto requires phrase again", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("demo-book-auto-pill"));
    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: AUTO_ARM_CONFIRM_PHRASE },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(loadDemoBookPrefs().mode).toBe("auto");

    fireEvent.click(screen.getByRole("button", { name: /SEMI/i }));
    expect(loadDemoBookPrefs().mode).toBe("semi");

    fireEvent.click(screen.getByTestId("demo-book-auto-pill"));
    expect(screen.getByTestId("demo-book-auto-arm-form")).toBeTruthy();
    expect(loadDemoBookPrefs().mode).toBe("semi");
  });

  it("shows MANUAL / SEMI / AUTO labels with mode hints", () => {
    renderPanel();
    expect(screen.getByTestId("demo-book-mode-manual").textContent).toMatch(
      /MANUAL/,
    );
    expect(screen.getByTestId("demo-book-mode-semi").textContent).toMatch(
      /SEMI/,
    );
    expect(screen.getByTestId("demo-book-auto-pill").textContent).toMatch(
      /AUTO/,
    );
    expect(
      screen.getByTestId("demo-book-mode-active-hint").textContent,
    ).toMatch(/firmas en Confirmar/i);
  });
});
