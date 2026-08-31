/**
 * Tests — AdminRail Perfiles + Estadísticas preparadas + chincheta 3 modos.
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

describe("AdminRail profiles + stats", () => {
  afterEach(() => {
    cleanup();
    openPlatformConfig.mockClear();
  });

  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(window, "alert").mockImplementation(() => undefined);
  });

  it("renders Perfiles and Estadísticas actions", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("admin-rail-investor-profiles")).toBeTruthy();
    expect(screen.getByTestId("admin-rail-portfolio-stats")).toBeTruthy();
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

  it("Estadísticas alerts próximamente and does not open config", () => {
    render(
      <MemoryRouter>
        <AdminRail />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("admin-rail-portfolio-stats"));
    expect(window.alert).toHaveBeenCalled();
    expect(String(vi.mocked(window.alert).mock.calls[0]?.[0])).toMatch(
      /próximamente/i,
    );
    expect(openPlatformConfig).not.toHaveBeenCalled();
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
