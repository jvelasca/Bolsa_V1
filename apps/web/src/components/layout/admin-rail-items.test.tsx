/**
 * Tests — AdminRail Perfiles (estado preparado) + chincheta 3 modos.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const openPlatformConfig = vi.fn();

vi.mock("@/stores/ui-store", () => ({
  useUiStore: (
    sel: (s: { openPlatformConfig: typeof openPlatformConfig }) => unknown,
  ) => sel({ openPlatformConfig }),
}));

import { AdminRail, loadAdminRailMode } from "@/components/layout/admin-rail";

describe("AdminRail Perfiles", () => {
  afterEach(() => {
    cleanup();
    openPlatformConfig.mockClear();
  });

  beforeEach(() => {
    localStorage.clear();
  });

  it("renders Perfiles action alongside the nav items", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("admin-rail-investor-profiles")).toBeTruthy();
    expect(screen.getByTestId("admin-rail-overview")).toBeTruthy();
    expect(screen.getByTestId("admin-rail-accounts")).toBeTruthy();
  });

  it("Perfiles opens investor-profile config", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("admin-rail-investor-profiles"));
    expect(openPlatformConfig).toHaveBeenCalledWith("investor-profile");
  });
});

describe("AdminRail groups (UI5-08)", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    localStorage.clear();
  });

  it("expone los tres grupos y sitúa AUTO en Administración", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    // Expandido para que los encabezados de grupo sean visibles.
    fireEvent.mouseEnter(screen.getByTestId("admin-rail"));
    expect(
      screen.getByTestId("admin-rail-group-product").textContent,
    ).toContain("Producto");
    const admin = screen.getByTestId("admin-rail-group-admin");
    expect(admin.textContent).toContain("Administración");
    expect(admin.textContent).toContain("AUTO");
    // AUTO vive dentro del bloque Administración, no en una lista plana.
    expect(admin.contains(screen.getByTestId("admin-rail-auto"))).toBe(true);
    expect(
      screen.getByTestId("admin-rail-group-diagnostic").textContent,
    ).toContain("Diagnóstico");
  });

  it("retira el stub «Estadísticas · pronto» y conserva Consola avanzada en Diagnóstico", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    fireEvent.mouseEnter(screen.getByTestId("admin-rail"));
    // Stub que parecía navegación (`window.alert`): fuera (UI5-17).
    expect(screen.queryByTestId("admin-rail-portfolio-stats")).toBeNull();
    expect(screen.queryByText(/Estadísticas/)).toBeNull();
    // Consola avanzada sigue en Diagnóstico.
    expect(
      screen
        .getByTestId("admin-rail-group-diagnostic")
        .contains(screen.getByTestId("admin-rail-operational-console")),
    ).toBe(true);
  });
});

describe("AdminRail pin modes", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to auto and expands on hover", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    const rail = screen.getByTestId("admin-rail");
    expect(rail.getAttribute("data-mode")).toBe("auto");
    expect(rail.getAttribute("data-collapsed")).toBe("1");

    fireEvent.mouseEnter(rail);
    expect(rail.getAttribute("data-collapsed")).toBe("0");

    fireEvent.mouseLeave(rail);
    expect(rail.getAttribute("data-collapsed")).toBe("1");
  });

  it("cycles Auto → colapsado fijo → expandido fijo → Auto", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    const rail = screen.getByTestId("admin-rail");
    const toggle = screen.getByTestId("admin-rail-toggle");

    fireEvent.click(toggle);
    expect(rail.getAttribute("data-mode")).toBe("pinned-collapsed");
    expect(localStorage.getItem("bolsa-admin-rail-mode")).toBe(
      "pinned-collapsed",
    );

    fireEvent.mouseEnter(rail);
    expect(rail.getAttribute("data-collapsed")).toBe("1");

    fireEvent.click(toggle);
    expect(rail.getAttribute("data-mode")).toBe("pinned-expanded");
    expect(rail.getAttribute("data-collapsed")).toBe("0");

    fireEvent.click(toggle);
    expect(rail.getAttribute("data-mode")).toBe("auto");
  });

  it("migrates legacy pin=1 to pinned-expanded", () => {
    localStorage.setItem("bolsa-admin-rail-pinned", "1");
    expect(loadAdminRailMode()).toBe("pinned-expanded");
  });
});
