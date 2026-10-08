/**
 * UI Contract 5.0 (`RT-04`) — disclosure único + gate falsable de primer nivel.
 */

import { createElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  TECHNICAL_DETAIL_ATTR,
  TECHNICAL_DETAIL_LABEL,
  TechnicalDetail,
} from "@/components/technical-detail";
import {
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";

afterEach(() => cleanup());

describe("TechnicalDetail (RT-04)", () => {
  it("usa el rótulo único y expone la marca de nivel 3", () => {
    render(createElement(TechnicalDetail, null, "contenido"));
    const node = screen.getByTestId("technical-detail");
    expect(node.getAttribute(TECHNICAL_DETAIL_ATTR)).toBe("true");
    expect(node.textContent).toContain(TECHNICAL_DETAIL_LABEL);
    expect(node.tagName.toLowerCase()).toBe("details");
  });

  it("por defecto va cerrado (no expone el detalle sin pedirlo)", () => {
    render(createElement(TechnicalDetail, null, "contenido"));
    const node = screen.getByTestId("technical-detail") as HTMLDetailsElement;
    expect(node.open).toBe(false);
  });

  it("AutoTechnicalDetail delega con su propio testId", () => {
    render(
      createElement(
        AutoTechnicalDetail,
        { testId: "auto-x-technical" },
        "detalle",
      ),
    );
    const node = screen.getByTestId("auto-x-technical");
    expect(node.getAttribute(TECHNICAL_DETAIL_ATTR)).toBe("true");
    expect(node.textContent).toContain(TECHNICAL_DETAIL_LABEL);
  });
});

describe("first-level gate (R-G1 / RT-02)", () => {
  it("stripTechnicalDetailBlocks retira el contenido de nivel 3", () => {
    const src = [
      "const a = 1;",
      "<TechnicalDetail>runId · cycleId · ledger</TechnicalDetail>",
      "const b = 2;",
    ].join("\n");
    const stripped = stripTechnicalDetailBlocks(src);
    expect(stripped).not.toContain("runId");
    expect(stripped).toContain("const a = 1;");
  });

  it("detecta jerga de ingeniería fuera del disclosure", () => {
    const src = "Texto visible · Policy Gate · DecisionSession";
    expect(findFirstLevelViolations(src)).toEqual(
      expect.arrayContaining(["Policy Gate", "DecisionSession"]),
    );
  });

  it("no reporta jerga de ingeniería dentro del disclosure", () => {
    const src = [
      "Primer nivel honesto.",
      "<TechnicalDetail>Policy Gate · runId · ledger</TechnicalDetail>",
    ].join("\n");
    expect(findFirstLevelViolations(src)).toEqual([]);
  });
});
