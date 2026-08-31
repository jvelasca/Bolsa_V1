# Plan — V1.45 PAPER AUTO position execute

> **Padre:** [`spec-v145-paper-auto-position-2026-08-31.md`](./spec-v145-paper-auto-position-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (orquestador + Router reduce + GP-AUTO-01 E2E + HTTP estrecho).

## Objetivo

Cablear Policy → ExitPermission JIT → protect | Router reduce/exit → PositionRevision en PAPER. `PAPER_D_EXECUTE` default off. NO LIVE.

| ID  | Entrega                                        | Estado |
| --- | ---------------------------------------------- | ------ |
| D0  | Spec + plan + ADR-043 enmienda + stamp product | CÓDIGO |
| P1  | `ExecutePositionPolicyAuto`                    | CÓDIGO |
| P2  | Router `reduce` parcial + tests                | CÓDIGO |
| P3  | Caller mínimo opt-in (tests + HTTP estrecho)   | CÓDIGO |
| P4  | GP-AUTO-01 E2E pytest PAPER                    | CÓDIGO |
| P5  | Relevo + arranque auditor                      | CÓDIGO |

## Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · sin Lab SoT · sin bump package · sin Alembic · sin thaw LIVE.

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/exit-permission.test.ts
pytest packages/py/application/tests/test_execute_position_policy_auto.py packages/py/application/tests/test_execution_router_reduce.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```
