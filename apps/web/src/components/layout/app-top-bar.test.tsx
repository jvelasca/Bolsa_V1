/**
 * Tests — AppTopBar L1: exactamente UNA puerta activa (UI5-01 / UI5-20).
 *
 * Falsable 2.1 del [Mapa de problemas UI 5.0]: en `/mesa?view=posiciones` se
 * pintaban activas `Hoy` y `Cartera` a la vez. Cartera es una vista rotulada de
 * Hoy: cuando lo es, Hoy NO debe aparecer como puerta activa.
 */

import { cleanup, render, screen } from "@testing-library/react";
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
    trader: "Trader",
    analista: "Analista",
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
