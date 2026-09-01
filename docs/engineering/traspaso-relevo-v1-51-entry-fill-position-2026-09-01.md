# RELEVO — V1.51 Entry → Paper Fill → Position (2026-09-01)

> **Padre:** [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md) · [`plan-v151-entry-fill-position-2026-09-01.md`](./plan-v151-entry-fill-position-2026-09-01.md) · tip previo **`v1.50-beta` → `96623755`**.  
> **Estado:** **CÓDIGO** — pre-flight verde. Product certificado vigente **`V1.50-beta`**. Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué cierra

| Pieza                                                | Estado  |
| ---------------------------------------------------- | ------- |
| Router PAPER opening → `PersistPositionFromFill`     | DONE    |
| `decisionId` = `signal.id` en snapshot               | DONE    |
| `templateId` / `autoSource` en `trade_plan_snapshot` | DONE    |
| GP-DESK-07 + idempotencia + Gate DENY                | DONE    |
| EntryTick CandidateSnapshot V1.50                    | intacto |
| PositionTick Event Continuity V1.48                  | intacto |

```text
Estudio → TradePlan TRIGGERED → Gate → ledger fill
  → PositionState OPEN (trade_plan_snapshot)
```

## 1. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin UI Mesa · sin Golden birth+exit.

## 2. OUT / parked

- V1.52 Golden Session completa
- UI Mesa · scheduler · LIVE · package bump

## 3. Next

1. Commit + push stage cuando el owner lo pida. **NO LIVE**.
2. Tag `v1.51-beta` solo tras CI y cuando se pida.
