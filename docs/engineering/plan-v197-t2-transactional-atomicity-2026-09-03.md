# Plan — V1.97 T2 Transactional Atomicity

> **Padre:** [`spec-v197-t2-transactional-atomicity-2026-09-03.md`](./spec-v197-t2-transactional-atomicity-2026-09-03.md).  
> **Estado:** **CI GREEN tip** · tip [`v1.97-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.97-beta) → [`363dfcea`](https://github.com/jvelasca/Bolsa_V1/commit/363dfcea) · Python CI ([run 33811212221](https://github.com/jvelasca/Bolsa_V1/actions/runs/33811212221)).

| ID    | Entrega                                                       | Estado |
| ----- | ------------------------------------------------------------- | ------ |
| D0    | respuesta auditor V1.96 + spec/plan/relevo/arranque + CURRENT | DONE   |
| P2-01 | `append_many` + par atómico T2 en `AppendLifecycleEvent`      | DONE   |
| P2-02 | Unit + PG store + worker/Confirm crash mid-pair               | DONE   |
| P2-03 | CI lifecycle-pg + tag sobre stamp                             | DONE   |

## Política

- `T2_TRIGGERED` + `T2_EXECUTED` = una unidad transaccional (un `begin_nested`).
- Validación en memoria de ambos antes de persistir.
- Stage `t2_ready` (leftover / replay): solo `T2_EXECUTED`.
- Idempotencia: mismo `event_id`/`fill_id` → 0 inserts extra.
- Contrato externo intacto: `reduce` + `TARGET_2`.
- Sin Alembic nuevo.

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · queue_sequence · heartbeat · auto-heal · Playwright frontend-ci obligatorio
- E2E integrado · compose portfolio unavailable→blocked
- Commitear `**/logs/`
