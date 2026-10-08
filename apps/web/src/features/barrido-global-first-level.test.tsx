/**
 * UI 6.x — gate falsable de primer nivel del barrido global (`R-G1`/`RT-02`/`UI5-14`).
 *
 * Cubre las superficies que el sello `v2.88.91` declaró fuera de alcance y que este
 * barrido sí recorta:
 * - Mercado: `chart-workspace-page.tsx` + toolbar/`app-top-bar.tsx`.
 * - Laboratorio: `backtests-page.tsx` (+ pestañas).
 * - Chrome/palette: `app-top-bar.tsx` + `command-registry.ts` / `command-palette.tsx`.
 * - Barrido del comodín `—`: dashboard, cuentas, instrumentos, fiscal y screeners.
 *
 * Los identificadores TS legítimos (`runId`, `presetKey`) y las `keywords` de búsqueda no
 * son copy visible: se neutralizan antes de auditar. Los comentarios tampoco lo son.
 *
 * @see apps/web/src/components/first-level-gate.ts
 * @see docs/engineering/entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md §4
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  findFirstLevelDashes,
  findFirstLevelViolations,
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const ROOT = resolve(process.cwd(), "src");

/** Fuente sin comentarios (no son copy de usuario). */
function readSurface(relative: string): string {
  return readFileSync(resolve(ROOT, relative), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/** Identificadores TS y metadatos de búsqueda que NO son copy de primer nivel. */
function neutralizeIdentifiers(source: string): string {
  return source
    .replace(/\brunId\b/g, "identificador_interno")
    .replace(/\bpresetKey\b/g, "clave_preset")
    .replace(/\bcampaignId\b/g, "identificador_campana")
    .replace(/\bproposedBy\b/g, "propuesto_por")
    .replace(/keywords:\s*\[[^\]]*\]/g, "keywords: []");
}

/**
 * `OpportunityScore` colisiona como subcadena con el componente `OpportunityScoreBars`;
 * no aparece en estas superficies y se excluye del set por simetría con el gate de Hoy.
 */
const FIRST_LEVEL_TOKENS = FORBIDDEN_FIRST_LEVEL_TOKENS.filter(
  (token) => token !== "OpportunityScore",
);

const TOKEN_SURFACES: Array<{ name: string; file: string }> = [
  {
    name: "Mercado · chart-workspace-page.tsx",
    file: "features/charts/chart-workspace-page.tsx",
  },
  {
    name: "Mercado · app-top-bar.tsx",
    file: "components/layout/app-top-bar.tsx",
  },
  {
    name: "Laboratorio · backtests-page.tsx",
    file: "features/backtests/backtests-page.tsx",
  },
  {
    name: "Laboratorio · backtests-page-run-tab.tsx",
    file: "features/backtests/backtests-page-run-tab.tsx",
  },
  {
    name: "Laboratorio · backtests-page-jobs-tab.tsx",
    file: "features/backtests/backtests-page-jobs-tab.tsx",
  },
  {
    name: "Chrome · command-registry.ts",
    file: "features/command-palette/command-registry.ts",
  },
  {
    name: "Chrome · command-palette.tsx",
    file: "features/command-palette/command-palette.tsx",
  },
];

const DASH_SURFACES: string[] = [
  "features/dashboard/dashboard-page.tsx",
  "features/accounts/account-detail-panel.tsx",
  "features/instruments/instruments-page.tsx",
  "features/instruments/instruments-hub-detail-panel.tsx",
  "features/instruments/instrument-detail-page.tsx",
  "features/fiscal/tax-report-page.tsx",
  "features/screeners/fundamental-screener-panel.tsx",
  "features/screeners/paper-d-propose-panel.tsx",
];

describe("barrido global · primer nivel sin jerga de ingeniería (R-G1/RT-02)", () => {
  it.each(TOKEN_SURFACES)(
    "$name no expone tokens prohibidos fuera de TechnicalDetail",
    ({ file }) => {
      const source = neutralizeIdentifiers(readSurface(file));
      expect(findFirstLevelViolations(source, FIRST_LEVEL_TOKENS)).toEqual([]);
    },
  );

  it.each(TOKEN_SURFACES)(
    "$name no usa el comodín — como dato ausente",
    ({ file }) => {
      expect(findFirstLevelDashes(readSurface(file))).toEqual([]);
    },
  );
});

describe("barrido global · comodín — sustituido por vocabulario Opción B (UI5-14)", () => {
  it.each(DASH_SURFACES)("%s no usa el literal — como dato ausente", (file) => {
    expect(findFirstLevelDashes(readSurface(file))).toEqual([]);
  });
});

describe("barrido global · control de falsabilidad del gate", () => {
  it("el gate de tokens detecta una fuga conocida", () => {
    expect(findFirstLevelViolations("<p>Recommendation · runId</p>")).toEqual(
      expect.arrayContaining(["Recommendation", "runId"]),
    );
  });

  it("el gate de guion detecta el literal y respeta prosa y nivel 3", () => {
    expect(findFirstLevelDashes('{x ?? "—"}')).toHaveLength(1);
    expect(findFirstLevelDashes("<p>Editar — Nombre</p>")).toEqual([]);
    expect(
      findFirstLevelDashes('<TechnicalDetail>{"—"}</TechnicalDetail>'),
    ).toEqual([]);
  });

  it("stripTechnicalDetailBlocks sigue retirando el nivel 3", () => {
    expect(
      stripTechnicalDetailBlocks("<TechnicalDetail>ledger</TechnicalDetail>"),
    ).not.toContain("ledger");
  });
});
