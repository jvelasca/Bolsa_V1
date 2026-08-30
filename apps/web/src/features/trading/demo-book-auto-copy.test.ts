import { describe, expect, it } from "vitest";
import {
  DEMO_BOOK_AUTO_FOOTER,
  DEMO_BOOK_AUTO_RISK_LINES,
  DEMO_BOOK_AUTO_TOOLTIP,
  DEMO_BOOK_AUTO_UI_ENABLED,
  DEMO_BOOK_AUTO_UNAVAILABLE_LABEL,
} from "@/features/trading/demo-book-auto-copy";

describe("demo-book-auto-copy (ADR-023 BETA-D + V1.33 Libro AUTO)", () => {
  it("enables AUTO UI after BETA-D thaw", () => {
    expect(DEMO_BOOK_AUTO_UI_ENABLED).toBe(true);
  });

  it("exposes Libro AUTO copy with execute gate jargon", () => {
    expect(DEMO_BOOK_AUTO_UNAVAILABLE_LABEL).toMatch(/No disponible/);
    expect(DEMO_BOOK_AUTO_TOOLTIP).toMatch(/Libro AUTO/);
    expect(DEMO_BOOK_AUTO_TOOLTIP).toMatch(/PAPER_D_EXECUTE/);
    expect(DEMO_BOOK_AUTO_TOOLTIP).toMatch(/ACTIVAR AUTO/);
    expect(DEMO_BOOK_AUTO_FOOTER).toMatch(/Libro AUTO/);
    expect(DEMO_BOOK_AUTO_FOOTER).toMatch(/ACTIVAR AUTO/);
    expect(
      DEMO_BOOK_AUTO_RISK_LINES.some((line) => /PAPER_D_EXECUTE/.test(line)),
    ).toBe(true);
    expect(
      DEMO_BOOK_AUTO_RISK_LINES.some((line) =>
        /TradePlan TRIGGERED/.test(line),
      ),
    ).toBe(true);
  });
});
