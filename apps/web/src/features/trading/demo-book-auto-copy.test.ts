import { describe, expect, it } from "vitest";
import {
  DEMO_BOOK_AUTO_FOOTER,
  DEMO_BOOK_AUTO_RISK_LINES,
  DEMO_BOOK_AUTO_TOOLTIP,
  DEMO_BOOK_AUTO_UI_ENABLED,
} from "@/features/trading/demo-book-auto-copy";

describe("demo-book-auto-copy (A1)", () => {
  it("keeps AUTO UI disabled until thaw", () => {
    expect(DEMO_BOOK_AUTO_UI_ENABLED).toBe(false);
  });

  it("exposes risk copy for Camino D", () => {
    expect(DEMO_BOOK_AUTO_TOOLTIP).toMatch(/PAPER_D_EXECUTE/);
    expect(DEMO_BOOK_AUTO_RISK_LINES.length).toBeGreaterThanOrEqual(3);
    expect(DEMO_BOOK_AUTO_FOOTER).toMatch(/AUTO/);
  });
});
