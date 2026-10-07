/**
 * Shell del espacio AUTO (ADR-044).
 *
 * Verifica la sub-navegación persistente y las invariantes de accesibilidad:
 * el layout NO anida `<main>` (lo aporta `PlatformShell`) y la sección aporta
 * el único `<h1>`.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AutoWorkspaceLayout } from "@/components/layout/auto-workspace-layout";

// El semáforo de realidad tiene su propio test; aquí se aísla para verificar que
// el layout lo monta sin arrastrar I/O de red al test de navegación.
vi.mock("@/features/auto/auto-reality-strip", () => ({
  AutoRealityStrip: () => <div data-testid="auto-reality-strip" />,
}));

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/auto" element={<AutoWorkspaceLayout />}>
          <Route path="operar" element={<h1>Operar</h1>} />
          <Route path="cartera" element={<h1>Cartera</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("AutoWorkspaceLayout", () => {
  it("monta la sub-navegación con las secciones de AUTO", () => {
    renderAt("/auto/operar");
    expect(
      screen.getByRole("navigation", { name: "Secciones AUTO" }),
    ).toBeTruthy();
    for (const id of [
      "operar",
      "actividad",
      "cartera",
      "riesgo",
      "analisis",
      "sistema",
    ]) {
      expect(screen.getByTestId(`auto-nav-${id}`)).toBeTruthy();
    }
  });

  it("no anida un <main>: el shell aporta el único main", () => {
    renderAt("/auto/cartera");
    expect(screen.queryAllByRole("main")).toHaveLength(0);
  });

  it("marca la sección activa con aria-current", () => {
    renderAt("/auto/cartera");
    expect(
      screen.getByTestId("auto-nav-cartera").getAttribute("aria-current"),
    ).toBe("page");
    expect(
      screen.getByTestId("auto-nav-operar").getAttribute("aria-current"),
    ).toBeNull();
  });

  it("la sección activa aporta exactamente un h1", () => {
    renderAt("/auto/operar");
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("monta el semáforo de realidad sobre la sección activa", () => {
    renderAt("/auto/operar");
    expect(screen.getByTestId("auto-reality-strip")).toBeTruthy();
  });
});
