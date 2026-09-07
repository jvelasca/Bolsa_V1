# Deuda anotada — audit ampliado V2.13 (2026-09-07)

Registro de hallazgos **P0/P1 = ninguno**. Observaciones P2/P3 del audit ampliado sobre `main` tras fusionar V2.13 (head `6e279e2d`). Comparativa realizada sobre código real, no sobre doc.

Guardar como **deuda menor** (no bloquea ejecución LIVE en el estado actual). No se ha corregido nada en esta sesión: solo anotación.

---

## Contexto

- Release-tag CI del tag `v2.13-beta` (ramificado en `6e279e2d`): **GREEN real** — run `34124260037`, certify `success`, artefacto `"status": "GREEN"`.
- Delta `main..v2-13-1-rc-honesty-remediation` elevado a `main` en fast-forward (26 ficheros).
- Audit ampliado (fuera de los 26 ficheros del delta) sobre tres pilares de la deuda previa: **Reconciliation**, **OperationalIncident**, **Kill switch**.
- Modo: registrar, sin corregir ni enlazar aquí desde el índice de engineering.

## P2

### P2-1 — `check_opening`: `kill_switch` sin la exclusión de `_EXIT_SIGNAL_KINDS`

- Archivo: `packages/py/application/src/bolsa_application/risk_engine.py`
- El docstring declara que el gate "no aplica a `exit`/`exit_hint`/`reduce`". Freshness / mandate / recon / incident guardan esa exclusión (`if kind not in _EXIT_SIGNAL_KINDS and …`), **pero el primer `if kill_switch: return DENY("kill_switch_active")` es incondicional** (no consulta `_EXIT_SIGNAL_KINDS`).
- Estado actual: no hay ruta de cierre/reduce que invoquen `check_opening` con kill switch (los cierres van por Confirm/fill/adapter y `XtbBridgeOrderSubmitAdapter.submit`). No es un bug activo de dinero.
- Riesgo defensivo: si mañana una reducción/exit pasara por `check_opening`, el kill switch lo vetaría (impediría salir) — opuesto al fail-safe esperado "kill switch frena aperturas, no impide cerrar".
- Sugerencia futura: alinear la primera guarda con `_EXIT_SIGNAL_KINDS` (o documentar y blindar con test que un exit no queda DENY por kill switch).

### P2-2 — `OperationalIncidentStore.put`: doble-worker OPEN sin idempotencia ante IntegrityError

- Archivo: `packages/py/application/src/bolsa_application/operational_incident_store.py`
- El `PUT` hace select→insert (camino OPEN) y captura `IntegrityError` rollback→raise **sin tratar el caso "la fila ya existe"** (no usa `ON CONFLICT`/skip_locked).
- La migración `014` crea el índice parcial **UNIQUE** `(account_id, kind)` sobre `status IN ('open','in_review','resolved')`. Por diseño esto fuerza 1 fila no-cleared por `(account,kind)` y la reapertura exige pasar a `cleared` (bloquea reabrir mientras quede un `resolved` no-cleared). Correcto a nivel de modelado.
- Riesgo: dos ticks/workers ejecutando `sync_opening_incidents` a la vez para el mismo `(account,kind)` pueden intentar `insert` concurrente → el segundo recibe `IntegrityError`. No corrompe (hay rollback), pero el llamador debe tolerar el raise o logueará una excepción de tick.
- Sugerencia: en OPEN, capturar `IntegrityError` → tratar como "ya existe, no-op" (reintentar leer/reusar la existente) o usar `ON CONFLICT DO NOTHING`.

## P3

### P3-1 — `providers._qty` float → `NUMERIC(18,6)` sin rounding explícito

- Archivo: `packages/py/market/src/bolsa_market/providers.py` (+ migración `021_live_orders_fin.py`).
- El adapter mapea `filled/remaining` del venue como `float`; la columna es `NUMERIC(18,6)` con CHECK `filled_quantity + remaining_quantity = quantity`.
- Riesgo: si un respondido PARTIAL del broker llega con más de 6 decimales o no suma exacta a `quantity`, el `INSERT/UPDATE` puede fallar por `IntegrityError` en persistencia (sin elisión previa).
- Sugerencia: validar con órdenes PARTIAL reales/fraccionales en el bridge mock/live; considerar redondeo/elisión determinista antes de persistir.

### P3-2 — `_constraint_exists` en migración 021 consulta `pg_constraint` global (sin schema/relname)

- Archivo: `packages/py/infrastructure/alembic/versions/021_live_orders_fin.py`.
- La query es `SELECT 1 FROM pg_constraint WHERE conname = :n` (sin filtrar por `relname`/schema). Guard de tabla previo reduce el riesgo, pero un constraint con el mismo nombre (convención `live_orders_*`) en otra tabla/schema matchearía por igual.
- Sugerencia: añadir filtro por `relname`/schema para robustez (bajo impacto hoy).

---

## Conclusión

No hay P0/P1. El núcleo V2.13 elevado (concurrency / cancel honesta / UNKNOWN no-re-POST / reconcile fail-closed read-only) y los tres pilares ampliados evaluado en `main` cumplen la deuda previamente listada. Las observaciones P2/P3 anteriores quedan anotadas como deuda menor antes de una certificación "V2.13 completa" externa.

(fin)
