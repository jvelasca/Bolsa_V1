# Spec — V1.47 Paper Desk Runtime Truth

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v146-paper-desk-foundation-2026-08-31.md`](./spec-v146-paper-desk-foundation-2026-08-31.md).  
> **Plan:** [`plan-v147-paper-desk-runtime-truth-2026-09-01.md`](./plan-v147-paper-desk-runtime-truth-2026-09-01.md).  
> **Tip certificado previo:** `v1.45-beta` → `6ca5ec12`. V1.46 = foundation (Entry stub + Position AUTO). **No** AUTO completo.

Endurece el ciclo PAPER: hechos de mercado los obtiene el servidor. **No** LIVE. `PAPER_D_EXECUTE` default **off**. EntryTick sigue **HonestStub**.

```text
HTTP (accountId, executionPolicyId, dryRun, templateId, asOf)
  → OperationalContextBuilder
  → MarketSnapshot + Portfolio/Position/Risk/Execution
  → PaperDeskCycle (EntryTick STUB + PositionTick)
  → Policy → JIT Permission → ExecutePositionPolicyAuto
  → executionIntentId → Router / Protect
  → PaperDailyReport (proyección)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic · sin bump package · sin nav L1 · sin DeskRunner / scheduler · sin EntryTick Estudio real · `HonestStubPaperDeskEntry` permanece · dry_run default true.

## 1. Runtime Truth

- `MarketSnapshot` + `MarketDataPermission` (FRESH / STALE / MISSING / INVALID).
- Freshness AUTO = last bar vs `expected_last_daily_bar` (calendario), no flag HTTP.
- `SessionState`: PRE | OPEN | BREAK | CLOSED | POST. No-OPEN → T1 queue/defer.
- `stopTouched` = mark vs `currentStop`. Drift = recon lookup (OR-4).
- Sin mark válido: `DATA_UNAVAILABLE` → ninguna acción AUTO normal. **Nunca** `actual_entry` ni `defaultMarkPrice` operativo.

## 2. HTTP

- `POST /api/paper-desk/cycle` — único mutador. Body: dryRun, templateId, asOf. Query: accountId, executionPolicyId.
- `GET /api/paper-desk/daily-report` — consulta. Dry-run evaluate opcional. **Sin** `execute`.
- `POST /api/position-automation/execute-auto` — sin markPrice ni flags JIT en el body.

## 3. Idempotencia

`PositionEvent` (positionId + eventType + eventAsOf + sequence) → `executionIntentId` → `idempotencyKey`. Mismo evento dos veces = un sell. Crash tras order accepted → replay, no duplicar.

## 4. nextAction

Cada fila PositionTick proyecta: `MANTENER` · `SUBIR_STOP` · `REDUCIR` · `SALIR` · `ESPERAR_APERTURA` · `REVISAR_DATOS_NO_FRESCOS` · `BLOQUEADO`. Report ≠ estado operativo.

## 5. OUT

EntryTick real · capability matrix · scheduler · UI Mercado · LIVE · OCO · flip env default · package bump · Event Continuity (V1.48).
