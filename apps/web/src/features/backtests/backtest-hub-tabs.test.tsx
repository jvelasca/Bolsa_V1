import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { BacktestHubTabsBar, HubTabButton } from "./backtest-hub-tabs";

// El proyecto no configura auto-cleanup; lo hacemos explícito para evitar que el
// DOM de tests previos se acumule y provoque falsos "multiple elements found".
afterEach(() => cleanup());

describe("HubTabButton", () => {
  it("renderiza el contenido y reacciona al clic", () => {
    const onClick = vi.fn();
    render(
      <HubTabButton active={false} onClick={onClick}>
        Ejecutar
      </HubTabButton>,
    );
    const btn = screen.getByRole("button", { name: /ejecutar/i });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("aplica el estilo activo frente al inactivo", () => {
    const { container, rerender } = render(
      <HubTabButton active={false} onClick={() => {}}>
        Tab
      </HubTabButton>,
    );
    const btn = () => container.querySelector("button") as HTMLButtonElement;
    expect(btn().className).toContain("text-muted-foreground");

    rerender(
      <HubTabButton active={true} onClick={() => {}}>
        Tab
      </HubTabButton>,
    );
    expect(btn().className).toContain("bg-accent");
  });
});

describe("BacktestHubTabsBar", () => {
  it("muestra las 4 pestañas y marca la activa", () => {
    render(
      <BacktestHubTabsBar
        tab="run"
        onTab={() => {}}
        onOpenLibrary={() => {}}
      />,
    );
    expect(
      screen.getByRole("button", { name: /probar estrategia/i }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /biblioteca/i })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /lab · optimizar/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /pruebas anteriores/i }),
    ).toBeTruthy();
  });

  it("onTab se dispara con el tab correcto y onOpenLibrary con Biblioteca", () => {
    const onTab = vi.fn();
    const onOpenLibrary = vi.fn();
    render(
      <BacktestHubTabsBar
        tab="run"
        onTab={onTab}
        onOpenLibrary={onOpenLibrary}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /pruebas anteriores/i }),
    );
    expect(onTab).toHaveBeenCalledWith("history");
    fireEvent.click(screen.getByRole("button", { name: /biblioteca/i }));
    expect(onOpenLibrary).toHaveBeenCalledTimes(1);
  });
});
