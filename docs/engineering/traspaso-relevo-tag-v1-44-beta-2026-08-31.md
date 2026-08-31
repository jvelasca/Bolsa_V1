# RELEVO — tag v1.44-beta → auditoría / CI (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-44-position-automation-2026-08-31.md`](./traspaso-relevo-v1-44-position-automation-2026-08-31.md) · [`traspaso-relevo-tag-v1-43-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-43-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERTIFICADO** — tip `v1.44-beta` → `db346a11` · Release-tag CI **GREEN** · auditoría de contrato **PASS**.  
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

| Pieza           | Valor                                                                                                            |
| --------------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip         | `v1.44-beta` → `db346a11` (was `57cf41a3`; CI unblock ruff I001)                                                 |
| Código contrato | `57cf41a3` feat + `db346a11` ruff import sort                                                                    |
| Previo tip      | `v1.43-beta` → `5dfac890` (CI GREEN)                                                                             |
| CI tag          | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440633829) · `headSha=db346a11` |

Jobs del mismo push `v1.44-beta` (retag 2026-08-31T21:18Z), todos **success**:

| Workflow          | Run                                                                          |
| ----------------- | ---------------------------------------------------------------------------- |
| Release tag CI    | [33440633829](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440633829) |
| Frontend CI       | [33440634150](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440634150) |
| Python CI         | [33440633680](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440633680) |
| Optimize lab      | [33440633874](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440633874) |
| Fase 2 scientific | [33440634103](https://github.com/jvelasca/Bolsa_V1/actions/runs/33440634103) |

## 2. Pre-flight tip (local)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/position-revision.test.ts src/exit-permission.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_policy_decision.py packages/py/analytics/tests/test_exit_permission.py packages/py/analytics/tests/test_position_revision.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
```

Resultado local (2026-08-31): shared build OK · 47 shared + 20 web · tsc OK · pytest **40 passed** · ruff OK. Auditoría externa contrato: **PASS** (9/9).

## 3. Auditoría externa

**Veredicto (2026-08-31, tip `db346a11`):** **PASS** — Position Automation Contract (autorización + JIT). Nueve preguntas de foco OK.

**Matiz de alcance:** PASS V1.44 = contrato Policy + Permission JIT + Golden Paths de objetos. **No** AUTO execute de posiciones. **No** LIVE. `PAPER_D_EXECUTE` off. Next = V1.45 PAPER AUTO position (execute). Lab P2 / OCO / broker trail siguen parked.

| #   | Foco                                                 | Resultado |
| --- | ---------------------------------------------------- | --------- |
| 1   | `decidePositionPolicy` autorización · no Router      | PASS      |
| 2   | Perfiles vía `OperatingPolicy.exit` (T1/T2)          | PASS      |
| 3   | JIT AUTO stale/closed/drift · protective ALLOW · H2  | PASS      |
| 4   | `requireJitContext` fail-closed · omitido = gate off | PASS      |
| 5   | GP-AUTO-01 walk sin submit/Router                    | PASS      |
| 6   | GP-BAD crash/partial/T1+T2/closed/stale/recon        | PASS      |
| 7   | `revisionOriginFromExitReason` solo `TRAIL`→trail    | PASS      |
| 8   | Freeze money path / Confirm / package                | PASS      |
| 9   | Docs: PASS V1.43 ≠ AUTO posición ≠ LIVE              | PASS      |

**CI tag:** GREEN (tabla §1). No thaw. No Lab P2. No Alembic nuevo (sigue `014`). Package `1.35.0-beta` intacto.

HEAD post-tip `d6736126` = docs re-pin tip SHA; certify docs-only posterior **no** forma parte del tip certificado.

## 4. Residuals parked

- AUTO execution de posiciones / `PAPER_D_EXECUTE` default on / auto-promote
- GP-AUTO-01 E2E PAPER (**V1.45**)
- Lab P2 · broker trailing / OCO · thaw LIVE · package bump · Alembic · OpportunityScore

## 5. Next

**V1.45** PAPER AUTO position — Policy → Permission JIT → ExecutionRouter → fill. GP-AUTO-01 E2E PAPER. **NO LIVE**.
