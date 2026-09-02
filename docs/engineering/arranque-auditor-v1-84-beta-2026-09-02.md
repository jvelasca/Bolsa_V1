# Arranque auditor externo — V1.84 tip (Lifecycle Event-Driven Mock) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **tip `v1.84-beta`**. Producto bajo revisión **`V1.84-beta`** tip funcional **`504aa19d`**. Docs stamp en `main`: **`d47168b7`**. Partida certificada previa **`v1.83-beta` → `dc596ee5`** (Release-tag CI GREEN · PASS auditor 9,85/10). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.73→V1.84, mock E2E + event-driven lifecycle):**

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
- **V1.84** Lifecycle Event-Driven Mock (POST emit→log append-only→GET reduce · wire `events` ⊆ log · GP-V184)

**Regla absoluta en todo el arco:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto (`dryRun=true` · `paperDExecute=false`). **No** fills ledger · **no** `dryRun=false` browser.

**Contexto CI (2026-09-02):** tag `v1.84-beta` → `504aa19d` · Release-tag CI **GREEN** ([run 33659480690](https://github.com/jvelasca/Bolsa_V1/actions/runs/33659480690)). Previo: `v1.83-beta` → `dc596ee5` ([run 33657045026](https://github.com/jvelasca/Bolsa_V1/actions/runs/33657045026)). Pre-flight local = mismo filtro CI → **37 passed** (3 integrated skipped).

**GitHub (auditor):**

- Código tip: [`v1.84-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.84-beta) → commit `504aa19d`
- Docs stamp: [`d47168b7`](https://github.com/jvelasca/Bolsa_V1/commit/d47168b7) en `main`
- Previo certificado: [`v1.83-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.83-beta) → `dc596ee5`
- Auditoría V1.83 (input de esta slice): [`respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md`](./respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-84-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-84-beta-2026-09-02.md)
3. [`docs/engineering/respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md`](./respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md)
4. Specs: [V1.84](./spec-v184-lifecycle-event-driven-mock-2026-09-02.md) · [V1.83](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md) · [V1.81](./spec-v181-t2-pov-stages-2026-09-02.md)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) job `playwright-mock`
6. Código: [`helpers/lifecycle-events.ts`](../../apps/web/e2e/helpers/lifecycle-events.ts) · [`e2e-mock-runtime.ts`](../../apps/web/e2e/helpers/e2e-mock-runtime.ts) · [`e2e-mock-routes.ts`](../../apps/web/e2e/helpers/e2e-mock-routes.ts) · [`gp-v184-lifecycle-event-driven-mock.spec.ts`](../../apps/web/e2e/gp-v184-lifecycle-event-driven-mock.spec.ts)

**Preguntas de foco:**

1. ¿`POST /api/e2e/lifecycle/events` es append-only (no reescribe historia) y deriva `stage`/`lineagePath` del log completo?
2. ¿Con `lifecycleEvents.length > 0`, GET `/portfolio` · `/summary` · paper-desk reducen el **mismo** log (equity única)?
3. ¿Los `events` del DTO CLOSED son el subconjunto wire del log (`T1_EXECUTED` · `T2_*` · `POSITION_CLOSED`) y no un template vacío?
4. ¿CLOSED ⇒ `remainingQuantity=0` · último wire event `POSITION_CLOSED` · 0 COMPRAR?
5. ¿Path T2 (GP-V184-02) conserva `t2` executed en wire tras CLOSED?
6. ¿`setE2eMockPositionStage` limpia el log (compat proyección V1.83 / GP-V179..V183)?
7. ¿Filtro CI incluye `gp-v184` · pre-flight 37 passed · tip honesty (`frontend-ci` sin Playwright · integrated opt-in)?
8. ¿Sigue siendo mock (Node runtime + Playwright route) · **no** FastAPI/PG event store · freeze intacto (no LIVE · package `1.35.0-beta`)?

**Deuda aparcada:** LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger · event store FastAPI/PG · integrated E2E obligatorio · `/portfolio` open-only · desk CTA redesign T2 · thaw estricto.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on · segundo motor ranking.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
