# Auditoría de la operativa TRADING y AUTO — `v2.88.183-beta`

> **AsOf:** 2026-11-04 · **Base:** tag `v2.88.183-beta`, HEAD `09b395e5` (`v2.88.183-beta-2-g09b395e5`; los dos
> commits posteriores al tag solo tocan `CHANGELOG.md` y `docs/engineering/PROJECT_STATE.md`).
> **Estado:** **AUDITORÍA EN SOLO LECTURA.** No se modificó código de producto al redactarla. Este documento es el
> único artefacto escrito.
> **Alcance:** `auto_simulation_worker.py` (9.802 líneas) completo, la lógica de estrategia y señales, y la
> operativa TRADING/AUTO alrededor de ellos (decisión, riesgo, ejecución, workers).
> **Naturaleza:** endurecimiento. No se encontró ningún camino que envíe una orden real con AUTO OFF, en PAPER o en
> SIM; los hallazgos son fail-open ante dato ausente y persistencia fallida ignorada.
> **Certificación:** limitada a lo ejecutado en §7. No se ejecutó el motor con datos reales, ni los tests con
> Postgres, ni los E2E, ni se comprobó el número de workers del despliegue.
> **Trazabilidad de las correcciones:** `P1`, `P2`, `P4` y `P9` se cierran en la rama
> `fix/auto-fail-closed-p1-p2-p4-p9` (flags con lista blanca, `<Regla>_unmeasured`, `DataGatePolicy.require_evidence`
> y normalizador finito en `bolsa_domain`). `P5` y `P6` se cierran en la PR
> [#78](https://github.com/jvelasca/Bolsa_V1/pull/78) (`fix/auto-p5-p6-persistence`). `P7` y `P8` se cierran en la
> rama `fix/auto-p7p8-crossprocess-lease` (lease durable por `engine_id`, migración `063_auto_engine_lease`, claim
> del ciclo ANTES de ejecutar y reconstrucción de `_open` al cambiar de generación). `M12` y `M13` se cierran en la
> rama `fix/auto-m12-m13-watch-monitor` (lock del vigía con dueño probado PID/TTL + latido atómico, y estado
> `INCOMPLETE` explícito en el monitor). `P3`, el resto de la severidad media `M*` y `S1`-`S10` quedan abiertos:
> este documento sigue siendo el snapshot del estado auditado, no el estado corregido.

Alcance detallado: lógica de decisión, riesgo, ejecución, workers AUTO, `auto_simulation_worker.py` (9.802 líneas) y lógica de estrategia y señales.
Modo: solo lectura. No se modificó el repositorio. Las referencias `archivo:línea` son del tag `v2.88.183-beta`.

## 0. Veredicto

- **No se encontró ningún camino que envíe una orden real con AUTO OFF, en PAPER o en SIM.** La puerta de órdenes reales (`broker_adapter.py:178-279`) es fail-closed. `live_auto` se enruta a dry-run. Las órdenes UNKNOWN nunca se reenvían.
- El patrón de fallo dominante es **fail-open ante dato ausente o no finito**. El segundo es **persistencia fallida ignorada, con estado actualizado solo en RAM**.
- Calidad del sistema: la arquitectura es sólida (decisión fail-closed, reservas con claim, kill switch durable, sin lookahead en el simulador). Los fallos son de endurecimiento, no de diseño roto.

### Método y nivel de confianza

| Nivel | Significado |
|---|---|
| **Reproducido** | Ejecutado en una copia del tag. |
| **Verificado a mano** | Leído en el código por mí. |
| **Por lectura** | Informado por una pasada de lectura (agentes), con línea citada; no contrastado a mano. |

Límites: no se ejecutó el motor con datos reales, ni los tests con Postgres, ni E2E. Los hallazgos de concurrencia no se reprodujeron. La lectura del worker fue por tramos y paralela; puede haber falsos positivos y huecos. El despliegue (número de workers de uvicorn) no se comprobó.

---

## 1. Hallazgos prioritarios (corregir primero)

### P1 — Flags de activación fail-open · 🟠 Alta · Verificado a mano
- **Dónde:** `auto_simulation_worker.py:439-444` (`sim_worker_enabled`), `:458-463` (`AUTO_ENGINE_SIM_REAL_PRICE`), `paper_auto_engine_worker.py:96-102` (`_env_on`).
- **Fallo:** cualquier valor distinto de `""/0/false/no/off` activa. `disabled`, `n` u `of` encienden AUTO o el precio real.
- **Debería ser:** lista blanca (`1/true/yes/on`). Un valor desconocido es OFF con warning.

### P2 — El gate de política salta reglas sin dato · 🟠 Alta · Por lectura y verificado
- **Dónde:** `policy_gate.py:113-285`; `execution_router.py:942-962`.
- **Fallo:** MinMarketCap, MinADV, MaxSpread, sector y drawdown quedan `SKIPPED` si el dato es `None`, y SKIPPED no veta. El comentario "fail-closed" es falso. El router no pasa market cap, ADV ni spread, así que esas tres reglas están muertas en paper_auto.
- **Debería ser:** si la regla está activa y falta el dato, `FAILED` con motivo `*_unmeasured`. Las reglas opcionales se declaran en la política, no se deducen de la ausencia del dato.

### P3 — Circuit breaker de drawdown dependiente de un `except: pass` · 🟠 Alta · Por lectura
- **Dónde:** `execution_router.py:~899-914`, `account_drawdown.py`.
- **Fallo:** si falla hidratar o persistir las marcas de equity, el día "abre" con el equity actual y el drawdown diario es 0. Sin `initial_deposit`, `max_pct` es `None` (SKIPPED). `_dd_pct` devuelve 0,0 si la referencia ≤ 0. El día es UTC.
- **Debería ser:** sin marca de apertura fiable, vetar aperturas. Persistir transaccionalmente. Referencia ≤ 0 equivale a no medido, no a 0 %.

### P4 — Data gate abre con evidencia vacía · 🟠 Alta · Reproducido
- **Dónde:** `auto_adaptive_data_gate.py:340-345`; llamador `auto_simulation_worker.py:~5745-5790`.
- **Fallo:** `assess_data_gate()` sin evidencia devuelve `OK` con `evidence_not_provided`. En producción, si `by_strategy` está vacío, `completeness` y `recent_available` son `None` y el gate sale OK. `journal_age=None` nunca bloquea.
- **Debería ser:** `None` en un campo exigido es `DEGRADED`. "No se pidió medir" no debe poder expresarse en producción.

### P5 — Consumo de señal no durable tras el fill · 🟠 Alta · Verificado a mano
- **Dónde:** `auto_simulation_worker.py:5066-5086`.
- **Fallo:** la señal se añade a RAM (`:5069`) y después se persiste. Si `mark()` falla, el comentario promete reintento, pero el tick siguiente ve la señal ya en RAM y no vuelve a marcar. Un crash posterior permite una segunda entrada sobre la misma oportunidad.
- **Debería ser:** claim durable antes del fill, o un outbox con estados `reserved → filled → consumed` y reconciliación al arrancar. Mantener `pending_durable` aparte, con reintento y backoff.

### P6 — Escrituras de INTENT de salida con resultado ignorado · 🟠 Alta · Verificado a mano
- **Dónde:** `auto_simulation_worker.py:4249` (aplicar fill) y `:4366` (INTENT reservado).
- **Fallo:** `_v2_save_exit_order(...)` devuelve `False` si falla y el código lo ignora, actualizando RAM igualmente. Tras un reinicio, el INTENT durable difiere del aplicado: la salida puede reemitirse o quedar huérfana. La rama de emergencia (`:4358-4362`) sí hace HALT, así que el patrón correcto ya existe en el propio archivo.
- **Debería ser:** si la persistencia falla, no mutar RAM, declarar medición desconocida y activar reconciliación o kill switch. Idealmente, reserva e INTENT en una transacción.

### P7 — Dos workers pueden ejecutar el mismo ciclo · 🟠 Alta · Por lectura
- **Dónde:** `auto_sim_loop` (`:9224-9269`), `paper_auto_engine_loop`.
- **Fallo:** los schedulers usan advisory lock; estos loops no. Dentro del mismo proceso, `run_tick()` no está serializado y muta estado compartido (`_open`, stores sustituidos temporalmente; `:8330-8450`).
- **Debería ser:** `asyncio.Lock` por runtime, y advisory lock o lease en BD por `engine_id`, con un único líder si hay varios workers.
- **Cerrado (`fix/auto-p7p8-crossprocess-lease`):** `AutoSimRuntime` serializa con `asyncio.Lock` y arbitra entre procesos con un **lease durable** en `auto_engine_runs` (migración `063_auto_engine_lease`: `lease_owner`, `lease_generation`, `lease_expires_at`), adquirido por CAS atómico (`UPDATE … WHERE lease_owner IS NULL OR lease_expires_at <= now()`) y renovado antes de cada turno. El que no es dueño **no ejecuta** y **declara** `lease_not_held`. `lease_generation` es valla (fence) de escritura: un tick del dueño anterior lanza `AutoEngineLeaseLost` y se descarta; al cambiar de generación el worker exige `readopt_positions()` en vez de heredar `_open` de otra RAM. El apagado ordenado suelta el lease (`AutoSimRuntime.close()` desde el `finally` del loop); un crash lo deja vencer por TTL (`AUTO_ENGINE_LEASE_TTL_SECONDS`, default 180 s).

### P8 — Idempotencia de tick no es idempotencia de ciclo · 🟠 Alta · Por lectura
- **Dónde:** `auto_engine_state_store.py:204-331`.
- **Fallo:** se deduplica `(engine_id, seq)` tras ejecutar. El estado `_open` vive en RAM (`:8351-8353`, `:9330-9337`).
- **Debería ser:** clave `(engine, barra lógica)` reclamada antes de ejecutar; estado derivado reconstruible desde eventos durables.
- **Cerrado (`fix/auto-p7p8-crossprocess-lease`):** el `seq` y la identidad del ciclo (`tick_id = cycle-<engine>-<barra>-<seq>`) se **reservan antes** de ejecutar (`claim_cycle`, `reason='cycle_claimed'`), y el cierre **liquida esa fila** con los totales del turno en vez de crear otra. **Desvío declarado y medido de la auditoría:** la clave es `(engine, seq)`, no `(engine, barra)`: el reloj de decisión es `1d` y el motor ticka varias veces dentro de la MISMA barra (stops, gestión, salidas), así que bloquear por barra pararía el motor el resto del día; la idempotencia del ciclo la dan el lease, la señal consumida y la posición readoptada. Un ciclo interrumpido deja su fila `cycle_claimed` como traza y el siguiente proceso reanuda en `seq + 1`.

### P9 — Precios, cantidades y configuración no finitos · 🟠 Alta · Reproducido (parcial) y por lectura
- **Dónde:** `:2150-2199` (precios exec/mid/low/high), `:2561`, `:2956`, `:3112` (marks y señales), `:3299-3317` (liquidez), `:7659` (precio), `:7753` (cantidad), `:536-550` (`STOP_PCT` etc.), `:9574` (`AUTO_ENGINE_SIM_LOT_QTY`), `:9799-9802` (intervalo). También `exit_order.py:119`, `open_order.py:65`, `risk_allocator.py` con `inf`.
- **Fallo:** `NaN` e `inf` pasan los filtros `> 0`/`is None`, o provocan `OverflowError`, y el loop traga la excepción. Un lote inválido (`abc`, `NaN`) puede abortar `start_auto_sim_worker()`. Un intervalo `Infinity` suspende el worker indefinidamente.
- **Debería ser:** una función única de normalización de precio (finito, > 0, `low ≤ high`) y un parser de configuración (finito, rango, error explícito). Entrada inválida produce un veto auditable, nunca una excepción.

---

## 2. Hallazgos de severidad media

| # | Fallo | Dónde | Debería ser |
|---|---|---|---|
| M1 | `cancel_order` lee y hace upsert sin lock ni versión; puede borrar un fill ya reconciliado (latente: no hay órdenes reales) · Por lectura | `live_order_store.py:632-706` | `UPDATE … WHERE status IN (…) AND version=:v`, o `FOR UPDATE`; no reescribir cantidades |
| M2 | `max_position_pct`/`max_position_value` ≤ 0 significa "sin techo" (reproducido: qty 100 aprobada). Solo `max_risk_per_trade_pct=0` veta | `risk_allocator.py:319-337` | 0 = techo cero (veto), negativo = error; solo `None` = sin techo |
| M3 | `risk_budget` NaN/inf/≤0 cae al presupuesto por pct (reproducido). **Latente**: el único llamador (`portfolio_decision_engine.py:544`) veta antes | `risk_allocator.py:272-289` | Defensa en profundidad en la propia función |
| M4 | `remaining_qty` > `requested_qty` aceptado (reproducido: pedir 10, quedar 100) | `exit_order.py:299-323` | `0 ≤ remaining ≤ requested` y `filled + remaining ≈ requested` |
| M5 | `commit()` de reservas fallido se registra y se continúa. Seguro solo si el store es autocommit (el comentario lo asume; no verificado) | `auto_simulation_worker.py:3707` | Contrato explícito; si falla, no emitir órdenes |
| M6 | Pérdida de eventos de journal: la cola se vacía antes de publicar, y si el sink falla se pierde la evidencia | `:7373-7395` | Outbox con `pending/posted/failed` |
| M7 | Excepciones del tick, del refresco de watch y del refresco del decider se tragan; se opera con universo o estrategia caducados, sin backoff ni estado durable de fallo | `:9253-9267` | Marcar snapshot no fiable y vetar aperturas; backoff exponencial y circuit breaker a `PAUSED`; persistir tick `ERROR` |
| M8 | Sin stores durables inyectados, kill switch, posiciones, T1, P&L y journal viven solo en RAM; el modo estructural marca fills como `applied` sin libro financiero | `:1200-1470`, `:2275-2281`, `:2368-2375` | Stores obligatorios en modo operativo; rechazar el arranque si faltan |
| M9 | Excepción de `price_script` escapa sin el fail-closed que sí tiene `PriceSource` | `:2150-2172` | `try/except` → `None` → HOLD |
| M10 | AUTO se activa solo por variable de entorno; tras un reinicio con la variable puesta, arranca. Sin latch durable de OFF | workers AUTO | Intención del operador en BD; rearranque con confirmación |
| M11 | Calibración `positiveOosFoldShare` usa `>= 0.0`; el replay usa `R > 0`. Los folds planos inflan la métrica | `auto_adaptive_calibration.py:638` | Criterio único `> 0` |
| M12 | Lock y latido de ventana en fichero no atómicos; un `.run.lock` obsoleto silencia alertas · ✅ Cerrado | `window_day_watch_worker.py:341-535` | `os.replace`, lock con PID y TTL |
| M13 | El monitor devuelve un DTO coherente con lecturas caídas · ✅ Cerrado | `auto_operational_monitor.py:1897-2120` | Estado `INCOMPLETE` explícito |
| M14 | `load_book_equity` puede dejar equity de un tick anterior visible tras un fallo de lectura | `:2524-2544` | Snapshot atómico con `as_of` |
| M15 | P&L parcial contra `_entry_price` único, no contra coste medio del ledger · Por lectura, impacto sin verificar | `:8027-8044` | Coste medio ponderado o lotes |
| M16 | `AutoSimRuntime` carga la estrategia ACTIVE con `instrument_id=effective_account` · ✅ Cerrado | `:9723-9727` | Separar `account_id` de `instrument_id` |

### M12 — Lock del vigía con dueño probado y latido atómico · ✅ Cerrado (`fix/auto-m12-m13-watch-monitor`)
- **Fallo:** `day_is_running()` sólo comprobaba que existiera el directorio `.run.lock`; un lock **huérfano** (proceso muerto, host apagado o `lock.json` corrupto) silenciaba el «día perdido» para siempre. El latido se escribía con `write_text`, que deja una ventana en la que un lector ve el fichero truncado y pierde también las marcas de aviso.
- **Cerrado:** el lector aplica la MISMA política que el runner (`lockDecision`): lee `lock.json` (`pid`, `host`, `startedAt`) y sólo calla si el dueño se puede probar vivo —mismo host + PID vivo, otro host dentro del TTL de 12 h, o lock ilegible dentro de la ventana de adquisición de 5 min—. Un lock sin dueño probado vuelve a avisar. `write_status` escribe en temporal + `os.fsync` + `os.replace` (atómico en POSIX y Windows) y limpia el temporal si falla. En Windows la sonda de PID usa `OpenProcess`/`GetExitCodeProcess`, nunca `os.kill(pid, 0)` (que allí termina el proceso).

### M13 — Estado `INCOMPLETE` explícito en el monitor · ✅ Cerrado (`fix/auto-m12-m13-watch-monitor`)
- **Fallo:** las consultas del monitor se degradaban en silencio: una lectura caída y una cuenta sin operaciones producían el MISMO DTO (`cycles: []` + notas de «no durable»). Además, las lecturas de reservas/posiciones/engine no estaban protegidas y podían tumbar la ruta entera.
- **Cerrado:** cada lectura declara su resultado en `readStatus` (`COMPLETE`/`FAILED`, orden canónico en `MONITOR_READ_SOURCES`). Si alguna cae, el DTO publica `state: "INCOMPLETE"`, la lista `incompleteReads` y la nota `read_failed:<fuente>`. El contrato HTTP y el view model (`@bolsa/shared`) exponen `state`/`readStatus`/`incompleteReads`, y la UI (monitor experto y la historia de la operación) rotula «Lectura incompleta» con las fuentes antes de cualquier lista vacía: un vacío por fallo deja de leerse como «sin operaciones». Un ámbito demostrablemente vacío (sin ciclos) sigue declarándose `COMPLETE`.

### M16 — La cuenta y el instrumento de una ACTIVE son ámbitos distintos · ✅ Cerrado (`fix/auto-m16-account-scope`)
- **Fallo:** `AutoSimRuntime` pedía la estrategia ACTIVE con `load_active_strategy_decider(instrument_id=effective_account)`, es decir, la **cuenta** viajaba por la ruta del **instrumento** (y el símbolo de reserva sin watch era la cuenta). Funcionaba sólo porque la semilla de la ventana escribía la cuenta en `strategy_promotions.instrument_id`: una promoción de estudio (`inst-v229-…`) y una activa atribuida a una cuenta quedaban indistinguibles, y cualquier lectura por instrumento podía devolver la de la cuenta.
- **Cerrado:** migración `064_strategy_account_scope` añade `strategy_promotions.account_id` (nullable, **sin backfill**: rellenarla desde `instrument_id` sería repetir la confusión) con índice `(account_id, promoted)`. `ActiveStrategy` declara `account_id`, el store expone `get_active_for_account()` y `get_active()` sigue siendo la ruta de instrumento; `load_active_strategy_decider` recibe `account_id` **o** `instrument_id` (sin ninguno: `ValueError`, no un `None` mudo) y el runtime pide la cuenta por cuenta. La fila histórica (`instrument_id = <cuenta>`, `account_id = NULL`) se sigue leyendo por la ruta de compatibilidad, pero la ACTIVE devuelta declara `account_id = None`: el ámbito ausente no se inventa. La semilla de la ventana y el runner forward siembran/leen el ámbito correcto.

## 3. Severidad baja

- Conversión `Decimal → float → Decimal` en precios, equity, stops y cantidades de fills (`:971`, `:1052`, `:2561`, `:4570-4588`, `:6671-6699`, `live_order_recovery_worker.py:184,326,339`). Mantener `Decimal` hasta el borde.
- `auto_engine_ticks` sin retención; frescura con `datetime.now` (`auto_orchestrator_worker.py:620-628`). Retención e inyección de reloj.
- `TIME_STOP` inalcanzable si falta `created_at` o el holding period (`position_state.py:231-249`). Está documentado como intencional, pero sin alarma.
- `signal_id` ausente cae a UUID aleatorio (`auto_v2_entry.py:2140-2208`). Documentado como intencional; confirmar que un `signal_id` vacío se veta antes.
- Pickle en la caché Redis, con el sha256 guardado junto al blob (`redis_feature_cache.py:20-39`, `lightgbm_direction.py:185`): la integridad no es autenticación. Usar HMAC con clave o un formato sin pickle.

---

## 4. Estrategia y señales

Fuente: lectura de módulos de señales, ciclo de vida y promoción. No verificado a mano salvo indicación.

### Alta
- **S1 — La máquina de estados admite `PROMOCION → ACTIVE` sin comprobar gates** (`strategy_lifecycle.py:769-770`, `can_transition` devuelve `allowed=True`). `evaluate_promotion()` sí exige los siete gates, COACH sin veto y shadow, pero un llamador directo puede saltárselos. **Debería ser:** que la transición exija `validation.passed`, COACH y shadow, centralizada en el resultado de `evaluate_promotion()`.
- **S2 — Umbrales de LAB triviales por defecto:** `min_oos_score=0.0`, `min_wfe=0.0`, `max_pbo=1.0`, y el gate de riesgo solo exige `max_drawdown_pct >= 0` (`strategy_lab_phase.py:228-235`, `:356-365`). **Debería ser:** umbrales no triviales, límite máximo de drawdown, muestra mínima de operaciones y retorno neto de costes.
- **S3 — Sin corrección por pruebas múltiples en discovery** (`strategy_lab_phase.py:237-305`): se elige un campeón y se evalúa su OOS sin registrar el número de configuraciones. Riesgo de data snooping. **Debería ser:** registrar el universo probado y aplicar DSR, PBO o un hold-out intocable. · **✅ Cerrado (`fix/auto-s3-multiple-testing`)** — ver cierre al final de la sección.
- **S4 — Lookahead potencial por contrato:** `SignalEventV1` publica la señal con `closes[index]` y el timestamp de la barra `t` (`rules_engine.py:639-692`). El simulador lo evita (`rules_grid.py:91-96`: señal en `index-1`, ejecución al `open(index)`). El worker usa la barra cerrada anterior para decidir y el `open` actual para ejecutar, lo cual es correcto, pero el contrato general no lo impone. **Debería ser:** `signal_bar=t` y `execution_bar=t+1` explícitos en el contrato. · **✅ Cerrado (`fix/auto-s4-signal-timing`)** — ver cierre al final de la sección.

### Media
- **S5 —** El avance de fase solo exige que exista algún `GateResult` sin fallo, no que sean los gates requeridos de esa fase (`strategy_lifecycle.py:727-755`). Definir `estado → gates obligatorios`; `NOT_EVALUATED` bloquea.
- **S6 —** `PROMOCION` no comprueba que la evidencia corresponda a la misma versión, definición y dataset (`:758-766`). Verificar identidad por `version_id`, hash y fingerprint.
- **S7 —** La vigilancia trata una métrica ausente como "sin degradación" y no valida su frescura (`strategy_vigilance_phase.py:107-178`). Una estrategia activa con el feed roto sigue operando. Distinguir `unmeasured/stale/healthy` con TTL y `version_id`.
- **S8 —** Contexto close-only: `open=high=low=close`, `volume=0` (`signal_feature_context.py:36-83`). ATR, VWAP y Stochastic se calculan con datos artificiales. Sin OHLCV completo, devolver HOLD con motivo `insufficient_data`.
- **S9 —** `NaN`/`inf` no se validan en indicadores (`indicators/legacy.py`, `signal_feature_context.py:49-55`); RSI sin validar `period > 0`.
- **S10 —** La identidad de señal no es un claim atómico (`signal_identity.py:50-117`); `build_signal_identity()` devuelve `None` ante campos faltantes y un llamador puede ignorarlo. Las alertas sí tienen claim atómico (`signal_alerts.py:174-195`).

### Baja
- `bar_window()` con epoch no coincide con la frontera del proveedor en timeframes no divisores de 24 h (`signal_identity.py:78-95`).
- El cruce usa `<=`/`>=` en la barra previa, así que la igualdad cuenta como cruce (`rules_engine.py:246-263`).
- Las métricas observadas usan una única cola FIFO para todos los instrumentos (`strategy_observed_metrics.py:116-125`).
- `profit_factor` sin pérdidas devuelve `None`, indistinguible de "no medido".

### Cierres de la sección de estrategia

#### S3 — Universo probado registrado y corrección por pruebas múltiples · ✅ Cerrado (`fix/auto-s3-multiple-testing`)
- **Fallo:** el LAB traducía el campeón a gates sin dejar constancia de cuántas configuraciones se habían probado. El gate `dsr` comparaba el Deflated Sharpe con `min_dsr` como si el campeón fuera la única hipótesis: con N configuraciones probadas, exigir el mismo nivel de significación es *data snooping*, y a posteriori el DSR era ininterpretable porque nadie sabía el N.
- **Cerrado:** toda `StrategyEvaluation` publica en `metrics` el universo probado —`discovery_trials` (configuraciones evaluadas por el optimizador, `len(result.trials)`)— junto con `multiple_testing_correction` y el umbral efectivo `dsr_min`; el gate `dsr` lleva los mismos tres datos. La corrección de Bonferroni (`multiple_testing_correction()`) reparte el nivel de significación `alpha = 1 - min_dsr` entre las N hipótesis ⇒ `umbral' = 1 - alpha/N`, es monótona en N y es la identidad con N ≤ 1. Se aplica **con flag** (`LabThresholds.correct_multiple_testing`, env `AUTO_ORCHESTRATOR_LAB_CORRECT_MULTIPLE_TESTING`, default OFF): el registro es siempre, el endurecimiento del umbral es una decisión explícita y reversible.

#### S4 — Tiempo de la señal explícito en el contrato · ✅ Cerrado (`fix/auto-s4-signal-timing`)
- **Fallo:** `SignalEventV1` publicaba precio y timestamp de la barra `t` pero no declaraba cuándo se ejecuta. Simulador y worker lo hacían bien por convención local (`signal` en `t`, ejecución al `open(t+1)`), pero un consumidor nuevo —alerta, política o integración— no tenía forma de saberlo y podía operar en la misma barra.
- **Cerrado:** el contrato gana `signal_bar` y `execution_bar`, **opcionales** para no romper consumidores históricos: si faltan, se resuelven con `bar_index` (señal) y `bar_index + 1` (ejecución) vía `resolved_signal_bar` / `resolved_execution_bar`. `has_lookahead()` devuelve `True` cuando la ejecución declarada no es posterior a la señal. Los constructores (`evaluate_strategy`, `hybrid_scan`, `drawing_marker_to_signal_event_v1`) y los serializadores (DTO HTTP con `signalBar`/`executionBar`, payload de eventos, alertas, hits de scan y del evaluador de salidas) publican los valores resueltos. Guarda de router fail-closed en `ExecutionRouter`: una señal con lookahead se descarta con `signal_timing:lookahead` en vez de operarse; `/signals/evaluate` responde 500 si el motor emite una violación del contrato. El contrato TS (`SignalEventV1`) lleva los mismos campos opcionales.

---

## 5. Lo que está bien diseñado

- Real-order gate fail-closed; `live_auto` a dry-run; UNKNOWN nunca se reenvía; estados terminales protegidos.
- Motor de decisión con vetos de medición (`risk_measurement_*`, `open_orders_unmeasurable`, `liquidity_unknown`); `require_complete_measurement` en `True` sin override por entorno.
- Kill switch durable y fail-closed ante lectura ilegible (`:2035-2041`, `:2638-2655`). HALT durable ante `execution_id` duplicado.
- Reservas con claim atómico y dueño de sesión; filtro por lado; protección contra doble conteo de capital.
- Sin lookahead en calibración, replay y simulador; separación LAB/hold-out shadow estricta (`timestamp > lab_end`).
- Clamp de ventas contra sobreventa; cierre y P&L con el precio de protección; stops monótonos (ratchet).
- Reconciliación y readopción al arrancar; posiciones no administrables declaradas como `POSITION_UNMANAGED`.
- Alertas con claim atómico y outbox con reintentos.

## 6. Orden de corrección recomendado

1. **Fail-open de configuración y datos:** P1, P2, P4, P9 (bajo riesgo de cambio, alto impacto).
2. **Persistencia fallida ignorada:** P5, P6, M5, M6, M9.
3. **Circuit breaker y estado durable:** P3, P8, M8, M10, M14.
4. **Concurrencia:** P7, M1.
5. **Gates de estrategia:** S1, S2, S5, S6, S7, S3.
6. **Validaciones de bordes:** M2, M3, M4, M11 y la severidad baja.

Cada corrección debería ir con un test que muerda (entrada `NaN`, `None`, valor desconocido o fallo de persistencia inyectado) para que el comportamiento fail-closed quede protegido.

## 7. Entorno de la auditoría

- Herramientas sobre el tag: ruff limpio; import-linter 4 contratos OK; mypy 583 ficheros, 0 errores; pytest dominio, aplicación y analítica 4614 passed, 5 skipped; `tsc` limpio; ESLint 0 errores, 23 avisos; vitest 2743 passed.
- Dependencias con avisos: pyjwt 2.13.0, pillow 12.3.0, urllib3 2.7.0, react-router y deepmerge-ts.
- Workflows de CI sin bloques `permissions:` y con acciones fijadas por tag, no por SHA.
- Ficheros muy grandes (3k–9k líneas), entre ellos `auto_simulation_worker.py`, lo que dificulta la revisión.
