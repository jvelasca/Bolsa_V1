/**
 * Libro DEMO — modo AUTO / «Libro AUTO» (cuenta).
 * Thaw BETA-D (ADR-023 Accepted 2026-08-25): UI seleccionable tras armado local.
 * Execute sigue detrás de `PAPER_D_EXECUTE=1` (opt-in; default off).
 * V1.33 A-β: paridad SEMI (TradePlan TRIGGERED + risk_signature); solo salta Confirm.
 *
 * No confundir con Lista AUTO del Laboratorio (`list-auto-activity-store`).
 */

/** Flag de producto: pill Libro AUTO habilitada tras thaw BETA-D. */
export const DEMO_BOOK_AUTO_UI_ENABLED = true;

/** Etiqueta si un build legacy desactiva el flag. */
export const DEMO_BOOK_AUTO_UNAVAILABLE_LABEL = "No disponible";

/** Tooltip de mesa — Libro AUTO condicionado. */
export const DEMO_BOOK_AUTO_TOOLTIP =
  "Libro AUTO (BETA-D): escribe «ACTIVAR AUTO» para armar; execute solo con PAPER_D_EXECUTE=1. Misma disciplina SEMI (TradePlan) sin Confirm.";

/** Líneas de riesgo del panel. */
export const DEMO_BOOK_AUTO_RISK_LINES = [
  "Libro AUTO es thaw parcial (ADR-023 BETA-D): no broker live · no sizing libro paralelo.",
  "Armado UI (frase ACTIVAR AUTO) obligatorio; execute solo con PAPER_D_EXECUTE=1 + Gate / kill switch.",
  "Aperturas: TradePlan TRIGGERED + risk_signature (paridad SEMI). Sin claim de precisión Estudio (P3'/P4' diferidos).",
] as const;

/** Pie del panel Config operativa. */
export const DEMO_BOOK_AUTO_FOOTER =
  "SEMI = Confirm humano. Libro AUTO = armar con «ACTIVAR AUTO» + PAPER_D_EXECUTE=1 (BETA-D; paridad TradePlan).";
