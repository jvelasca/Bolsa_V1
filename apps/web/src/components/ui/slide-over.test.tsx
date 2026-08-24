/**
 * Smoke — open/close del SlideOver (U3 Confirm drawer primitive).
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SlideOver } from "@/components/ui/slide-over";

afterEach(() => cleanup());

describe("SlideOver", () => {
  it("renders nothing when closed", () => {
    const onClose = vi.fn();
    const { container } = render(
      <SlideOver open={false} onClose={onClose} title="Confirmar">
        cuerpo
      </SlideOver>,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("slide-over")).toBeNull();
  });

  it("opens with title and closes via button / Escape", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <SlideOver
        open
        onClose={onClose}
        title="Confirmar"
        testId="confirm-drawer"
      >
        <p>contenido SEMI</p>
      </SlideOver>,
    );

    expect(screen.getByTestId("confirm-drawer")).toBeTruthy();
    expect(screen.getByText("Confirmar")).toBeTruthy();
    expect(screen.getByText("contenido SEMI")).toBeTruthy();

    fireEvent.click(screen.getByTestId("confirm-drawer-close"));
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();
    rerender(
      <SlideOver
        open
        onClose={onClose}
        title="Confirmar"
        testId="confirm-drawer"
      >
        <p>contenido SEMI</p>
      </SlideOver>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
