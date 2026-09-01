# RELEVO — V1.52 Position Lifecycle (2026-09-01)

> **Padre:** [`spec-v152-position-lifecycle-2026-09-01.md`](./spec-v152-position-lifecycle-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md) · tip certificado **`v1.51-beta` → `5eb8e6de`** (auditoría PASS 9,1).  
> **Estado:** **TAG** — tip **`v1.52-beta` → `1da5eb3f`** ([relevo tag](./traspaso-relevo-tag-v1-52-beta-2026-09-01.md)). Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué cierra

| Pieza                                                                    | Estado   |
| ------------------------------------------------------------------------ | -------- |
| Lab `evaluate-exits?executeTrades=true` → 403 `lab_exit_execute_retired` | DONE     |
| `TargetLeg` pending/triggered/executed/failed (JSONB)                    | DONE     |
| `PositionRevision.decisionId` + `policyId`                               | DONE     |
| Handle `opening_fill_handle` + `RecoverOrphanOpeningFills`               | DONE     |
| GP-EXIT-01/02/03 · GP-TRAIL-01/02 · GP-CRASH-01                          | DONE     |
| GP-DESK-07/08/05b / V1.48 CAOS                                           | intactos |

```text
Estudio-born Position
  → TargetLeg pending
  → claim T1 → triggered → fill → executed
  → trail revisions (decisionId + policyId)
  → stop → CLOSED
Fill sin Position → cycle recover → 1 Position
Lab execute SELL → DENY
```

## 1. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic tabla nueva · sin UI Mesa · package `1.35.0-beta`.

## 2. OUT / parked

- **V1.53** Golden Session 09:00 Estudio → Journal
- **V1.54** Operating Desk (UI Mesa · excepción cubo)
- rankingEngineId · perfil→política · candidateSnapshot tesis

## 3. Next

1. Push `v1.52-beta` → Release-tag CI GREEN.
2. **V1.53** Golden Session — [`traspaso-relevo-v1-53-golden-session-2026-09-01.md`](./traspaso-relevo-v1-53-golden-session-2026-09-01.md). **NO LIVE** · **no** UI Mesa.
