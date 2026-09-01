# Spec — V1.52 Position Lifecycle

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [`respuesta-auditor-v151-entry-fill-position-2026-09-01.md`](./respuesta-auditor-v151-entry-fill-position-2026-09-01.md).  
> **Plan:** [`plan-v152-position-lifecycle-2026-09-01.md`](./plan-v152-position-lifecycle-2026-09-01.md).  
> **Tip certificado previo:** `v1.51-beta` → `5eb8e6de` (auditoría PASS 9,1). **No** LIVE.

Cierra agujeros del ciclo post-nacimiento. **No** construye un motor nuevo. Reutiliza ExitPlan → Policy → Permission → `ExecutePositionPolicyAuto`.

```text
Market → PositionTick (ExitPlan)
  → PositionPolicyDecision → ExitPermission JIT
  → protect | REDUCE/EXIT (Router) → Fill → PositionRevision
Lab evaluate-exits?executeTrades=true → DENY lab_exit_execute_retired
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · sin OCO · sin Alembic tabla nueva · sin bump package · sin nav L1 · sin scheduler · dry_run default true · **no** UI Mesa · **no** Golden Session 09:00→Journal (V1.53) · **no** ExecutionIntent de apertura · **no** PositionEngine2 / TrailingEngine.

## 1. IN

### 1.1 Una sola autoridad AUTO SELL

`POST /position-policies/evaluate-exits?executeTrades=true` → **403** `lab_exit_execute_retired` siempre (env on no abre la puerta). Eval-only (`executeTrades=false`) intacto. SEMI Confirm intacto.

### 1.2 TargetLeg (JSONB, sin Alembic)

```text
TargetLegStatus = pending | triggered | executed | failed
target1Leg / target2Leg: { status, at?, eventId?, fillId? }
```

- Birth: precio T1/T2 → `pending`. Sin precio → omitir.
- `mark >= T1` ≠ `executed`. Claim REDUCE T1 → `triggered`.
- Reduce fill OK → `executed` + `target1AchievedAt` (ExitPlan no re-emite).
- Sell/persist fallido **después** de triggered → `failed` (reintento: failed → triggered). JIT DENY ≠ failed.
- `aggressive_swing` T1 HOLD de diseño: puede quedar `pending`.
- Legacy: `*AchievedAt` set ⇒ `executed`; si no y hay precio ⇒ `pending`.

`PositionStatus` sigue `OPEN|PARTIAL|PROTECTED|CLOSED`.

### 1.3 PositionRevision enrich

Campos opcionales: `decisionId` (TradePlan) · `policyId` (`OperatingPolicy.templateId`). `fromUnknown` tolerante. Trail = `origin=trail`. H2 stop-down DENY intacto. **No** tipo `StopRevision`.

### 1.4 GP-CRASH-01

Tras fill AUTO de apertura, stamp handle durable (`opening_fill_handle` en Journal + store) **antes** de persist. `PaperDeskCycle` recupera huérfanos con el mismo `PersistPositionFromFill`. Sin TradePlan recuperable → no inventar Position.

## 2. Golden Paths

| ID                | Comportamiento                                            |
| ----------------- | --------------------------------------------------------- |
| GP-EXIT-01        | Estudio-born → stop → fill → CLOSED; identidades intactas |
| GP-EXIT-02        | T1 → reduce parcial → PARTIAL + `target1Leg.executed`     |
| GP-EXIT-03        | T1 executed luego T2/exit → CLOSED; no re-emitir T1       |
| GP-TRAIL-01       | precio ↑ → stop ↑ ×N; `origin=trail` + `decisionId`       |
| GP-TRAIL-02       | stop ↓ → DENY; 0 revisión nueva                           |
| GP-CRASH-01       | BUY FILLED → persist crash → restart → 1 Position         |
| GP-DESK-07/08/05b | Intactos                                                  |
| Lab execute       | DENY con env on                                           |

## 3. OUT / parked

Golden Session 09:00 (**V1.53**) · UI Mesa / excepción cubo (**V1.54**) · candidateSnapshot tesis · rankingEngineId · perfil→política · rename recon · LIVE · package bump.

## 4. Pre-flight

Bloque V1.51 + TargetLeg + revision enrich + GP-EXIT/CRASH + Lab DENY + ruff + tsc.
