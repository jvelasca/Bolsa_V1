/**
 * Fecha única de sync Ayuda ↔ trackers ↔ encabezados de docs.
 * Actualizar al cambiar estado de producto (no tipografía).
 *
 * Incluye: espacios, BD, perfiles, listas/índices, embudo Play,
 * Finalistas→A/C, Monitor MVP, CORE-P, CORE-R **v1.12** (BD + cron off + toast remoto),
 * **Backtesting DÍA D** (v0.11 · archivo también en Ayuda),
 * Lista AUTO frescura **v1.3**, CORE-B **v0.2**, CAPM Tarjeta v0,
 * Composite **v1.1**, fix Trading fullBleed,
 * **ADR-019** dos universos LAB vs TRADING (U1–U5).
 * **ADR-020** Mandato operativo (M0–M3 + **M1b BD** · tenure + trades + churn + sync).
 * **ADR-021** Reconciliación DÍA D (F-hoy · F-D · V · SAME/DRIFT · contrafactual).
 * Continuidad Verify (lookback + carry) · higiene `strategyType` Finalistas.
 * Post-auditorías Q0–Q3 + Q1.6 warm-up + estabilidad IBEX (Gate C4 cerrado).
 * **2026-08-04** — Panel **Operativa** + lista **Estudio** (membresía · bulk · gate SEMI/AUTO)
 * + Chart TOP#1 switches · **A1–A5 prep** Libro AUTO / kill switch / ADR-023 Proposed.
 * Pack auditoría: `docs/engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md`.
 * HELP.md sync Trading SEMI vs AUTO · Asesor Diario R1 · telemetría.
 * **2026-08-06** — **ADR-024** Estudio canónica + Supervisión ON + cadencias 3 capas
 * (vigilia / frescura / rediscubrimiento) · «Eliminar de la lista».
 * **2026-08-06b** — UI procesos (subtítulo V·F·R · Actualizar/Redescubrir) ·
 * Manual/SEMI/AUTO en barra de estado → Cuentas (fuera del panel Operativa por valor).
 * **2026-08-06c** — Actualizar/Redescubrir solo barra inferior · chips cadencia V·F·R en banner.
 * **2026-08-06d** — Visualizados = pestañas · Por IO · columnas recomendación ·
 * foco Cartera→Estudio→resto + scroll bajo cabecera sticky.
 *
 * Auditoría cierre: `docs/engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md`
 *
 * Track FA / FIE (2026-08-01): valoración cerrada en código
 * F0–F2.8 + F3 Composite + F4 Screener + Paper D + cron FA→D ·
 * Beneish→distress · Tarjeta densificada · CAPM rf/ERP visibles.
 *
 * Docs:
 * - `docs/adr/024-estudio-supervision-universe.md`
 * - `docs/engineering/estudio-supervision-model-2026-08-06.md`
 * - `docs/engineering/estudio-process-status-ui-2026-08-06.md`
 * - `docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md`
 * - `docs/engineering/visualizados-list-ux-2026-08-06.md`
 * - `docs/engineering/session-handoff-2026-08-06-visualizados-list-ux.md`
 * - `docs/engineering/trading-operativa-panel-2026-08-04.md`
 * - `docs/engineering/chart-top1-indicator-switch-2026-08-03.md`
 * - `docs/engineering/session-handoff-2026-08-04-operativa.md`
 * - `docs/engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md`
 * - `docs/adr/019-dual-universes-lab-vs-trading.md`
 * - `docs/adr/020-operating-mandate-tenure.md`
 * - `docs/adr/021-dia-d-reconciliation.md`
 * - `docs/engineering/dual-universes-lab-trading-design-2026-08-02.md`
 * - `docs/engineering/session-handoff-2026-08-01.md` ← handoff código racha
 * - `docs/engineering/fa-status-and-test-plan-2026-07-31.md`
 * - `docs/engineering/backtesting-dia-d-premises-2026-07-31.md`
 * - `docs/engineering/operativa-test-plan-2026-07-31.md`
 * - `docs/engineering/fundamental-intelligence-engine-2026-07-30.md`
 * - `docs/engineering/list-auto-ops-2026-07-29.md` § CORE-R
 *
 * Verificar: `pnpm test:fa` · `pnpm test:operativa` · `pnpm test:coach`
 *
 * @see docs/adr/024-estudio-supervision-universe.md
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 * @see docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 * @see docs/adr/020-operating-mandate-tenure.md
 * @see docs/engineering/session-handoff-2026-08-04-operativa.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */
export const HELP_CONTENT_AS_OF = '2026-08-06' as const;
