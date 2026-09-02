# Plan — V1.65 Operational Identity & Canonical DTO

> **Padre:** [`spec-v165-operational-identity-dto-2026-09-02.md`](./spec-v165-operational-identity-dto-2026-09-02.md).  
> **Estado:** **CERRADA** — partida **V1.64** (`cbe89c8`).

| ID  | Entrega                                    | Estado |
| --- | ------------------------------------------ | ------ |
| D0  | spec/plan V1.65 + CURRENT_SYSTEM V1.64     | DONE   |
| P0a | PositionState.decisionId TS+Python + birth | DONE   |
| P0b | POV + lineage sin alias + tests DEC≠TP     | DONE   |
| P0c | Python POV + HTTP operationalView + hook   | DONE   |
| P1  | GP-V162-04 fix + relevo/arranque           | DONE   |
| R1  | pre-flight                                 | DONE   |

## Orden

1. Identidad TS+Python (GP-V165-01)
2. POV builder + lineage (GP-V165-02..03)
3. Python POV + DTO HTTP (GP-V165-04..06)
4. Test CTA + docs cierre (GP-V165-07..08)
5. Pre-flight + relevo

## No hacer

LIVE · bump package · Alembic · LISTA→GRÁFICO · Why · E2E Mercado real · quitar fallback cliente.
