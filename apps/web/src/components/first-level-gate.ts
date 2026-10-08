/**
 * Gate falsable de primer nivel (UI 6.x · `R-G1`/`RT-02`).
 *
 * Fuente de verdad para detectar jerga de ingeniería que NO debe vivir en el primer nivel
 * de una superficie (solo dentro de un `TechnicalDetail` / `AutoTechnicalDetail`).
 *
 * Es un helper PURO sobre el texto fuente de un componente, para que cada oleada ancle su
 * propio test sin montar React. `stripTechnicalDetailBlocks` retira los bloques de nivel 3
 * y lo que quede es el primer nivel auditable.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (RT-02, RT-04)
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §1
 */

/** Identificadores de modelo / motor prohibidos en primer nivel (auditoría UI 6.x §8). */
export const FORBIDDEN_FIRST_LEVEL_TOKENS: readonly string[] = [
  "Recommendation",
  "DecisionSession",
  "Policy Gate",
  "OpportunityScore",
  "Risk Gate",
  "Heartbeat",
  "heartbeat",
  "provenance",
  "runId",
  "cycleId",
  "PAPER_D_EXECUTE",
  "settlement",
  "ledger",
  "Ledger",
  "fills",
  "DÍA-D",
  "WFE",
  "PBO",
  "DSR",
  "campaignId",
  "proposedBy",
  "presetKey",
];

const TECHNICAL_DETAIL_TAG =
  /<(AutoTechnicalDetail|TechnicalDetail)\b[\s\S]*?<\/\1>/g;

/**
 * Devuelve el `source` sin los bloques de `TechnicalDetail` / `AutoTechnicalDetail`.
 * Sirve para afirmar que un token prohibido vive SOLO en nivel 3.
 */
export function stripTechnicalDetailBlocks(source: string): string {
  return source.replace(TECHNICAL_DETAIL_TAG, "");
}

/** Tokens prohibidos presentes en el primer nivel (fuera de los disclosures). */
export function findFirstLevelViolations(
  source: string,
  tokens: readonly string[] = FORBIDDEN_FIRST_LEVEL_TOKENS,
): string[] {
  const firstLevel = stripTechnicalDetailBlocks(source);
  return tokens.filter((token) => firstLevel.includes(token));
}

/**
 * Comodín `—` de dato ausente en primer nivel (`UI5-14`).
 *
 * Detecta el literal de guion (`"—"`, `'—'`, `` `—` ``, `&mdash;`) usado como relleno de
 * un dato ausente, fuera de los bloques `TechnicalDetail`. El guion de prosa (p. ej. un
 * inciso «Editar — Nombre») NO es un comodín y no se marca: la coincidencia exige el
 * literal entrecomillado o la entidad HTML.
 */
const DASH_WILDCARD = /["'`]—["'`]|&mdash;/g;

/** Literales de guion `—` de primer nivel (vacío si solo aparece en nivel 3 o en prosa). */
export function findFirstLevelDashes(source: string): string[] {
  return stripTechnicalDetailBlocks(source).match(DASH_WILDCARD) ?? [];
}
