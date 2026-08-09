import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { HubTabButton } from "./backtest-hub-tabs";

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
