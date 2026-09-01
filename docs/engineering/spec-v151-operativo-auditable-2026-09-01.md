# Spec — V1.51 close-out: Entry → Position operativo y auditable

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · auditoría 2 (2026-09-01).  
> **Plan:** [`plan-v151-operativo-auditable-2026-09-01.md`](./plan-v151-operativo-auditable-2026-09-01.md).  
> **No** es V1.52 Golden Session. **No** LIVE. `PAPER_D_EXECUTE` default **off**.

Cierra los P0 de auditoría que impiden demostrar V1.51: identidad colapsada, snapshot de candidato incompleto, pruebas partidas (GP-DESK-04 dry_run vs GP-DESK-07 hit sintético), Gate DENY mockeado.

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Alembic · no UI Mesa · no Golden birth+exit · no PaperOrder nuevo · no ExecutionIntent de apertura · package `1.35.0-beta`. Honesty: AUTO apertura = ledger `ExecuteTrade`; `fillId` = `open_transaction_id`.

## 1. IN

### 1.1 Tres identidades (no pisar)

En `trade_plan_snapshot` (JSONB, sin Alembic):

| Campo                 | Origen                                                    | Nunca                               |
| --------------------- | --------------------------------------------------------- | ----------------------------------- |
| `decisionId`          | TradePlan (propose). Si falta, sintético `tp-…` en el hit | **No** sobrescribir con `signal.id` |
| `candidateDecisionId` | `CandidateSnapshot.decision_id` = `signal.id`             | —                                   |
| `fillId`              | ledger `transaction.id` (= `open_transaction_id`)         | —                                   |

`PositionState.trade_plan_id` = `decisionId` del plan. Fila `open_transaction_id` = `fillId`.

### 1.2 CandidateSnapshot viaja

El hit Estudio estampa `rank` / `score` (proyección estrellas, no Composite). El enrich de apertura copia `templateId`, `autoSource`, `rank`, `score`, `dictamenStars` y un `candidateSnapshot` compacto al JSON persistido.

### 1.3 Golden Paths

| ID          | Comportamiento                                                                                                                                                                                                                                                        |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-DESK-08  | Estudio A,B,C,D; `maxCandidates=2` → solo A,B. Execute A (y B si TRIGGERED) → Position. `candidate.decision_id == snapshot.candidateDecisionId`; `position.trade_plan_id == snapshot.decisionId`; `position.open_transaction_id == snapshot.fillId == transaction.id` |
| GP-DESK-07  | Intacta salvo: ya no pisa `decisionId`; afirma las tres identidades                                                                                                                                                                                                   |
| GP-DESK-05b | `check_opening` real (p.ej. `book_max_open_positions`) → skipped · 0 Positions · ranking ≠ autorización                                                                                                                                                               |

## 2. OUT

T1/T2 estados · trailing sobre birth AUTO · UI Mesa · ExecutionIntent/PaperOrder de apertura · segundo factory · LIVE.
