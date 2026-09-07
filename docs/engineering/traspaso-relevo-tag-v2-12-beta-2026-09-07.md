# RELEVO — tag v2.12-beta → XL-3 durable core (2026-09-07)

> **Padre:** [relevo XL-3 durable core](./traspaso-relevo-xl3-durable-core-2026-09-07.md) · [roadmap LIVE Execution](./roadmap-live-execution-core-2026-09-07.md) · [honesty bridge XTB](./honesty-pack-xtb-bridge-external-2026-09-07.md).  
> **Estado:** tip `v2.12-beta` → commit de release formal (package `1.41.0-beta`). Partida tip previo: `v2.11-beta` → `80e891c4` / `1.40.0-beta` (**inmutable**).

## Cinco verdades

| Verdad          | Valor                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------- |
| Product         | `V2.12` — XL-3 durable core (`live_orders` PG + UNKNOWN recovery)                           |
| Git tag         | `v2.12-beta` → commit de release formal de la V2.12                                         |
| Package         | `1.41.0-beta` (**bump** desde `1.40.0-beta`)                                                |
| Tip previo      | `v2.11-beta` → `80e891c4` · **no retaguear**                                                |
| Motor / capital | **sin** thaw venue · **sin** LIVE capital · execute **off** · cancel broker real **PARKED** |

## Release

| Pieza   | Valor                                                                        |
| ------- | ---------------------------------------------------------------------------- |
| Tag tip | `v2.12-beta`                                                                 |
| Package | `1.41.0-beta`                                                                |
| CI tip  | Release-tag CI según run sobre este tag (stamp tras `conclusion`)            |
| Pack    | [relevo XL-3 durable core](./traspaso-relevo-xl3-durable-core-2026-09-07.md) |

## Hecho

- Tabla `live_orders` (PK `order_id`) · migración `020_live_orders` idempotente (down `019_outbox_position_fifo`).
- `PostgresLiveOrderStore` durable cross-PID (put/get/delete/list_unknown/list_open_orders/cancel_order) · mapeo dominio↔fila con `account_id`.
- Worker `live_order_recovery_worker` relee `UNKNOWN` y resuelve vía `query_broker` (**no re-POST**; fail-closed; nunca sintetiza ledger). Wiring `scheduler_worker` + `dependencies` (PG sync).
- OR-6 fail-closed: live recon no medido → **`LIVE_BLOCKED`**; adapter `None` → `live_adapter_not_wired`.
- Sandbox VIRTUAL: sin `LIVE_EXECUTION_UNLOCKED` → cero POST bridge; kill switch reconsultado en adapter.
- Tests: store PG (InMemory+PG AsyncMock) · recovery worker · dominio analytics `test_live_order` · operational_readiness/ops_self_eval · shared TS parity. Verdes en el entorno de auditoría.
- Docs: CHANGELOG `[1.41.0-beta]` · help-as-of `2026-09-07e` · relevo durable core.

## Freeze (post-tip)

NO LIVE capital · LIVE estudio = VIRTUAL/SIMULADO · `LIVE_EXECUTION_UNLOCKED` default off · `PAPER_D_EXECUTE` default off · Confirm = firma · **no** re-POST desde UNKNOWN · **no** cancel broker real (PARKED) · package `1.41.0-beta` · tip `v2.12-beta` · **no** settlement · **no** Accept estricto · **no** thaw venue.

## Next

- Stamp CI tip (Release-tag CI) → `CERTIFICABLE` cuando el run sobre el tag sea `success`.
- Auditor externo: auditar el **tag `v2.12-beta`** · package `1.41.0-beta` —— ya **NO** `main` desactualizado: main refleja V2.12 (fast-forward).
- Pendiente dominio: real XTB `GET /orders/{venueOrderId}` (query) y round-trip real de cancel (PARKED, audit Hallazgo 3).
