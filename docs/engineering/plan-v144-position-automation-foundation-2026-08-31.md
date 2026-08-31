# Plan — V1.44 Position Automation Foundation

> **Padre:** [`spec-v144-position-automation-2026-08-31.md`](./spec-v144-position-automation-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (contrato + Golden Paths; sin AUTO execute).

## Objetivo

Materializar el contrato V1.44: `PositionEvent` + `decidePositionPolicy` + ExitPermission JIT + Golden Paths. Reutilizar ExitPlan / ExitPolicy / OperatingPolicy / PositionRevision. Sin ExecutionRouter de posición. Sin UI nueva. Sin Lab P2.

```text
SEMI:  Event → ExitPlan → Proposal → Human Confirm → PositionRevision
AUTO:  Event → ExitPlan → PositionPolicyDecision → ExitPermission JIT
         → [V1.45] Execution → Fill → PositionRevision
```

## Entregables

| ID  | Entrega                                                   | Estado |
| --- | --------------------------------------------------------- | ------ |
| D   | Spec + ADR-043 + stamp PASS nuance / Lab P2 parked        | CÓDIGO |
| P1  | `PositionEvent` + `revisionOriginFromExitReason`          | CÓDIGO |
| P2  | `PositionPolicyDecision` + `decidePositionPolicy` (TS+Py) | CÓDIGO |
| P3  | ExitPermission JIT: stale / marketClosed / drift          | CÓDIGO |
| P4  | GP-AUTO-01 walk + casos malos (sin Router)                | CÓDIGO |
| P5  | Enqueue protect usa helper TRAIL → `origin=trail`         | CÓDIGO |

## Freeze intacto

Confirm = firma · Router money path · `PAPER_D_EXECUTE` off · AUTO execute off · sin LIVE thaw · sin OCO · sin Lab P2 · sin trail auto-authority · sin bump `package.json` · Ranking ≠ BUY.

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/position-revision.test.ts src/exit-permission.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_policy_decision.py packages/py/analytics/tests/test_exit_permission.py -q
```
