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
 *
 * Auditoría cierre: `docs/engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md`
 *
 * Track FA / FIE (2026-08-01): valoración cerrada en código
 * F0–F2.8 + F3 Composite + F4 Screener + Paper D + cron FA→D ·
 * Beneish→distress · Tarjeta densificada · CAPM rf/ERP visibles.
 *
 * Docs:
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
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 * @see docs/adr/020-operating-mandate-tenure.md
 * @see docs/engineering/session-handoff-2026-08-04-operativa.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */
export const HELP_CONTENT_AS_OF = '2026-08-04' as const;
