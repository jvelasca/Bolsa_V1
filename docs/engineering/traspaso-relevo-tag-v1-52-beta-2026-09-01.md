# RELEVO — tag v1.52-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-52-position-lifecycle-2026-09-01.md`](./traspaso-relevo-v1-52-position-lifecycle-2026-09-01.md) · [`traspaso-relevo-tag-v1-51-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-51-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CÓDIGO** — tip `v1.52-beta` → `1da5eb3f` · Release-tag CI **pendiente push**. Previo certificado **`v1.51-beta` → `5eb8e6de`** (auditoría PASS 9,1).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Golden Session 09:00 (V1.53) · UI Mesa (V1.54) · scheduler · OCO · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.51-beta` → `5eb8e6de`:

| Pieza                                               | Entrega                                      |
| --------------------------------------------------- | -------------------------------------------- |
| Lab `evaluate-exits?executeTrades=true`             | 403 `lab_exit_execute_retired` (env on ≠ OK) |
| `TargetLeg` pending/triggered/executed/failed       | JSONB TS+Py                                  |
| `PositionRevision.decisionId` + `policyId`          | protect/trail/reduce                         |
| `opening_fill_handle` + `RecoverOrphanOpeningFills` | GP-CRASH-01                                  |
| GP-EXIT-01/02/03 · GP-TRAIL-01/02 · GP-CRASH-01     | Estudio-born                                 |
| GP-DESK-07/08/05b / V1.48 CAOS                      | intactos                                     |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no UI Mesa · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                 |
| ---------- | ----------------------------------------------------- |
| Tag tip    | `v1.52-beta` → `1da5eb3f`                             |
| Código     | `1da5eb3f` feat position lifecycle                    |
| Previo tip | `v1.51-beta` → `5eb8e6de` (CI GREEN · audit PASS 9,1) |
| CI tag     | **pendiente** — push tag + Release-tag workflow       |

## 2. Pre-flight local (2026-09-01)

vitest shared 41 · pytest desk-block 95 · ruff OK · tsc OK.

## 3. Residuals parked

- **V1.53** Golden Session 09:00 Estudio → Journal
- **V1.54** Operating Desk (UI Mesa)
- rankingEngineId · perfil→política · candidateSnapshot tesis

## 4. Next

1. Push `v1.52-beta` → Release-tag CI GREEN.
2. **V1.53** Golden Session — **NO LIVE** · **no** UI Mesa.
