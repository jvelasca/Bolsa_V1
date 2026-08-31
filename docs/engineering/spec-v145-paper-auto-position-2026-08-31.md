# Spec — V1.45 PAPER AUTO position execute

> **AsOf:** 2026-08-31 · **Estado:** **CÓDIGO** (orquestador + Router reduce + GP-AUTO-01 E2E).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v144-position-automation-2026-08-31.md`](./spec-v144-position-automation-2026-08-31.md).  
> **Tip certificado previo:** `v1.44-beta` → `db346a11` (contrato Policy + JIT; sin execute).  
> **Plan:** [`plan-v145-paper-auto-position-2026-08-31.md`](./plan-v145-paper-auto-position-2026-08-31.md).

Cablea el contrato V1.44 a **execute PAPER**. **No** LIVE. **No** flip `PAPER_D_EXECUTE` default.

```text
SEMI:  Event → ExitPlan → Proposal → Human Confirm → PositionRevision
AUTO:  Event → ExitPlan → PositionPolicyDecision → ExitPermission JIT
         → Execution (protect persist | Router reduce/exit) → Fill → PositionRevision
```

## 0. Freeze

Confirm SEMI = firma · Spine · `PAPER_D_EXECUTE` **default off** · arm ≠ execute (F8) · sin LIVE thaw · sin OCO · sin Lab P2 · sin auto-promote trail · sin Alembic · sin bump `package.json` · Ranking ≠ BUY · Mercado = terminal · Lab `evaluate-exits` **no** es SoT canónico.

## 1. Orquestador canónico

`ExecutePositionPolicyAuto`:

1. `decide_position_policy`
2. `check_exit_permission(auto_execute=True, require_jit_context=True, paper_d_execute=…, JIT signals)`
3. HOLD / DENY → no-op estructurado
4. PROTECT | TRAIL → `PersistPositionFromProtect` (`revision_origin_from_exit_reason`)
5. REDUCE | EXIT → `ExecutionRouter` sell (`reduce` qty o `exit` full) → `PersistPositionFromExit`

## 2. Router reduce

`signal.kind == "reduce"` → sell con `quantity` explícita clamp ≤ open. `exit` sigue = full qty. Mismo gate `paper_auto` / `PAPER_D_EXECUTE`.

## 3. DoD — GP-AUTO-01 E2E PAPER

Pytest application (env on solo en test):

```text
Position post-fill
  → T1 REDUCE → Permission ALLOW → Router reduce → revision reduce
  → TRAIL → PersistProtect origin=trail
  → T2 REDUCE → fill → CLOSED → TradeStory / ExecutionState
```

Env off → DENY `paper_auto_env_blocked`. Stale/closed/drift JIT. Protective STOP ALLOW.

## 4. OUT

Lab EvaluatePositionExits retrofit · browser E2E / Daily Journal UI · LIVE · Accept estricto · `PAPER_D_EXECUTE` default on · OCO · OpportunityScore.
