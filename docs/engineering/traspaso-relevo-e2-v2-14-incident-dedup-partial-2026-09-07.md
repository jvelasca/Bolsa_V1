# Traspaso de relevo — E2 V2.14 PARTIAL (dedup incident OPEN multi-worker)

Fecha: 2026-09-07 · Rama `v2-14-financial-execution` · Repo. Sigue a E1.

> ⚠️ **ESTADO: E2 NO CERRADO.** Este es el trozo entregado dentro de E2 (P2-2), con el resto
> pendiente y descrito en §Remanente. NO marcar E2 completo.

---

## Hecho en este trozo E2 (P2-2 — dedup de OPEN en OperationalIncidentStore PG)

`packages/py/application/src/bolsa_application/operational_incident_store.py` →
`PostgresOperationalIncidentStore.put`: al insertar una Open fresh cuyo `(account_id, kind)` activo ya
existe (por otro worker), el partial-unique activo colisiona con IntegrityError. Antes eso **re-lanzaba**
(segundo poller podía romper). Ahora:

- tras rollback, se re-consulta `get_active(account, kind)`;
- si ya hay un activo competidor → se trata como **OPEN deduplicado** (return, sin 2ª fila, sin
  auto-heal ni cierre) — ambos pollers quedan apuntando al MISMO incidente (semántica 1 OPEN por
  `(account,kind)` activo, que es justo el invariante del índice);
- si tras el vencedor NO hay activo → colisión real → re-raise.

Verificado ruff 0 y los 20 tests unitarios de incidentes (deamond dex3/analytics) siguen verdes.

## Remanente de E2 (NO cerrado — para el agente siguiente)

1. **Full account/position/cash/exposure reconciliation del machine (P1-02)**: extender
   `reconcile_live_ledger.py`/máquina a comparar posiciones broker↔local (v.g. AAPL 120 vs 100) y
   `XtbBridgePosition.quantity` Decimal (B1 ya decimal) → drift/incidente; nuevo DENY OR-4 de apertura.
2. **Durable máquina-order drift (P2-01)**: `LiveOrderDrift` solo loguea hoy; falta un writer que abra
   incidente durable `live_drift` por cuenta tras drift real (reusar `sync_opening_incidents`/OR-4),
   cableado en el recovery worker bajo go; y su test PG 2-sesión.
3. P2-2 parte PG con dos sesiones concurrentes (el corte actual se probó semánticamente; falta el
   determinista 2-session sobre PostgreSQL real, en la batería C1).

FIN (PARTIAL) DE TRASPASO E2
