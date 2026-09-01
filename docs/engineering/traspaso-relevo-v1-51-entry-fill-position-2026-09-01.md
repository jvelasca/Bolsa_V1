# RELEVO — V1.51 Entry → Paper Fill → Position (2026-09-01)

> **Padre:** [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [`spec-v151-operativo-auditable-2026-09-01.md`](./spec-v151-operativo-auditable-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md) · tip previo **`v1.50-beta` → `96623755`**.  
> **Estado:** **CI GREEN** — tip `v1.51-beta` → `5eb8e6de` (close-out identidades). Auditoría externa **PASS 9,1**. Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué cierra

| Pieza                                                         | Estado  |
| ------------------------------------------------------------- | ------- |
| Router PAPER opening → `PersistPositionFromFill`              | DONE    |
| Tres identidades (plan / candidate / fill)                    | DONE    |
| `templateId` / `autoSource` / `candidateSnapshot` en snapshot | DONE    |
| GP-DESK-07 + GP-DESK-08 + GP-DESK-05b                         | DONE    |
| EntryTick CandidateSnapshot V1.50                             | intacto |
| PositionTick Event Continuity V1.48                           | intacto |

```text
Estudio → TradePlan TRIGGERED → Gate → ledger fill
  → PositionState OPEN (decisionId ≠ candidateDecisionId ≠ fillId)
```

## 1. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin UI Mesa · sin Golden birth+exit.

## 2. OUT / parked

- Golden Session 09:00 (**V1.53**) · UI Mesa (**V1.54**)
- scheduler · LIVE · package bump

## 3. Next

1. Tip `v1.51-beta` **certificado** (auditoría PASS 9,1).
2. **V1.52** Position Lifecycle — **NO LIVE** · **no** UI Mesa.
