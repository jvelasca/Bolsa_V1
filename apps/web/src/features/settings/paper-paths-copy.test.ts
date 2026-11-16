/**
 * R3.3 — copy canónica de «Desplegar en demo» (auditoría LAB 2026-11-16).
 *
 * El despliegue del camino A **crea una cuenta paper de procedencia** y guarda allí la
 * evidencia del LAB; **no** escribe trades ni asientos en el ledger de la cuenta DEMO.
 * Este test fija la frase en la UI y en los dos documentos que la repetían al revés.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  DEPLOY_DEMO_CANONICAL,
  PAPER_PATH_LAB,
  PAPER_PATH_PRODUCT_DECISION,
  PAPER_PATHS_COMPARE,
} from "@/features/settings/paper-paths-copy";

const REPO_ROOT = resolve(process.cwd(), "../..");

function readDoc(relative: string): string {
  return readFileSync(resolve(REPO_ROOT, relative), "utf8");
}

describe("copy canónica del despliegue (R3)", () => {
  it("la frase canónica dice cuenta paper de procedencia y niega el ledger DEMO", () => {
    expect(DEPLOY_DEMO_CANONICAL).toMatch(/cuenta paper de procedencia/i);
    expect(DEPLOY_DEMO_CANONICAL).toMatch(
      /no escribe trades ni asientos en el ledger de la cuenta DEMO/i,
    );
  });

  it("el checklist pre-demo usa la frase canónica", () => {
    expect(PAPER_PATH_LAB.blurb).toBe(DEPLOY_DEMO_CANONICAL);
  });

  it("ninguna copy de la UI afirma que el deploy escriba la DEMO activa", () => {
    const uiCopy = [
      PAPER_PATH_LAB.blurb,
      PAPER_PATH_LAB.accountNote,
      PAPER_PATH_LAB.libraryHint,
      PAPER_PATH_LAB.finalistsHint,
      PAPER_PATH_PRODUCT_DECISION.summary,
      PAPER_PATHS_COMPARE,
    ].join(" \n ");
    expect(uiCopy).not.toMatch(/deploy en cuenta activa/i);
    expect(uiCopy).not.toMatch(/despliega sobre la cuenta activa/i);
    expect(PAPER_PATH_LAB.accountNote).toMatch(/cuenta paper de procedencia/i);
  });

  it("los documentos dicen lo mismo que la UI", () => {
    const domain = readDoc("docs/domain-language.md");
    expect(domain).toMatch(/cuenta paper de procedencia/i);
    expect(domain).toMatch(/ledger de la DEMO/i);

    const lifecycle = readDoc("docs/engineering/research-lifecycle.md");
    expect(lifecycle).toMatch(/cuenta paper de procedencia/i);
    expect(lifecycle).toMatch(
      /\*{0,2}no\*{0,2} escribe trades ni asientos en el ledger de la (cuenta )?DEMO/i,
    );
  });
});
