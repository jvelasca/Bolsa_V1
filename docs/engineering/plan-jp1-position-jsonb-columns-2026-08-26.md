# Plan — JP-1 PositionState JSONB → SQL columns

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo VS-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código).** Alembic `012` + dual-write repo + modelo + test extract.
> **Relevo previo:** VS-1 venue selector.

---

## Objetivo

Promover escalares calientes de `position_state` JSONB a columnas SQL en `position_states` (filtro/index/consulta sin parse). Dual-write. JSONB sigue SoT para nested/advisory. **No** thaw `PAPER_D_EXECUTE`. **No** Redis venue.

## Decisiones

| ID  | Decisión                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Alembic **`012`** sobre `position_states` (`down_revision = 011_position_states`).                                             |
| D2  | Dual-write columnas nullable: `direction`, `current_stop`, `remaining_quantity`, `quantity`, `initial_stop`, `actual_entry`.   |
| D3  | JSONB `position_state` permanece SoT para nested/advisory; columnas = proyección hot.                                          |
| D4  | Backfill en migración desde JSONB (`direction`, `currentStop`, `remainingQuantity`, `quantity`, `initialStop`, `actualEntry`). |
| D5  | **No** tablas `paper_orders` / `execution_records`. **No** child `revisions`.                                                  |
| D6  | **No** `contract:gen` · **no** Prisma DDL. Manual types solo si API expone campos.                                             |
| D7  | Freeze: Confirm firma · VS-1/RV-1 intactos · `PAPER_D_EXECUTE` off · sin Redis venue.                                          |
| D8  | Dual-write en `insert` + `update_state` del repo; callers `persist_position_from_{fill,exit,protect}`.                         |

## Kernel

```text
position_state JSONB = SoT (nested/advisory)
columns = hot scalars (dual-write on every insert/update_state)
012: ADD COLUMN + backfill from JSONB camelCase keys
```

## Freeze

VS-1 · RV-1 · Confirm firma · `PAPER_D_EXECUTE` off · Redis venue parked · Prisma/`contract:gen` off.

## E1

Parked: thaw **estricto** · per-account venue · revisions child · paper_orders/execution_records DDL. Thaw stamp DEMO opt-in **cerrado** (docs/ops). Redis venue global = RV-1 cerrado.
