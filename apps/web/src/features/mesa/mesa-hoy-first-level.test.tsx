/**
 * UI 6.x — gate falsable de primer nivel para Hoy (`R-G1`/`RT-02`).
 *
 * Auditoría `docs/engineering/auditoria-ui-6-x-global-2026-10-08.md` §4:
 * H-01…H-06. El primer nivel de estas superficies (fuera de `TechnicalDetail`)
 * no debe exponer identificadores de motor ni jerga de ingeniería.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";
import { HOY_DETAIL_ITEMS } from "@/features/mesa/mesa-hoy-view";

const FIRST_LEVEL_FILES = [
  "mesa-hoy-page.tsx",
  "mesa-hoy-view.ts",
  "mesa-candidates-panel.tsx",
] as const;

function readSource(file: string): string {
  return readFileSync(resolve(__dirname, file), "utf8");
}

/**
 * `OpportunityScore` colisiona como subcadena con el componente de barras
 * `OpportunityScoreBars` (símbolo de código, no texto de usuario). Se excluye
 * del set para evitar el falso positivo y se cubre aparte con un guard que sí
 * detecta la nota de score cruda.
 */
const FIRST_LEVEL_TOKENS = FORBIDDEN_FIRST_LEVEL_TOKENS.filter(
  (token) => token !== "OpportunityScore",
);

describe("Hoy · primer nivel sin jerga de ingeniería (R-G1/RT-02)", () => {
  for (const file of FIRST_LEVEL_FILES) {
    it(`${file} no expone tokens prohibidos fuera de TechnicalDetail`, () => {
      expect(
        findFirstLevelViolations(readSource(file), FIRST_LEVEL_TOKENS),
      ).toEqual([]);
    });
  }

  it("mesa-candidates-panel no reintroduce el score crudo como texto", () => {
    const firstLevel = stripTechnicalDetailBlocks(
      readSource("mesa-candidates-panel.tsx"),
    );
    // `OpportunityScoreBars` (componente) queda permitido; la nota cruda no.
    expect(firstLevel).not.toMatch(/OpportunityScore(?!Bars)/);
  });

  it("el menú Avanzado no usa el alias deprecado «Libro» (UI5-20)", () => {
    const blob = HOY_DETAIL_ITEMS.map((i) => `${i.label} ${i.hint}`).join(" ");
    expect(blob).not.toMatch(/Libro/);
  });

  it("la pregunta declarada es «¿Qué requiere mi atención?» (H-08)", () => {
    const src = readSource("mesa-hoy-page.tsx");
    expect(src).toMatch(/¿Qué requiere mi\s+atención\?/);
    expect(src).not.toMatch(/¿qué debo hacer\?/);
  });
});
