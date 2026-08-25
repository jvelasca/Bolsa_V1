/**
 * Tests — sync Ayuda C1 (v1.8 HELP + Hoy honesty).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";
import { HoyEnLaMesaBlock } from "@/features/help/hoy-en-la-mesa";

afterEach(() => cleanup());

describe("help C1 v1.8 sync", () => {
  it("HELP_CONTENT_AS_OF is 2026-08-25", () => {
    expect(HELP_CONTENT_AS_OF).toBe("2026-08-25");
  });

  it("Hoy en la mesa states BUY only with TradePlan TRIGGERED", () => {
    render(
      <MemoryRouter>
        <HoyEnLaMesaBlock />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("hoy-en-la-mesa").textContent).toMatch(
      /BUY solo con TradePlan TRIGGERED/i,
    );
    expect(screen.getByTestId("hoy-en-la-mesa").textContent).toMatch(
      /nunca BUY/i,
    );
  });
});
