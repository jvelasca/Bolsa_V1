/**
 * Tracker Ayuda → Backtesting.
 * Resumen no técnico primero; pantallas, seguimiento de plataforma y detalle después.
 * El detalle vivo está en docs (no duplicar aquí el lifecycle completo).
 *
 * Sync embudo 5 etapas + soft-ACK + Lista AUTO frescura v1.3 + DÍA D v0.11 + CORE-R v1.8 + CORE-B v0.2 (2026-08-01).
 *
 * @see docs/HELP.md
 * @see docs/engineering/research-lifecycle.md
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 * @see docs/engineering/operativa-test-plan-2026-07-31.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 * @see docs/engineering/session-handoff-2026-08-01.md
 * @see docs/adr/009-backtesting-research-platform-h0.md
 */

import { HELP_CONTENT_AS_OF } from '@/features/help/help-content-as-of';

export const BACKTESTING_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  lifecycleDoc: 'docs/engineering/research-lifecycle.md',
  handoffDoc: 'docs/engineering/session-handoff-2026-08-01.md',
  listAutoOps: 'docs/engineering/list-auto-ops-2026-07-29.md',
  listsUniverses: 'docs/engineering/lists-universes-design-2026-07-30.md',
  funnelHandoff: 'docs/engineering/backtesting-funnel-handoff-2026-07-29.md',
  diaDPremises: 'docs/engineering/backtesting-dia-d-premises-2026-07-31.md',
  operativaTestPlan: 'docs/engineering/operativa-test-plan-2026-07-31.md',
  adrH0: 'docs/adr/009-backtesting-research-platform-h0.md',
  dataArch: 'docs/BACKTESTING_DATA_ARCHITECTURE.md',
  adrEvidence: 'docs/adr/018-fase2-evidence-store-v0.md',
  route: '/backtests',
} as const;

/** Orientación en lenguaje llano (primera tarjeta). */
export const BACKTESTING_SUMMARY = {
  title: 'En pocas palabras',
  body:
    'Backtesting responde: «si hubiera seguido esta regla en el pasado, ¿qué habría pasado?». No es una predicción ni una orden de compra. Usas datos históricos de tu base local, eliges un valor (o una lista), una estrategia y un periodo; la app simula operaciones y te muestra el resultado en lenguaje claro.',
  bullets: [
    'Pantalla principal: Probar estrategia (valor o lista + matriz; periodo/capital en Opciones avanzadas).',
    'Play (ciclo ON): 1 Probar genéricas → 2 Coach (ACK¹) → 3 Lab → 4 Revalidar (ACK final) → 5 Finalistas. Lista = mismo × ticker.',
    '⋯ = diagrama de flujo con checks (Auto-ACK, Pausar ACK, atajo semifinal OFF, Lab si no mejora = no grabar).',
    'Lista AUTO: puedes ir a Trading mientras corre (barra de estado abajo). Tras reinicio, omite si no cambió nada.',
    'Universo → Lista: miembros con resumen (Finalistas / ★ / Lab / AUTO). Clic = pestaña Valor. Soft-cap 40 + confirm; filtro opcional «solo sin Finalistas».',
    'Finalistas: Checklist = demo activa (A); Rastreador = Radar (B); Proponer = Supervisado F3 (C). Distintos.',
    'DÍA D: fecha «hoy simulado» en Probar → Play → Finalistas #1 «Simular D→hoy» → Trading (película ± pantalla completa + Manual/Semi/Auto + Evidence + archivo JSON import/export).',
    'Monitor Finalistas: hub Probar / Ayuda — TOP + DEMO retorno % + cola CORE-R (Encolar / Narrar / auto-sync / chip barra). Solo lectura; no es auto-paper.',
    'Cuentas: una Activa · hoy solo DEMO. Paper = broker futuro. docs/engineering/account-premises-demo-vs-paper-2026-07-31.md',
    'Unificación Research→Radar: docs/engineering/research-radar-unification-2026-07-31.md',
  ],
} as const;

export const BACKTESTING_YOU_ARE_HERE = {
  title: 'Cómo empezar (usuario básico)',
  body: 'Ruta corta para la primera prueba útil. No hace falta Optimizar a mano ni paper el primer día.',
  steps: [
    'Abre Backtesting (/backtests) → pestaña Probar estrategia.',
    'Elige un valor con histórico (periodo/capital en Opciones avanzadas; se recuerda tras reinicio).',
    'Pulsa Play (ciclo completo ON) → mapa 5 etapas hasta Finalistas (solo guarda TOP con mejora Lab).',
    'Lista IBEX/S&P: modo Lista + Play = Lista AUTO. Pref «Omitir si Finalistas frescos» ON. ≠ «Probar lista».',
    'En Lista valores, ojea el resumen por ticker; clic abre Valor/Detalle.',
    'Mientras corre: ve a Trading — footer con progreso. Tras reinicio, un 2º Play debe Omitir (histéresis: 1 barra diaria no fuerza re-embudo).',
    'Desde Finalistas: Checklist → demo activa (A), Rastreador → Screeners (B), o Proponer → Supervisado F3 (C).',
  ],
  pause:
    'Paper D (execute) es otra puerta — off por defecto (`PAPER_D_EXECUTE`). Primero entiende una prueba simple, Finalistas y el checklist.',
} as const;

/** Cómo arrancar Backtesting DÍA D (verificación D→hoy). */
export const BACKTESTING_DIA_D_GUIDE = {
  title: 'Backtesting DÍA D — cómo arrancar',
  body:
    'Simula que «hoy» es una fecha pasada (D), construye Finalistas solo con datos ≤ D, y verifica en Trading qué habría pasado de D a hoy con la #1.',
  steps: [
    'Backtesting → Probar estrategia → bloque amarillo/gris «Backtesting DÍA D».',
    'Elige una fecha pasada (p. ej. hace 1 año). No dejes «hoy» si quieres la verificación.',
    'Elige un valor con histórico → Play (ciclo completo) hasta Finalistas.',
    'En el panel derecho, pestaña Finalistas. En la fila #1 pulsa «Simular D→hoy».',
    'Se abre Trading con banner MODO DÍA D + película (sandbox; no escribe la DEMO live).',
    'Elige modo: Auto (fills solos), Semi (pausa → Aceptar/Rechazar reescribe equity), Manual (▶ + mismo gate).',
    'Opcional: «Pantalla completa» en el banner (oculta watchlist/gráfico/Operaciones); «Salir pantalla completa» vuelve. Al recargar, full-bleed no se restaura (siempre docks).',
    'Revisa el Informe lateral (Evidence band + retorno gate vs Auto). «Narrar con IA» opcional.',
    '«Guardar Evidence»: archivo local + Fase 2. Archivo en Trading + Ayuda (preview / JSON / Importar). «Salir DÍA D» cierra la sesión y restaura Trading normal (Operaciones).',
  ],
  notes: [
    'Sin fecha en el pasado no aparece el CTA «Simular D→hoy».',
    'Hay que tener Finalistas con #1 (strategyDefinitionId). Si el embudo no guardó TOP, no hay botón.',
    'Semi/Manual: solo Aceptar ejecuta el fill. Rechazar un buy anula también su sell. Equity y markers se recalculan.',
    'FA as-of: con statementPack (tras refresh FA) reconstruye estados ≤ D (pointInTime=reconstructed). Sin pack → blocked. Composite TA corta OHLCV ≤ D.',
    'Evidence sesión C: no es Coach FA. Archivo también en Ayuda → Backtesting. Export/Import JSON = local (mismo valor).',
    'fullBleedMovie no se persiste (2026-08-01): si Trading «desapareció», Salir DÍA D o recarga.',
    'Reinicia api-python tras pulls para rutas Evidence / asOf / CORE-R.',
    'Doc técnico: docs/engineering/backtesting-dia-d-premises-2026-07-31.md',
    'Plan de prueba: docs/engineering/operativa-test-plan-2026-07-31.md · pnpm test:operativa',
  ],
} as const;

/** Monitor + cola CORE-R (reevaluación; no auto-paper). */
export const BACKTESTING_CORE_R_GUIDE = {
  title: 'CORE-R / Monitor — cola de revisión',
  body:
    'Tras Lista AUTO (o con DEMO vinculada al TOP), el Monitor encola juicios a revisar. No pisa Finalistas ni despliega paper.',
  steps: [
    'Abre Monitor: hub Probar (desplegable) o Ayuda → Backtesting (panel debajo de DÍA D).',
    'Elige la lista (p. ej. IBEX). Filas con TOP muestran demo/paper + retorno % si hay cuenta vinculada.',
    'Pulsa «Encolar revisiones»: mezcla informe Lista AUTO + PnL DEMO ≤ −5% (Lab) / ≤ −10% (cambio).',
    'Abre Lab / Finalistas / Checklist desde la cola; marca «Hecho» al cerrar.',
    'Opcional: «Narrar cola» (heurística; LLM si hay Ollama).',
    'Opcional: «Auto-sync app abierta» · chip · toast Abrir Monitor · «Hecho todos» en cola.',
  ],
  notes: [
    'Sandbox DÍA D ≠ DEMO live. CORE-R lee DEMO/paper vinculadas al TOP (prefer simulated).',
    'Cron shell ≠ cron multi-dispositivo: la cola vive en localStorage de este navegador.',
    'Chip barra / toast «Abrir Monitor» → Ayuda · Monitor. También /backtests?tab=run&focus=monitor',
    'Hecho todos cierra abiertas de la lista actual (no borra; clearDone limpia done).',
    'Toast solo si added > 0 (sin ruido en ticks vacíos).',
    'No es auto-paper D. No overwrite de TOP active.',
    'Ops: pnpm test:operativa · ISSUES.md · CORE-R · list-auto-ops § CORE-R',
  ],
} as const;

export const BACKTESTING_SCREENS = [
  {
    id: 'probar',
    title: 'Probar estrategia',
    plain: 'Wizard: valor o lista + matriz. Periodo/capital en Opciones avanzadas.',
    detail:
      'Play ciclo = embudo hasta Finalistas. Lista + Play = Lista AUTO (frescura/Omitido; keep-alive en Trading). «Probar lista» = Fase C.',
  },
  {
    id: 'dia-d',
    title: 'Backtesting DÍA D',
    plain:
      'Fecha «hoy simulado» en Probar → embudo ≤ D → Finalistas #1 «Simular D→hoy» → Trading (película).',
    detail:
      'Sandbox ≠ DEMO live. Manual/Semi/Auto. Pantalla completa efímera (no persiste al recargar) + Guardar Evidence + archivo. Premisas: backtesting-dia-d-premises-2026-07-31.md',
  },
  {
    id: 'resultado',
    title: 'Resultado (Análisis técnico / fundamental / Coach / Lab / Finalistas / Lista AUTO)',
    plain:
      'Pestañas del panel derecho: técnico (gráfico/replay), fundamental (Tarjeta Valor), TOP ★, laboratorio y campaña.',
    detail:
      'Análisis técnico = Detalle clásico (sin FA mezclado). Análisis fundamental = Tarjeta Valor + Composite + filings. Finalistas: Checklist (A) y Proponer (C).',
  },
  {
    id: 'estrategias',
    title: 'Biblioteca',
    plain: 'Genéricas, Mis estrategias y Finalistas del valor.',
    detail:
      'Lista first; filtros alcance/TF/origen. Paper solo vía checklist del resultado (sin atajo Paper).',
  },
  {
    id: 'optimizar',
    title: 'Lab · Optimizar',
    plain: 'Busca mejores parámetros; no declara «lista para invertir».',
    detail:
      'Mismo Lab del embudo. Empty state → Coach. Memoria CORE-B v0.2 (meseta/pico + familia por horizonte). Lab no escribe Finalistas → Reanalizar con Coach.',
  },
  {
    id: 'anteriores',
    title: 'Pruebas anteriores / Research',
    plain: 'Histórico de lo ya ejecutado para revisar y comparar.',
    detail:
      'Lista acotada (default 20, ⚙). Enlace al ledger Research. Vacío → CTA Probar.',
  },
  {
    id: 'monitor-ayuda',
    title: 'Monitor Finalistas',
    plain: 'Tablero de estado por lista: TOP, paper, último Proponer.',
    detail:
      'En hub Probar (desplegable abajo) y Ayuda → Backtesting. TOP + DEMO % + cola CORE-R (Encolar / Narrar / Auto-sync). Solo lectura; no auto-paper D.',
  },
] as const;

/** Seguimiento de plataforma — badges alineados con research-lifecycle.md. */
export const BACKTESTING_TRACKING = [
  {
    id: 'ui-abc',
    title: 'Wizard + resultado + listas',
    status: 'listo' as const,
    plain: 'Hub Probar (matriz + Coach + Lab + Finalistas) operativo; catálogo 21 genéricas.',
  },
  {
    id: 'full-cycle',
    title: 'Play ciclo completo (1 valor)',
    status: 'listo' as const,
    plain:
      '⋯ diagrama de flujo: ACK¹→Lab, Lab sin mejora=no grabar, ACK final. Soft-ACK / Pausar. Atajo semifinal OFF.',
  },
  {
    id: 'list-auto',
    title: 'Lista AUTO (ciclo × N)',
    status: 'listo' as const,
    plain:
      'Lista + Play: embudo × ticker (máx. 40). Keep-alive + barra Trading. Frescura v1.3 omite tras reinicio / pocas barras. ≠ Fase C.',
  },
  {
    id: 'list-auto-freshness',
    title: 'Frescura / Omitido (post-reinicio)',
    status: 'listo' as const,
    plain:
      'Huella local+DB; histéresis lastBar (1d ≤5d → bar_hysteresis; stamp no desliza). Reevaluar resto = forzar.',
  },
  {
    id: 'dia-d',
    title: 'Backtesting DÍA D (v0.11)',
    status: 'listo' as const,
    plain:
      'asOf + gate + full-bleed efímero + Evidence + archivo. Salir DÍA D restaura Operaciones. DÍA D v1 operable.',
  },
  {
    id: 'lab-core-b',
    title: 'Lab memoria (CORE-B v0.2)',
    status: 'listo' as const,
    plain:
      'Adopción → espacio guiado (meseta ancha / pico estrecho). Sin semilla: familia = adopción → horizonte perfil → SMA.',
  },  {
    id: 'finalists-to-tracker',
    title: 'Finalistas → Rastreador (B)',
    status: 'listo' as const,
    plain:
      'CTA Rastreador crea TrackerDefinition (assisted) y abre Screeners. Camino B ≠ A ≠ C. Ver research-radar-unification.',
  },
  {
    id: 'finalists-paper',
    title: 'Finalistas → checklist paper',
    status: 'listo' as const,
    plain:
      'CTA Checklist en Finalistas (runId) abre Detalle + checklist. Camino A manual; no es auto-paper D.',
  },
  {
    id: 'finalists-supervised',
    title: 'Finalistas → Supervisado F3',
    status: 'listo' as const,
    plain:
      'CTA Proponer (lab_validated): FA+perfil → cola F3 (origen Finalistas) + foco Confirm. Camino C ≠ A ≠ D.',
  },
  {
    id: 'strategy-monitor',
    title: 'Monitor Finalistas (MVP)',
    status: 'listo' as const,
    plain:
      'Hub Probar + Ayuda: TOP + DEMO retorno % + Proponer. Cola CORE-R (Encolar / Narrar / cron shell). Solo lectura; D congelado.',
  },
  {
    id: 'core-r-queue',
    title: 'CORE-R cola revisión (Monitor)',
    status: 'listo' as const,
    plain:
      'v1.8: informe + PnL + Narrar + cron + chip + toast Abrir Monitor + Hecho todos. Sin overwrite TOP ni auto-paper D.',
  },
  {
    id: 'lab-ui',
    title: 'Laboratorio Optimizar (P3–P9)',
    status: 'cerrado' as const,
    plain: 'OOS/WF, checklist pre-demo, EdgeReport y adopt están hechos; el track UI del lab está en pausa deliberada.',
  },
  {
    id: 'fase2',
    title: 'Fase 2 — evidencia científica (P2.A–P2.F)',
    status: 'listo' as const,
    plain:
      'Hipótesis, evidencia, creencia y nodos de conocimiento existen en backend (sin auto-live). La UI cognitiva profunda sigue congelada.',
  },
  {
    id: 'auto-paths',
    title: 'Paper / auto: puertas etiquetadas',
    status: 'listo' as const,
    plain:
      'A checklist · B radar · C Supervisado · Monitor estado · D Paper D (propose + execute gated PAPER_D_EXECUTE). Screeners FA→whitelist→D.',
  },
  {
    id: 'frozen',
    title: 'Aún no (congelado)',
    status: 'congelado' as const,
    plain:
      'Discovery automático, Planner IA, Decay/Pruning, UI cognitiva completa. Execute paper sigue off-by-default (no es auto de producción).',
  },
] as const;

export const BACKTESTING_IDEAS = [
  {
    id: 'no-crystal',
    title: 'No es una bola de cristal',
    body: 'El pasado no garantiza el futuro. Una curva bonita puede ser suerte o sobreajuste.',
  },
  {
    id: 'vs-bh',
    title: 'Siempre mira vs buy & hold',
    body: 'Si no mejoras a comprar y mantener (con costes), la regla no aporta valor práctico.',
  },
  {
    id: 'oos',
    title: 'Validar fuera de muestra',
    body: 'Antes de desplegar en la demo activa, usa hold-out o walk-forward en Optimizar y el checklist pre-demo.',
  },
  {
    id: 'ledger',
    title: 'Todo deja rastro',
    body: 'Las pruebas quedan en el ledger de research para auditar qué se probó y con qué parámetros.',
  },
  {
    id: 'auto-paths',
    title: 'Varias puertas, ninguna «auto de producción»',
    body:
      'Checklist (A) ≠ Radar (B) ≠ Proponer F3 (C). El Monitor solo muestra estado. Auto completo (D) congelado.',
  },
  {
    id: 'list-auto-fresh',
    title: 'Lista AUTO no debe recalcular por capricho',
    body:
      'Si periodo/costes/perfil/lote no cambiaron, el 2º Play omite. Histéresis v1.3: pocas barras nuevas (1d ≤5d) también Omitido. «Reevaluar resto» fuerza.',
  },
] as const;

export const BACKTESTING_NEXT = [
  'Cierre código 2026-08-01 OK · siguiente = smoke UI humano',
  'Smoke UI a fondo: operativa-test-plan D1–D12 + R1–R9',
  'Smoke UI: DÍA D → Análisis fundamental badge reconstructed/blocked',
  'Smoke UI: reinicio → Play IBEX → mayoritariamente Omitido (histéresis v1.3)',
  'Checklist FA APP: refresh · Tarjeta CAPM/ADV · Screener · Paper D dry-run',
  'Ops: pnpm test:operativa · test:operativa:smoke · test:fa · test:coach',
  'Handoff: docs/engineering/session-handoff-2026-08-01.md',
  'Congelado: auto-paper D · Lab P3–P9 / Belief · CORE-R multi-dispositivo',
] as const;

export function backtestingStatusLabel(
  status: (typeof BACKTESTING_TRACKING)[number]['status'],
): string {
  if (status === 'listo') return 'Listo';
  if (status === 'cerrado') return 'Cerrado / en uso';
  return 'Congelado';
}
