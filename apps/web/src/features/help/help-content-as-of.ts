/**
 * Fecha única de sync Ayuda ↔ trackers ↔ encabezados de docs.
 * Actualizar al cambiar estado de producto (no tipografía).
 *
 * Incluye: espacios, BD, perfiles, listas/índices, embudo Play,
 * Finalistas→A/C, Monitor MVP, CORE-P, CORE-R v1.8 (Hecho todos),
 * **Backtesting DÍA D** (v0.11 · archivo también en Ayuda),
 * Lista AUTO frescura **v1.3**, CORE-B **v0.2**, CAPM Tarjeta v0,
 * Composite **v1.1**, fix Trading fullBleed.
 *
 * Track FA / FIE (2026-08-01): valoración cerrada en código
 * F0–F2.8 + F3 Composite + F4 Screener + Paper D + cron FA→D ·
 * Beneish→distress · Tarjeta densificada · CAPM rf/ERP visibles.
 * Fase actual: **smoke UI humano** (código de racha cerrado).
 *
 * Docs:
 * - `docs/engineering/session-handoff-2026-08-01.md` ← handoff actual
 * - `docs/engineering/fa-status-and-test-plan-2026-07-31.md`
 * - `docs/engineering/backtesting-dia-d-premises-2026-07-31.md`
 * - `docs/engineering/operativa-test-plan-2026-07-31.md`
 * - `docs/engineering/fundamental-intelligence-engine-2026-07-30.md`
 * - `docs/engineering/list-auto-ops-2026-07-29.md` § CORE-R
 *
 * Verificar: `pnpm test:fa` · `pnpm test:operativa` · `pnpm test:coach`
 *
 * @see docs/engineering/session-handoff-2026-08-01.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */
export const HELP_CONTENT_AS_OF = '2026-08-01' as const;
