/**
 * Falsable — P5 · vocabulario del espacio AUTO en primer nivel (`R-G1`, `RT-02`).
 *
 * `DÍA-D` es un token PROHIBIDO en primer nivel (`components/first-level-gate.ts`): la copy
 * de nivel 1 usa el vocabulario permitido «D→hoy» / «Verificar D→hoy». Este test ancla el
 * vocabulario de las superficies AUTO de primer nivel (nav, home, listado/operación, el
 * puente de estrategia y el tabpanel de Análisis) leyendo su FUENTE: los comentarios no son
 * copy de usuario y el acrónimo solo puede vivir tras el disclosure (`AutoTechnicalDetail`).
 *
 * @see apps/web/src/components/first-level-gate.ts
 * @see apps/web/src/features/barrido-global-first-level.test.tsx
 * @see apps/web/src/features/platform/product-universe.ts (VERIFY_DIA_D_CTA)
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { findFirstLevelViolations } from "@/components/first-level-gate";

const ROOT = resolve(process.cwd(), "src");

/** Fuente sin comentarios (no son copy de usuario), como en el barrido global. */
function readSurface(relative: string): string {
  return readFileSync(resolve(ROOT, relative), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

const FIRST_LEVEL_AUTO_SURFACES: Array<{ name: string; file: string }> = [
  { name: "AUTO · auto-nav.ts", file: "features/auto/auto-nav.ts" },
  {
    name: "AUTO · auto-home-page.tsx",
    file: "features/auto/auto-home-page.tsx",
  },
  {
    name: "AUTO · auto-operar-page.tsx",
    file: "features/auto/auto-operar-page.tsx",
  },
  {
    name: "AUTO · auto-operar-verify-action.tsx",
    file: "features/auto/auto-operar-verify-action.tsx",
  },
  {
    name: "AUTO · auto-operacion-page.tsx",
    file: "features/auto/auto-operacion-page.tsx",
  },
  {
    name: "AUTO · auto-operation-strategy.ts",
    file: "features/auto/auto-operation-strategy.ts",
  },
  {
    name: "AUTO · auto-analisis-page.tsx",
    file: "features/auto/auto-analisis-page.tsx",
  },
];

describe("AUTO · primer nivel sin el token «DÍA-D» (P5 · R-G1/RT-02)", () => {
  it.each(FIRST_LEVEL_AUTO_SURFACES)(
    "$name deja «DÍA-D» solo tras el detalle técnico",
    ({ file }) => {
      expect(findFirstLevelViolations(readSurface(file), ["DÍA-D"])).toEqual(
        [],
      );
    },
  );

  it("el gate detecta una fuga conocida de «DÍA-D» (control de falsabilidad)", () => {
    // Copy de nivel 1 ⇒ se marca.
    expect(findFirstLevelViolations("<p>DÍA-D</p>", ["DÍA-D"])).toEqual([
      "DÍA-D",
    ]);
    // Tras el disclosure (`AutoTechnicalDetail`) ⇒ permitido.
    expect(
      findFirstLevelViolations(
        "<AutoTechnicalDetail>DÍA-D</AutoTechnicalDetail>",
        ["DÍA-D"],
      ),
    ).toEqual([]);
  });
});
