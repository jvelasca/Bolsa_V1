# Arranque auditor externo — V1.82 tip (mock E2E certification stack) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **tip `v1.82-beta`**. Producto bajo revisión **`V1.82-beta`** tip funcional **`d0ccf235`**. Docs stamp en `main`: **`f543fab5`**. Partida certificada previa **`v1.81-beta` → `4fcfc9bb`** (Release-tag CI GREEN). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.73→V1.82, mock E2E + tip honesty):**

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

**Regla absoluta en todo el arco:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto (`dryRun=true` · `paperDExecute=false`). **No** fills ledger · **no** `dryRun=false` browser.

**Contexto CI (2026-09-02):** tag `v1.82-beta` → `d0ccf235` · Release-tag CI **GREEN** ([run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262)). Previo: `v1.81-beta` → `4fcfc9bb` ([run 33648642728](https://github.com/jvelasca/Bolsa_V1/actions/runs/33648642728)) · `v1.80-beta` → `7bd6ed81` ([run 33644966298](https://github.com/jvelasca/Bolsa_V1/actions/runs/33644966298)). Pre-flight local = mismo filtro CI → **33 passed** (3 integrated skipped).

**GitHub (auditor):**

- Código tip: [`v1.82-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.82-beta) → commit `d0ccf235`
- Docs stamp: [`f543fab5`](https://github.com/jvelasca/Bolsa_V1/commit/f543fab5) en `main`
- Previo certificado: [`v1.81-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.81-beta) → `4fcfc9bb`

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-82-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-82-beta-2026-09-02.md)
3. [`docs/engineering/traspaso-relevo-v1-82-fixtures-split-2026-09-02.md`](./traspaso-relevo-v1-82-fixtures-split-2026-09-02.md)
4. Specs arco: [V1.82](./spec-v182-fixtures-split-2026-09-02.md) · [V1.81](./spec-v181-t2-pov-stages-2026-09-02.md) · [V1.80](./spec-v180-ci-green-tip-honesty-2026-09-02.md) · [V1.79](./spec-v179-stateful-position-lifecycle-2026-09-02.md) (y V1.73–V1.78 según foco)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) job `playwright-mock`
6. Código: [`apps/web/e2e/fixtures.ts`](../../apps/web/e2e/fixtures.ts) (barrel) · [`helpers/e2e-mock-*`](../../apps/web/e2e/helpers/) · specs `gp-v173`…`gp-v181` · `gp-e2e`

**Preguntas de foco:**

1. ¿El tip `v1.82-beta` / `d0ccf235` certifica **solo** higiene de fixtures **sin** cambiar semántica mock ni asserts?
2. ¿`fixtures.ts` es barrel estable; implementations en `e2e-mock-runtime|routes|installers`; specs siguen `from "./fixtures"`?
3. ¿Filtro `playwright-mock` = `gp-e2e|gp-v173|…|gp-v179|gp-v181` **sin** `|gp-v182` obligatorio · pre-flight 33 passed?
4. ¿`frontend-ci` **sin** Playwright · integrated E2E **opt-in** (skipped en run stamp)?
5. ¿V1.79 lifecycle AAPL conserva IDs · 0 COMPRAR en cada transición hasta CLOSED?
6. ¿V1.81 T2_READY/T2_EXECUTED → MONITOR/Mantener · 0 COMPRAR · **sin** rediseño CTA «GESTIONAR T2»?
7. ¿V1.75/V1.76 stale → `ENTRY_STALE_DATA` → BLOCKED fail-closed · recovery no inventa COMPRAR?
8. ¿DryRun honesto en todo el arco (`dryRun=true` · `paperDExecute=false`) · **no** fills ledger?
9. ¿Freeze intacto: Confirm SEMI · package **`1.35.0-beta`** · **no LIVE** · **no** scheduler · **no** bump · **no** Playwright en cada PR?

**Deuda aparcada:** LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger · integrated E2E obligatorio · desk CTA redesign T2 · thaw estricto.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on · segundo motor ranking.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
