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

## Resultado del subagente auditor externo (read-only, 2026-09-07)

Se ejecutó una auditoría de solo lectura del delta `b9b35ec2..6e279e2d` + pilares del tronco (concurrency, integridad, cancel, UNKNOWN, reconcile, incident, kill-switch). No se ejecutaron tests (estática).

- **Sin P0 ni P1**. Ningún hallazgo bloquea apertura LIVE, salta Decision Spine, fabrica estados terminales sin confirmación del venue, ni corrompe libros financieros.
- A–G veredictos ✅ con matices y estos hallazgos nuevos:

### Hallazgo N-1 — P2 (refina P2-1): `execution_router` paper_auto/dry-run SÍ vuelca exit/reduce por `check_opening` con kill_switch

`signal_kind_to_trade_type` mapea `exit`/`reduce`→`trade_type="sell"` y el guard unificado llama `check_opening(..., signal_kind=..., kill_switch=await effective_kill_switch())`; en `check_opening` el primer `if kill_switch` no está envuelto por `kind not in _EXIT_SIGNAL_KINDS`. No es bug activo de dinero (live real dry-run/PARKED, paper_auto demo), pero si mañana un exit/reduce real pasa por ese router con kill switch activo, quedaría DENY (no deja salir). Recomendación futura: alinear con `_EXIT_SIGNAL_KINDS` o test «exit bajo kill switch NO DENY».

### Hallazgo N-2 — P2 (informativo): suggestion de reconcile CANCEL_REQUESTED repetida

En `live_order_machine_reconcile.py`, branch cancel, cuando la máquina local YA está `CANCEL_REQUESTED` y el broker confirma `cancelled`, se vuelve a sugerir `CANCEL_REQUESTED` (no `CANCELLED`). Read-only/sin auto-heal → la máquina puede quedar presentada como «in-flight» una orden que el broker tiene muerta hasta que otra capa la pase a CANCELLED. No fabrica dinero. Falta en test el caso `CANCEL_REQUESTED`local→broker cancelled.

### Hallazgo N-3 — P3 (nuevo): `resolve_one_unknown` sin bump cuando la transición lanza

Si `transition_live_order` lanza (filled fuera de 0..quantity / remaining<0) la excepción se captura en `_drain_unknowns`, no se llama `_refresh_unknown`/`put`, y la fila queda `UNKNOWN` SIN bump de `updated_at` → puede hilar el poll repetidamente (thrashing en partial con conflicto de cantidad). Fail-closed correcto; riesgo de reintento sin progreso.

### Hallazgo N-4 — P3: NUMERIC(18,6) como única fianza → IntegrityError en persistencia de filas mal construidas

`live_order_from_row` pasa NUMERIC→Decimal 6dp; una fila ya a 6dp que no satisfaga la suma lanzará CHECK en el primer put (IntegrityError→fail-closed). Refuerza P3-1.

### Dictamen sobre deuda anotada original

- **P2-1**: correcta en el hecho; exposición algo mayor a la narrada (ver N-1). Sigue P2 defensivo.
- **P2-2**: correcta y reproducible (`put` select→insert sin ON CONFLICT; ante IntegrityError rollback/raise; `sync_opening_incidents` get_active→put sin guard; [execution_router.py:417, opening_permission.py:217] bajo `uvicorn --workers N`). No corrompe.
- **P3-1**: real en adversarial venue-reporting, pero **sobreestimado** en el flujo actual de PARTIAL: la máquina **recomputa `remaining=quantity−filled` en Decimal 6dp** y no persiste el `remaining` float del broker; el riesgo queda acotado a si `quantity` local difiere del real o a futuras escrituras que no pasen por `transition_live_order`.
- **P3-2**: correcta (confirmado).

Este adendo se incorporó tras el commit `0a217468` (registro en un commit posterior de la rama `v2-13-1-rc-honesty-remediation`).

## Conclusión

No hay P0/P1. El núcleo V2.13 elevado (concurrency / cancel honesta / UNKNOWN no-re-POST / reconcile fail-closed read-only) y los tres pilares ampliados evaluado en `main` cumplen la deuda previamente listada. Las observaciones P2/P3 quedan anotadas como deuda menor antes de una certificación "V2.13 completa" externa.

(fin)
