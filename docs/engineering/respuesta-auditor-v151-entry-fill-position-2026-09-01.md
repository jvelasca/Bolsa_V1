# Respuesta auditor — V1.51 Entry → Fill → Position (2026-09-01)

> **Padre:** [`traspaso-relevo-tag-v1-51-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-51-beta-2026-09-01.md) · [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Tip auditado:** `v1.51-beta` → `5eb8e6de` (Release-tag CI GREEN).  
> **Estado:** auditoría externa **PASS 9,1/10**. Entry → Position **cerrado**. Operativa AUTO **no** cerrada. Siguiente = [`spec-v152-position-lifecycle-2026-09-01.md`](./spec-v152-position-lifecycle-2026-09-01.md). **No** LIVE.

---

## 0. Acuerdo

V1.51 **sí** consigue el objetivo: una apertura PAPER nace desde Estudio y termina en `PositionState` conservando `decisionId` (TradePlan) ≠ `candidateDecisionId` (`signal.id`) ≠ `fillId` (ledger). GP-DESK-08 / 05b / 07 lo demuestran. Persist fail **no** revierte el fill (`position_birth_failed`). No se crea `ExecutionIntent` de apertura. `PAPER_D_EXECUTE` off.

Global **9,1/10** aceptado. Entry → Position cerrado. El ciclo Position → Exit **no** está cerrado.

## 1. Contrastado (PASS)

| #   | Afirmación del auditor                                      | Código                                            |
| --- | ----------------------------------------------------------- | ------------------------------------------------- |
| 1   | Tres identidades distintas; no pisar `TradePlan.decisionId` | `enrich_opening_trade_plan_for_position`          |
| 2   | Snapshot con templateId / rank / score / candidateSnapshot  | Router post-fill                                  |
| 3   | GP-DESK-08 Estudio A,B → fill → identidades                 | `test_paper_desk_entry.py`                        |
| 4   | GP-DESK-05b Gate DENY real → 0 Position                     | `test_paper_desk_entry.py` / Router               |
| 5   | Sin ExecutionIntent de apertura                             | Router → `ExecuteTrade` ledger                    |
| 6   | Fill OK + persist FAIL no revierte ledger                   | `trade_executed` + `reason=position_birth_failed` |
| 7   | DI Router = mismo store Confirm                             | `get_execution_router_use_case`                   |
| 18  | `PAPER_D_EXECUTE` off; no LIVE                              | freeze intacto                                    |

## 2. Deuda (no FAIL de V1.51; IN de V1.52+)

| #     | Hallazgo                                                                  | Acción                                                  |
| ----- | ------------------------------------------------------------------------- | ------------------------------------------------------- |
| 9–10  | Ciclo Position → Exit no Golden; Lab `evaluate-exits` sigue pudiendo SELL | **V1.52** autoridad única AUTO SELL + GP-EXIT           |
| 11    | T1/T2 = precios + `*AchievedAt`, no estados                               | **V1.52** `TargetLeg` pending/triggered/executed/failed |
| 12    | Trailing = `PositionRevision` sin decisionId/policy                       | **V1.52** enriquecer revisión; no tipo `StopRevision`   |
| 13–15 | candidateSnapshot compacto; ranking versions; perfil→política             | **V1.53/V1.54**                                         |
| 16–17 | Recon vocabulario; excepción UI birth-failed                              | **V1.54** (recovery P4 cubre el caso sin UI)            |
| 19–20 | Golden Paths de ciclo + crash tras fill                                   | **V1.52** GP-EXIT + GP-CRASH-01                         |
| 21    | Position Lifecycle conceptual                                             | documentado; `PositionStatus` no cambia                 |

## 3. Roadmap acordado

```text
V1.52  Position Lifecycle     (autoridad SELL · T1/T2 legs · crash recovery · GP-EXIT)
V1.53  Golden Session         (09:00 Estudio → … → CLOSED → Journal)
V1.54  Operating Desk         (UI Mesa · excepciones)
```

**No** UI en V1.52. **No** más ranking. **No** más IA. Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.
