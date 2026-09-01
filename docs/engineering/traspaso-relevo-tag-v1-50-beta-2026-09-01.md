# RELEVO — tag v1.50-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md`](./traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md) · [`traspaso-relevo-tag-v1-49-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-49-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** tip `v1.50-beta` → `9e511715` · Release-tag CI **pendiente push**.  
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

| Pieza      | Valor                                           |
| ---------- | ----------------------------------------------- |
| Tag tip    | `v1.50-beta` → `9e511715`                       |
| Código     | `9e511715` feat(v1.50) Entry Decision Integrity |
| Previo tip | `v1.49-beta` → `c8975c9d` (CI GREEN)            |
| CI tag     | **pendiente** tras `git push origin v1.50-beta` |

**GitHub auditoría:** [tag `v1.50-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.50-beta) · [rama stage/v150](https://github.com/jvelasca/Bolsa_V1/tree/stage/v150-entry-decision-integrity-2026-09-01)

## 2. Auditoría

**Veredicto local (2026-09-01, tip `9e511715`):** pre-flight verde (vitest 7 · pytest 83 · ruff · tsc). **No** LIVE. Pendiente Release-tag CI + auditoría externa ([arranque](./arranque-auditor-v1-50-beta-2026-09-01.md)).

## 3. Residuals parked

- **V1.51** Entry → Fill → Position (snapshot viaja con la posición)
- **V1.52** Golden Session completa · UI Mesa
- Paper-D desk entry · scheduler · LIVE · package bump

## 4. Next

1. Push tag → Release-tag CI GREEN → certificar tip `v1.50-beta`.
2. Auditoría externa PASS.
3. **V1.51** Fill→Position — **NO LIVE**.
