# Arranque auditor — V1.83 Lifecycle Snapshot Truth (2026-09-02)

> **Padre:** [`spec-v183-lifecycle-snapshot-truth-2026-09-02.md`](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md) · partida **V1.82** [`d0ccf235`](https://github.com/jvelasca/Bolsa_V1/commit/d0ccf235)  
> **Estado slice:** **CERRADA (código + E2E mock locales)** · **stamp CI GREEN remoto PENDIENTE** tag `v1.83-beta`.

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.83-beta** (Lifecycle Snapshot Truth, mock E2E). Partida certificada **`v1.82-beta` → `d0ccf235`** (Release-tag CI GREEN [run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262)). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** certificar que el mock E2E ya no destruye historia en EXIT_REQUIRED/CLOSED, que las finanzas del DTO cumplen identidades matemáticas, y que portfolio / summary / paper-desk derivan del mismo `LifecycleSnapshot`. Sigue siendo **Stateful Projection** (stage → DTO), no motor de eventos. Integrated E2E **opt-in**.

**Regla absoluta:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto (`dryRun=true` · `paperDExecute=false`). **No** fills ledger · **no** `dryRun=false` browser.

Pre-flight local (2026-09-02): filtro CI `gp-e2e|gp-v173|…|gp-v179|gp-v181|gp-v183` → **35 passed** (3 integrated skipped) · `tsc --noEmit` EXIT 0.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/respuesta-auditor-v182-operational-financial-truth-2026-09-02.md`](./respuesta-auditor-v182-operational-financial-truth-2026-09-02.md)
3. [`docs/engineering/spec-v183-lifecycle-snapshot-truth-2026-09-02.md`](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md)
4. Código: [`apps/web/e2e/helpers/lifecycle-snapshot.ts`](../../apps/web/e2e/helpers/lifecycle-snapshot.ts) · [`e2e-mock-routes.ts`](../../apps/web/e2e/helpers/e2e-mock-routes.ts) · [`gp-v183-lifecycle-snapshot-truth-mock.spec.ts`](../../apps/web/e2e/gp-v183-lifecycle-snapshot-truth-mock.spec.ts) · GP-V179/V181 CLOSED
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) job `playwright-mock` (filtro `+gp-v183`)

**Preguntas de foco:**

1. ¿`EXIT_REQUIRED` y `CLOSED` conservan T1 (y T2 o trail según path) en lugar de reconstruir un DTO vacío?
2. ¿CLOSED añade `POSITION_CLOSED` al final sin borrar events previos · `remainingQuantity=0`?
3. ¿Invariantes `marketValue` / PnL / R / remaining se evalúan sobre el DTO, no solo HUD?
4. ¿Mismo `totalEquity` en `/portfolio`, `/summary` y paper-desk en modo lifecycle?
5. ¿GP-V181 CLOSED en path T2 conserva `t2` executed?
6. ¿`/portfolio.positions` incluye el registro CLOSED (qty 0) y está documentado (no open-only)?
7. ¿Filtro CI incluye `gp-v183` · GP-V178 aislado no rompe · 0 COMPRAR · freeze intacto?
8. ¿Sigue siendo proyección mock (no POST/engine) · integrated E2E opt-in?

**Deuda aparcada:** LIVE · scheduler · bump · `dryRun=false` browser · fills ledger · event-driven E2E · integrated obligatorio · `/portfolio` open-only · desk CTA T2 · thaw estricto.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on.

---
