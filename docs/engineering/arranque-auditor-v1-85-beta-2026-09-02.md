# Arranque auditor externo — V1.85 tip (Lifecycle Integrity) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor) **tras** Release-tag CI GREEN:

---

Eres auditor externo de Bolsa V1 **tip `v1.85-beta`**. Producto bajo revisión **`V1.85-beta`** tip funcional **`665242a3`**. Partida certificada previa **`v1.84-beta` → `504aa19d`** (Release-tag CI GREEN · PASS auditor **9,5/10**). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.73→V1.85, mock E2E + log de dominio validado):**

- **V1.73…V1.83** (stack mock previo CERRADO)
- **V1.84** Lifecycle Event-Driven Mock (POST→log append-only→GET reduce · wire `events` ⊆ log · GP-V184)
- **V1.85** Lifecycle Integrity & Financial Event Model:
  - `VALIDATE FSM + time + identity → APPEND (o idempotent) → REDUCE → SNAPSHOT + accounting`
  - HTTP 409 fail-closed · realized/unrealized/totalPnl · Vitest + GP-V185

**Regla absoluta en todo el arco:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto (`dryRun=true` · `paperDExecute=false`). **No** fills ledger · **no** `dryRun=false` browser · **no** FastAPI/PG event store (V1.86).

**Contexto CI (2026-09-02):** tag `v1.85-beta` → `665242a3` · Release-tag CI **GREEN** ([run 33663836923](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663836923)). Previo: `v1.84-beta` → `504aa19d` ([run 33659480690](https://github.com/jvelasca/Bolsa_V1/actions/runs/33659480690)). Pre-flight local = mismo filtro CI → **40 passed** (3 integrated skipped) · Vitest FSM **16 passed**.

**GitHub (auditor):**

- Código tip: [`v1.85-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.85-beta) → commit `665242a3`
- Previo certificado: [`v1.84-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.84-beta) → `504aa19d`
- Auditoría V1.84 (input): [`respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md`](./respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-85-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-85-beta-2026-09-02.md)
3. [`docs/engineering/respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md`](./respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md)
4. Specs: [V1.85](./spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md) · [V1.84](./spec-v184-lifecycle-event-driven-mock-2026-09-02.md)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) job `playwright-mock` (`+gp-v185`)
6. Código: [`lifecycle-events.ts`](../../apps/web/e2e/helpers/lifecycle-events.ts) · [`lifecycle-fsm.test.ts`](../../apps/web/e2e/helpers/lifecycle-fsm.test.ts) · [`e2e-mock-runtime.ts`](../../apps/web/e2e/helpers/e2e-mock-runtime.ts) · [`e2e-mock-routes.ts`](../../apps/web/e2e/helpers/e2e-mock-routes.ts) · [`e2e-mock-installers.ts`](../../apps/web/e2e/helpers/e2e-mock-installers.ts) · [`gp-v185-lifecycle-integrity-mock.spec.ts`](../../apps/web/e2e/gp-v185-lifecycle-integrity-mock.spec.ts)

**Preguntas de foco:**

1. ¿Transiciones ilegales → `illegal_transition` · HTTP 409 · log **sin** mutar?
2. ¿Timestamps regresivos / CLOSED no-estricto → `time_regression`?
3. ¿Mismo `eventId` → 200 idempotent · `fillId` duplicado → `duplicate_fill_id` · `positionId` extranjero → `position_mismatch`?
4. ¿CLOSED trail/T2: `realizedPnl` + cash reconciliados · `totalEquity` portfolio===summary===desk?
5. ¿GP-V184 journeys siguen verdes con accounting (equity CLOSED ≠ cash-only)?
6. ¿`setStage` limpia log · Vitest en `frontend-ci` sin Playwright browser · filtro `+gp-v185` · tip honesty?
7. ¿Freeze intacto · sigue siendo mock en memoria (no durable PG / V1.86)?

**Deuda aparcada:** FastAPI+PG event store (V1.86) · wire projection completa · LIVE · bump · integrated obligatorio · `/portfolio` open-only.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
