# Spec — V1.54 Operating Desk (autoDesk → Hoy)

> **AsOf:** 2026-09-01 · **Estado:** **DOCS**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v153-golden-session-2026-09-01.md`](./spec-v153-golden-session-2026-09-01.md) · tip certificado previo **`v1.52-beta` → `1da5eb3f`** · V1.53 tip **pendiente**. **No** LIVE.

Primera rebanada **UI Mesa**: proyectar `DailyOpsReport.autoDesk` + `CandidateSnapshot` en filas del inbox Hoy (`EntryOpportunity` thin). Cubo 🔴 para excepciones operativas. Reutiliza V1.46 `autoDesk` · V1.50 `CandidateSnapshot` · V1.41 Daily Desk cuatro cubos. **No** segundo motor · **no** backend tick nuevo.

```text
GetDailyOpsReport
  → autoDesk (PaperDailyReportV1 · candidates / positions.rows / notes)
  → buildDailyDeskInbox (+ autoDesk overlay)
       🟢 EntryOpportunity thin (CandidateSnapshot proposed)
       🔴 position_birth_failed · recon drift|unavailable · UNKNOWN order
  → mesa-hoy-page → daily-desk-inbox
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · sin browser E2E · sin backend motor · V1.48 CAOS + V1.53 Golden Session intactos.

## 1. IN

| ID             | Comportamiento                                                                          |
| -------------- | --------------------------------------------------------------------------------------- |
| GP-DESK-UI-01  | Sin `autoDesk` → inbox actual intacto (backward compat)                                 |
| GP-DESK-UI-02  | `CandidateSnapshot` proposed → fila 🟢 `EntryOpportunity` thin (symbol, reason, no BUY) |
| GP-DESK-UI-03  | `CandidateSnapshot` skipped/denied → no fila 🟢; reason honesto en notes si aplica      |
| GP-DESK-UI-04  | `position_birth_failed` (fill OK, persist fail) → 🔴 `requiere_accion`                  |
| GP-DESK-UI-05  | Portfolio recon `drift` \| `unavailable` → 🔴 (fail-closed OR-4)                        |
| GP-DESK-UI-06  | ExecutionState / order `UNKNOWN` → 🔴 (OR-2 honesty)                                    |
| GP-DESK-UI-07  | `mesa-hoy-page` lee `autoDesk` del `DailyOpsReport` y lo pasa al compositor             |
| GP-DESK-UI-08  | `daily-desk-inbox` renderiza filas `EntryOpportunity` + excepciones 🔴                  |
| GP-DESK-UI-09  | Misma verdad shared ↔ web (vitest shared P1–P2; web smoke mínimo)                       |
| V1.53 session  | intacto (Golden Session pytest)                                                         |
| V1.41–V1.42 F6 | cuatro cubos §B.7 intactos; no redesign chrome                                          |

### EntryOpportunity thin

Proyección read-only desde `autoDesk` — **no** permiso · **no** CTA COMPRAR · **no** rankingEngineId.

Campos mínimos: `instrumentId` · `symbol` · `decisionId?` · `reasonCode?` · `phrase` (copy humano) · bucket fijo `oportunidades` salvo excepción.

## 2. OUT / parked

Redesign completo Daily Desk · scheduler · LIVE · bump package · `rankingEngineId` · browser E2E Journal · backend PaperDeskCycle extend · nav L1 · `PAPER_D_EXECUTE` default on.

## 3. Pre-flight

Bloque V1.53 + `daily-desk.test.ts` + `daily-desk-inbox.test.tsx` + ruff + tsc.
