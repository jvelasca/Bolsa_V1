/**
 * AUTO Monitor — contrato WAI-ARIA de la barra de vistas (P1).
 *
 * La barra usa `role="tablist"/"tab"`; debe completar el patrón: `aria-controls` a un
 * `tabpanel` real, roving `tabIndex` y flechas/Home/End que mueven la pestaña activa
 * pidiendo el foco tras el commit. El `tabpanel` de la página se comprueba mockeando el
 * hook del monitor (vista `current` en carga, sin montar los paneles pesados).
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view: null,
    isLoading: true,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
    accountId: "acc-1",
  }),
}));

import { AutoMonitorPage } from "@/features/auto-monitor/auto-monitor-page";
import {
  AutoMonitorModeToolbar,
  type AutoMonitorMode,
} from "@/features/auto-monitor/dia-d-auto-toolbar";

afterEach(cleanup);

function renderToolbar(initial: AutoMonitorMode = "operation") {
  const onChange = vi.fn();
  render(<AutoMonitorModeToolbar mode={initial} onChange={onChange} />);
  return { onChange };
}

describe("AutoMonitorModeToolbar — patrón WAI-ARIA de tabs", () => {
  it("enlaza cada tab con su tabpanel y sólo la activa es tabulable", () => {
    renderToolbar("operation");

    const tablist = screen.getByTestId("auto-monitor-mode-toolbar");
    expect(tablist.getAttribute("role")).toBe("tablist");

    const operation = screen.getByTestId("auto-monitor-mode-operation");
    expect(operation.getAttribute("role")).toBe("tab");
    expect(operation.getAttribute("aria-selected")).toBe("true");
    expect(operation.getAttribute("tabIndex")).toBe("0");
    expect(operation.getAttribute("aria-controls")).toBe(
      "auto-monitor-mode-panel-operation",
    );

    // Las pestañas inactivas no participan del orden de tabulación (roving).
    expect(
      screen.getByTestId("auto-monitor-mode-current").getAttribute("tabIndex"),
    ).toBe("-1");
    expect(
      screen.getByTestId("auto-monitor-mode-dia-d").getAttribute("tabIndex"),
    ).toBe("-1");
  });

  it("mueve la pestaña con flechas y Home/End pidiendo foco tras el commit", () => {
    const { onChange } = renderToolbar("operation");

    fireEvent.keyDown(screen.getByTestId("auto-monitor-mode-operation"), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenLastCalledWith("dia-d", true);

    fireEvent.keyDown(screen.getByTestId("auto-monitor-mode-operation"), {
      key: "ArrowLeft",
    });
    expect(onChange).toHaveBeenLastCalledWith("current", true);

    fireEvent.keyDown(screen.getByTestId("auto-monitor-mode-operation"), {
      key: "Home",
    });
    expect(onChange).toHaveBeenLastCalledWith("current", true);

    fireEvent.keyDown(screen.getByTestId("auto-monitor-mode-operation"), {
      key: "End",
    });
    expect(onChange).toHaveBeenLastCalledWith("dia-d", true);
  });

  it("ignora teclas que no son de navegación de tabs", () => {
    const { onChange } = renderToolbar("operation");
    fireEvent.keyDown(screen.getByTestId("auto-monitor-mode-operation"), {
      key: "a",
    });
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("AutoMonitorPage — tabpanel enlazado con la pestaña activa", () => {
  function renderPage(entry: string) {
    return render(
      <MemoryRouter initialEntries={[entry]}>
        <AutoMonitorPage />
      </MemoryRouter>,
    );
  }

  it("expone un tabpanel con el id de la vista activa y su aria-labelledby", () => {
    renderPage("/auto-monitor?mode=current");

    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("id")).toBe("auto-monitor-mode-panel-current");
    expect(panel.getAttribute("aria-labelledby")).toBe(
      "auto-monitor-mode-tab-current",
    );
    expect(panel.getAttribute("tabIndex")).toBe("0");
    // La pestaña activa referencia EXACTAMENTE ese panel.
    expect(
      screen
        .getByTestId("auto-monitor-mode-current")
        .getAttribute("aria-controls"),
    ).toBe("auto-monitor-mode-panel-current");
  });
});
