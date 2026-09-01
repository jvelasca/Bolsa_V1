# RELEVO — tag v1.51-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md`](./traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md) · [`traspaso-relevo-tag-v1-50-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-50-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.51-beta` → `5eb8e6de` · Release-tag CI **GREEN** · **pendiente auditoría externa**. Previo certificado **`v1.50-beta` → `96623755`**.  
> **Arranque auditor:** [`arranque-auditor-v1-51-beta-2026-09-01.md`](./arranque-auditor-v1-51-beta-2026-09-01.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Golden Session birth+exit (V1.52) · UI Mesa · scheduler · OCO · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.50-beta` → `96623755` + birth `ab6a5bc6`:

| Pieza                    | Entrega                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------- |
| Router post opening fill | `PersistPositionFromFill` / `sync_position_after_ledger_fill`                      |
| Identidad (close-out)    | `decisionId` (TradePlan) ≠ `candidateDecisionId` (`signal.id`) ≠ `fillId` (ledger) |
| Snapshot                 | entry/stop/T1/T2/risk + `templateId` / `autoSource` / `candidateSnapshot`          |
| Fail persist             | ledger OK; `reason=position_birth_failed`                                          |
| DI                       | `get_execution_router_use_case` inyecta mismo store Confirm                        |
| GP-DESK-07/08/05b        | birth + Estudio→Position identidades + Gate real DENY 0 Position                   |
| GP-DESK-03..06 / V1.48   | Intactos                                                                           |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no UI Mesa · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.51-beta` → `5eb8e6de` (was `ab6a5bc6`; close-out identidades)                                                |
| Código     | `5eb8e6de` feat close-out                                                                                        |
| Previo tip | `v1.50-beta` → `96623755` (CI GREEN · audit PASS)                                                                |
| CI tag     | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33496236067) · `headSha=5eb8e6de` |

**GitHub auditoría:** [tag `v1.51-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.51-beta) · [rama stage/v151](https://github.com/jvelasca/Bolsa_V1/tree/stage/v151-entry-fill-position-2026-09-01) · tip también en `main` tras merge.

Jobs del push `v1.51-beta` (retag close-out 2026-09-01T10:12Z), todos **success**:

| Job            | Resultado |
| -------------- | --------- |
| python         | success   |
| shared         | success   |
| frontend       | success   |
| decision-spine | success   |
| security       | success   |
| certify        | success   |

## 2. Auditoría

**Veredicto local (2026-09-01, tip `5eb8e6de`):** pre-flight desk-block 66 · ruff OK · Release-tag CI **GREEN**. **Pendiente auditoría externa** con [`arranque-auditor-v1-51-beta-2026-09-01.md`](./arranque-auditor-v1-51-beta-2026-09-01.md). **No** LIVE.

## 3. Residuals parked

- **V1.52** Golden Session completa · UI Mesa
- T1/T2 estados · Paper-D desk entry · scheduler · LIVE · package bump

## 4. Next

1. Auditoría externa PASS → certificar tip `v1.51-beta`.
2. **V1.52** Golden Session · UI Mesa — **NO LIVE**.
