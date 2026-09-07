# Traspaso de relevo — B2 V2.14 (worker lease config + cancel honesta)

Fecha: 2026-09-07 · Rama `v2-14-financial-execution` · Repo `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`.

> Sigue a B1. Pega este texto al agente que continúe V2.14.

---

## RESULTADO B2

1. **Lease configurable por entorno (P2-04, parte real)** — `apps/api-python/src/bolsa_api/background/
live_order_recovery_worker.py`: la ventana del lease (`DEFAULT_CLAIM_STALE_SECONDS`, antes const fija 120)
   ahora se resuelve desde la env **`LIVE_RECOVERY_CLAIM_STALE_SECONDS`** (fallback fail-closed 120 para
   vacío/no-numérico/≤0) vía `_claim_stale_seconds_default()`. Sigue siendo override-able por parámetro en
   tests/llamadas (compatible con el ciclo `claim/lease` del recovery). +test `test_claim_stale_seconds_default_env_operations`.
2. **Observabilidad por-fila (P2-04, columnas)** — DIFERIDA intencionadamente a **E1** para mantener **una única
   migración nueva**. El repo fija head `021_live_orders_fin` con guards de fixture (exact-set) en lifecycle-pg;
   añadir columnas exige migración nueva y actualizar guards. E1 abrirá la migración que añade
   `attempt_count`/`last_error`/`claim_expires_at` a `live_orders` + tabla `execution_events`, validada al final
   contra PostgreSQL real (C1). DECISIÓN de secuencia: observabilidad y persistencia de intentos se entregan
   con el mismo salto de migración que ExecutionEvent (evita dos migrations sobre `live_orders`).
3. **XTB cancel REAL (P2-05)** — **PARKEADA honestamente** tras verificar `scripts/xtb-bridge-mock.mjs`:
   el bridge expone `POST /orders` y `GET /orders/{id}` pero **NO** `POST /orders/{id}/cancel`. No hay forma
   legítima de round-trip de cancelación hoy; forzarla sería inventar un endpoint inexistente del venue.
   Se mantiene el modelo honesto H5 (`CANCEL_REQUESTED` sin auto-promover a `CANCELLED`). El audit acepta este
   PARKED único. Desbloqueo cuando el venue/bridge exponga cancel.

## Verificación B2

- ruff 0 · mypy (worker módulo) no regresión · pytest `test_live_order_recovery_worker.py` **8 passed**
  (incluye el nuevo test de env config).

## Archivos B2

MOD (2): live_order_recovery_worker.py · test_live_order_recovery_worker.py. NUEVO: este traspaso. ÍNDICE #93.

## Remanente honesto

- Columnas `attempt_count/last_error/claim_expires_at` → entregadas en E1 (migración única) + C1 (PG).
- Real XTB cancel → PARKED hasta que el venue/sim exponga el endpoint.

FIN DE TRASPASO B2
