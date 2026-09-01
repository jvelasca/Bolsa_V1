# Plan — V1.52 Position Lifecycle

> **Padre:** [`spec-v152-position-lifecycle-2026-09-01.md`](./spec-v152-position-lifecycle-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CÓDIGO**.

| ID  | Entrega                                                                 | Estado |
| --- | ----------------------------------------------------------------------- | ------ |
| D0  | Stamp auditoría V1.51 PASS + spec/plan/relevo V1.52                     | DONE   |
| P1  | Lab `evaluate-exits` execute → `lab_exit_execute_retired` (env on ≠ OK) | DONE   |
| P2  | `TargetLeg` pending/triggered/executed/failed (TS+Py JSONB)             | DONE   |
| P3  | `PositionRevision.decisionId` + `policyId` opcionales                   | DONE   |
| P4  | Handle durable + `RecoverOrphanOpeningFills` en PaperDeskCycle          | DONE   |
| P5  | GP-EXIT-01/02/03 · GP-TRAIL-01/02 · GP-CRASH-01                         | DONE   |

## Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Alembic tabla nueva · no UI Mesa · package `1.35.0-beta`.

## Criterios

```bash
pnpm --filter @bolsa/shared exec vitest run src/position-state.test.ts src/position-revision.test.ts src/cognitive/position-automation-golden-path.test.ts
pytest packages/py/application/tests/test_paper_desk_entry.py packages/py/application/tests/test_execution_router.py packages/py/application/tests/test_paper_desk_cycle.py packages/py/application/tests/test_paper_desk_golden_session.py packages/py/application/tests/test_paper_desk_caos.py packages/py/application/tests/test_position_exits_paper_auto_gate.py packages/py/application/tests/test_paper_desk_lifecycle.py packages/py/analytics/tests/test_position_state.py packages/py/analytics/tests/test_position_revision.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

## No hacer

UI Mesa · Golden Session 09:00→Journal · ExecutionIntent de apertura · segundo motor · LIVE · encender `PAPER_D_EXECUTE` · bump package.
