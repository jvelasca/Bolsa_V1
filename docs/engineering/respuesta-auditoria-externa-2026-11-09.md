# Respuesta a la auditoría externa del 2026-11-09 — cinco reparos y la causa raíz de los `attnum`

**Fecha:** 2026-11-09
**Objeto:** entrega de `2.11.186-beta` / árbol `c6cef5c9` (pin `apps 2675ed02…`, `packages 27df47…`)
**Estado:** cuatro reparos **aceptados y corregidos en el documento**; el quinto (horario de barras) se
**corrige en código hoy** (reintento del `POST`, puerta de barras y supervisor del stack, §5.5), sin tocar
`apps/` ni `packages/`. La tabla RANDOM/CSV está en
[control-entradas-aleatorias-2026-11-09.md](./control-entradas-aleatorias-2026-11-09.md) §1 y §1.1, y la
restauración del backup está medida en §3.4. Las salidas literales de todas las comprobaciones están en
[`evidence/cierre-auditoria-2026-11-09/`](./evidence/cierre-auditoria-2026-11-09/README.md).

| # | Reparo | Veredicto | Dónde |
| --- | --- | --- | --- |
| 1 | `stopFiredNotFilled` no es arrastre de ejecución | **Aceptado**; causa medida, no es reserva/lease/kill switch | §1 |
| 2 | El freeze y el parche chocan | **Aceptado** con una corrección: el evaluador del árbol medido **ya** usa ida y vuelta | §2 |
| 3 | La causa raíz de los 1.597 `attnum` sigue abierta | **Aceptado**: causa encontrada, y el 1.597 **no es reproducibly hoy** | §3 |
| 4 | Refactor y freeze en el mismo commit | **Aceptado**: es una corrida local, no CI; el tag de hoy lo confirma | §4 |
| 5 | `BarsSync` a las 17:40 con valores de EE. UU. | **Aceptado en el fondo, corregida la premisa**: el watch es europeo y la tarea sirve; el fallo real fue el API caído. **Corregido hoy** (§5.5) | §5 |

---

## 1. `stopFiredNotFilled`: posición desprotegida, no "arrastre"

### 1.1 La cuenta

Del ledger [`v2_93_2026-11-09.cycles.json`](../../operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json)
(192 ciclos, 182 emparejados):

| Medida | Valor |
| --- | --- |
| Ciclos con la marca `stopFiredNotFilled` | **27 / 192 (14,1 %)** |
| Pares con la marca | **26 / 182 (14,3 %)** |
| Pérdida extra media por ciclo afectado (real − sim) | **+0,3447 R** |
| Pérdida extra acumulada | **8,96 R** |
| Coste por ciclo sobre el total | **0,0492 R** |
| Sesgo total simulador − ledger | **+0,1314 R/ ciclo** |
| Peso de este grupo en el sesgo total | **37,4 %** |

Tus cifras (~9 R, ~0,05 R/ciclo, 13,5 %) quedan confirmadas. **El signo del sesgo es positivo: el
simulador es más optimista que el ledger** (sim -0,0558 R frente a real -0,1872 R). Por eso este informe
compara **relativos**, nunca niveles.

### 1.2 La causa no es reserva, lease, kill switch ni fuente de precio

Comprobado ciclo a ciclo en los 27:

| Hipótesis | Resultado medido |
| --- | --- |
| El decider no corre en el toque | **Falso**: `deciderRanOnTouch = True` en 27/27 |
| El stop no se evalúa | **Falso**: `stopEvaluatedOnTouch = True` en 27/27 |
| El stop dispara pero no se crea orden | **Falso** en los ticks disparados reales: `orderCreated = True` en todos |
| Veto o corte antes de `_v2_reserve_exit` | **Falso**: la orden de salida existe (ruta `materializado` en 24, `orden_creada_sin_fill` en 3) |

La orden **se crea**. Lo que falla es el **llenado**:

| Patrón | n | Lectura |
| --- | ---: | --- |
| Fill en un tick **posterior** (posición sobrevive al toque) | **24** | La orden nace, no llena y llena después |
| **Nunca** llena al stop; sale por `thesis_exit` | **3** | Posición desprotegida hasta la salida por tesis |

Desfase en filas del timeline desde el primer toque hasta el primer fill: mediana **1**, máximo
**15**; 4 casos llenan en un tick posterior **del mismo día**, 13 al tick siguiente.

Salidas finales de los 27: `structural_stop` **22**, `thesis_exit` **4**, `SIN_MECANISMO` **1**.

### 1.3 Un defecto de datos que infla la métrica

Hay **93 filas con `mark = 0.0` en 66 de los 192 ciclos (34 %)**. No son precios: son **barras ausentes
codificadas como 0**. `finite_number` las acepta y `mark <= stop` las cuenta como toque, así que
`stopTouchDays`, `firstTouchDay` y `maeR` salen inflados, y 10 de los 27 ciclos marcados tienen una
fila `mark = 0` como primer "toque". Esto no cambia la conclusión (en los ticks disparados reales
`orderCreated = True`), pero **sí contamina la métrica de toques** y hay que corregirlo: una barra
ausente debe ser `None`, nunca `0.0`.

### 1.4 Lo que esto bloquea

El stop del motor es una **salida sintética evaluada por tick**, no una orden en firme en el bróker:

- 24 ciclos: **riesgo de hueco de un día** entre el disparo y el fill.
- 3 ciclos: **posición desprotegida** hasta que llega la salida por tesis.

Con dinero real eso es inaceptable. Los requisitos no son "modelar el sesgo en el simulador"; son
operativos: stop en firme en el bróker por posición, invariante `protective_order_present` evaluada cada
tick, aperturas vetadas si falta la protección, y reconciliación de órdenes vivas. Queda como bloqueo
declarado, no como deuda de documentación.

---

## 2. Freeze y parche: aceptado, con una corrección

### 2.1 Lo que tienes razón en plantear

- Cambiar `config.py`, `roles.py`, `rate_limit.py`, `backtests.py` o `dia_d_equity_evidence.py` mueve el
  árbol y rompe el pin: **no se aplica durante la ventana**.
- El refactor y el parche en el mismo commit que el freeze es riesgo de regresión: **se separan**.

### 2.2 Lo que hay que corregir del informe: el evaluador del árbol medido ya está arreglado

El `minRoundTripCostBps` **no** es un falso fallo en el árbol que se va a medir. En
[`dia_d_equity_evidence.py`](../../packages/py/application/src/bolsa_application/dia_d_equity_evidence.py)
(raíz `c6cef5c9`) el veredicto recibe el coste de **ida y vuelta**:

```python
_at_least(
    "minRoundTripCostBps",
    getattr(policy, "min_round_trip_cost_bps", None),
    realized_cost_round_trip_bps,
),
```

y la conversión está aislada y documentada (`2 × per_side` más `2 × commission_bps` cuando la comisión
no viaja en el precio), con `realizedCostBpsPerSide` y `realizedCostRoundTripBps` publicados por
separado y una base declarada en `realizedCostBasis`. El propio docstring lo dice: pasar la medición por
lado era el bug de unidades. Ver
[errata-coste-ida-vuelta-dia-d-2026-11-08.md](./errata-coste-ida-vuelta-dia-d-2026-11-08.md).

Consecuencia: **el informe de la ventana no marcará un fallo espurio**. El riesgo aplica solo a
reevaluaciones con árboles anteriores.

### 2.3 Un agujero del freeze que sí hay que cerrar

`window-pin.mjs` compara **solo** `HEAD:apps` y `HEAD:packages`:

```javascript
function readActual() {
  const lines = git(['rev-parse', 'HEAD:apps', 'HEAD:packages']).split(/\r?\n/);
  const commit = git(['rev-parse', '--short=8', 'HEAD']);
  return { appsHash: lines[0], packagesHash: lines[1], commit };
}
```

Un parche **sin commitear** en `apps/` o `packages/` es invisible para `pnpm window:freeze`: daría
`freeze OK` con código que no es el pinneado. Cierre propuesto (`2.11.188-beta`, no en este release):
`git status --porcelain -- apps packages` no vacío ⇒ salir `1` con `TREE_DIRTY`, en el pin y en el
preflight. Esta noche se hace **a mano** y se deja la salida en el expediente.

### 2.4 Estado real de la ventana

`pnpm window:freeze` → `freeze OK (c6cef5c9)` con los árboles del pin. Pero el **gate está `STALE`**:
las cuatro jornadas medidas (`20261019`, `20261021`, `20261022`, `20261105`) arrastran
`apps_hash_no_congelado, packages_hash_no_congelado`. Son de árboles anteriores y se archivan como
`INVALID_TREE`; la ventana del árbol actual empieza hoy. Presentarlas como progreso sería el mismo error
que el `days 4/4` del `20261106`.

---

## 3. La causa raíz de los `attnum`: encontrada

### 3.1 La migración que recicla columnas

[`054_dia_d_verified_and_alerts.py`](../../packages/py/infrastructure/alembic/versions/054_dia_d_verified_and_alerts.py)
tiene guards en el `upgrade`, pero el `downgrade` **borra cuatro columnas** de
`signal_alert_subscriptions`:

```python
if _column_exists(_ALERTS, "processing_started_at"):
    op.drop_column(_ALERTS, "processing_started_at")
if _column_exists(_ALERTS, "processing_token"):
    op.drop_column(_ALERTS, "processing_token")
if _column_exists(_ALERTS, "processing_bar_timestamp"):
    op.drop_column(_ALERTS, "processing_bar_timestamp")
if _column_exists(_ALERTS, "signal_alert_subscriptions_account_id_idx"):
    op.drop_index("signal_alert_subscriptions_account_id_idx", table_name=_ALERTS)
if _column_exists(_ALERTS, "account_id"):
    op.drop_column(_ALERTS, "account_id")
```

PostgreSQL **no reutiliza** el `attnum` de una columna borrada (`attisdropped = true` ocupa slot hasta
recrear la tabla). Cada ciclo `downgrade` → `upgrade` deja **4 slots quemados**. Con ~400 ciclos se llega
a los 1.600: **exactamente el techo que reportaste**. La fuente es la suite de tests haciendo
`downgrade base` / `upgrade head` contra una base de desarrollo compartida, no un fallo de esquema
aleatorio.

**No es reproducible hoy:** `signal_alert_subscriptions` en `bolsa_v1` tiene `max_attnum = 21` y **0**
columnas borradas. Esa base se recreó o se restauró después del incidente. La deuda sigue en las otras
dos tablas que sí acumulan:

| Tabla | `max attnum` | `attisdropped` | % del techo (1.600) |
| --- | ---: | ---: | ---: |
| `auto_engine_runs` | **968** | **954** | **60,5 %** |
| `sim_fill_finance_context` | **915** | **902** | **57,2 %** |
| `sync_settings` | 527 | 516 | 32,9 % |
| `auto_engine_ticks` | 374 | 363 | 23,4 % |
| `decision_journal_entries` | 373 | 363 | 23,3 % |
| `research_trials` | 255 | 233 | 15,9 % |
| `strategy_promotions` | 200 | 189 | 12,5 % |
| `sim_auto_positions` | 179 | 165 | 11,2 % |

**Ninguna tabla supera 1.400**; el máximo es 968. El barrido se hizo sobre **todas** las bases del
contenedor y solo `bolsa_v1` pasa de 900.

### 3.2 El error de arranque que lo confirma

La API no arranca hoy sobre una base con el techo agotado:

```text
sqlalchemy.exc.OperationalError: (psycopg.errors.TooManyColumns)
tables can have at most 1600 columns
[SQL: ALTER TABLE signal_alert_subscriptions ADD COLUMN processing_started_at TIMESTAMP WITH TIME ZONE]
ERROR:    Application startup failed. Exiting.
```

Es el mismo mecanismo visto desde el otro lado: el `upgrade` vuelve a añadir columnas sobre una tabla
cuyos slots ya están quemados.

### 3.3 Arreglo propuesto (no en este release)

1. **Guard de esquema** que salte con `max(attnum) > 1.200` **o** `attisdropped > 0,5 × max(attnum)`.
   Un umbral de solo `attnum` no basta: `auto_engine_runs` tiene 968 y 954 borradas.
2. **Reconstrucción** de las tablas afectadas (`CREATE TABLE … LIKE … INCLUDING ALL` + copia
   + renombrado) en ventana de mantenimiento, con verificación de FKs, índices y recuento de filas.
3. **Aislar los tests**: ningún test que haga `downgrade`/`upgrade` puede apuntar a `bolsa_v1`; cada uno
   usa su base scratch. Hoy conviven varias (`bolsa_c1_scratch`, `bolsa_v1_e2e`, `bolsa_ev_a_new`…).
4. **Un solo migrador**: `db-ensure` declara "migraciones al día — skip" y a la vez la API migra al
   arrancar. Dos migradores sobre la misma base es parte del problema.

### 3.4 El backup: probado, y con un hallazgo

Se restauró `operability_runs/backups/pre-window-2026-11-09.dump` (**124 576 003 bytes**, formato
**custom**, mtime `2026-11-09 10:00:19`) en una base vacía:

```powershell
docker exec bolsa-postgres createdb -U bolsa scratch_restore
cmd /c "docker exec -i bolsa-postgres pg_restore -U bolsa -d scratch_restore --no-owner --no-privileges --exit-on-error < operability_runs\backups\pre-window-2026-11-09.dump"
```

`pg_restore` terminó con **exit 0** en 24 s: el fichero **no está corrupto y restaura**. La cabecera del
archivo (`pg_restore -l`) confirma qué se volcó:

```text
; Archive created at 2026-11-09 09:00:08 UTC
;     dbname: bolsa_v1
;     TOC Entries: 381
;     Format: CUSTOM
```

Es decir, el dump se escribió a las **10:00:08 local** sobre `bolsa_v1` — pero `bolsa_v1` estaba
**entonces** en el esquema `038` y con 1.037 runs. La verificación de contenido no cuadra con la base de
ahora, y la diferencia es material:

| Medida | `bolsa_v1` (11:35) | `scratch_restore` del dump pre-window | Lectura |
| --- | ---: | ---: | --- |
| `alembic_version` | `066_account_evidence_policy` | **`038_research_trials_param_region`** | 13 migraciones por detrás |
| Tablas en `public` | 91 | **78** | faltan las tablas de las migraciones 039-066 |
| `auto_engine_runs` | 1038 | **1037** | falta el run de `2026-11-09 09:04 UTC` (10:04 local) |
| `paper_forward_results` | 0 | 0 | igual |
| `ohlcv_bars` | 226 780 | **226 780** | igual (no hubo ingesta entre ambos) |
| `decision_journal_entries` | 44 313 | **44 313** | igual |
| Último run en la tabla (UTC) | `2026-11-09 09:04:25` | `2026-11-08 20:26:53` | el dump es anterior al run de la mañana |

**Conclusión honesta:** el dump restaura, pero **no es una copia de la base actual**: se escribió a las
10:00:08 local y en ese instante `bolsa_v1` estaba **13 migraciones por detrás** (039-066) y sin el run de
las 10:04 local. Un DR con ese fichero exigiría `alembic upgrade head` (lo hace el arranque de la API) y
perdería ese run.

Por eso se tomó un dump **nuevo y verificado** a las 11:38 (`window-ready-2026-11-09.dump`, 124 636 279
bytes; cabecera `Archive created at 2026-11-09 10:37:50 UTC`, 453 entradas TOC) y se restauró en otra base
vacía con el mismo comando:

| Medida | `bolsa_v1` | `scratch_restore` del dump nuevo | Veredicto |
| --- | ---: | ---: | --- |
| `alembic_version` | `066_account_evidence_policy` | `066_account_evidence_policy` | **igual** |
| Tablas en `public` | 91 | 91 | **igual** |
| `auto_engine_runs` | 1038 | 1038 | **igual** |
| `paper_forward_results` | 0 | 0 | **igual** |
| `ohlcv_bars` | 226 780 | 226 780 | **igual** |
| `decision_journal_entries` | 44 313 | 44 313 | **igual** |
| `instrument_list_items` (`estudio`) | 80 | 80 | **igual** |

`scratch_restore` se borró después (`dropdb`). **El backup pre-window no sirve como punto de restauración
del árbol actual; el `window-ready` de las 11:38 sí, y está verificado fila a fila en las cinco tablas
críticas.**

---

## 4. Refactor del worker y freeze en el mismo commit

Lo que hay registrado en [dividir-worker-auto-2026-11-08.md](./dividir-worker-auto-2026-11-08.md):

| Comprobación | Resultado |
| --- | --- |
| `pytest apps/api-python/tests` | **1.805 passed, 7 skipped** |
| `pytest packages/py/{domain,market,application,analytics}/tests` | **5.094 passed, 5 skipped** |
| Identidad método a método por AST | **185 / 185 idénticos** |
| `pnpm window:freeze` | `freeze OK` |

**Lo que no puedes asumir:** es una corrida **local**, no CI. La rama `docs/post-tag-v2.88.186` es local
y GitHub no tiene ningún run de `cc1775de`. Y el `window:freeze` del informe es el chequeo HEAD-only del
§2.3. La confirmación fuerte será el job `shared` (`window:freeze`) y el job `python` del tag de
auditoría de hoy: si el tag pasa verde sobre los árboles de `cc1775de`, la afirmación deja de ser local.
Hasta entonces, la ventana se apoya en evidencia local y así se declara.

---

## 5. Horario de las tareas y barras incompletas

### 5.1 Estado de las tareas

| Tarea | Hora | Última ejecución | Último resultado |
| --- | --- | --- | --- |
| `BolsaV1_StackReady` | **17:33** | — (registrada hoy 11:31) | — |
| `BolsaV1_StackReadyLate` | **18:25** | — (registrada hoy 11:31) | — |
| `BolsaV1_BarsSync` | **17:40** | 2026-11-08 17:40 | **1 (fallo)** |
| `BolsaV1_WindowForward` | **18:30** | 2026-11-08 18:30 | 0 |
| `BolsaV1_WindowWatch` | **20:20** | 2026-11-08 20:20 | 0 |

Las cinco se **re-registraron hoy a las 11:31** con `WakeToRun=true` y sin bloqueo por batería (§5.5).

Las cinco hacen `cd /d` a la **raíz** del repo, no al worktree del sello. Con el alcance de este release
eso es lo correcto (el árbol medido es la raíz), pero los documentos que dicen "desde el sello
`a5013f75`" están desfasados y se corrigen.

### 5.2 El fallo del `BarsSync` no era de barras ni de esquema: el API estaba caído

`BarsSync` no toca la base de datos. Su único trabajo es un `POST` a
`http://127.0.0.1:8000/api/sync/queue/enqueue-stale`; si el API no responde, el runner sale `1` por
diseño. Desde hoy lo intenta tres veces antes de rendirse:

```532:546:scripts/window-forward-runner.mjs
    const retry = attempt < SYNC_BARS_MAX_ATTEMPTS && shouldRetrySync(result);
    logError(
      SCOPE,
      `sync-bars: ${detail}` +
        (retry
          ? ` — reintento ${attempt + 1}/${SYNC_BARS_MAX_ATTEMPTS} en ${SYNC_BARS_RETRY_DELAY_MS / 1000} s`
          : attempt === 1
            ? " — NO se reintenta (fallo de configuracion)"
            : " — sin mas reintentos"),
    );
    if (!retry) return 1;
    await new Promise((resolve) => setTimeout(resolve, SYNC_BARS_RETRY_DELAY_MS));
  }
  return 1;
```

Y eso es exactamente lo que pasó el 2026-11-08 a las 17:40 (`logs/agent/events.log`):

```text
{"at":"2026-11-08T16:40:01.558Z","level":"error","scope":"window",
 "message":"sync-bars: no se pudo llamar al API (http://127.0.0.1:8000/api/sync/queue/enqueue-stale): fetch failed"}
```

El stack de desarrollo estaba caído: el log de esa sesión se corta a las **17:24:08** sin línea de
parada y el siguiente arranca a las **18:22:35** con `Application startup complete`. Fue **domingo**
(`NON_MARKET_DAY`), así que no se perdió medición. **No fue `TooManyColumns`**: ese error es de hoy a las
09:15 y ya no bloquea (head `066`, tabla con `max(attnum) = 21` y **0** columnas borradas).

El patrón se repite desde octubre (`fetch failed` el 10-24, 10-25, 10-26, 10-27, 10-31, 11-01 y 11-08;
un `500` el 11-04). La causa raíz operativa es **que el API no esté arriba a la hora de la tarea**, no la
ingesta.

### 5.3 El horario es correcto para el watch real, y por eso el fallo importa

**Corrección al informe anterior:** el `run-day` **no** mide los 7 valores de EE. UU. del universo de
control. Se lanza con `--watch-from-estudio` y su universo es la lista `Estudio`: **80 instrumentos, todos
europeos** (`BME`, `XETRA`, `FR`; 40 por versión).

| Lista | Miembros | Mercados |
| --- | ---: | --- |
| `S&P 100` | 100 | EE. UU. (`UNKNOWN`) |
| **`Estudio`** (watch del forward) | **80** | **BME, XETRA, FR — sin EE. UU.** |
| `Euro Stoxx 50` | 49 | BME, XETRA, FR |
| `IBEX 35` | 35 | BME |

Verificado en `instruments`: `AI`, `NOKIA` y `OR` **sí existen**, con `yahoo_symbol` `AI.PA`,
`NOKIA.HE` y `OR.PA`, y barras hasta **2026-11-06**. La afirmación de que faltaban era errónea: lo que
falta es normalizar `exchange` (**129 de 197** instrumentos en `UNKNOWN`), no los símbolos.

Con esa composición, el calendario de `expected_last_daily_bar`
([`market_calendar.py`](../../packages/py/market/src/bolsa_market/market_calendar.py)) da, a las 17:40
del lunes:

| Mercado | Miembros | Barra esperada a 17:40 | Se encolan |
| --- | ---: | --- | ---: |
| ES | 48 | 2026-11-09 | 48 |
| DE | 16 | 2026-11-09 | 16 |
| FR | 16 | 2026-11-09 | 16 |
| US | 100 | 2026-11-06 (aún 11:40 en NY) | 0 |
| **Total** | **180** | | **80** |

Así que la tarea de las 17:40 **sí sirve** para el watch: el drenaje medido es de ~2-3 ítems/minuto, o
sea **30-40 min para 80**, y terminaría hacia las **18:10-18:20**, antes del `run-day` de las 18:30.

**Y por eso el fallo de las 17:40 es crítico:** si la tarea cae, el único respaldo es el scan propio del
`auto_sync_worker` (cada 30 min, `scan_interval_minutes = 30`), que a las 18:03 arranca **antes** del
post-cierre europeo de 17:35… y el siguiente ya no llega. El `run-day` de las 18:30 se quedaría sin las
barras del día.

### 5.4 Lo que sí queda pendiente (y no bloquea hoy)

| Hecho | Consecuencia |
| --- | --- |
| **0** barras de `2026-11-09` en `ohlcv_bars`; **180** de `2026-11-06` | Normal a las 11:00: el cierre europeo es a las 17:30 |
| Sin barra del día, `OhlcvPriceSource.execution()` devuelve `None` y el símbolo queda en `HOLD` | **Fail-closed**: se pierde el turno, no se opera con precio rancio. No hay fallback a `B-1` |
| Los 7 valores de EE. UU. tienen barra de `2026-11-06` | Irrelevante para el watch actual; **bloqueante** si se añaden al forward: a las 18:30 su barra de hoy no existe por construcción |
| `BBVA` (`NYQ`) con última barra `2026-11-02`; 16 instrumentos `BMAD` sin ninguna barra | Fuera de las listas: no entran en el scan ni en el watch. Deuda declarada |
| `sync_queue`: **963 completed, 0 pendientes** | No hay atasco; el fallo del 11-08 no dejó residuo |

### 5.5 Arreglo aplicado hoy (solo `scripts/` y `docs/`; `apps/` y `packages/` intactos)

1. **Reintento del `POST`.** `cmdSyncBars` reintenta hasta **3 veces con 30 s** (timeout de 30 s por
   intento) cuando el fallo es de red, `5xx`, `408` o `429`; **no** reintenta `401`/`403`/demás `4xx`
   (configuración, no corte). La clasificación vive en `shouldRetrySync` y está cubierta en
   `scripts/lib/window-forward.test.mjs`. Al agotar los intentos sigue devolviendo `1`: la semántica no
   cambia.
2. **Puerta de completitud de barras, antes del preflight.** `scripts/lib/daily-bars-coverage.mjs`
   consulta `instrument_list_items` (`list_id='estudio'`) contra `ohlcv_bars` (`1d`, día, `close > 0`).
   Umbral **95 %** (76/80), espera máxima **1800 s** y sondeo **60 s**; configurable por
   `WINDOW_BARS_MIN_COVERAGE`, `WINDOW_BARS_WAIT_SECONDS` y `WINDOW_BARS_POLL_SECONDS`. Si no llega:
   `manifest.json` con `status: INCOMPLETE_BARS`, `reason: BARS_INCOMPLETE` y el detalle de cobertura,
   **sin fila en `ledger.jsonl`** y exit `1`. `INCOMPLETE_BARS` **no** entra en `TERMINAL_STATUSES`, así
   que el día siguiente no se salta ni se cuenta como medido. Fail-closed si la lista no tiene 80
   miembros.
   Medición de hoy a las 11:30: `2026-11-06 → 80/80` (pasa), `2026-11-09 → 0/80` (la puerta esperaría y
   abortaría; es lo correcto antes del cierre). **Simulación del aborto** a las 11:47 con
   `WINDOW_BARS_MIN_COVERAGE=1` y `WINDOW_BARS_WAIT_SECONDS=0`: `manifest.json` con `INCOMPLETE_BARS`,
   `reason: BARS_INCOMPLETE`, `barsCoverage 0/80`, **cero** filas de `20261109` en `ledger.jsonl` y exit
   `1`.
   **Riesgo declarado:** el calendario de la puerta solo distingue fines de semana, así que un festivo
   con mercado europeo cerrado también abortará como incompleto. Es fail-closed a propósito: se declara
   el día y no se mide a ciegas.
3. **Supervisor del stack.** `scripts/window-stack-ready.mjs` consulta `/api/health/ready`; si no está
   listo revisa los puertos **8000 (API), 5173 (web) y 3002 (puente XTB)**. Solo el **API** bloquea:
   si hay un listener en 8000 pero `ready` no responde, declara y sale `1` (matar a un proceso ajeno no
   es tarea del supervisor). Si solo están ocupados 5173/3002 **avisa y arranca** `pnpm dev` en segundo
   plano (log en `logs/agent/`), porque `run-dev.mjs` libera los tres puertos en `ensureStackPortsFree()`.
   Espera hasta 300 s. **Corregido el 2026-11-09 (12:40)** tras medir que `webPort()` devolvía 3002 (el
   puente) y no 5173: un puente huérfano hacía que el supervisor se negara a arrancar justo el escenario
   que debe recuperar. Ver [stackready-supervivencia-2026-11-09.md](./stackready-supervivencia-2026-11-09.md) §3.1.
4. **Tareas programadas (registradas hoy, 11:31).** Se añaden `BolsaV1_StackReady` (**17:33**) y
   `BolsaV1_StackReadyLate` (**18:25**) y se re-registran las tres existentes. Verificado leyendo el XML
   del Programador:

| Tarea | Hora | `StartWhenAvailable` | `WakeToRun` | `DisallowStartIfOnBatteries` | `StopIfGoingOnBatteries` |
| --- | --- | --- | --- | --- | --- |
| `BolsaV1_StackReady` | 17:33 | true | **true** | **false** | **false** |
| `BolsaV1_StackReadyLate` | 18:25 | true | **true** | **false** | **false** |
| `BolsaV1_BarsSync` | 17:40 | true | **true** | **false** | **false** |
| `BolsaV1_WindowForward` | 18:30 | true | **true** | **false** | **false** |
| `BolsaV1_WindowWatch` | 20:20 | true | **true** | **false** | **false** |

   `BolsaV1_BarsSync` **se queda a las 17:40**: adelantarlo no arregla un API caído y el drenaje medido
   termina 18:10-18:20.

   Añadidas el mismo 2026-11-09, con el mismo principal y los mismos flags: `BolsaV1_StackReadyBars`
   (**17:39**, diaria, guardia un minuto antes del `BarsSync`), `BolsaV1_ClosesSnapshot` (**23:30** del
   11-09, única) y `BolsaV1_ClosesCompare` (**18:45** del 11-10, única). Ver
   [rutina-ventana-paper-2026-11-09.md](./rutina-ventana-paper-2026-11-09.md) §2.1.
5. **Energía.** Plan activo `Equilibrado`; `STANDBYIDLE` y `HIBERNATEIDLE` en **corriente alterna** a
   `0x00000000` (nunca suspender). En batería siguen a 15 min / nunca: la ventana debe correr
   **enchufada**, y ahora las tareas ya no se bloquean por batería. `WakeToRun=true` cubre el caso de que
   el equipo se duerma igualmente.
6. **Calidad del cierre.** `scripts/snapshot-daily-closes.mjs` y `scripts/compare-daily-closes.mjs`
   (read-only) capturan el cierre del día en 10 valores —4 BME, 3 XETRA, 3 FR— y al día siguiente miden
   la deriva en bps contra lo que deje el `BarsSync`. El snapshot de hoy se toma **tras el `run-day`**
   (o a las 23:30), porque antes no hay barras del día.
7. **Lo que no se toca:** `apps/`, `packages/`, el tag y el bump. `pnpm window:freeze` sigue dando
   `freeze OK (c6cef5c9)`.

### 5.6 Registro de energía y eventos del 2026-11-08

Consulta a `Get-WinEvent` (System/Application) y `powercfg` sobre la ventana `17:00-18:30` del 11-08:

| Comprobación | Resultado |
| --- | --- |
| `Kernel-Power` **41** (apagado inesperado), **109**, `EventLog` **6008** | **ninguno** en la ventana |
| `Power-Troubleshooter` **42**/`Kernel-Power` **107** (suspensión/reanudación) | **ninguno** en la ventana |
| `EventLog` **6005/6006** (inicio/parada del servicio) | **ninguno** en la ventana |
| `BatteryStatus` | **2** (en corriente), **100 %** |
| `STANDBYIDLE` / `HIBERNATEIDLE` en AC | **`0x00000000` / `0x00000000`** (nunca) |
| Log de desarrollo | corta a las **17:24:08**; el siguiente arranca a las **18:22:34** |
| `RestartManager` (Application) | sesión de **18:20:44 a 18:22:36** |

Conclusión: **no hubo suspensión, apagado ni reinicio del sistema a las 17:24**. Murió el **stack de
desarrollo interactivo** y el operador lo relanzó a las 18:22. Histórico que sí explica otras noches:
BSOD `0x116` (VIDEO_TDR) el **10-26, 10-27 y 11-03**, y cierres inesperados el **10-13, 10-26, 10-30 y
11-03**.

### 5.7 Cuenta, sesión y causa de la caída del 2026-11-08 (re-verificado el 2026-11-09, 13:05)

**a) Tarea y stack usan la misma cuenta y la misma sesión.** Medido con `schtasks /query /xml` sobre las
cinco tareas y `Win32_Process`/`query user` sobre los procesos vivos:

| Comprobación | Valor medido |
| --- | --- |
| Principal de las cinco tareas | SID `S-1-5-21-446501823-3854145363-1019770800-1001` → `ASUSPORTATIL\josea` |
| `LogonType` | `InteractiveToken` en las cinco ("Solo interactivo") |
| Sesión interactiva | `console`, **ID 1**, estado `Activo`, desde `2026-11-08 14:45` |
| `SessionId` de `cmd` 30476, `run-dev` 16396, uvicorn 33992, Vite 22900, puente 33404 | **1** en los cinco |
| `/api/health/ready` (13:02) | **200** |

La cuenta coincide y la sesión sigue abierta, que es la condición que la prueba del 12:18-12:32 asumía.

**b) El límite real.** Bloquear la sesión **no** la cierra: el token interactivo sigue vivo y las tareas
`InteractiveToken` siguen pudiendo correr. Lo que tumba el stack es **cerrar sesión**, **reiniciar** o
**apagar**. Frente a eso: `STANDBYIDLE`/`HIBERNATEIDLE` en corriente alterna a `0x00000000` (nunca),
`WakeToRun=true` y `StartWhenAvailable=true` en las cinco tareas, y `DisallowStartIfOnBatteries=false`.
Condición operativa declarada: la ventana corre **enchufada** y **con la sesión iniciada**.

**c) La caída del 8-N, otra vez medida (no heredada del informe).** Consulta repetida sobre
`System`/`Application` en `17:00-18:30`:

| Consulta | Resultado |
| --- | --- |
| Eventos `System` totales en `17:00-18:30` | **5** (uno `IsolatedUserMode` 17:02:53 y cuatro `SCM` 7040 entre 18:09 y 18:24) |
| `Kernel-Power` **41 / 42 / 107 / 109** en la ventana | **0** |
| `EventLog` **6005 / 6006 / 6008** en la ventana | **0** |
| Eventos `System` en `17:20-17:30` | **0** |
| `Kernel-Power` en todo el día | pares 507/566 (Modern Standby): último **16:55:16** (salida por touchpad); siguiente **19:21:46** (entrada por `Idle Timeout`) |
| `LastBootUpTime` | **2026-11-08 14:45:10** — no hubo reinicio entre el arranque del stack (13:49 UTC) y la caída |
| `Windows Error Reporting` 1000 de `node.exe` en la ventana | **0**; sólo depósitos 1001 de BSOD históricos a las 17:11:25-28 |
| `RestartManager` | sesión **18:20:44 → 18:22:36** (posterior a la caída) |

**d) El mecanismo: terminación dura, no parada.** `run-dev.mjs` escribe `status: stopped` en
`logs/agent/dev-<sello>.json` desde `shutdown()`, que se invoca en `SIGINT`/`SIGTERM`. El fichero de la
sesión caída (`logs/agent/dev-2026-11-08T13-49-51-544Z.json`) se quedó en `ready`, y
`logs/dev/dev-2026-11-08T13-49-12-680Z.log` termina sin `Deteniendo stack` ni `Application shutdown
complete` de uvicorn. Es decir: **no llegó ninguna señal capturable**; el proceso padre y su árbol
desaparecieron de golpe.

Hipótesis principal, declarada como tal: **cierre de la consola/padre que lo lanzó**. En Windows, cerrar
la ventana de consola entrega `CTRL_CLOSE_EVENT`, que Node traduce a `SIGHUP`; sin listener, la acción por
defecto es terminar sin ejecutar ningún `process.on('exit')`, y no deja evento en `System`. Encaja con
todo lo medido: sin señal registrada, sin parada limpia, sin evento de energía, sin crash report y con el
padre reparentado. Lo que **no** se puede afirmar con la telemetría de ese día es *quién* cerró la consola;
por eso no se presenta como causa probada.

**e) Lo que se hace para que deje de ser invisible.** (1) handler `SIGHUP`/`SIGBREAK` en
[`scripts/run-dev.mjs`](../../scripts/run-dev.mjs) que registra `status: stopped`, `reason:
console-close:<señal>` antes de salir — si vuelve a pasar, la próxima vez queda nombrado; (2)
[`scripts/enable-task-scheduler-log.ps1`](../../scripts/enable-task-scheduler-log.ps1) habilita el log
operativo del Programador, que fecha los disparos y las salidas de cada tarea — **pendiente de una
consola elevada**: la elevación se pidió hoy a las 13:12 y el UAC se **canceló** a las 13:14:33 (*"El
usuario ha cancelado la operación"*), así que el registro sigue `enabled: false`; (3) guardia
`BolsaV1_StackReadyBars` a las 17:39, ya registrada, que recupera el API justo antes del `BarsSync` de
17:40. `taskkill /F` sigue sin dejar rastro: eso se declara y no se disfraza de cierre limpio.

---

## 6. Qué cambia en la entrega

- **`2.11.187-beta`** (hoy): sello **funcional**. Publica el árbol que ya estaba en la rama —división del
  worker AUTO en módulos, dinero en `Decimal`, gate de drawdown, línea base, rutas diferidas, 401 global,
  formato `es-ES`, paridad cliente-API y ratchet `S110`/`S112`— **más** este expediente y el control de
  entradas aleatorias. **Sin migración** (`head` `066`) y **contrato aditivo**. Delta medido: 86 ficheros
  en `apps/` y 43 en `packages/` respecto a `.186`.
- **Rectificación declarada:** una versión previa de este apartado describía `.187` como documental y
  «cero cambios en `apps/`/`packages/`». Era un error de base de comparación (se citaron los hashes del
  pin re-anclado como si fueran los de `.186`). Corregido en `CHANGELOG.md` §`2.11.187-beta`.
- **Herramientas operativas:** los cambios de §5.5 viven en `scripts/` y `docs/`, fuera del pin. Se
  publican **con** este sello; no alteran `appsHash`/`packagesHash` salvo el bump.
- **`2.11.188-beta`** (después de la ventana): el parche de los cinco ficheros, el `TREE_DIRTY` del pin,
  el guard de `attnum`, la reconstrucción de tablas y la reevaluación de la evidencia guardada.
- **Bloqueo de dinero real**: stop en firme, invariante `protective_order_present`, kill switch de
  aperturas y corrección del `mark = 0.0`.
