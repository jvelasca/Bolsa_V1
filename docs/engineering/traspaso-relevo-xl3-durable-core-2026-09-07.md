# Traspaso de relevo — V2.12 XL-3 durable core (handover agente)

Fecha: 2026-09-07 · Rama: `live-honesty-post-tip-2026-09-07` (HEAD 6c780ecc)
Repo root: `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`
Shell: Windows/powershell → **NO usar `&&`** en la Shell (usar `;`).
Tooling: `uv` (Python), vitest en `packages/shared`.

> Pega todo el contenido de este archivo en el nuevo agente como primer mensaje.
> Instrucción del usuario: «continuar hacia la v2.12 pero en un nuevo agente»
> y «dame el texto exacto y el link al texto. El nuevo agente debe tener siempre claro lo que queda por hacer».

---

## RESULTADO de la faena (YA implementado y verificado — TODO COMPLETADO)

Se construyó el núcleo durable XL-3: tabla `live_orders` (PG) + store + poller de
recovery de UNKNOWN vía `query_broker` (sin re-POST, fail-closed), preservando el
slice síncrono XL-2 (fill → execute_trade). Se hereda de la faena `xl3-wire`
prevista en `docs/engineering/` para el mismo día.

1. **`LiveOrderRow`** en `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`
   — tabla `live_orders`, PK `order_id`, + `account_id/status/venue/instrument_id/side/
quantity/filled_quantity/remaining_quantity/venue_order_id/intent_id/
financial_apply_count/created_at/updated_at`; índices `(account_id,status)` y `updated_at`.

2. **Migración `packages/py/infrastructure/alembic/versions/020_live_orders.py`**
   — `revision="020_live_orders"`, `down_revision="019_outbox_position_fifo"`,
   idempotente con guards `_table_exists`/`_index_exists` (estilo 013/017), sin imports ORM.

3. **`PostgresLiveOrderStore(session)`** + helpers `live_order_to_row_fields` /
   `live_order_from_row` + `list_unknown(limit)` en
   `packages/py/application/src/bolsa_application/live_order_store.py`.
   Se amplió el Protocol `LiveOrderStore` y `InMemoryLiveOrderStore.put` a
   `account_id: str | None`.
   ⚠️ Convención real del repo: la clase fila se importa DESDE
   `bolsa_infrastructure.database.models.tables` DIRECTO, NO vía `models/__init__.py`
   (SubmitIntentRow/OperationalIncidentRow tampoco se re-exportan ahí).
   → Por eso NO se re-exportó `LiveOrderRow` en `__init__.py` (el punto 1 del plan
   pedía re-export, pero no es la convención real; no introducir el drift).

4. **Worker `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`**
   — `start_live_order_recovery_worker`(env `LIVE_RECOVERY_WORKER_ENABLED`) →
   `live_order_recovery_worker_loop` → `_drain_once`(=Postgres) /
   `_drain_unknowns`(agnóstico al store, testable) / `resolve_one_unknown`.
   Fail-closed: sin query client o `unavailable`/intraducible → la fila QUEDA UNKNOWN
   y refresca `updated_at`; resolución legal → persiste transición. NUNCA re-POSTea
   ni sintetiza `execute_trade`.

5. **Wiring** — `scheduler_worker._event_loop_starters()` incluye ahora
   `start_live_order_recovery_worker`; y en
   `apps/api-python/src/bolsa_api/api/dependencies.py` (`get_confirm_intent_use_case`)
   se inyecta `live_order_store=PostgresLiveOrderStore(session)`.

6. **Dominio**: `account_id: str | None = None` añadido a `LiveOrder` en
   `packages/py/analytics/src/bolsa_analytics/cognitive/live_order.py`, y su espejo
   TS `accountId?: string | null` en `packages/shared/src/cognitive/live-order.ts`
   (propagado en build/transition/to_dict y `live_order_from_row`).
   `LiveOrderCoordinator.persist_after_submit` (en
   `packages/py/application/src/bolsa_application/confirm/live_order_sync.py`) ahora
   deriva la cuenta de `intent.account_id` y hace `store.put(target, account_id=...)`.

7. **Tests nuevos**: `packages/py/application/tests/test_live_order_store_pg.py`
   (contrato store InMemory+PG con AsyncMock, mapping domain↔fila con account_id,
   unique-violation rollback, list_unknown, parity migration/model + cadena
   down_revision) y `apps/api-python/tests/test_live_order_recovery_worker.py`
   (drain resolviendo → FILLED/PARTIAL sin execute_trade; no-client/unavailable →
   se queda UNKNOWN; respeta grafo no-re-POST).
   También se actualizó `apps/api-python/tests/test_scheduler_worker.py` para incluir
   el nuevo starter en el set esperado.

---

## Qué queda por hacer (PENDIENTE / SIEMPRE claro)

1. **Commit de esta faena** (ver TEXTO DE COMMIT SEGURO abajo). No está committeado.
   4 archivos nuevos sin trackear, 7 modificados.
2. **`alembic upgrade head` contra una PG real** para validar la migración 020
   (NO pude: requiere base PostgreSQL. `--sql` offline falla porque la migración `001`
   usa `conn.scalar`, que MockConnection no soporta — limitación preexistente).
   Verificado en su lugar: la migración 020 carga (`revision`/`down_revision` OK) y
   hay parity-test de columnas modelo↔migración.
3. **Continuar agenda V2.12** (scope out de esta faena / extension set V2.12):
   `list_open_orders`, `cancel_order`, idempotencia-de-mock-hardening.
   Persistente: NO tocar (PARKED honest-boundary):
   - Real XTB query client (`LiveOrderQueryPort` real queda gated/PARKED):
     no existe `GET /orders/{venueOrderId}` (audit Hallazgo 3).
   - `PARTIAL/FILLED → execute_trade`/ledger (XL-2 sync preservado).
   - UI / `result["liveOrder"]` surface (UI freeze; faena aparte).

---

## Archivos de esta faena (11)

MODIFICADOS (7):

- `apps/api-python/src/bolsa_api/api/dependencies.py`
- `apps/api-python/src/bolsa_api/workers/scheduler_worker.py`
- `apps/api-python/tests/test_scheduler_worker.py`
- `packages/py/analytics/src/bolsa_analytics/cognitive/live_order.py`
- `packages/py/application/src/bolsa_application/confirm/live_order_sync.py`
- `packages/py/application/src/bolsa_application/live_order_store.py`
- `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`

NUEVOS (4):

- `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`
- `apps/api-python/tests/test_live_order_recovery_worker.py`
- `packages/py/application/tests/test_live_order_store_pg.py`
- `packages/py/infrastructure/alembic/versions/020_live_orders.py`

NOTA: `confirm_recommendation.py` NO está tocado (se revirtió a HEAD para respetar el
test `dex4_orchestrator_module_is_thin` de <1100 líneas, verde en 1099).

---

## Verificación ya pasada

- 93 tests verdes: store PG, submit_intent_store_pg, confirm_broker_adapter,
  confirm_crash_restart, dex4_confirm_orchestrator, dex5_operational_invariants,
  or5_broker_execution_scenarios, operational_readiness, live_execution_runtime,
  analytics `test_live_order`, recovery_worker, scheduler_worker.
- ruff `check` OK en ficheros no-legacy. mypy OK en los módulos clave.
- ruff `format` NO aplicado en whole-file a `tables.py` ni legacy (drift preexistente; evita ruido).

---

## TEXTO DE MANO / COMMIT (copia exacta para el nuevo agente)

### TEXTO DE MANO

Pega todo lo anterior (resultado + pendientes + archivos) añadiendo esta nota de herramientas:
NOTA herramienta: usa code references `startLine:endLine:filepath` sólo para código confirmado.
NO edites los `.jsonl` logs (`apps/api-python/logs/*.jsonl`, `packages/py/application/logs/estudio_auto_propose.jsonl`)
ni las ediciones extranjeras (e2e, docs) pendientes. Arranca leyendo el estado real
(`git status` + `git diff --stat HEAD`) antes de proponer, para no alucinar.

### TEXTO DE COMMIT SEGURO

Antes de commitear, valida el árbol y sube SOLO los 11 archivos de esta faena. NO incluyas
`.jsonl` logs ni ediciones extranjeras (e2e/doc) pendientes. Commit atómico del núcleo durable LX-3.

1. Confirma estado:

```
cd "C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1"
git status --short
git diff --stat HEAD
```

2. Revisa si hay otros archivos modificados fuera de mi faena (debe ser exactamente los 11 listados arriba).
3. Stage SOLO esos 11 (git add con paths explícitos; NUNCA `git add -A` ni add de todo). Luego:

```
git status --short        # verifica staged == 11 y que jsonl/docs/e2e ajenos NO están staged
git diff --cached --stat
```

4. Commit con mensaje alineado al estilo del repo (mira `git log --oneline -10`; se usa español/conventional):

```
git commit -m "V2.12 XL-3 durable core: live_orders PG + UNKNOWN recovery worker (query_broker, no re-POST)"
```

(ajusta cuerpo si el repo usa body multilínea; observa commits previos). 5) NO hagas push salvo que el usuario lo pida. Reporta el hash + `git status` final.

Regla de oro: si `git status` no coincide con la lista de 11, DETENTE y reporta el excedente antes de stagear.

FIN DE TRASPASO
