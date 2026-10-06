/**
 * AUTO · CARTERA — el aviso DEMO es inequívoco y va ANTES de las acciones (spec 3.0 §5).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/features/trading/operations-panel", () => ({
  OperationsPanel: () => <div data-testid="operations-panel-stub" />,
}));

import { AutoCarteraPage } from "@/features/auto/auto-cartera-page";

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/auto/cartera"]}>
      <AutoCarteraPage />
    </MemoryRouter>,
  );
}

describe("AutoCarteraPage", () => {
  it("expone un h1 y declara CARTERA DEMO antes de las acciones", () => {
    renderPage();
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);

    const banner = screen.getByTestId("auto-cartera-demo-banner");
    expect(banner.textContent).toContain("CARTERA DEMO");
    expect(banner.textContent).toContain("No se envían órdenes reales a XTB");
    expect(banner.getAttribute("role")).toBe("note");

    // El aviso precede a las acciones (posiciones y órdenes).
    const panel = screen.getByTestId("operations-panel-stub");
    expect(
      banner.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
