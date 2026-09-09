# DECISIÓN OWNER — Deuda P3 del núcleo C2, ACEPTADA como riesgo medido (2026-09-09)

> Sigue a [`auditoria-v2-15-1-c2-2026-09-08.md`](./auditoria-v2-15-1-c2-2026-09-08.md) y
> [`audit-interno-lectura-v2-14-2026-09-08.md`](./audit-interno-lectura-v2-14-2026-09-08.md).
> **Criterio de cierre elegido por el owner:** los frentes P3 que apuntan a código del
> **núcleo financiero congelado** (FSM/reconcilers/DR activos) **NO se tocan en esta
> elevación**. Se acepta el riesgo P3 como **riesgo medido** y se registra este documento
> por ítem (ruta:línea, riesgo, motivo de deferimiento, condición de reapertura). Cero
> riesgo de regresión por no alterar caminos congelados que hoy viven bajo single-owner.

---

## 1. Marco de la decisión

- Repo base de trabajo: `main` en `021671a6` (relevo posterior documenta iso **GREEN** v2.16-beta en `39b16f4a`; los "3 fallos de scope" del relevo de elevación fueron **residuo entre pasos lifecycle-pg**, no bug).
- Los defectos **vivientes** ya corregidos en sesiones recientes (inyectar antes de auditar): ver §3.
- Este fichero recoge únicamente la **deuda P3 aceptada** surgida de `auditoria-v2-15-1-c2` + `audit-interno-lectura-v2-14` y que reside en el **núcleo congelado**.

---

## 2. Deuda P3 ACEPTADA — por ítem

### `V2.15.1-C2-07` · P3 · columnas muertas en `live_orders` (bicefalía DB-vs-mecanismo)

- **Riesgo:** columnas `attempt_count` / `last_error` / `claim_expires_at` declaradas
  (`migración 022_live_orders_exec.py`, ORM `tables.py` `LiveOrderRow`) sin ningún
  escritor en `packages/py|apps|scripts`. El reclaim usa únicamente
  `recovery_worker_id`/`recovery_claimed_at` +
  `LiveOrderRow.recovery_claimed_at <= stale_before`
  (`live_order_store.py::claim_unknown_batch` L579-593). No corrompe dinero; es deuda de
  telemetría (no hay `attempt_count` incrementado) y de **coherencia de schema**.
- **Motivo de deferimiento:** eliminar las columnas exigiría una migración Alembic nueva
  (romper coincidente con guard/head y con la cadena DDL vigente de V2.14), o añadir un
  escritor = ampliar superficie de un mecanismo de recovery **sin runtime LIVE demos de
  comportamiento**. No aporta valor certificable con el núcleo congelado.
- **Condición de reapertura:** cuando se arma el runtime LIVE real (A7) o se toque
  `live_order_store` / migración del ciclo; entonces se decide eliminar
  `claim_expires_at`/`attempt_count`/`last_error` o darles uso real con telemetría.

### `V2.15.1-C2-09` · P3 · `test_live_order_store_pg.py` es AsyncMock, no real-PG (nombre engañoso)

- **Riesgo:** el nombre sugiere cobertura real-PG del store/machine de live-orders, pero es
  un "mapping stub, sin DB" con `AsyncMock`. La cobertura real-PG del claim
  (`FOR UPDATE SKIP LOCKED`, unión sin solape) vive en `test_live_order_recovery_concurrency_pg.py`.
- **Motivo de deferimiento:** convertir el test a real-PG real es añadir un job/ fixture →
  es **esfuerzo de evidencia/CI**, no cierre de un defecto; con PG local limitado y núcleo
  congelado no justifica ampliar la batería en esta pasada. (La observación en sí es
  verídica y queda registrada.)
- **Condición de reapertura:** en un ciclo que toque `live_order_store` o el job `lifecycle-pg`;
  entonces renombrar/re-forcar el test o migrar su cobertura al real-PG.

### `V2.15.1-C2-10` · P3 · reconciliadores detect-only y matiz epsilon/Decimal

- **Riesgo:** varios reconcilers (`reconcile_live_ledger.py`, `reconcile_portfolio_integrity.py`,
  `reconcile_lifecycle_integrity.py` L340 `abs(pos.remaining - rem_lc) > 1e-6`) convierten a
  `float()` y comparan con tolerancia `1e-6`, mientras la cadena financiera se valida
  Decimal-exacto en M2/`test_crash_consistency.py`. Riesgo bajo, **inherente a la tolerancia
  float**, y los reconcilers son **detect-only sin auto-heal** (correcto).
- **Motivo de deferimiento:** endurecer a comparación Decimal-exacta en caminos de
  reconciliación detect-only puede producir falsos positivos al cambiar de representación
  numérica en un núcleo congelado validado ya con Decimal en M2. No aporta cierre de riesgo
  vivo: ningún reconciler muta; solo abre incidente → DEGRADED/BLOCKED.
- **Condición de reapertura:** al tocar `reconcile_*` (p. ej. por el runtime LIVE/A7) usar
  un helper de comparación Decimal con tolerancia explícita solo donde la fuente sea flotante
  del venue; mantener exactitud donde ambas fuentes son Decimal.

### `V2.15.1-C2-11` · P3 · FSM lifecycle/esquinas `position_state` permisivas pero dormidas

- **Riesgo:** aristas no vetadas — `domain/lifecycle/__init__.py` (arista `open→T1_EXECUTED`
  directa legal; el tiempo solo lo valida si existe `T1_TRIGGERED`) y
  `_advance_target_leg` (`position_state.py::86-105`) no fuerzan `pending→triggered→executed`
  ni impiden `failed→executed`. Solo `executed` es terminal/sticky. **Ningún call-site de
  producción alimenta `failed` o un `open→T1_EXECUTED` sin T1_TRIGGERED** → esquinas dormidas,
  solo unit-tested.
- **Motivo de deferimiento:** endurecer las transiciones es tocar el **dominio FSM congelado**
  (núcleo financiero, adn solo unit-tested hoy). Cambiarlo de forma estricta podría
  rechazar caminos que el ciclo productivo legítimo usa y que aún no se han explorado en
  runtime LIVE. Riesgo > beneficio con núcleo congelado.
- **Condición de reapertura:** si en una certificación LIVE/A7/M2 emerge un `failed→executed`
  o un `open→T1_EXECUTED` real (por contra del single-owner actual), endurecer el invariante
  junto con test que modele el camino legítimo.

### `V2.15.1-C2-03` · P3 (observación) · mensajes "head 023" hardcodeados en DR tooling

- **Riesgo/ubicación:** `scripts/db-restore.mjs` L218 y L236 loguean literalmente
  "Alembic aplicado a head (023)" / "…⇢ head 023" como constante, mientras la autoridad de
  schema en runtime es `provenance.schema_revision`. Deuda de consistencia de logs/herramientas,
  no de comportamiento.
- **Motivo de deferimiento:** es un script de DR (restore destructivo) cuya verificación de
  head real ya ocurre en otro punto vía autoridad; hardcodear el log no altera la restauración.
  Cambiarlo implica revisar la fuente única de head en `.mjs` sin tocar la ruta crítica de DR
  en esta pasada.
- **Condición de reapertura:** al evolucionar la cadena de restore/test (job `dr-verify`) hacer
  que el log consuma el head resuelto (p. ej. `provenance.schema_revision` o la variable ya
  usada por la autoridad) en lugar de la constante.

### `V2.15.1-C2-04` · P3 (observación/runtime) · provenance cacheada a 1 entrada fija `expected_head` de por vida

- **Riesgo/ubicación:** `provenance.py` `@lru_cache(maxsize=1)` → `build_provenance()`
  congela `expected_head` al primer acceso del proceso; si `_read_db_schema_revision()` no
  resuelve devuelve `None` y `/health/ready` degrada a 503 (fail-closed correcto). Observación
  de robustez, no fallo activo.
- **Motivo de deferimiento:** tocar el cache implica cambiar el comportamiento de readiness
  (posible re-lectura de schema en cada health check) que toca `/health` y el `dr-verify` del
  CT; riesgo de ampliar el alcance. El estado actual es correcto y defensivo.
- **Condición de reapertura:** si en runtime hubiera upgrade en vivo con proceso largo que
  exigiera re-resolver el head tras un alembic upgrade sin reinicio; entonces re-evaluar.

---

## 3. Estado global de los frentes (para la auditoría externa)

**CERRADOS (ya implementados y verificados; solo queda commitear):**

| Frente                                                                    | Cierre                                                  | Verificación                                          |
| ------------------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| P1-02/03 owner default (`set_default_account`/`delete_simulated_account`) | fix owner-scope + `for_purge`                           | iso PG 43 verdes; reproducción PG ok en sesión previa |
| v2.16-beta iso (3 §6 reales)                                              | residuo entre pasos → limpiado; iso GREEN en `39b16f4a` | relevo actual sobre `021671a6`                        |
| Auditoría 2 (fill_unseen tapado por cancel en `live_drift`)               | snapshot merge idempotente por firma                    | e2 PG + unit verdes (esta sesión)                     |
| Auditoría 3 (consentimiento del operador en dos fases de ExecutionEvent)  | `apply_pending_execution` (fase 2 separada)             | unit verdes (esta sesión)                             |

**ACEPTADOS P3 (núcleo congelado, no tocar)** — §2 completo (C2-07/09/10/11 + C2-03/04).

**DEUDA FUERA DE ESTE ALCANCE (no bloqueante; no toca el núcleo):**

- 3er medio off-site del backup 3-2-1 sin automatizar (`guia-off-site-3er-medio-2026-09-09.md`).
- Retención off-site sin estado propio (poda remota `retentionPrune` local-only).
- Cola `[runtime/aislamiento]` LIVE A7 (replay idempotente post-crash + doble-writer cancel):
  exige PG real / 2 workers / broker real; NO LIVE certificado.

FIN DE LA DECISIÓN — Deuda P3 del núcleo C2 aceptada como riesgo medido y registrada por
ítem (ruta:línea · riesgo · deferimiento · condición de reapertura). Núcleo congelado NO se
modifica. Estado global listo para elevar y auditar externamente.
