import { describe, expect, it } from "vitest";
import {
  DEMO_BOOK_AUTO_FOOTER,
  DEMO_BOOK_AUTO_RISK_LINES,
  DEMO_BOOK_AUTO_TOOLTIP,
  DEMO_BOOK_AUTO_UI_ENABLED,
  DEMO_BOOK_AUTO_UNAVAILABLE_LABEL,
} from "@/features/trading/demo-book-auto-copy";

describe("demo-book-auto-copy (R-12 C3)", () => {
  it("keeps AUTO UI disabled until thaw", () => {
    expect(DEMO_BOOK_AUTO_UI_ENABLED).toBe(false);
  });

  it("exposes BETA unavailable copy without execute-flag jargon", () => {
    expect(DEMO_BOOK_AUTO_UNAVAILABLE_LABEL).toMatch(/BETA/);
    expect(DEMO_BOOK_AUTO_UNAVAILABLE_LABEL).toMatch(/No disponible/);
    expect(DEMO_BOOK_AUTO_TOOLTIP).not.toMatch(/PAPER_D_EXECUTE/);
    expect(DEMO_BOOK_AUTO_FOOTER).not.toMatch(/PAPER_D_EXECUTE/);
    for (const line of DEMO_BOOK_AUTO_RISK_LINES) {
      expect(line).not.toMatch(/PAPER_D_EXECUTE/);
    }
  });
});
