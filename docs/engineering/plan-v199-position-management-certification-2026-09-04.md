# Plan — V1.99 Position Management Certification

> **Padre:** [`spec-v199-position-management-certification-2026-09-04.md`](./spec-v199-position-management-certification-2026-09-04.md).  
> **Estado:** **IN** · partida `v1.98-beta` → `7b5b1052`.

| ID  | Entrega                                                                              | Estado |
| --- | ------------------------------------------------------------------------------------ | ------ |
| C1  | `test_lifecycle_position_management_v199.py` — G1–G6, G8, lineage ≠ log, G5 agresivo | DONE   |
| C2  | Analytics: trail/reduce no muta `initial_risk` / `initial_stop`                      | DONE   |
| C3  | G7 ancla docstring + alias en V1.97 crash/retry                                      | DONE   |
| C4  | Vitest `describe("V1.99 position management")` G1/G4/G5/G6/G8                        | DONE   |
| D0  | spec/plan/relevo/arranque + CURRENT_SYSTEM + engineering-index §68                   | DONE   |

## Política

- **Solo certificación** — cero cambios de FSM / outbox / ExitPolicy / Alembic.
- Trail **solo después de T1** (OUT: `open` → TRAIL).
- G2/G3 HTTP reusan V1.95/V1.96; G7 reusa V1.97; no duplicar atomicidad.
- `lifecycle-pg` no añade HTTP v199; domain + vitest cubren G1/G4/G5/G6/G8 offline.

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · SEMI protect→TRAIL · open→T2/TRAIL · LineagePath flags · cuarteto riesgo · UI V2.0
