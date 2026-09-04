# RELEVO — V1.99 Position Management Certification (2026-09-04)

> **Padre:** [`spec-v199`](./spec-v199-position-management-certification-2026-09-04.md) · [`plan-v199`](./plan-v199-position-management-certification-2026-09-04.md).  
> **Partida:** tip [`v1.98-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.98-beta) → `7b5b1052`.  
> **Estado:** tip [`v1.99-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.99-beta) → [`bf57899b`](https://github.com/jvelasca/Bolsa_V1/commit/bf57899b) · Release-tag CI en curso ([run 33847460567](https://github.com/jvelasca/Bolsa_V1/actions/runs/33847460567)) · stamp GREEN + PASS auditor pendientes.

## Hecho

- Spec/plan + CURRENT_SYSTEM + engineering-index §68
- Domain goldens G1–G6, G8 + lineage ≠ log + G5 agresivo (`test_lifecycle_position_management_v199.py`)
- PositionState: trail/reduce no mutan `initial_risk` / `initial_stop`
- G7 anclado en V1.97 `test_crash_mid_pair_rolls_back_then_retry_exactly_once` (+ `test_lifecycle_position_management_v199_g7.py`)
- Vitest mirror G1/G4/G5/G6/G8 · `lastFillPrice` / `stopWorsens` exportados en e2e helper
- **Cero** cambios de `TRANSITIONS` / Alembic / ExitPolicy / ledger

## Residuales (OUT)

- `open` → TRAIL / T2 · LineagePath flags · cuarteto de riesgo persistido
- SEMI protect → `TRAIL_APPLIED` · UI MERCADO / AUTO Desk (V2.0)
- HTTP golden de 8 caminos (G2/G3 siguen en V1.95/V1.96)

## Next

1. Release-tag GREEN del tip · stamp `traspaso-relevo-tag-v1-99-beta` + CURRENT_SYSTEM
2. Arranque auditor tip ([arranque](./arranque-auditor-v1-99-position-management-certification-2026-09-04.md)) — **auditoría actual se mantiene**
3. Plan cierre PAPER AUTO (siguiente agente): [relevo planificador](./traspaso-relevo-post-v199-plan-cierre-paper-auto-2026-09-04.md) → ENGINE FREEZE → V2.0 AUTO Desk

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no Alembic · no auto-heal · no unificar ledger · no features FSM
