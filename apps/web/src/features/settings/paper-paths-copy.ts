/**
 * Copy unificada de los caminos Lab checklist (A), Radar (B), Supervisado F3 (C)
 * y Monitor Finalistas (pre-D, solo lectura).
 *
 * Premisa 2026-07-31: operación solo sobre la **cuenta activa DEMO** (`simulated`).
 * «Paper» como tipo de cuenta = broker real futuro — no usar ahora.
 * IDs técnicos (paper_auto, PAPER_PATH_*) se conservan; el lenguaje de producto dice demo.
 *
 * Regla: no mezclar etiquetas. Checklist ≠ Proponer ≠ Radar ≠ auto D.
 *
 * @see docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
 * @see docs/engineering/research-lifecycle.md § Narrativa unificada
 */

/** Camino A — deploy manual al ledger de la cuenta activa (DEMO). */
export const PAPER_PATH_LAB = {
  id: 'lab_checklist' as const,
  shortTitle: 'Lab → demo',
  cta: 'Desplegar en demo',
  checklistTitle: 'Checklist pre-demo',
  blurb:
    'Despliega sobre la cuenta activa DEMO (simulada) desde un run con checklist y evidencia lab. Manual · no es broker real ni auto.',
  accountNote: 'Camino Lab (checklist) · cuenta activa DEMO, no tipo Paper/broker',
  libraryHint:
    'Para demo: Usar → probar → checklist «Desplegar en demo». Sin atajo desde la lista.',
  finalistsHint:
    'Demo: Checklist abre el resultado del embudo (sin re-Lab). Luego «Desplegar en demo» en la cuenta activa. No es auto ni broker Paper.',
} as const;

/**
 * Camino C — propose con FA + perfil de cuenta → cola Supervisado F3 (SEMI).
 * Humano confirma. Entrada desde Finalistas, chart, scan o alarmas Radar.
 * Producto: modo libro SEMI · canal Confirm DEMO.
 */
export const PAPER_PATH_SUPERVISED = {
  id: 'supervised_f3' as const,
  shortTitle: 'SEMI · Confirm DEMO',
  cta: 'Proponer',
  blurb:
    'SEMI: propose (FA + perfil + momento) → cola Confirm F3 → humano ejecuta en DEMO. No es AUTO ni Desplegar checklist (A).',
  finalistsHint:
    'Proponer = SEMI / Camino C (→ F3 → Confirm). Checklist = Camino A (demo). Distintos; ninguno es broker Paper ni AUTO.',
} as const;

/**
 * Precondición de auto demo D: tablero de estado (Ayuda → Backtesting).
 * No despliega ni ejecuta.
 */
export const PAPER_PATH_MONITOR = {
  id: 'strategy_monitor' as const,
  shortTitle: 'Monitor Finalistas',
  blurb:
    'Estado TOP por valor: evidencia, DEMO/paper (retorno %), Proponer F3 y cola CORE-R. Solo lectura. No cambia mandato hasta aceptar.',
  warnLine:
    'Vista de estado · precondición de D. Encolar/Narrar/auto-sync no ejecutan ni pisan TOP. Propose D vive en Screeners.',
} as const;

/** Camino B — paper_auto técnico desde rastreador (Gate) sobre cuenta DEMO si se ejecuta. */
export const PAPER_PATH_RADAR = {
  id: 'radar_paper_auto' as const,
  shortTitle: 'Radar → demo',
  modeLabel: 'Automático en demo (radar)',
  cta: 'Rastreador',
  blurb:
    'Hit de rastreador → Gate. Sin checklist Lab. Si ejecuta, usa la cuenta activa DEMO. Distinto del Checklist del hub Probar.',
  warnLine:
    'No confundir con el Lab: aquí no hay checklist OOS/WF. Modo técnico paper_auto = ledger DEMO, no broker Paper.',
  finalistsHint:
    'Rastreador = Camino B: vigilancia sobre la estrategia del slot → Screeners. Política inform/alert = alarmas; paper_auto = DEMO activa (no broker). ≠ Checklist (A) ≠ Proponer (C).',
  requireValidatedLabel:
    'Exigir backtest validado (recomendado · acerca el radar al rigor Lab)',
  requireValidatedHint:
    'Si lo desactivas, el auto en demo puede operar sin evidencia lab. Sigue siendo radar, no el embudo Probar.',
} as const;

/**
 * Camino D — plan completo (Composite × FA whitelist) / Libro AUTO Estudio.
 * Propose + execute opcional (PAPER_D_EXECUTE + Risk Engine + política paper_auto).
 * Producto Libro: modo AUTO visible en Operativa (A1) pero deshabilitado hasta thaw.
 */
export const PAPER_PATH_D = {
  id: 'paper_d_full_auto' as const,
  shortTitle: 'Plan D (demo)',
  cta: 'Proponer plan D',
  blurb:
    'Composite × FA whitelist → propose; pipeline semanal; execute opcional en cuenta DEMO vía Risk Engine (modo técnico paper_auto). Libro AUTO = misma disciplina sin Confirm.',
  warnLine:
    'Execute: PAPER_D_EXECUTE=1 + checklist thaw. Libro AUTO pill = prep (A1), no activa fills. ≠ radar B ≠ Supervisado C. No es cuenta tipo Paper/broker.',
} as const;

/**
 * Decisión de producto: no unificar en un solo «auto».
 * Cuenta operativa = DEMO activa. Tipo Paper = broker futuro.
 */
export const PAPER_PATH_PRODUCT_DECISION = {
  asOf: '2026-07-31' as const,
  stance: 'demo_active_only' as const,
  summary:
    'Operar solo cuenta activa DEMO. Caminos A/B/C/D → ledger demo. Tipo cuenta Paper = broker real futuro. No unificar A/B/C/D.',
} as const;

export const PAPER_PATHS_COMPARE =
  'Puertas: Lab→demo (A) ≠ Radar (B) ≠ Supervisado (C) ≠ Plan D. Todo sobre cuenta activa DEMO. Paper broker = futuro.';

/** Al crear política paper_auto, default ON para requireValidatedBacktest. */
export function defaultRequireValidatedBacktest(mode: string): boolean {
  return mode === 'paper_auto';
}
