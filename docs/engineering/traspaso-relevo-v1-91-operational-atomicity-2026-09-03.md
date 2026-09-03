# RELEVO — V1.91 Operational Atomicity & Full Confirm Golden (2026-09-03)

> **Padre:** [`respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md`](./respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md).  
> **Spec/plan:** [`spec-v191-operational-atomicity-2026-09-03.md`](./spec-v191-operational-atomicity-2026-09-03.md) · [`plan-v191-operational-atomicity-2026-09-03.md`](./plan-v191-operational-atomicity-2026-09-03.md).  
> **Estado:** **ABIERTA**.  
> **Partida:** `v1.90-beta` → `0c2e3af7`.

## Objetivo

Cerrar P1 del auditor V1.90: atomicidad PositionState+Outbox, worker continuo del outbox, Golden Confirm HTTP real OPEN→T1→EXIT. Sin nuevas features de producto.

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · integrated E2E opt-in

## Entregas

1. PositionState + Outbox misma TX; drain post-COMMIT
2. Alembic 018 + LifecycleOutboxWorker (`pending→processing→applied|dead`)
3. Golden Confirm HTTP real en `lifecycle-pg` (V1.88+V1.90+V1.91)
4. Requeue dead · Mesa `lifecycleStage` · tipar append DTO

## Next

Implementación · stamp CI · auditoría tip V1.91. **Sin** LIVE.
