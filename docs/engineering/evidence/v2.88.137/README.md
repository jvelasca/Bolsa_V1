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

### 6.1 Ventana PAPER — estado medido al cerrar el sello (2026-10-16)

Ledger local (`operability_runs/window-runs/ledger.jsonl`, artefacto **no** versionado):

| día | estado | régimen |
| --- | --- | --- |
| `20261014` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261015` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261016` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |

`medidos=0 · veto=3 · declarados=0 · duros=0` ⇒ gate **`NO_MEDIDO`**: la ventana sigue
**`0/4 días`, `0/2 episodios`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. No es un fallo: el mercado veta LONG
(23 `trend_down` / 7 `range` / 5 `trend_up` sobre los 35 valores del ESTUDIO el `2026-10-16`) y el
eje operativo es el **más conservador** del watch. **No** se fuerza el régimen ni se toca ADR-046.

Bundle `v2_100` del día (`operability_runs/daily-evidence/20261016/`): `P1 INCONCLUSIVE (0/0/0)` ·
`P2 0/35` · `P3 0` · **`P4 CERRADO`** (`venue paper`, envs LIVE ausentes, `0` trazas LIVE).

**Continuidad del entorno (medida, no supuesta).** La BD de desarrollo se recreó durante la
remediación de `v2.88.136` (drop + create para esquivar el tope de columnas de
`sim_fill_finance_context`), así que el `preflight` de la ventana fallaba **duro**
(`watch ESTUDIO vacío (status='empty')`), **no** como veto. El entorno se re-sembró con los **casos de
uso del producto**, no a mano:

- **Catálogo + barras + ESTUDIO:** `SubscribeMarketIndex('IBEX35', sync_bars=True, years_back=2)` ⇒
  **35** instrumentos y **17 854** barras `1d` reales de Yahoo (+ lista de catálogo `ibex35`), y
  `estudio = ibex35` con `SqlAlchemyListRepository.update`. El `preflight` vuelve a funcionar
  (`watchSource: estudio`, `barsLoaded: 35`).
- **Cuenta fija de la ventana** `1484e253d2d54645945a6b1d7` (`PAPER-VENTANA-a9c515`, `simulated`,
  `active`): re-sembrada con **el MISMO id documentado** —precedente idéntico del `2026-10-02`,
  [`arranque-ventana-paper-operativa-2026-09-27.md`](./arranque-ventana-paper-operativa-2026-09-27.md)
  §0.2— usando el constructor del repo (`create_simulated_account`, `initial_deposit=100000.0`) y
  forzando **solo** el id de la cuenta ⇒ **1** cartera de inversión + **1** asiento de depósito.
- **Par A/B:** `ops_seed_window_pair.py --account-id … --version-a v283-window-a --version-b
  v283-window-b` ⇒ `v283-window-b` creada (`PAPER-WINDOW sma_crossover`), `EdgeReport` de **A** y de
  **B** y el localizador de promoción por cuenta (`promoted=true`, **no** gate-certificada:
  `pairActive` ⇒ «par **sembrado**»), con watch derivado de **20** símbolos del catálogo.

**Verificación read-only tras la re-siembra:** `estudio: ok · 35` valores · **35** instrumentos con
**17 854** barras `1d` · cuenta `('1484e253d2d54645945a6b1d7', 'PAPER-VENTANA-a9c515', 'simulated',
'active')` con **1** cartera y **1** asiento · `v283-window-b = PAPER-WINDOW sma_crossover` · **1**
localizador de promoción · **2** `edge_reports`.

**Pendiente del operador para el primer día OPERABLE** (no afecta a ningún día vetado: un veto se
registra sin forward ni API): (1) reiniciar la API **desde el árbol pineado** —el readiness es
schema-aware, así que la API vieja contra la BD ya migrada responde `503` y el `run-day` aborta con
`API_NOT_READY`, que **no** es veto—; y (2) declarar en `.env` `PAPER_D_ACCOUNT_ID=1484e253d2d54645945a6b1d7`
y `BROKER_VENUE=paper` (el runner de la ventana ya inyecta `BROKER_VENUE=paper` en el hijo).

---

## 7. Cierre POST-TAG — tag `v2.88.137-beta` y su CI de etiqueta

El tag (**anotado, unsigned**) se publica sobre el commit cuyo **pin PAPER casa con su árbol** —no
sobre el commit del sello—. Motivo (fail-closed): el gate `pnpm window:freeze` del job `shared`
compara los **dos tree hashes** del pin con `HEAD:apps`/`HEAD:packages`; en el commit del sello el pin
aún cita el árbol **previo** ⇒ taggearlo deja su propio CI en `TREE_MOVED` (runbook P1-P4 §4).

### 7.1 Primer intento (`736c0bf3`) — `lifecycle-pg` ROJO por el fixture del sello `BY_FILL`

`Release tag CI` — run [`38865153082`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38865153082):

- Job `shared`: **VERDE** — `window:test` + `window:freeze` (**`freeze OK`**) ⇒ el pin casaba con el
  árbol del tag (el objetivo de comprobación del plan).
- Job `lifecycle-pg`: **ROJO** en
  [`test_auto_fill_cycle_seal_pg.py`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py)
  `::test_by_fill_release_is_driven_by_the_persisted_cycle_context`, en el step **#8** del job
  (`Pytest lifecycle PG + auth + golden …`; `1 failed, 221 passed`), con
  `AssertionError: con contexto persistido la liberación debe ser BY_FILL (real=OPEN)`.
- Resto **VERDE**: `frontend`, `python` (ruff/imports/mypy/pytest offline), `security (gitleaks)`,
  `dr-verify`, `a7-gate`, `decision-spine`, `replay-repro`, `playwright` (mock E2E, integrated axe,
  integrated AUTO S5); `playwright (integrated E2E, opt-in)` **skipped** por diseño. El job
  `certify` falló **como consecuencia** (`Fail if any required job failed`), no por un hallazgo
  propio: al abortar el step #8 los pasos posteriores del job `lifecycle-pg` quedaron `skipped` y sus
  guardas anti-skip (`Fail on skipped …`) se declararon en fallo.

**Causa raíz (medida; NO es contaminación entre tests ni ruido del runner).** El `instrument_id` del
test es **aleatorio por corrida** (`inst-sealpos-<hex10>`) y el ruido del venue depende solo de
`(seed, side, instrument_id)`: `_filling_seed` devolvía el **primer** seed con fill, que es **PARCIAL**
en ~**12%** de los prefijos medidos (200 muestras ⇒ 24 parciales; lotes de **50.0** y **73.5** sobre
100). Con un fill **parcial**, `ReservationLedger.release` **escala** las dimensiones y **conserva** la
reserva **VIVA** (`status` sigue `OPEN`, la cola es capital comprometido), que es el comportamiento
**declarado** del camino caliente
(`AutoSimulationWorker._v2_release_reservations_for_fill`); por tanto el assert
`status == "RELEASED_BY_FILL"` **no aplica** a un llenado parcial.

La instrumentación **provisional** del reconciliador (revertida antes del commit) lo dejó por escrito
en el caso que falló: `live=1 mine=True aged=True measurable=True facts=2 meas=COMPLETE
in_flight_len=0 fill_qty=73.5 resremaining=100.0` ⇒ la decisión era liberar y **liberó**… pero
**parcialmente**. La lista **exacta** de tests del mismo step **#8** del job, ejecutada en local
**por sí sola**, reproduce el rojo sobre BD fresca (`1 failed, 217 passed, 4 errors` — los errores,
por migración ausente sin el paso `alembic upgrade head`), así que no hacía falta ninguna
contaminación de orden ni la suite completa para verlo.

### 7.2 Remedio y re-sello — el tag se mueve al commit re-anclado

| paso | commit | contenido |
| --- | --- | --- |
| fix del fixture | `7ac1d999` | `_filling_seed(require_full=True)` exige `status == "filled"` (llenado **TOTAL**) + assert explícito del discriminador y `filled_total == _QTY` |
| re-anclaje del pin | `0303cd47` | `pnpm run window:pin -- --note …` ⇒ `apps d706f132` / `packages 19099646`, `freeze OK` (`scripts/` no participa del freeze) |

**Medido localmente:** **300/300** instrumentos aleatorios tienen seed de llenado **COMPLETO** en el
barrido `<500` y la suma del schedule es **exacta** (`100`); el fichero del sello **25/25 verde**
(antes ~12% de rojo por corrida); la lista **exacta** del step **#8** del job `lifecycle-pg` queda
**`222 passed / 0 failed`** sobre BD fresca migrada (`055_dia_d_identity_nullable`) — el mismo step
que en CI daba `1 failed / 221 passed`.

El tag `v2.88.137-beta` (anotado, **unsigned**; objeto de tag `cb592357`, commit `0303cd47`) se
**movió** de `736c0bf3` al commit re-anclado `0303cd47` —precedente idéntico del sello `v2.88.136`
(`71d366e5` fix → `c3bccf88` POST-TAG con el tag movido)—, que pasa el gate fail-closed
`window:freeze`.

**`Release tag CI` — run [`38871657998`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38871657998)
(tag movido a `0303cd47`): VERDE** — `2026-10-16T08:07:57Z` → `08:22:27Z` (~**14m30s**);
**13 jobs `success` + `certify` `success`** y `playwright (integrated E2E, opt-in)` **`skipped`**
(declarado). Evidencia decisiva del re-sello:

- **El job que fallaba, ahora VERDE:** `lifecycle-pg` **`success`** (`08:08:43Z` → `08:14:59Z`) con
  el step **#8** (`Pytest lifecycle PG + auth + golden …`) **`success`** y **las 10 compuertas
  anti-skip posteriores** (`Golden Day 2.0`, `account-isolation gate V2.15.4`, `AUTO universe
  coverage + DÍA-D trace + daily watch ESTUDIO + PAPER window + ESTUDIO chain`, `Crash/Recovery Day`,
  `Concurrent AUTO`, `HardKill recovery`, `crash injection matrix`, `multiprocess AUTO`) **`success`**
  — ya **no** quedan `skipped` colgando del aborto del step #8.
- **El gate fail-closed, VERDE:** en `shared` (`08:08:01Z` → `08:08:33Z`) pasan `window:test`,
  **`Window freeze gate (pin == HEAD:apps/packages)`** y los guardas del runner de ventana ⇒ `freeze
  OK` sobre el árbol del tag movido (era el objetivo de comprobación del plan).
- **`replay-repro` REPRODUCIDO:** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`
  (`3 340 728` bytes, sello en CRLF, veredicto `REPRODUCIDO (mismo CONTENIDO)`) — **idéntico** al del
  `Release tag CI` verde de `v2.88.136`: el remedio del fixture y el re-anclaje del pin **no** movieron
  el artefacto congelado ⇒ **`Δ decisión = 0`** medido, no declarado.
- **`python`** (ruff/imports/mypy/pytest offline), **`frontend`** (`contract:check` incluido),
  **`security (gitleaks)`**, **`dr-verify`**, **`a7-gate`**, **`decision-spine`**, `playwright`
  (**mock E2E**, **integrated axe**, **integrated AUTO S5**) y `certify` **`success`**.
- **Sigue ABIERTA y declarada** la intermitencia del arranque en frío de `S5-04`: intento 0
  **`failed` en `63.80s`** (los `60.00s` son de espera de la evidencia de la sesión LAB) e intento 1
  **`passed` en `6.04s`** (`delta primero-retry 57.76s`) — **el mismo fenómeno ya declarado en
  `v2.88.136`** (allí `64.96s` → `7.33s`), con `timeouts`/`retries`/`ADR-046` **sin tocar**.

**Δ producto del remedio = 0.** Solo cambian el **fixture del test** y el pin (`scripts/`): no se toca
motor, umbrales ADR-046, contrato HTTP ni migración; la ventana PAPER real (ADR-046) sigue
**`INCONCLUSIVE`** (`0/4 días`, `0/2 regímenes`, `0/32 ciclos`; ledger: `medidos=0`, `veto=2` por
`BEAR_TREND` ⇒ `NO_MEDIDO_REGIMEN`).
