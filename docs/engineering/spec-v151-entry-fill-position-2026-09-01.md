# Spec — V1.51 Entry → Paper Fill → Position

> **AsOf:** 2026-09-01 · **Estado:** **CI GREEN**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v150-entry-decision-integrity-2026-09-01.md`](./spec-v150-entry-decision-integrity-2026-09-01.md).  
> **Plan:** [`plan-v151-entry-fill-position-2026-09-01.md`](./plan-v151-entry-fill-position-2026-09-01.md).  
> **Tip:** `v1.51-beta` → `ab6a5bc6` (Release-tag CI GREEN). Previo `v1.50-beta` → `96623755`. **No** LIVE.

Cierra el nacimiento de **PositionState** tras un fill PAPER de apertura AUTO (Estudio). Reutiliza OI-1 `PersistPositionFromFill`. El `CandidateSnapshot` / TradePlan viaja en `trade_plan_snapshot` con `decisionId` = `signal.id`.

```text
Estudio → rank → TradePlan TRIGGERED → OpeningGate
  → ExecuteTrade (ledger)
  → PersistPositionFromFill (PositionState OPEN + trade_plan_snapshot)
PositionTick (protect/reduce/exit) intacto V1.48
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic · sin bump package · sin nav L1 · sin scheduler · dry_run default true · BME/ES hardcode · **no** UI Mesa · **no** Golden Session birth+exit mismo ciclo (V1.52).

## 1. IN

- Tras `trade_executed` de **apertura** `paper_auto` + TradePlan TRIGGERED: llamar `sync_position_after_ledger_fill` / `PersistPositionFromFill`.
- Stamp `tradePlan.decisionId` **conservado** (no pisar con `signal.id`); `candidateDecisionId` = `signal.id`; `fillId` = ledger tx.
- Enriquecer snapshot JSON (sin Alembic): `templateId`, `autoSource`, `rank`/`score`, `candidateSnapshot`.
- DI: `get_execution_router_use_case` inyecta el mismo store Confirm.
- Fallo de persist: **no** revierte el fill; `trade_executed` + `reason=position_birth_failed` (honesty OI-1).

## 2. OUT / parked

- Golden Session Entry fill → protect → exit mismo ciclo (**V1.52**).
- UI Mesa EntryOpportunity.
- LIVE · `PAPER_D_EXECUTE` default on · package bump · Paper-D desk entry · scheduler.

## 3. Golden Paths

| ID             | Comportamiento                                                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| GP-DESK-07     | hit TRIGGERED + execute → Position; `trade_plan_id` = plan `decisionId`; `candidateDecisionId` = `signal.id`; `fillId` = ledger tx |
| GP-DESK-08     | Estudio A,B,C,D `maxCandidates=2` → A,B → fill → Position con las tres identidades                                                 |
| GP-DESK-05b    | `check_opening` real DENY → 0 Positions                                                                                            |
| Idempotencia   | misma `open_transaction_id` no duplica Position                                                                                    |
| Gate DENY      | sin fill → sin Position (GP-DESK-05 intacto)                                                                                       |
| GP-DESK-03..06 | Intactos                                                                                                                           |

## 4. Pre-flight

Bloque V1.50 + `test_execution_router.py` (GP-DESK-07) + ruff + tsc.
