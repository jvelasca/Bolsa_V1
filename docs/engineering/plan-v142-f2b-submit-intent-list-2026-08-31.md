# Plan — V1.42 F2b SubmitIntent read list

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §D · [ADR-042](../adr/042-operating-excellence.md) · [`plan-v142-f2-execution-state-2026-08-31.md`](./plan-v142-f2-execution-state-2026-08-31.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

GET read-only de `submit_intents` in-flight para que Mercado (y peers) alimenten `submitIntent` → `buildExecutionState` y muestren GP-10 UNKNOWN **sin** Confirm / re-POST.

## Entregables

| ID  | Entrega                                                                  | Estado |
| --- | ------------------------------------------------------------------------ | ------ |
| F2b | `list_in_flight(account_id)` en SubmitIntentStore (InMemory + PG)        | CÓDIGO |
| F2b | `GET /api/accounts/{account_id}/submit-intents` + soft-join instrumentId | CÓDIGO |
| F2b | Shared `SubmitIntentListItemV1` · web `getSubmitIntents` + hook          | CÓDIGO |
| F2b | Thin wire: summaries · cockpit · Mesa · Operaciones · Journal            | CÓDIGO |
| F2b | UNKNOWN → «Ver operaciones» / nunca reenviar (cockpit)                   | CÓDIGO |

## Freeze intacto

Confirm write/recover · `POST /ai/intents/confirm` · Router · `PAPER_D_EXECUTE` · AUTO execute · `buildExecutionState` precedencia F2 · F3/F4 · sin schema change · sin thaw.

## Criterios de cierre

```bash
uv run --project packages/py/application pytest packages/py/application/tests/test_submit_intent_store_pg.py -q
uv run --project apps/api-python pytest apps/api-python/tests/test_submit_intent_api.py -q
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/entry-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/decision-journal/decision-ficha-panel.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
