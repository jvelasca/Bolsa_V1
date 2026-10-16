# Respuesta a la auditoría AUDITORIA3 — sello `v2.88.137-beta` (2026-10-16)

> **Sello:** `v2.88.137-beta` · package `2.11.137-beta` · Alembic `055_dia_d_identity_nullable` (**sin migración nueva**).
> **Base:** `v2.88.136-beta` más la remediación AUDITORIA2 (commit `fc0808aa`).
> **Naturaleza:** producto/operación acotado — **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**).
> **Evidencia:** [`evidence/v2.88.137/README.md`](./evidence/v2.88.137/README.md) · **CHANGELOG:** [`CHANGELOG.md`](../../CHANGELOG.md) · **Estado:** [`CURRENT_SYSTEM.md`](./CURRENT_SYSTEM.md) / [`PROJECT_STATE.md`](./PROJECT_STATE.md).

---

## 1. Identidad del sello (qué es y qué no es)

`v2.88.137-beta` es un incremento **de remediación y operación**, no de agenda ni de motor. Cierra los dos pendientes que AUDITORIA2 dejó **explícitamente declarados** (worker del OUTBOX y gate de release) y consolida, en un único bump, la remediación AUDITORIA2 ya comiteada.

- **No** toca el motor de decisión ni umbrales ⇒ **`Δ motor = 0`**.
- **No** amplía endpoints: el componente nuevo de `/health` viaja en el `dict[str, ComponentHealthDto]` existente ⇒ **`Δ contrato HTTP = 0`**.
- **No** añade migración: la tabla `alert_deliveries` ya existía (migración `054`); el head sigue `055` (de la remediación AUDITORIA2).

---

## 2. Respuesta punto por punto

### Hallazgo 5 (OUTBOX de alertas) — **CERRADO**

**Estado previo:** *Parcialmente corregido.* La entrega ya no se perdía (tabla OUTBOX `alert_deliveries` con estados, backoff y dead letter), pero el **único** disparador era `POST /signal-alerts/deliveries/process`, diseñado para un cron **externo**. Sin ese cron desplegado ni supervisado, una entrega fallida **no** se reintentaba tras la barra inicial; y no había métrica de `RETRYABLE_FAILED` ni **alerta** sobre `DEAD_LETTER`.

**Cierre:**

| Sub-punto | Artefacto |
| --- | --- |
| Driver **periódico** interno (no depende de cron externo) | [`alert_delivery_worker.py`](../../apps/api-python/src/bolsa_api/background/alert_delivery_worker.py) · registrado en [`scheduler_worker`](../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py) |
| Intervalo configurable, **on-by-default** | `ALERT_DELIVERY_WORKER_INTERVAL_SECONDS` (default 15s) · `ALERT_DELIVERY_WORKER_ENABLED` |
| **Métrica** de `RETRYABLE_FAILED` | contador por tick + componente `alert_outbox` en `/health` |
| **Alerta** sobre `DEAD_LETTER` | WARNING por fila en el worker + `alert_outbox` en `degraded` |
| Reintento garantizado e idempotente | claim con lease (`FOR UPDATE SKIP LOCKED`) de `ProcessAlertDeliveries` (ya existente) |

El endpoint manual permanece como disparador **adicional** (útil para operación puntual), pero **ya no es el único**. No toca la decisión: sólo reintenta entregas **ya encoladas**.

### Hallazgo 6 (SSRF por DNS rebinding) — **CERRADO** (base `fc0808aa`, incluida en este bump)

La validación resolvía el DNS y luego la conexión **volvía a resolver**, dejando la ventana de rebinding (TOCTOU). Ahora `resolve_public_webhook_target` **devuelve** las IPs validadas y `_dispatch_webhook` conecta **directamente por IP**, fijando `Host` y `sni_hostname` originales, **sin** segunda resolución. Guardia falsable con `MockTransport`.

### Huecos DÍA-D `UNKNOWN != 0` — **CERRADO** (base `fc0808aa`)

Migración aditiva **`055_dia_d_identity_nullable`**: `instrument_id`/`symbol` pasan a `NULLABLE`; el caso de uso deja de coercionar `None → ""`; el DTO de respuesta pasa a nullable. `None` viaja de extremo a extremo y se distingue de `""`.

### Hallazgo auto-declarado (gate `window:freeze` en CI) — **CERRADO**

El gate existía en el runner local pero **no** se ejecutaba en el CI de release. Ahora el job `shared` de [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) ejecuta `pnpm window:freeze` (fail-closed: `TREE_MOVED` tumba el job). Sólo dispara por tag `v*`/manual ⇒ el pin está re-anclado al árbol del sello.

---

## 3. Qué certifica / qué NO

**Certifica:** el OUTBOX de alertas se **drena periódicamente** con reintentos y backoff; la métrica de `RETRYABLE_FAILED` y la **alerta** de `DEAD_LETTER` son observables en logs y `/health`; el SSRF por DNS rebinding está cerrado; los huecos DÍA-D `UNKNOWN != 0` están cerrados; y el sello no puede publicarse con el pin PAPER desviado.

**NO certifica:** la **operabilidad real** de la ventana PAPER (ver §5), la **rentabilidad**, ni un modelo **multi-tenant** (el aislamiento por `account_id` es defensa, no promesa multi-tenant).

---

## 4. Verificación reproducible

- `ruff` **limpio** · `lint-imports` **4 kept / 0 broken** · `mypy` **0 errores / 555 ficheros**.
- `test_alert_delivery_worker` + `test_scheduler_worker` + `test_health` **verdes**; `test_dia_d_bump_guard` **1 passed**.
- `pnpm --filter @bolsa/web typecheck` **OK** · `contract:check` **OK**.
- `pnpm run window:freeze` → **`freeze OK`**.
- **CI de etiqueta:** `Release tag CI` [run **`38871657998`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38871657998) **VERDE** (~14m30s; **13 jobs `success` + `certify` `success`**; `playwright (integrated E2E, opt-in)` `skipped`) con el job `shared` (**gate `window:freeze`**) **verde**, `lifecycle-pg` **verde** (step #8 + 10 compuertas anti-skip) y `replay-repro` **REPRODUCIDO** (`sha256 1E3ADAC2…929A37E7`, idéntico al de `v2.88.136` ⇒ `Δ decisión = 0` **medido**). El tag se **movió** a `0303cd47` (commit con el pin re-anclado) tras remediar un **falso rojo** del sello `BY_FILL` del primer intento ([run `38865153082`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38865153082)): su fixture aceptaba un fill **parcial** (~**12%** de las corridas, porque el `instrument_id` es **aleatorio**) y una reserva parcial **sigue viva** (`OPEN`) por diseño ⇒ el helper ahora exige **llenado TOTAL** (`7ac1d999`). **No** se relajó ningún umbral ni se tocaron `timeouts`/`retries`/`ADR-046`.

---

## 5. Ventana PAPER (ADR-046) — **`INCONCLUSIVE`** (se declara, no se fuerza)

La ventana PAPER real sigue en **`0/4 días`, `0/2 regímenes`, `0/32 ciclos`** ⇒ **`INCONCLUSIVE`**. Lo que falta es **OPERACIÓN**, no software: este sello **instrumenta** y **endurece** pero **no** acredita la ventana ni demuestra rentabilidad. **No** se toca ADR-046, ni umbrales, ni el motor.

---

## 6. Límites declarados (sin fabricar)

- La métrica del OUTBOX es **observabilidad** (logs + `/health`), **no** un backend Prometheus (no hay esa infraestructura en el repo).
- El worker reintenta entregas encoladas; no crea señales ni altera umbrales.
- Tag **unsigned**.
