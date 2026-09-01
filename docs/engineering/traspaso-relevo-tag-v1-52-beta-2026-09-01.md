# RELEVO — tag v1.52-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-52-position-lifecycle-2026-09-01.md`](./traspaso-relevo-v1-52-position-lifecycle-2026-09-01.md) · [`traspaso-relevo-tag-v1-51-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-51-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.52-beta` → `9725e9e7` · Release-tag CI **GREEN** · previo certificado **`v1.51-beta` → `5eb8e6de`** (auditoría PASS 9,1).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Golden Session (V1.53) · UI Mesa (V1.54) · scheduler · OCO · package bump.

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

| Pieza      | Valor                                                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.52-beta` → `9725e9e7` (was `1da5eb3f`; mypy unblock)                                                         |
| Código     | `1da5eb3f` feat lifecycle + `9725e9e7` mypy fix                                                                  |
| Previo tip | `v1.51-beta` → `5eb8e6de` (CI GREEN · audit PASS 9,1)                                                            |
| CI tag     | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33502192108) · `headSha=9725e9e7` |

Jobs del push `v1.52-beta` (retag mypy 2026-09-01), todos **success**:

| Job            | Resultado |
| -------------- | --------- |
| python         | success   |
| shared         | success   |
| frontend       | success   |
| decision-spine | success   |
| security       | success   |
| certify        | success   |

## 2. Pre-flight

vitest shared 41 · pytest desk-block 95 · ruff OK · tsc OK · Release-tag CI **GREEN**.

## 3. Residuals parked

- **V1.53** Golden Session 09:00 Estudio → Journal
- **V1.54** Operating Desk (UI Mesa)
- rankingEngineId · perfil→política · candidateSnapshot tesis

## 4. Next

1. Tip `v1.52-beta` **certificado** (CI GREEN).
2. **V1.53** Golden Session · **V1.54** Operating Desk — **NO LIVE**.
