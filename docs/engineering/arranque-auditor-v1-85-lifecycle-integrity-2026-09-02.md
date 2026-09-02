# Arranque auditor — V1.85 Lifecycle Integrity & Financial Event Model (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor) tras tip/CI GREEN de V1.85:

---

Eres auditor externo de Bolsa V1 **producto V1.85**. Partida certificada **`v1.84-beta` → `504aa19d`** (CI GREEN · PASS auditor **9,5/10**). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance V1.85 (mock E2E — log de dominio validado):**

```text
POST event → VALIDATE FSM + time + identity → APPEND (o idempotent)
          → REDUCE → SNAPSHOT + accounting(fills) → GET
```

- FSM fail-closed (goldens V1.84: T1_TRIGGERED opcional · T2 cierra sin EXIT_REQUIRED)
- Monotonicidad `at` · `eventId` · `fillId` único · `positionId`
- Realized / unrealized / total PnL + cash equity (path event-driven)
- Vitest tabla negativa + GP-V185 · filtro `+gp-v185`
- Compat: `setStage` limpia log (GP-V179..V183)

**Regla absoluta:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto. **No** fills ledger · **no** FastAPI/PG (V1.86).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md`](./respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md)
3. [`spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md`](./spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md)
4. [`traspaso-relevo-v1-85-lifecycle-integrity-2026-09-02.md`](./traspaso-relevo-v1-85-lifecycle-integrity-2026-09-02.md)
5. Código: [`lifecycle-events.ts`](../../apps/web/e2e/helpers/lifecycle-events.ts) · [`lifecycle-fsm.test.ts`](../../apps/web/e2e/helpers/lifecycle-fsm.test.ts) · [`gp-v185-lifecycle-integrity-mock.spec.ts`](../../apps/web/e2e/gp-v185-lifecycle-integrity-mock.spec.ts) · [`e2e-mock-runtime.ts`](../../apps/web/e2e/helpers/e2e-mock-runtime.ts) · [`e2e-mock-routes.ts`](../../apps/web/e2e/helpers/e2e-mock-routes.ts)

**Preguntas de foco:**

1. ¿Transiciones ilegales rechazan con `illegal_transition` y **no** mutan el log?
2. ¿Timestamps regresivos / CLOSED no-estricto → `time_regression`?
3. ¿Mismo `eventId` → 200 idempotent · `fillId` duplicado → `duplicate_fill_id` · `positionId` extranjero → `position_mismatch`?
4. ¿CLOSED trail/T2: `realizedPnl` + `cash` reconciliados · `totalEquity` portfolio===summary===desk?
5. ¿GP-V184 journeys siguen verdes con equity accounting (no cash-only)?
6. ¿`setStage` limpia log · Vitest en `frontend-ci` sin Playwright browser · filtro `+gp-v185`?
7. ¿Freeze intacto · sigue siendo mock en memoria (no durable PG)?

**Deuda aparcada:** FastAPI+PG event store (V1.86) · wire projection completa · LIVE · bump · integrated obligatorio.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · `PAPER_D_EXECUTE` default on.

**Respuesta auditor:** (pendiente hasta tip CI GREEN V1.85).

---
