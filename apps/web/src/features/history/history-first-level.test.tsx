/**
 * Falsable — oleada 2 Cartera/Historial (`R-G1`, `UI5-20`, `UI5-14`).
 *
 * Lee el FUENTE de las superficies de primer nivel y afirma que `Libro`/`Ledger`/`fills`
 * no viven fuera del disclosure único (`TechnicalDetail`). El gate compartido
 * (`stripTechnicalDetailBlocks`) retira los bloques de nivel 3; lo que queda es nivel 1.
 *
 * El barrido busca la palabra COMPLETA (`\b…\b`): identificadores de código
 * (`MesaLibroPanel`, `LedgerEntryDto`, `api.getAccountLedger`) no son copy de primer
 * nivel; el test sigue falsando el término visible (`Libro`, `Ledger`, `ledger`, `fills`).
 *
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §5 oleada 2 / §6
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (UI5-14, UI5-20, R-G1)
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const HISTORY_PAGE = resolve(
  process.cwd(),
  "src/features/history/history-page.tsx",
);
const MESA_LIBRO_PANEL = resolve(
  process.cwd(),
  "src/features/mesa/mesa-libro-panel.tsx",
);

const SURFACES = [
  { name: "history-page.tsx", path: HISTORY_PAGE },
  { name: "mesa-libro-panel.tsx", path: MESA_LIBRO_PANEL },
] as const;

/** Términos prohibidos de `UI5-20` como palabra completa (no fragmento de identificador). */
const FORBIDDEN_WORDS = ["Libro", "Ledger", "ledger", "fills"] as const;

function readSource(path: string): string {
  return readFileSync(path, "utf8");
}

function findWholeWordViolations(source: string): string[] {
  const firstLevel = stripTechnicalDetailBlocks(source);
  return FORBIDDEN_WORDS.filter((word) =>
    new RegExp(`\\b${word}\\b`).test(firstLevel),
  );
}

describe("Cartera/Historial — primer nivel sin Libro/Ledger/fills (R-G1/UI5-20)", () => {
  it.each(SURFACES)(
    "$name no filtra jerga fuera de TechnicalDetail",
    ({ path }) => {
      const source = readSource(path);
      // Gate compartido: `fills` como subcadena no aparece en primer nivel.
      expect(findFirstLevelViolations(source, ["fills"])).toEqual([]);
      // `Libro`/`Ledger`/`ledger`/`fills` como palabra completa (evita colisiones de código).
      expect(findWholeWordViolations(source)).toEqual([]);
    },
  );

  it("history-page.tsx: el gate compartido no ve `Libro`/`fills` en primer nivel", () => {
    const firstLevel = stripTechnicalDetailBlocks(readSource(HISTORY_PAGE));
    expect(findFirstLevelViolations(firstLevel, ["Libro", "fills"])).toEqual(
      [],
    );
  });

  it.each(SURFACES)(
    "$name usa `Cartera`/`Posiciones`/`Historial`",
    ({ path }) => {
      const firstLevel = stripTechnicalDetailBlocks(readSource(path));
      expect(firstLevel).toMatch(/Posiciones|Historial|Cartera/);
    },
  );
});
