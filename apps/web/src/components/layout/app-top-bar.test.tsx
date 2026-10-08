/**
 * Tests — AppTopBar L1: exactamente UNA puerta activa (UI5-01 / UI5-20).
 *
 * Falsable 2.1 del [Mapa de problemas UI 5.0]: en `/mesa?view=posiciones` se
 * pintaban activas `Hoy` y `Cartera` a la vez. Cartera es una vista rotulada de
 * Hoy: cuando lo es, Hoy NO debe aparecer como puerta activa.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/stores/auth-store", () => ({
  useAuthStore: (sel: (s: { clearSession: () => void }) => unknown) =>
    sel({ clearSession: vi.fn() }),
}));

vi.mock("@/stores/ui-store", () => ({
  useUiStore: (
    sel: (s: {
      openWorkspacePicker: () => void;
      openPlatformConfig: () => void;
    }) => unknown,
  ) => sel({ openWorkspacePicker: vi.fn(), openPlatformConfig: vi.fn() }),
}));

vi.mock("@/stores/trading-layout-store", () => ({
  useTradingLayoutStore: () => ({
    listsOpen: false,
    operationsOpen: false,
    operativaOpen: false,
    namedLayoutId: null,
    toggleLists: vi.fn(),
    toggleOperations: vi.fn(),
    toggleOperativa: vi.fn(),
    applyNamedLayout: vi.fn(),
    resetLayout: vi.fn(),
  }),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: (
    sel: (s: {
      workspace: { name: string };
      isDirty: boolean;
      isSaving: boolean;
    }) => unknown,
  ) =>
    sel({
      workspace: { name: "Espacio de prueba" },
      isDirty: false,
      isSaving: false,
    }),
}));

vi.mock("@/stores/list-auto-activity-store", () => ({
  useListAutoActivityStore: (
    sel: (s: { active: boolean; summary: string | null }) => unknown,
  ) => sel({ active: false, summary: null }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (sel: (s: { items: unknown[] }) => unknown) =>
    sel({ items: [] }),
}));

vi.mock("@/features/research/use-asesor-alarma-badge", () => ({
  useAsesorAlarmaBadge: () => 0,
}));

vi.mock("@/features/command-palette/command-palette-host", () => ({
  requestOpenCommandPalette: vi.fn(),
}));

vi.mock("@/features/command-palette/named-layout", () => ({
  NAMED_LAYOUT_LABELS: {
    simple: "Simple",
    trader: "Completa",
    analista: "Análisis",
  },
}));

vi.mock("@/features/help/app-help-menu", () => ({
  AppHelpMenu: () => <span data-testid="help-menu-stub" />,
}));

vi.mock("@/features/platform/universe-chip", () => ({
  UniverseChip: () => <span data-testid="universe-chip-stub" />,
}));

vi.mock("@/features/accounts/account-scope-selector", () => ({
  AccountScopeSelector: () => <span data-testid="account-scope-stub" />,
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({
    mode: "auto",
    maxOpenPositions: 10,
    defaultSizePctOfCash: 10,
    countryPrefer: "home_first",
  }),
}));

import { AppTopBar } from "@/components/layout/app-top-bar";

afterEach(cleanup);

function renderTopBar(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AppTopBar />
    </MemoryRouter>,
  );
}

function activeDoorCount(): number {
  const nav = screen.getByRole("navigation", { name: "Principal" });
  return nav.querySelectorAll(".text-primary").length;
}

describe("AppTopBar — una sola puerta L1 activa", () => {
  it("en /mesa?view=posiciones solo Cartera está activa (Hoy no)", () => {
    renderTopBar("/mesa?view=posiciones");
    expect(screen.getByRole("button", { name: "Cartera" }).className).toContain(
      "text-primary",
    );
    expect(screen.getByRole("link", { name: "Hoy" }).className).not.toContain(
      "text-primary",
    );
    expect(activeDoorCount()).toBe(1);
  });

  it("en /mesa (resumen) solo Hoy está activa", () => {
    renderTopBar("/mesa");
    expect(screen.getByRole("link", { name: "Hoy" }).className).toContain(
      "text-primary",
    );
    expect(
      screen.getByRole("button", { name: "Cartera" }).className,
    ).not.toContain("text-primary");
    expect(activeDoorCount()).toBe(1);
  });

  it("en /mesa?view=oportunidades (detalle de Hoy) solo Hoy está activa", () => {
    renderTopBar("/mesa?view=oportunidades");
    expect(screen.getByRole("link", { name: "Hoy" }).className).toContain(
      "text-primary",
    );
    expect(activeDoorCount()).toBe(1);
  });

  it("en /history (Historial de Cartera) solo Cartera está activa", () => {
    renderTopBar("/history");
    expect(screen.getByRole("button", { name: "Cartera" }).className).toContain(
      "text-primary",
    );
    expect(screen.getByRole("link", { name: "Hoy" }).className).not.toContain(
      "text-primary",
    );
    expect(activeDoorCount()).toBe(1);
  });
});

describe("AppTopBar — lenguaje de primer nivel (`R-G1`/`R-G2`/`RT-01`)", () => {
  it("declara la pregunta acordada de Hoy en su title", () => {
    renderTopBar("/mesa");
    expect(
      screen.getByRole("link", { name: "Hoy" }).getAttribute("title"),
    ).toBe("¿Qué requiere mi atención?");
  });

  it("no deja la toolbar avanzada en el primer nivel", () => {
    const { container } = renderTopBar("/trading");
    expect(screen.queryByRole("group", { name: "Paneles Mercado" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: /layout/i })).toBeNull();
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/watchlist/i);
    expect(text).not.toMatch(/DECISIÓN/);
    expect(text).not.toMatch(/\bCustom\b/);
    expect(text).not.toMatch(/\bTrader\b/);
  });

  it("en Mercado pliega paneles y disposición tras «Ajustes de vista»", () => {
    renderTopBar("/trading");
    fireEvent.click(screen.getByRole("button", { name: "Ajustes de vista" }));
    expect(screen.getByText("Listas")).toBeTruthy();
    expect(screen.getByText("Operaciones")).toBeTruthy();
    expect(screen.getByText("Completa")).toBeTruthy();
    expect(screen.getByText("Abrir en otra pestaña")).toBeTruthy();
  });
});

describe("AppTopBar — modo operativo persistente (`UI5-21`)", () => {
  it("muestra el modo vigente y enlaza a /auto", () => {
    renderTopBar("/mesa");
    const chip = screen.getByTestId("operative-mode-chip");
    expect(chip.getAttribute("href")).toBe("/auto");
    expect(chip.textContent).toContain("AUTO");
    expect(chip.getAttribute("data-mode")).toBe("AUTO");
  });

  it("NO es una sexta puerta L1: vive fuera de la nav Principal", () => {
    renderTopBar("/mesa");
    const chip = screen.getByTestId("operative-mode-chip");
    const nav = screen.getByRole("navigation", { name: "Principal" });
    expect(nav.contains(chip)).toBe(false);
  });
});
