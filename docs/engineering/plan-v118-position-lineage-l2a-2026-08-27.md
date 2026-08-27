# Plan V1.18 L2a — Origin Package snapshot at fill

> **AsOf:** 2026-08-27 · **Baseline:** L1 `a4311d0`.
> **Padre:** [ADR-038](../adr/038-position-operational-memory.md) · [plan L1](./plan-v118-position-lineage-l1-2026-08-27.md).
> **Estado:** implementación L2a.

## Entrega

| Pieza                                             | Qué                                   |
| ------------------------------------------------- | ------------------------------------- |
| `get_decision_session_by_decision_id`             | Lookup write-only al fill             |
| `originDecisionPackage` en `position_state` JSONB | Write-once; sin Alembic               |
| Preserve en protect/exit                          | No borrar snapshot                    |
| `operational.originThesis`                        | Slice HTTP para aggregate             |
| Aggregate                                         | Prefiere snapshot si studies divergen |

## Freeze

Confirm · DEX · `PAPER_D_EXECUTE` off · AUTO · B-read Mesa · backfill legacy · Stress · Opportunity.

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run position-lineage investment-position-aggregate mesa-hoy-model
python -m pytest packages/py/application/tests/test_origin_decision_package.py packages/py/application/tests/test_persist_position_from_fill.py packages/py/application/tests/test_persist_position_from_protect.py -q
```
