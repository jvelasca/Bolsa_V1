import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Ratchet de formato (Fase 3.3, auditoría externa).
 *
 * ``toFixed(2)`` produce punto decimal y no conoce divisa: en pantallas de usuario se
 * cambia por ``formatMoney``/``formatPct``/``formatBps`` (``@/lib/format``). No es un
 * reemplazo ciego: ejes de charts y cálculos internos pueden necesitar precisión fija,
 * así que el test **no prohíbe** la llamada, impide que el número crezca.
 *
 * Si lo bajas, ajusta ``BASELINE`` en el mismo PR para que el suelo no se pierda.
 */
const BASELINE = 131;
const FEATURES_ROOT = resolve(process.cwd(), "src/features");
const TO_FIXED_TWO = /\.toFixed\(\s*2\s*\)/g;
const CODE_FILE = /\.(ts|tsx)$/;
const TEST_FILE = /\.(test|spec)\.(ts|tsx)$/;

function filesUnder(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__snapshots__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      filesUnder(full, out);
    } else if (CODE_FILE.test(entry) && !TEST_FILE.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

function countToFixedTwo(): Map<string, number> {
  const byFile = new Map<string, number>();
  for (const file of filesUnder(FEATURES_ROOT)) {
    const matches = readFileSync(file, "utf8").match(TO_FIXED_TWO);
    if (matches?.length)
      byFile.set(file.replace(FEATURES_ROOT, "src/features"), matches.length);
  }
  return byFile;
}

describe("ratchet · toFixed(2) en componentes", () => {
  it(`no crece por encima de la línea base (${BASELINE})`, () => {
    const byFile = countToFixedTwo();
    const total = [...byFile.values()].reduce((sum, n) => sum + n, 0);
    const detail = [...byFile.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([file, n]) => `  ${n}  ${file}`)
      .join("\n");

    expect(
      total,
      `toFixed(2) en src/features: ${total} (línea base ${BASELINE}).\n` +
        "Migra los importes/porcentajes visibles a formatMoney/formatPct/formatBps " +
        "(@/lib/format) en vez de subir la línea base.\n" +
        detail,
    ).toBeLessThanOrEqual(BASELINE);
  });
});
