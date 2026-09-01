# RELEVO — tag v1.50-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md`](./traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md) · [`traspaso-relevo-tag-v1-49-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-49-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.50-beta` → `96623755` · Release-tag CI **GREEN** · **pendiente auditoría externa**.  
> **Arranque auditor:** [`arranque-auditor-v1-50-beta-2026-09-01.md`](./arranque-auditor-v1-50-beta-2026-09-01.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Fill→Position (V1.51) · scheduler · UI Mesa · OCO · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.49-beta` → `c8975c9d`:

| Pieza               | Entrega                                                         |
| ------------------- | --------------------------------------------------------------- |
| `CandidateSnapshot` | EntryTick transporta `hits[]` (TradePlan, rank, score canónico) |
| `decisionId`        | `signal.id` por propuesta                                       |
| Reason codes        | `reasonCode` + `humanMessage`; `notes` humanas se conservan     |
| Profile             | `template_id` → `OperatingPolicy` + `policy_version` en propose |
| Relojes             | `analysisAsOf` Daily; `marketAsOf`/`executionAsOf` nullable     |
| Errores             | dominio `blocked` · infra/universo `unavailable`                |
| GP-DESK-04/05/06    | ranking top-N · gate DENY sin Intent · stop inválido ≠ BUY      |
| GP-DESK-03 / V1.48  | Intactos                                                        |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Fill→Position · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.50-beta` → `96623755` (was `9e511715`; CI unblock mypy)                                                      |
| Código     | `9e511715` feat + `96623755` mypy                                                                                |
| Previo tip | `v1.49-beta` → `c8975c9d` (CI GREEN)                                                                             |
| CI tag     | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33483870030) · `headSha=96623755` |

**GitHub auditoría:** [tag `v1.50-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.50-beta) · [rama stage/v150](https://github.com/jvelasca/Bolsa_V1/tree/stage/v150-entry-decision-integrity-2026-09-01)

Jobs del push `v1.50-beta` (retag 2026-09-01T07:47Z), todos **success**:

| Job            | Resultado |
| -------------- | --------- |
| python         | success   |
| shared         | success   |
| frontend       | success   |
| decision-spine | success   |
| security       | success   |
| certify        | success   |

## 2. Auditoría

**Veredicto local (2026-09-01, tip `96623755`):** pre-flight verde (vitest 7 · pytest 83 · ruff · tsc) · Release-tag CI **GREEN**. **Pendiente auditoría externa** con [`arranque-auditor-v1-50-beta-2026-09-01.md`](./arranque-auditor-v1-50-beta-2026-09-01.md). **No** LIVE.

## 3. Residuals parked

- **V1.51** Entry → Fill → Position (snapshot viaja con la posición)
- **V1.52** Golden Session completa · UI Mesa
- Paper-D desk entry · scheduler · LIVE · package bump

## 4. Next

1. Auditoría externa PASS → certificar tip `v1.50-beta`.
2. **V1.51** Fill→Position — **NO LIVE**.
