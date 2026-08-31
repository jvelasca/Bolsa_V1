/**
 * Tests — AdminRail Perfiles + Estadísticas preparadas.
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

import { AdminRail } from "@/components/layout/admin-rail";

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
