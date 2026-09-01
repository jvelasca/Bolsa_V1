# RELEVO — tag v1.51-beta → CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md`](./traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md) · [`traspaso-relevo-tag-v1-50-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-50-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI PENDING** — tip `v1.51-beta` → `ab6a5bc6` · Release-tag CI en curso. Previo certificado **`v1.50-beta` → `96623755`** (audit PASS).  
> **Arranque auditor:** [`arranque-auditor-v1-51-beta-2026-09-01.md`](./arranque-auditor-v1-51-beta-2026-09-01.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Golden Session birth+exit (V1.52) · UI Mesa · scheduler · OCO · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.50-beta` → `96623755`:

| Pieza                    | Entrega                                                       |
| ------------------------ | ------------------------------------------------------------- |
| Router post opening fill | `PersistPositionFromFill` / `sync_position_after_ledger_fill` |
| Identidad                | `tradePlan.decisionId` = `signal.id` (= CandidateSnapshot)    |
| Snapshot                 | entry/stop/T1/T2/risk + `templateId` / `autoSource`           |
| Fail persist             | ledger OK; `reason=position_birth_failed`                     |
| DI                       | `get_execution_router_use_case` inyecta mismo store Confirm   |
| GP-DESK-07               | birth + idempotencia + Gate DENY sin Position                 |
| GP-DESK-03..06 / V1.48   | Intactos                                                      |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no UI Mesa · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                             |
| ---------- | ------------------------------------------------- |
| Tag tip    | `v1.51-beta` → `ab6a5bc6`                         |
| Previo tip | `v1.50-beta` → `96623755` (CI GREEN · audit PASS) |
| CI tag     | **PENDING**                                       |

**GitHub:** [tag `v1.51-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.51-beta) · rama [`stage/v151-entry-fill-position-2026-09-01`](https://github.com/jvelasca/Bolsa_V1/tree/stage/v151-entry-fill-position-2026-09-01)

## 2. Next

1. Push tag → Release-tag CI verde → stamp tip aquí + CURRENT_SYSTEM.
2. Auditoría externa con arranque. **NO LIVE**.
3. V1.52 Golden Session · UI Mesa — después.
