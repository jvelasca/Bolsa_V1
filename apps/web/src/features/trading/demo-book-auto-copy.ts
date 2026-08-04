/**
 * A1 — copy de riesgos del modo AUTO (Libro DEMO).
 * UI muestra AUTO deshabilitado; execute sigue freeze (`PAPER_D_EXECUTE` + checklist thaw).
 *
 * @see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md §3 A1
 */

/** Flag de producto: no habilitar pill AUTO hasta A3 + evidencia P1–P10. */
export const DEMO_BOOK_AUTO_UI_ENABLED = false;

export const DEMO_BOOK_AUTO_TOOLTIP =
  'AUTO (Camino D) no disponible. Misma Alarma Estudio + Gate + Risk Engine, sin Confirm humano. Requiere evidencia + PAPER_D_EXECUTE + doble confirmación. Usa SEMI.';

export const DEMO_BOOK_AUTO_RISK_LINES = [
  'Sin Confirm: Alarma Estudio → Risk Engine → fill DEMO.',
  'Kill switch servidor (RISK_KILL_SWITCH) + confirmación doble en UI antes de activar.',
  'No es Radar paper_auto ni Auto del sandbox DÍA D.',
  'Thaw solo con checklist P1–P10 + ADR; PAPER_D_EXECUTE off por defecto.',
] as const;

export const DEMO_BOOK_AUTO_FOOTER =
  'SEMI = Confirm humano (F3). AUTO = prep visible, execute congelado (Camino D). Geo ordena la cola; no veta.';
