# RELEVO — V1.44 Position Automation Contract (2026-08-31)

> **Padre:** [`spec-v144-position-automation-2026-08-31.md`](./spec-v144-position-automation-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md) · [`plan-v144-position-automation-foundation-2026-08-31.md`](./plan-v144-position-automation-foundation-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO (código de contrato)** — `PositionEvent` → `decidePositionPolicy` → ExitPermission JIT + GP-AUTO-01 / casos malos. **No** AUTO execute de posiciones. **Tag tip:** [`v1.44-beta` → `db346a11`](./traspaso-relevo-tag-v1-44-beta-2026-08-31.md) (CI pending; was `57cf41a3` ruff unblock).  
> **Arranque auditor:** [`arranque-auditor-v1-44-beta-2026-08-31.md`](./arranque-auditor-v1-44-beta-2026-08-31.md).

---

## 0. Qué cierra

| Pieza                                                                  | Estado       |
| ---------------------------------------------------------------------- | ------------ |
| Spec + ADR-043 + stamp PASS V1.43 ≠ AUTO posición                      | DOCS         |
| `PositionEvent` (vista `ExitReasonV1`)                                 | CÓDIGO TS+Py |
| `PositionPolicyDecision` + `decidePositionPolicy`                      | CÓDIGO TS+Py |
| ExitPermission JIT: `data_stale` / `market_closed` / `portfolio_drift` | CÓDIGO TS+Py |
| `revisionOriginFromExitReason` en enqueue protect + drawer             | CÓDIGO       |
| GP-AUTO-01 walk + GP-BAD (crash, partial, T1+T2, closed, stale, recon) | CÓDIGO       |

**Regla:** SEMI = Confirm = firma. AUTO futuro = Policy + Permission JIT **antes** de execute. Trail calculado ≠ `currentStop`. `PositionRevision` ≠ Journal ≠ ExecutionRecord.

```text
SEMI:  Event → ExitPlan → Proposal → Human Confirm → PositionRevision
AUTO:  Event → ExitPlan → PositionPolicyDecision → ExitPermission JIT
         → [V1.45] Execution → Fill → PositionRevision
```

## 1. Pre-flight

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/position-revision.test.ts src/exit-permission.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_policy_decision.py packages/py/analytics/tests/test_exit_permission.py packages/py/analytics/tests/test_position_revision.py -q
```

Resultado local (2026-08-31): shared build OK · 47 shared + 20 web · tsc OK · pytest **40 passed**.

## 2. Freeze (intactos)

Confirm = firma · Spine · Router money path · `check_opening` · `PAPER_D_EXECUTE` off · AUTO execute off · sin auto-promote · sin broker trail/OCO · sin Lab P2 · sin Alembic · sin bump `package.json` · nav L1 · Mercado = terminal.

## 3. OUT (sigue parked)

- AUTO execution de posiciones / auto-promote / `PAPER_D_EXECUTE` default on
- GP-AUTO-01 E2E PAPER (DoD **V1.45**)
- Lab P2 (`backtest_risk_policy_from_trading_policy` Moderado+5%)
- Broker trailing / OCO / thaw LIVE / package bump / segundo Mercado
- Tabla nueva de `PositionRevision`

## 4. Next

1. Esperar Release-tag CI **GREEN** → certify en [`traspaso-relevo-tag-v1-44-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-44-beta-2026-08-31.md).
2. **V1.45** PAPER AUTO position — solo tras tip certificado. NO LIVE.
