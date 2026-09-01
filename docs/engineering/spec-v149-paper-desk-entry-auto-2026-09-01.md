# Spec — V1.49 Paper Desk Entry AUTO (Estudio)

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v148-paper-desk-event-continuity-2026-09-01.md`](./spec-v148-paper-desk-event-continuity-2026-09-01.md).  
> **Plan:** [`plan-v149-paper-desk-entry-auto-2026-09-01.md`](./plan-v149-paper-desk-entry-auto-2026-09-01.md).  
> **Tip certificado previo:** `v1.48-beta` → `d5852e8d` (Release-tag CI GREEN). **No** LIVE.

Cierra EntryTick real del ciclo PAPER: **Estudio → Ranking → TradePlan → OpeningGate** (`check_opening` vía `ExecutionRouter`). PositionTick / Event Continuity **sin cambios** (V1.48).

```text
PaperDeskCycle
  → EntryTick: Estudio list → ProposeEstudioAutoOpenings
      → select_estudio_opening_candidates (rank)
      → ProposeRecommendationFromTa (TradePlan TRIGGERED)
      → dry_run | ExecutionRouter (check_opening)
  → PositionTick (ExecutePositionPolicyAuto)
  → PaperDailyReport / autoDesk
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic (tabla nueva) · sin bump package · sin nav L1 · sin scheduler · dry_run default true · BME/ES hardcode · **no** Paper-D desk entry · **no** LIVE.

## 1. EntryTick (IN)

- **`EstudioPaperDeskEntry`** implementa `PaperDeskEntryPort`.
- Universo = lista canónica **`estudio`** (`GetInstrumentList`). Empty ≠ unavailable.
- Reutiliza **`ProposeEstudioAutoOpenings`** (misma semántica que `POST /instrument-daily-opinions/auto-propose`).
- `dry_run=true` → propose sin Router; `proposed_count = hitCount` (TradePlan TRIGGERED).
- `dry_run=false` + env + `executionPolicyId` → Router `paper_auto` + `check_opening`.
- OR-4 pre-gate en `PaperDeskCycle` (drift/unavailable bloquean entry antes del port) **sin cambios**.
- `HonestStubPaperDeskEntry` permanece para tests / fallback explícito.

## 2. OUT / parked

- Paper-D Composite en desk entry (Router ya lo rechaza).
- Scheduler / DeskRunner multi-día · UI Mercado cards.
- MarketProfile · freshness matrix simétrica ExecutionTruth.
- LIVE · `PAPER_D_EXECUTE` default on · package bump · Golden Session con birth entry+exit mismo ciclo.

## 3. Golden Paths

| ID             | Comportamiento                                                                   |
| -------------- | -------------------------------------------------------------------------------- |
| GP-DESK-03     | dry_run → EntryTick propone hits Estudio (`proposed_count > 0`) sin mutar ledger |
| GP-DESK-01..02 | Intactos (env block · stale derived)                                             |

## 4. Pre-flight

Mismo bloque V1.48 + `test_paper_desk_entry.py`.
