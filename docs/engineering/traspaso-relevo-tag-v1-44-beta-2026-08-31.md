# RELEVO — tag v1.44-beta → auditoría / CI (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-44-position-automation-2026-08-31.md`](./traspaso-relevo-v1-44-position-automation-2026-08-31.md) · [`traspaso-relevo-tag-v1-43-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-43-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **TIP PUBLICADO** — tag `v1.44-beta` → `57cf41a3` · Release-tag CI **pending** tras push. Auditoría de contrato local **PASS**.  
> **Arranque auditor:** [`arranque-auditor-v1-44-beta-2026-08-31.md`](./arranque-auditor-v1-44-beta-2026-08-31.md).  
> **Fuera:** AUTO execute posición · auto-promote · broker trailing / OCO · Lab P2 · thaw LIVE · OpportunityScore · segundo Mercado · package bump · GP-AUTO-01 E2E PAPER (V1.45).

---

## 0. Confirmación

Sobre tip `v1.43-beta` → `5dfac890` (TRAIL SEMI PASS):

| Pieza                                             | Entrega                                                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| Spec + ADR-043                                    | Contrato Position Automation; PASS V1.43 ≠ AUTO posición                 |
| `PositionEvent`                                   | Vista tipada de `ExitReasonV1` (TS+Py)                                   |
| `PositionPolicyDecision` + `decidePositionPolicy` | Autorización HOLD/PROTECT/TRAIL/REDUCE/EXIT · no Router                  |
| ExitPermission JIT                                | `data_stale` / `market_closed` / `portfolio_drift` · `requireJitContext` |
| `revisionOriginFromExitReason`                    | Solo `TRAIL` → `origin=trail` (enqueue + drawer)                         |
| GP-AUTO-01 + GP-BAD                               | Walk de objetos + crash/partial/T1+T2/closed/stale/recon                 |

**Regla:** SEMI = Confirm = firma. AUTO futuro = Policy + Permission JIT **antes** de execute. Trail calculado ≠ `currentStop`.

Freeze: Confirm = firma · Spine · Router money path · `PAPER_D_EXECUTE` off · AUTO execute off · sin auto-promote · sin Lab P2 · sin Alembic · sin bump `package.json` · Mercado = terminal.

## 1. Release

| Pieza           | Valor                                                                                |
| --------------- | ------------------------------------------------------------------------------------ |
| Tag tip         | `v1.44-beta` → `57cf41a3`                                                            |
| Código contrato | `57cf41a3` `feat(v1.44): Position Automation contract — policy + ExitPermission JIT` |
| Previo tip      | `v1.43-beta` → `5dfac890` (CI GREEN)                                                 |
| CI tag          | **pending** — Release tag CI tras push del tag                                       |

## 2. Pre-flight tip (local)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/position-revision.test.ts src/exit-permission.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_policy_decision.py packages/py/analytics/tests/test_exit_permission.py packages/py/analytics/tests/test_position_revision.py -q
```

Resultado local (2026-08-31): shared build OK · 47 shared + 20 web · tsc OK · pytest **40 passed**. Auditoría externa contrato: **PASS** (9/9).

## 3. Residuals parked

- AUTO execution de posiciones / `PAPER_D_EXECUTE` default on / auto-promote
- GP-AUTO-01 E2E PAPER (**V1.45**)
- Lab P2 · broker trailing / OCO · thaw LIVE · package bump · Alembic · OpportunityScore

## 4. Next

1. Esperar Release-tag CI **GREEN** → stamp certify en CURRENT_SYSTEM / este relevo.
2. **V1.45** PAPER AUTO position — solo tras tip certificado. **NO LIVE**.
