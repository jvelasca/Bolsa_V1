/**
 * Gate falsable UI 6.x — primer nivel de Confirmar sin arquitectura interna.
 *
 * Lee el TEXTO FUENTE de las superficies de Confirmar y exige que ningún token de
 * ingeniería (`FORBIDDEN_FIRST_LEVEL_TOKENS`) viva fuera de un `TechnicalDetail`.
 *
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §3 (C-01/C-02)
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  findFirstLevelViolations,
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const here = dirname(fileURLToPath(import.meta.url));

const FIRST_LEVEL_FILES: string[] = [
  "live-virtual-order-gateway.tsx",
  "live-virtual-ladder.ts",
  "live-virtual-why.ts",
  "confirm-content.tsx",
  "../settings/supervised-f3-panel.tsx",
];

function readSource(relativePath: string): string {
  return readFileSync(join(here, relativePath), "utf8");
}

/**
 * Identificadores TS legítimos que CONTIENEN un token prohibido pero NO son copy
 * de UI (p. ej. el método de API `proposeRecommendation`). Se neutralizan antes
 * de auditar; cualquier otra aparición del token sigue fallando el gate.
 */
function neutralizeTsIdentifiers(source: string): string {
  return source.replace(/proposeRecommendation/g, "propuesta_solicitada");
}

describe("Confirmar — primer nivel sin arquitectura interna (gate falsable)", () => {
  it("el gate detecta una fuga conocida (control de falsabilidad)", () => {
    const leak = "<p>DecisionSession: abc</p>";
    expect(findFirstLevelViolations(leak)).toContain("DecisionSession");
    expect(stripTechnicalDetailBlocks(leak)).toContain("DecisionSession");
  });

  it.each(FIRST_LEVEL_FILES)(
    "%s: sin tokens prohibidos fuera de TechnicalDetail",
    (relativePath) => {
      const source = neutralizeTsIdentifiers(readSource(relativePath));
      expect(findFirstLevelViolations(source)).toEqual([]);
    },
  );

  it("el gate compartido declara tokens prohibidos", () => {
    expect(FORBIDDEN_FIRST_LEVEL_TOKENS.length).toBeGreaterThan(0);
  });
});
