# Plan — V1.51 Entry → Paper Fill → Position

> **Padre:** [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CI GREEN**.

| ID  | Entrega                                                          | Estado |
| --- | ---------------------------------------------------------------- | ------ |
| D0  | Stamp auditoría V1.50 PASS + spec/plan/relevo V1.51              | DONE   |
| P0  | `PersistPositionFromFill` en `ExecutionRouter` post opening fill | DONE   |
| P0  | DI `get_execution_router_use_case`                               | DONE   |
| P0  | `decisionId` = `signal.id` + templateId/autoSource en snapshot   | DONE   |
| P0  | Hit `templateId` desde propose payload                           | DONE   |
| P0t | GP-DESK-07 + idempotencia + Gate DENY sin Position               | DONE   |

## Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Alembic · no UI Mesa · package `1.35.0-beta`.

## Criterios

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/paper-daily-report.test.ts src/daily-ops-report.test.ts src/cognitive/operational-context.test.ts
pytest packages/py/application/tests/test_execution_router.py packages/py/application/tests/test_paper_desk_entry.py packages/py/application/tests/test_estudio_auto_hits.py packages/py/application/tests/test_post_fill_position_sync.py packages/py/application/tests/test_paper_desk_cycle.py packages/py/application/tests/test_paper_desk_golden_session.py packages/py/application/tests/test_paper_desk_caos.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

## No hacer

Segundo factory de Position · Alembic · LIVE · UI Mesa · Golden Session birth+exit · encender `PAPER_D_EXECUTE`.
