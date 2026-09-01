# Plan — V1.50 Entry Decision Integrity

> **Padre:** [`spec-v150-entry-decision-integrity-2026-09-01.md`](./spec-v150-entry-decision-integrity-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CÓDIGO**.

| ID  | Entrega                                                                            | Estado |
| --- | ---------------------------------------------------------------------------------- | ------ |
| D0  | spec-v150 + respuesta auditor + relevo + CURRENT_SYSTEM                            | DONE   |
| P0  | `CandidateSnapshot` en `PaperDeskEntryTickResult`; map `hits[]` (no tirarlos)      | DONE   |
| P0  | `decisionId` por propuesta                                                         | DONE   |
| P0  | `reasonCode` + `humanMessage` (notes humanas se conservan)                         | DONE   |
| P0  | `template_id` → `resolve_operating_policy` en EntryTick (quitar `_ = template_id`) | DONE   |
| P0  | Relojes `analysisAsOf` / `marketAsOf` / `executionAsOf` (nullable honestos)        | DONE   |
| P0  | Errores: dominio blocked · infra unavailable                                       | DONE   |
| P0t | GP-DESK-04 ranking top-N + TradePlan intacto                                       | DONE   |
| P0t | GP-DESK-05 Gate DENY sin ExecutionIntent                                           | DONE   |
| P0t | GP-DESK-06 stop inválido ≠ BUY                                                     | DONE   |

## Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no scheduler · no Alembic tabla nueva · no Fill→Position · package `1.35.0-beta`.

## Criterios

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/paper-daily-report.test.ts src/daily-ops-report.test.ts src/cognitive/operational-context.test.ts
pytest packages/py/application/tests/test_paper_desk_cycle.py packages/py/application/tests/test_paper_desk_entry.py packages/py/application/tests/test_estudio_auto_hits.py packages/py/application/tests/test_paper_daily_report.py packages/py/application/tests/test_execute_position_policy_auto.py packages/py/application/tests/test_operational_context.py packages/py/application/tests/test_paper_desk_idempotency.py packages/py/application/tests/test_auto_execute_idempotency.py packages/py/application/tests/test_position_event_log.py packages/py/application/tests/test_paper_desk_caos.py packages/py/application/tests/test_paper_desk_golden_session.py packages/py/market/tests/test_market_calendar.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

Local 2026-09-01: vitest **7** · pytest **83** (bloque) · ruff OK · web tsc OK. **Sin tag.**

## No hacer

Segundo ranking · segundo OpeningGate · persistir snapshot en Position · UI Mesa · LIVE · encender `PAPER_D_EXECUTE`.
