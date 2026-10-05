/**
 * DÍA-D AUTO · FEEDBACK — tooltip del heatmap.
 *
 * Invariante: un día NO MEDIDO no declara `0 ciclo(s) · 0 error(es)` (eso fingía una medición);
 * se rotula `sin dato`. Un día medido sí declara sus ciclos y errores.
 */

import { describe, expect, it } from "vitest";

import { formatCellTooltip } from "@/features/auto-monitor/dia-d-auto-feedback-heatmap";

describe("formatCellTooltip", () => {
  it("un día sin celda declara 'sin dato', no 0 ciclos", () => {
    const tooltip = formatCellTooltip("AAA", "2026-09-30", undefined);
    expect(tooltip).toContain("sin dato");
    expect(tooltip).not.toContain("0 ciclo(s)");
    expect(tooltip).not.toContain("0 error(es)");
  });

  it("una celda NOT_MEDIDO declara 'sin dato', no 0 ciclos", () => {
    const tooltip = formatCellTooltip("BBB", "2026-09-30", {
      day: "2026-09-30",
      realizedR: null,
      cycles: 0,
      errors: 0,
      outcome: "NOT_MEASURED",
    });
    expect(tooltip).toContain("NO MEDIDO");
    expect(tooltip).toContain("sin dato");
    expect(tooltip).not.toContain("0 ciclo(s)");
  });

  it("una celda medido declara ciclos y errores", () => {
    const tooltip = formatCellTooltip("AAA", "2026-09-29", {
      day: "2026-09-29",
      realizedR: 3,
      cycles: 6,
      errors: 0,
      outcome: "GAIN",
    });
    expect(tooltip).toContain("+3.00R");
    expect(tooltip).toContain("6 ciclo(s)");
    expect(tooltip).toContain("0 error(es)");
    expect(tooltip).not.toContain("sin dato");
  });
});
