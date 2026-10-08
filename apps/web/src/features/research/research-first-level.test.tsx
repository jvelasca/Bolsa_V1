/**
 * Gate falsable de primer nivel · Asesor (`/research`) — oleada 4 (UI 6.x).
 *
 * El primer nivel de Asesor solo muestra resultado/veredicto («¿Por qué?»); la
 * jerga estadística/de ingeniería (`Sharpe`, `campaignId`, `WFE`/`PBO`/`DSR`,
 * `ledger`, `Params`/`Manifest`…) vive detrás del `TechnicalDetail` único.
 *
 * @see apps/web/src/components/first-level-gate.ts
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §5 (oleada 4)
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

function readSource(file: string): string {
  return readFileSync(resolve(__dirname, file), "utf8");
}

/**
 * Falsos positivos legítimos del gate textual sobre TSX: además de identificar
 * la jerga, estos tokens son nombres de parámetro HTTP / estado de React / query
 * de URL (`row.proposedBy`, `presetKey:`, `?runId=`). No se pintan como texto —
 * se pinta su valor, que sí va plegado tras el `Detalle técnico`.
 */
const CODE_IDENTIFIER_TOKENS: readonly string[] = [
  "proposedBy",
  "presetKey",
  "runId",
];

const FIRST_LEVEL_TOKENS = FORBIDDEN_FIRST_LEVEL_TOKENS.filter(
  (token) => !CODE_IDENTIFIER_TOKENS.includes(token),
);

const SOURCES: Record<string, string> = {
  "research-page.tsx": readSource("research-page.tsx"),
  "research-trial-result-block.tsx": readSource(
    "research-trial-result-block.tsx",
  ),
  "asesor-daily-ops-panel.tsx": readSource("asesor-daily-ops-panel.tsx"),
};

describe("Asesor · primer nivel sin jerga de ingeniería (R-G1 / RT-04)", () => {
  it("ninguna superficie expone jerga fuera de TechnicalDetail", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(
        findFirstLevelViolations(source, FIRST_LEVEL_TOKENS),
        file,
      ).toEqual([]);
    }
  });

  it("usa el disclosure único `TechnicalDetail` (sin `<details>` paralelos)", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(source, file).not.toContain("<details");
      expect(source, file).not.toContain("<summary");
    }
  });

  it("pliega la jerga estadística del laboratorio tras el nivel 3", () => {
    const src = SOURCES["research-page.tsx"];
    const firstLevel = stripTechnicalDetailBlocks(src);
    expect(firstLevel).not.toContain("Sharpe presente");
    expect(firstLevel).not.toContain("campaignId");
    // Sigue existiendo: solo que dentro del disclosure.
    expect(src).toContain("Sharpe presente");
    expect(src).toContain("campaignId");
  });

  it("no usa «Sin datos.» ni el comodín `—` de dato ausente (UI5-14)", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(stripTechnicalDetailBlocks(source), file).not.toContain(
        "Sin datos.",
      );
    }
    expect(
      stripTechnicalDetailBlocks(SOURCES["research-page.tsx"]),
    ).not.toMatch(/\?\?\s*"—"/);
  });

  it("Diario nombra el resultado, no el almacén (`Ledger`)", () => {
    const firstLevel = stripTechnicalDetailBlocks(
      SOURCES["asesor-daily-ops-panel.tsx"],
    );
    expect(firstLevel).not.toContain("Ledger");
    expect(firstLevel).not.toContain("balance ledger");
  });
});
