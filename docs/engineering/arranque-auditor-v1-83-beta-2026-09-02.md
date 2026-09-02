# Arranque auditor externo — V1.83 tip (Lifecycle Snapshot Truth) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **tip `v1.83-beta`**. Producto bajo revisión **`V1.83-beta`** tip funcional **`dc596ee5`**. Docs stamp en `main`: **`67ab2e75`**. Partida certificada previa **`v1.82-beta` → `d0ccf235`** (Release-tag CI GREEN). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.73→V1.83, mock E2E + operational/financial truth):**

- **V1.73** Multi-instrument integrity (A→B→C→A · Entry↔Position · refresh)
- **V1.74** Paper Autonomous Day (Hoy autoDesk · T1→Mercado · Journal · dryRun)
- **V1.75** Chaos & stale → no-execute (`ENTRY_STALE_DATA` · UNKNOWN · dryRun stale)
- **V1.76** Certification Hardening (causalidad stale→BLOCKED)
- **V1.77** Session Reliability (A→B→C→A→refresh→stale→recovery→UNKNOWN→recon→clean)
- **V1.78** Session Golden MERCADO→EXIT (candidato→ENTRY→…→EXIT_REQUIRED)
- **V1.79** Stateful Position Lifecycle AAPL (candidato→CLOSED · IDs congelados · 0 COMPRAR)
- **V1.80** CI GREEN Tip Honesty (`release-tag-ci` `playwright-mock` = curado único; `frontend-ci` **sin** Playwright)
- **V1.81** T2 POV Stages (`t2_ready`/`t2_executed` · MONITOR/Mantener · 0 COMPRAR)
- **V1.82** Fixtures Split (higiene `fixtures.ts` → `helpers/e2e-mock-*` + barrel · **misma** semántica)
- **V1.83** Lifecycle Snapshot Truth (`LifecycleSnapshot` SoT · lineage EXIT/CLOSED · invariantes qty/PnL/R · equity única · GP-V183)

**Regla absoluta en todo el arco:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto (`dryRun=true` · `paperDExecute=false`). **No** fills ledger · **no** `dryRun=false` browser.

**Contexto CI (2026-09-02):** tag `v1.83-beta` → `dc596ee5` · Release-tag CI **GREEN** ([run 33657045026](https://github.com/jvelasca/Bolsa_V1/actions/runs/33657045026)). Previo: `v1.82-beta` → `d0ccf235` ([run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262)). Pre-flight local = mismo filtro CI → **35 passed** (3 integrated skipped).

**GitHub (auditor):**

- Código tip: [`v1.83-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.83-beta) → commit `dc596ee5`
- Docs stamp: [`67ab2e75`](https://github.com/jvelasca/Bolsa_V1/commit/67ab2e75) en `main`
- Previo certificado: [`v1.82-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.82-beta) → `d0ccf235`
- Auditoría V1.82 (input de esta slice): [`respuesta-auditor-v182-operational-financial-truth-2026-09-02.md`](./respuesta-auditor-v182-operational-financial-truth-2026-09-02.md)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-83-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-83-beta-2026-09-02.md)
3. [`docs/engineering/respuesta-auditor-v182-operational-financial-truth-2026-09-02.md`](./respuesta-auditor-v182-operational-financial-truth-2026-09-02.md)
4. Specs: [V1.83](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md) · [V1.82](./spec-v182-fixtures-split-2026-09-02.md) · [V1.81](./spec-v181-t2-pov-stages-2026-09-02.md) · [V1.79](./spec-v179-stateful-position-lifecycle-2026-09-02.md)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) job `playwright-mock`
6. Código: [`helpers/lifecycle-snapshot.ts`](../../apps/web/e2e/helpers/lifecycle-snapshot.ts) · [`e2e-mock-routes.ts`](../../apps/web/e2e/helpers/e2e-mock-routes.ts) · [`gp-v183-lifecycle-snapshot-truth-mock.spec.ts`](../../apps/web/e2e/gp-v183-lifecycle-snapshot-truth-mock.spec.ts) · GP-V179/V181 CLOSED

**Preguntas de foco:**

1. ¿`EXIT_REQUIRED` y `CLOSED` conservan T1 (y T2 o trail según path) en lugar de reconstruir un DTO vacío?
2. ¿CLOSED añade `POSITION_CLOSED` al final sin borrar events previos · `remainingQuantity=0`?
3. ¿Invariantes `marketValue` / PnL / R / remaining se evalúan sobre el DTO?
4. ¿Mismo `totalEquity` en `/portfolio`, `/summary` y paper-desk en modo lifecycle?
5. ¿GP-V181 CLOSED en path T2 conserva `t2` executed?
6. ¿`/portfolio.positions` incluye el registro CLOSED (qty 0) y está documentado?
7. ¿Filtro CI incluye `gp-v183` · pre-flight 35 passed · tip honesty (`frontend-ci` sin Playwright · integrated opt-in)?
8. ¿Sigue siendo proyección mock (no POST/engine) · freeze intacto (no LIVE · package `1.35.0-beta`)?

**Deuda aparcada:** LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger · event-driven E2E · integrated E2E obligatorio · `/portfolio` open-only · desk CTA redesign T2 · thaw estricto.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on · segundo motor ranking.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
