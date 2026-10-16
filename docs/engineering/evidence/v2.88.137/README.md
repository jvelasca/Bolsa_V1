# Evidencia `v2.88.137-beta` — mejoras AUDITORIA3 (worker del OUTBOX de alertas + observabilidad `/health` + gate `window:freeze`) sobre la remediación AUDITORIA2

> **Bump:** `2.11.136-beta` → **`2.11.137-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **de producto/operación acotado** (backend + observabilidad + CI + documentación) — **no** toca el motor de decisión, umbrales ni el contrato HTTP, y **no** amplía endpoint alguno. · **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**: el componente nuevo de `/health` viaja en el `dict[str, ComponentHealthDto]` existente) · **SIN migración nueva** (head `055_dia_d_identity_nullable`, de la remediación AUDITORIA2). Tag **unsigned**.
>
> **Base:** `v2.88.136-beta`.
>
> **Alcance del modelo de cuentas:** **single-user/single-account**. No cambia con este sello.

---

## 0. Qué cierra (y qué NO)

| Hallazgo AUDITORIA3 | Estado | Qué se remedia |
| --- | --- | --- |
| **5 — worker del OUTBOX ausente** | **CERRADO** | `alert_deliveries` ya existía con backoff, pero **sólo** la drenaba un endpoint manual (cron **externo**). NUEVO worker periódico que la drena desde el proceso de crons. |
| **5 — métrica/alerta** | **CERRADO** | Métrica de `RETRYABLE_FAILED` y **alerta** sobre `DEAD_LETTER` expuestas en logs (WARNING por fila) y en `/health` (`alert_outbox`, `degraded`). |
| **6 — SSRF por DNS rebinding** | **CERRADO** (base `fc0808aa`) | La conexión del webhook se fija a la **IP ya validada** (sin segunda resolución DNS). |
| **Huecos DÍA-D `UNKNOWN != 0`** | **CERRADO** (base `fc0808aa`) | Migración `055` nullable + `None` de extremo a extremo. |
| **Gate `window:freeze` en CI** (hueco auto-declarado) | **CERRADO** | `pnpm window:freeze` en el job `shared` de `release-tag-ci.yml` (fail-closed). |

**NO cierra** (se declara): la **ventana PAPER real** (ADR-046) sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** — lo que falta es **OPERACIÓN**, no software. Este sello **no demuestra rentabilidad** ni acredita la ventana. La métrica del OUTBOX es **observabilidad** (logs + `/health`), **no** un backend Prometheus (no hay esa infraestructura en el repo).

---

## 1. Worker periódico del OUTBOX de alertas (hallazgo 5)

**Problema.** La entrega de una alerta ya **no** se perdía (vive en la tabla OUTBOX `alert_deliveries` con estados `PENDING`/`DELIVERED`/`RETRYABLE_FAILED`/`DEAD_LETTER`, backoff exponencial y lease). Pero **nadie la drenaba periódicamente**: el único disparador era `POST /signal-alerts/deliveries/process`, pensado para un cron **externo**. Sin ese cron desplegado ni supervisado, una entrega fallida no se reintentaba tras la barra inicial.

**Cambio.** NUEVO [`alert_delivery_worker.py`](../../../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py), patrón idéntico a [`lifecycle_outbox_worker`](../../../../apps/api-python/src/bolsa_api/background/lifecycle_outbox_worker.py):

- `_process_once()` ([L49](../../../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py#L49)) abre sesión, ejecuta `ProcessAlertDeliveries.execute(limit=50)`, hace `rollback` ante error, y **cuenta por desenlace**: `delivered` (`ok`), `retryable_failed` (`not ok and will_retry`), `dead_letter` (`not ok and not will_retry`).
- `alert_delivery_worker_loop()` ([L91](../../../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py#L91)) espera `ALERT_DELIVERY_WORKER_INTERVAL_SECONDS` (default `15s`) y registra un INFO estructurado por tick con los contadores; un error del tick se registra y **no** mata el bucle.
- `start_alert_delivery_worker()` ([L117](../../../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py#L117)) devuelve `None` si el worker está apagado.
- **On-by-default**: `_worker_enabled()` ([L44](../../../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py#L44)) se apaga con `ALERT_DELIVERY_WORKER_ENABLED` ∈ `{0,false,no,off}` (igual que el outbox de lifecycle: un reintento garantizado no puede depender de una variable ausente).
- Registrado en [`scheduler_worker._event_loop_starters()`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), que corre en el proceso dedicado de crons (`python -m bolsa_api.workers.scheduler_worker`), no en el lifespan de la API (evita duplicación con `--workers N`).

**Config.** NUEVO `alert_delivery_worker_interval_seconds` (`ALERT_DELIVERY_WORKER_INTERVAL_SECONDS`, default `15.0`) en [`config.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py).

**No toca la decisión.** El worker sólo reintenta entregas **ya encoladas**; nunca crea señales, no altera umbrales ni ejecuta órdenes. El endpoint manual permanece como disparador **adicional**.

---

## 2. Observabilidad: métrica y alerta (`/health` + logs)

- NUEVO `count_deliveries_by_status() -> dict[str, int]` en [`signal_alert_repository.py` (L333)](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/signal_alert_repository.py#L333) — `SELECT status, count(*) GROUP BY status` (read-only, sin ámbito de cuenta).
- NUEVO componente **`alert_outbox`** en `GET /api/health`: `_alert_outbox_component()` ([`health.py` L222](../../../../apps/api-python/src/bolsa_api/api/v1/routes/health.py#L222)) devuelve `details` en camelCase (`pending`, `retryableFailed`, `deadLetter`, `delivered`) y `status="degraded"` cuando `deadLetter > 0` (la **alerta**); `"ok"` en caso contrario. Un fallo de consulta se declara `degraded` con mensaje genérico (nunca filtra DSN ni la excepción cruda — respeta `test_health_redacts_internal_details`). Registrado en [`health_check` (L349)](../../../../apps/api-python/src/bolsa_api/api/v1/routes/health.py#L349).
- El worker emite un **WARNING explícito por cada `DEAD_LETTER`** (con `subscription_id`, canal, `delivery_id`, `attempt` y error) — una entrega que agota su presupuesto **nunca** se pierde en silencio.

**Sin contrato nuevo.** `components` es `dict[str, ComponentHealthDto]` en el esquema OpenAPI, así que añadir una clave **no** cambia el contrato (`contract:check` **OK**, sin `contract:gen`).

---

## 3. Gate `window:freeze` en el CI de release

El hallazgo auto-declarado era que `pnpm window:freeze` **no** estaba cableado en el CI: el gate existía en el runner local pero nada impedía publicar un tag con el pin PAPER desviado del árbol.

**Cambio.** Nuevo step en el job `shared` de [`release-tag-ci.yml` (L67)](../../../../.github/workflows/release-tag-ci.yml#L67), tras `pnpm window:test`: `pnpm window:freeze`. Si `HEAD:apps`/`HEAD:packages` no casan con `WINDOW_CONFIG`, el job **falla** (`TREE_MOVED`) — **fail-closed real**. El workflow sólo dispara por **tag `v*`** o `workflow_dispatch`, de modo que el pin ya está re-anclado al árbol del sello cuando el gate corre. Sólo toca `.github/`, que **no** participa del freeze ⇒ no mueve el árbol.

---

## 4. Base — remediación AUDITORIA2 (incluida en este bump, commit `fc0808aa`)

- **SSRF por DNS rebinding (hallazgo 6 AUDITORIA3) CERRADO.** `resolve_public_webhook_target` ahora **devuelve** las IPs validadas y `_dispatch_webhook` conecta **por IP** (fijando `Host` y `sni_hostname` originales, **sin** segunda resolución DNS). Guardia falsable con `MockTransport`: si el atacante cambia el DNS entre la validación y la conexión, el webhook **no** puede alcanzar la IP interna.
- **Huecos DÍA-D `UNKNOWN != 0` CERRADO.** Migración aditiva **`055_dia_d_identity_nullable`** relaja `instrument_id`/`symbol` a `NULLABLE`; el caso de uso deja de coercionar `None → ""`; el DTO de respuesta pasa a nullable (contrato regenerado). `test_055_dia_d_identity_nullable.py` + casos en las suites PG lo fijan.

---

## 5. Verificación

- **Estáticos canónicos:** `ruff` **limpio** · `lint-imports` **4 kept / 0 broken** · `mypy` **0 errores / 555 ficheros**.
- **Tests nuevos/actualizados:** [`test_alert_delivery_worker.py`](../../../../apps/api-python/tests/test_alert_delivery_worker.py) (contadores por desenlace + WARNING de `DEAD_LETTER` + gate on/off) · [`test_scheduler_worker.py`](../../../../apps/api-python/tests/test_scheduler_worker.py) (starter nuevo) · [`test_health.py`](../../../../apps/api-python/tests/test_health.py) (`alert_outbox` presente + `degraded` con `DEAD_LETTER` + `ok` sin él).
- **Guardián de bump:** `test_dia_d_bump_guard` **1 passed**.
- **Web/contrato:** `pnpm --filter @bolsa/web typecheck` **OK** · `contract:check` **OK** (sin contrato nuevo).
- **Operación:** `pnpm run window:freeze` → **`freeze OK`** (tras re-anclar el pin al árbol del sello).

---

## 6. Límites declarados (sin fabricar)

- La **ventana PAPER real** (ADR-046) sigue **`INCONCLUSIVE`** (`0/4 días`, `0/2 regímenes`, `0/32 ciclos`): falta **OPERACIÓN**.
- El worker **reintenta** entregas encoladas; no decide, no crea señales, no altera umbrales ⇒ **`Δ motor = 0`**.
- La métrica del OUTBOX es **observabilidad** (logs + `/health`), **no** Prometheus.
- Tag **unsigned**. Este sello **no demuestra rentabilidad**.
