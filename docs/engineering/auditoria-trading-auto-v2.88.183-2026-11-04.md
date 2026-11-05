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
> **Trazabilidad de las correcciones:** `P1`, `P2`, `P4` y `P9` se cierran en la PR
> [#77](https://github.com/jvelasca/Bolsa_V1/pull/77) (`fix/auto-fail-closed-p1-p2-p4-p9`: flags con lista blanca,
> `<Regla>_unmeasured`, `DataGatePolicy.require_evidence` y normalizador finito en `bolsa_domain`). `P5` y `P6` se
> cierran en la PR [#78](https://github.com/jvelasca/Bolsa_V1/pull/78) (`fix/auto-p5-p6-persistence`). `P7` y `P8` se
> cierran en la PR [#80](https://github.com/jvelasca/Bolsa_V1/pull/80) (`fix/auto-p7p8-crossprocess-lease`: lease
> durable por `engine_id`, migración `063_auto_engine_lease`, claim del ciclo ANTES de ejecutar y reconstrucción de
> `_open` al cambiar de generación). `M12` y `M13` se cierran en la PR
> [#81](https://github.com/jvelasca/Bolsa_V1/pull/81) (`fix/auto-m12-m13-watch-monitor`: lock del vigía con dueño
> probado PID/TTL + latido atómico, y estado `INCOMPLETE` explícito en el monitor). `M16` se cierra en la PR
> [#82](https://github.com/jvelasca/Bolsa_V1/pull/82) (`fix/auto-m16-account-scope`: `account_id` separado de
> `instrument_id`, migración `064_strategy_account_scope`). `S3` se cierra en la PR
> [#83](https://github.com/jvelasca/Bolsa_V1/pull/83) (`fix/auto-s3-multiple-testing`: universo probado registrado y
> corrección de Bonferroni tras flag). `S4` se cierra en la PR
> [#84](https://github.com/jvelasca/Bolsa_V1/pull/84) (`fix/auto-s4-signal-timing`: `signal_bar`/`execution_bar` en el
> contrato y guarda anti-lookahead). `P3` se cierra en la PR
> [#86](https://github.com/jvelasca/Bolsa_V1/pull/86) (`fix/auto-p3-drawdown-breaker`: una referencia no medible es
> `None` y no `0 %`, el libro no se envenena con equity no finito y una marca no persistida veta aperturas). `S5` se
> cierra en la PR [#88](https://github.com/jvelasca/Bolsa_V1/pull/88) (`fix/auto-s5-required-gates`: tabla
> `estado → gates obligatorios` aplicada por el dominio y consultada por el orquestador antes de materializar el
> finalista). `S6` se cierra en la PR [#89](https://github.com/jvelasca/Bolsa_V1/pull/89) (`fix/auto-s6-evidence-identity`:
> la validación declara definición y dataset, y el Promotion Gate veta la evidencia de otra definición, de otro
> snapshot o del mismo tramo de barras que el LAB). `S7` se cierra en la PR [#90](https://github.com/jvelasca/Bolsa_V1/pull/90)
> (`fix/auto-s7-vigilance-freshness`: la vigilancia distingue `stale`/`unmeasured`/`healthy`, con TTL de la evidencia
> predictiva, identidad por `version_id` y ausencia de medida fail-closed sobre el bloque predictivo). `M5`, `M6` y
> `M9` viajaron dentro de la PR [#78](https://github.com/jvelasca/Bolsa_V1/pull/78) (`fix/auto-p5-p6-persistence`), pero
> el documento los seguía listando como abiertos; la PR
> [#91](https://github.com/jvelasca/Bolsa_V1/pull/91) (`fix/auto-m5-m6-m9-commit`) cierra el resto que quedaba en `M5`
> —la sesión se declaraba dueña y publicaba sus claims **antes** del commit— y añade el certificado que faltaba de los
> tres. `M8`, `M10` y `M14` se cierran en la PR
> [#92](https://github.com/jvelasca/Bolsa_V1/pull/92) (`fix/auto-m8-m10-m14-durable-state`: espejos durables
> obligatorios en el turno operativo, intención del operador durable en `auto_engine_intent` con migración `065` y
> ganando al env, y `book_equity` como snapshot atómico con `as_of`). `M1`-`M4` y `M11` se cierran en la PR
> [#93](https://github.com/jvelasca/Bolsa_V1/pull/93) (`fix/auto-m1m4-cierre-verificado`: el ack del broker pasa a
> `UPDATE` condicionado —lo que faltaba de `M1`— y se certifica con tests mordientes el resto, que ya estaba en el
> árbol desde `53f6845a` y `e295092c`). `M7` y `M15` se cierran en la PR
> [#94](https://github.com/jvelasca/Bolsa_V1/pull/94) (`fix/auto-m7-m15-control-plane`: `M15` ya estaba en `4d3082fd` y
> aquí se certifica; `M7` deja de tragarse los fallos del loop). Las quince PR están
> fusionadas en `fix/059-060-proveedores`; **no** hay sello ni bump, y las únicas migraciones son las citadas.
> **Sincronización del documento (`2026-11-05`, sin PR de código):** al verificar la sección de estrategia contra el
> árbol, `S1` y `S2` ya estaban resueltos en código y con pruebas (`test_strategy_lifecycle_s1_s5_s6.py`, `LabThresholds`),
> así que el documento los daba por abiertos **por desfase**, no por defecto. **Sincronización de la sección de
> ejecución/riesgo (`2026-11-05`):** `M1` (`53f6845a`) y `M2`/`M3`/`M4`/`M11` (`e295092c`) también estaban resueltos en
> el árbol con pruebas, y sus tests se verificaron **mordientes** contra el código previo (6 fallos sin el arreglo, 2
> más del ack condicionado de `M1`), así que pasan a cerrados. **Abiertos:** de la sección media no queda ninguno; siguen
> abiertos los de severidad baja `S8`-`S10`.

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

### P1 — Flags de activación fail-open · 🟠 Alta · Verificado a mano · ✅ Cerrado ([#77](https://github.com/jvelasca/Bolsa_V1/pull/77))
- **Dónde:** `auto_simulation_worker.py:439-444` (`sim_worker_enabled`), `:458-463` (`AUTO_ENGINE_SIM_REAL_PRICE`), `paper_auto_engine_worker.py:96-102` (`_env_on`).
- **Fallo:** cualquier valor distinto de `""/0/false/no/off` activa. `disabled`, `n` u `of` encienden AUTO o el precio real.
- **Debería ser:** lista blanca (`1/true/yes/on`). Un valor desconocido es OFF con warning.

### P2 — El gate de política salta reglas sin dato · 🟠 Alta · Por lectura y verificado · ✅ Cerrado ([#77](https://github.com/jvelasca/Bolsa_V1/pull/77))
- **Dónde:** `policy_gate.py:113-285`; `execution_router.py:942-962`.
- **Fallo:** MinMarketCap, MinADV, MaxSpread, sector y drawdown quedan `SKIPPED` si el dato es `None`, y SKIPPED no veta. El comentario "fail-closed" es falso. El router no pasa market cap, ADV ni spread, así que esas tres reglas están muertas en paper_auto.
- **Debería ser:** si la regla está activa y falta el dato, `FAILED` con motivo `*_unmeasured`. Las reglas opcionales se declaran en la política, no se deducen de la ausencia del dato.

### P3 — Circuit breaker de drawdown dependiente de un `except: pass` · 🟠 Alta · Por lectura · ✅ Cerrado ([#86](https://github.com/jvelasca/Bolsa_V1/pull/86))
- **Dónde:** `execution_router.py:~899-914`, `account_drawdown.py`.
- **Fallo:** si falla hidratar o persistir las marcas de equity, el día "abre" con el equity actual y el drawdown diario es 0. Sin `initial_deposit`, `max_pct` es `None` (SKIPPED). `_dd_pct` devuelve 0,0 si la referencia ≤ 0. El día es UTC.
- **Debería ser:** sin marca de apertura fiable, vetar aperturas. Persistir transaccionalmente. Referencia ≤ 0 equivale a no medido, no a 0 %.
- **Cerrado (`fix/auto-p3-drawdown-breaker`):** `_dd_pct` devuelve `None` —no `0.0`— cuando la referencia es `≤ 0` o no finita, y `EquityMarkBook.update` no muta el libro con equity `NaN`/`inf` (la marca buena anterior sigue siendo la referencia). Sin `initial_deposit` el `max_pct` sigue sin medirse y el Policy Gate lo veta como `HardMaxDrawdown_unmeasured` (cerrado ya en P2). La hidratación fallida sin marcas en memoria veta con `drawdown_marks:unavailable` y, a partir de aquí, un fallo al **persistir** veta con `drawdown_marks:not_persisted`: la marca vale para el tick pero no para sobrevivir a un reinicio, así que no se acepta una apertura contra una referencia que un crash convertiría en 0 %. El libro reintenta la escritura en cada evaluación y deja de vetar cuando vuelve a persistir. La frontera del día se mantiene en **UTC** y queda declarada en el propio libro (`dayKey`/`weekKey` viajan con las marcas, así que una marca de otro día se descarta).

### P4 — Data gate abre con evidencia vacía · 🟠 Alta · Reproducido · ✅ Cerrado ([#77](https://github.com/jvelasca/Bolsa_V1/pull/77))
- **Dónde:** `auto_adaptive_data_gate.py:340-345`; llamador `auto_simulation_worker.py:~5745-5790`.
- **Fallo:** `assess_data_gate()` sin evidencia devuelve `OK` con `evidence_not_provided`. En producción, si `by_strategy` está vacío, `completeness` y `recent_available` son `None` y el gate sale OK. `journal_age=None` nunca bloquea.
- **Debería ser:** `None` en un campo exigido es `DEGRADED`. "No se pidió medir" no debe poder expresarse en producción.

### P5 — Consumo de señal no durable tras el fill · 🟠 Alta · Verificado a mano · ✅ Cerrado ([#78](https://github.com/jvelasca/Bolsa_V1/pull/78))
- **Dónde:** `auto_simulation_worker.py:5066-5086`.
- **Fallo:** la señal se añade a RAM (`:5069`) y después se persiste. Si `mark()` falla, el comentario promete reintento, pero el tick siguiente ve la señal ya en RAM y no vuelve a marcar. Un crash posterior permite una segunda entrada sobre la misma oportunidad.
- **Debería ser:** claim durable antes del fill, o un outbox con estados `reserved → filled → consumed` y reconciliación al arrancar. Mantener `pending_durable` aparte, con reintento y backoff.

### P6 — Escrituras de INTENT de salida con resultado ignorado · 🟠 Alta · Verificado a mano · ✅ Cerrado ([#78](https://github.com/jvelasca/Bolsa_V1/pull/78))
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

### P9 — Precios, cantidades y configuración no finitos · 🟠 Alta · Reproducido (parcial) y por lectura · ✅ Cerrado ([#77](https://github.com/jvelasca/Bolsa_V1/pull/77))
- **Dónde:** `:2150-2199` (precios exec/mid/low/high), `:2561`, `:2956`, `:3112` (marks y señales), `:3299-3317` (liquidez), `:7659` (precio), `:7753` (cantidad), `:536-550` (`STOP_PCT` etc.), `:9574` (`AUTO_ENGINE_SIM_LOT_QTY`), `:9799-9802` (intervalo). También `exit_order.py:119`, `open_order.py:65`, `risk_allocator.py` con `inf`.
- **Fallo:** `NaN` e `inf` pasan los filtros `> 0`/`is None`, o provocan `OverflowError`, y el loop traga la excepción. Un lote inválido (`abc`, `NaN`) puede abortar `start_auto_sim_worker()`. Un intervalo `Infinity` suspende el worker indefinidamente.
- **Debería ser:** una función única de normalización de precio (finito, > 0, `low ≤ high`) y un parser de configuración (finito, rango, error explícito). Entrada inválida produce un veto auditable, nunca una excepción.

---

## 2. Hallazgos de severidad media

| # | Fallo | Dónde | Debería ser |
|---|---|---|---|
| M1 | `cancel_order` lee y hace upsert sin lock ni versión; puede borrar un fill ya reconciliado (latente: no hay órdenes reales) · ✅ Cerrado | `live_order_store.py:632-706` | `UPDATE … WHERE status IN (…) AND version=:v`, o `FOR UPDATE`; no reescribir cantidades |
| M2 | `max_position_pct`/`max_position_value` ≤ 0 significa "sin techo" (reproducido: qty 100 aprobada). Solo `max_risk_per_trade_pct=0` veta · ✅ Cerrado | `risk_allocator.py:319-337` | 0 = techo cero (veto), negativo = error; solo `None` = sin techo |
| M3 | `risk_budget` NaN/inf/≤0 cae al presupuesto por pct (reproducido). **Latente**: el único llamador (`portfolio_decision_engine.py:544`) veta antes · ✅ Cerrado | `risk_allocator.py:272-289` | Defensa en profundidad en la propia función |
| M4 | `remaining_qty` > `requested_qty` aceptado (reproducido: pedir 10, quedar 100) · ✅ Cerrado | `exit_order.py:299-323` | `0 ≤ remaining ≤ requested` y `filled + remaining ≈ requested` |
| M5 | `commit()` de reservas fallido se registra y se continúa. Seguro solo si el store es autocommit (el comentario lo asume; no verificado) · ✅ Cerrado | `auto_simulation_worker.py:3707` | Contrato explícito; si falla, no emitir órdenes |
| M6 | Pérdida de eventos de journal: la cola se vacía antes de publicar, y si el sink falla se pierde la evidencia · ✅ Cerrado | `:7373-7395` | Outbox con `pending/posted/failed` |
| M7 | Excepciones del tick, del refresco de watch y del refresco del decider se tragan; se opera con universo o estrategia caducados, sin backoff ni estado durable de fallo · ✅ Cerrado | `:9253-9267` | Marcar snapshot no fiable y vetar aperturas; backoff exponencial y circuit breaker a `PAUSED`; persistir tick `ERROR` |
| M8 | Sin stores durables inyectados, kill switch, posiciones, T1, P&L y journal viven solo en RAM; el modo estructural marca fills como `applied` sin libro financiero · ✅ Cerrado | `:1200-1470`, `:2275-2281`, `:2368-2375` | Stores obligatorios en modo operativo; rechazar el arranque si faltan |
| M9 | Excepción de `price_script` escapa sin el fail-closed que sí tiene `PriceSource` · ✅ Cerrado | `:2150-2172` | `try/except` → `None` → HOLD |
| M10 | AUTO se activa solo por variable de entorno; tras un reinicio con la variable puesta, arranca. Sin latch durable de OFF · ✅ Cerrado | workers AUTO | Intención del operador en BD; rearranque con confirmación |
| M11 | Calibración `positiveOosFoldShare` usa `>= 0.0`; el replay usa `R > 0`. Los folds planos inflan la métrica · ✅ Cerrado | `auto_adaptive_calibration.py:638` | Criterio único `> 0` |
| M12 | Lock y latido de ventana en fichero no atómicos; un `.run.lock` obsoleto silencia alertas · ✅ Cerrado | `window_day_watch_worker.py:341-535` | `os.replace`, lock con PID y TTL |
| M13 | El monitor devuelve un DTO coherente con lecturas caídas · ✅ Cerrado | `auto_operational_monitor.py:1897-2120` | Estado `INCOMPLETE` explícito |
| M14 | `load_book_equity` puede dejar equity de un tick anterior visible tras un fallo de lectura · ✅ Cerrado | `:2524-2544` | Snapshot atómico con `as_of` |
| M15 | P&L parcial contra `_entry_price` único, no contra coste medio del ledger · ✅ Cerrado (`4d3082fd` + certificado) | `:8027-8044` | Coste medio ponderado o lotes |
| M16 | `AutoSimRuntime` carga la estrategia ACTIVE con `instrument_id=effective_account` · ✅ Cerrado | `:9723-9727` | Separar `account_id` de `instrument_id` |

### M5 — El commit fallido no deja dueño ni claim · ✅ Cerrado (`fix/auto-m5-m6-m9-commit`)
- **Fallo:** el `commit()` de reservas se daba por implícito («el store es autocommit», no verificado). Dos restos
  sobrevivían al primer endurecimiento: la sesión se registraba como **dueña** de cada reserva al ganar el claim y
  **antes** de confirmar, así que el cierre de turno intentaba retirar una fila que nunca se escribió; y el journal
  publicaba `claimed=True` de ese capital no reservado, dejando al monitor de concurrencia un dueño inexistente.
- **Cerrado:** no se asume autocommit. Un `commit()` fallido veta el instrumento (`reservation_unmeasurable`), deja el
  libro vivo como estaba, **no** registra propiedad y **no** publica claims ganados (las carreras perdidas sí, porque
  ocurrieron antes y sin depender del commit). La propiedad se registra sólo tras el commit confirmado.
  Certificado en `apps/api-python/tests/test_auto_m5_reservation_commit_fail_closed.py`: los dos tests de propiedad y
  claim **fallan** contra el código previo.

### M6 — La evidencia del journal no se pierde con un sink caído · ✅ Cerrado (`fix/auto-p5-p6-persistence` + certificado)
- **Fallo:** la cola de eventos de gestión de posición se vaciaba antes de publicar; si el sink fallaba, el hecho se
  perdía y el turno seguía como si la traza estuviera escrita.
- **Cerrado:** los eventos cuyo sink falla se **reencolan** (acotados por `_POSITION_JOURNAL_RETRY_CAP`, descartando
  los MÁS ANTIGUOS con un `ERROR` explícito) y se publican en el turno siguiente conservando el orden. Un evento
  descartado por tope es un hueco declarado, no un silencio. El descarte por tope y la publicación diferida quedan
  certificados en `test_auto_m5_reservation_commit_fail_closed.py`.

### M9 — `price_script` que lanza es «no hay precio» · ✅ Cerrado (`fix/auto-p5-p6-persistence`)
- **Fallo:** la fuente real (`PriceSource`) ya convertía una excepción en ausencia de precio, pero el `price_script`
  inyectado dejaba escapar la excepción del proveedor: el tick moría en vez de quedarse en HOLD.
- **Cerrado:** `_safe_price_script` envuelve la llamada y registra la excepción; `_v2_price_exec`/`_v2_price_mid`
  devuelven `None`, que es la misma declaración de «sin precio» que usa la fuente real. Certificado en
  `apps/api-python/tests/test_auto_m6_m9_fail_closed.py`.

### M1 — Cancelar y confirmar son escrituras CONDICIONADAS al estado leído · ✅ Cerrado (`53f6845a`, ack ampliado en esta PR)
- **Fallo:** `cancel_order` leía la fila, mutaba el objeto ORM y hacía `commit()`: entre la lectura y la escritura el broker podía reconciliar un fill, y el `UPDATE` ciego lo pisaba (y el upsert reescribía cantidades). El mismo patrón estaba en `set_broker_cancel_confirmed`, que es el **único** sitio que materializa un `CANCELLED` «verdadero»: un ack tardío podía convertir en `CANCELLED` una orden ya `FILLED`.
- **Cerrado:** las dos escrituras son `UPDATE … WHERE order_id=:k AND status=:leído AND filled_quantity=:leído`. Si la fila cambió, `rowcount == 0`, no se toca nada y se devuelve el estado vigente (`cancel_order`) o `None` (`set_broker_cancel_confirmed`: nada que confirmar, sin ack fabricado). Ninguna de las dos escribe `quantity`/`filled_quantity`/`remaining_quantity`; el `commit` sólo ocurre si el `UPDATE` afectó la fila.
- **Desvío declarado:** no hay columna `version` en `live_orders`; la valla es `(status, filled_quantity)`, que es exactamente el par que un fill cambia y el que un cancel no debe pisar. Añadir `version` exigía migración sin ganancia demostrable sobre este par.
- **Ampliación medida:** el ack condicionado (`set_broker_cancel_confirmed`) se cerró en esta PR, no en la anterior; sus dos tests nuevos **fallan** contra la implementación previa (`CancelDocumentation` devuelto con la carrera perdida, y `SET` sin condición).

### M2 — Un techo de posición no legible VETA, no desaparece · ✅ Cerrado (`e295092c`)
- **Fallo:** `max_position_pct`/`max_position_value` ≤ 0 se trataban como «sin techo»: el test de la auditoría aprobaba qty 100 con `max_position_pct=0`, y un `NaN`/`inf`/negativo de configuración daba barra libre.
- **Cerrado:** `0` es techo **cero** (veto con `CAP_POSITION_PCT`/`CAP_POSITION_VALUE`), e ilegible (`NaN`/`inf`) o negativo también veta; **sólo `None`** significa «sin techo por porcentaje». Lo mismo para `max_risk_per_trade_pct`, donde ya era así.
- **Desvío declarado:** un valor **negativo** veta en vez de lanzar excepción. La auditoría pedía «negativo = error»; se elige el veto porque un `raise` en el allocator tumba el turno entero y el resultado fail-closed (qty 0, `approved=False`) es el mismo que un error para el llamador, sin el riesgo de abortar el tick. La configuración ilegible sigue siendo visible en `capped_reasons`.

### M3 — `risk_budget` no finito o negativo no cae al presupuesto por porcentaje · ✅ Cerrado (`e295092c`)
- **Fallo:** un `risk_budget` `NaN`/`inf`/≤ 0 se descartaba en silencio y el sizing caía a `equity × max_risk_per_trade_pct`, es decir, un presupuesto **no medible** asignaba riesgo real.
- **Cerrado:** defensa en profundidad en la propia función: `risk_budget` no finito o negativo devuelve `approved=False`, `quantity=0.0` (no un fallback). Certificado con `NaN`, `inf` y `-10`; el test **falla** contra el código previo.

### M4 — El remanente de una salida vive en `[0, solicitado]` · ✅ Cerrado (`e295092c`)
- **Fallo:** `build_exit_order` aceptaba `remaining_qty` sin cota: pedir 10 y declarar 100 dejaba una orden de salida por diez veces la posición.
- **Cerrado:** un remanente negativo, no finito o mayor que lo solicitado **no se cree**: se deriva de `requested − filled` (acotado a `[0, requested]`). Un remanente consistente se conserva.
- **Desvío declarado:** **no** se exige `filled + remaining ≈ requested`. Una cancelación parcial legítima deja menos remanente que el solicitado y esa diferencia es información del broker, no una inconsistencia; imponer la igualdad obligaría a inventar el remanente.

### M11 — Un fold OOS plano no es positivo · ✅ Cerrado (`e295092c`)
- **Fallo:** `positiveOosFoldShare` contaba con `>= 0.0`, así que los folds de `0.0` inflaban la métrica frente al `R > 0` que usa el replay.
- **Cerrado:** criterio único `> 0` en la calibración; un fold plano no cuenta como positivo. Certificado con dos folds planos y uno positivo (`0.25`, no `0.75`); el test **falla** contra el código previo.

### M8 — Un turno operativo sin sus espejos durables se RECHAZA · ✅ Cerrado (`fix/auto-m8-m10-m14-durable-state`)
- **Fallo:** el runtime real componía sus stores por sesión, pero nada **exigía** que existieran. Sin `kill_switch_store`
  la parada dura vivía en RAM; sin `position_store`/`reservation_store` el compromiso de capital y la posición morían en
  el reinicio; sin `finance_applier` el turno «estructural» marcaba fills como `applied` sin libro financiero. El
  camino hermético (tests, replay) los omite **a propósito**, y esa misma laxitud dejaba que un cableado real
  incompleto operase con media cartera olvidada.
- **Cerrado:** `OPERATIVE_DURABLE_SEAMS` declara los seis espejos que hacen honesto un turno operativo
  (`exec_store`, `auto_store`, `finance_applier`, `position_store`, `reservation_store`, `kill_switch_store`) y
  `AutoSimRuntime` compone con `require_durable_stores=True`. Si a un turno le falta uno, `real_turn` **no muta
  estado**: declara `durable_stores_missing:<seams>` y devuelve el turno sin operar. El fallback estructural deja de
  ser una salida silenciosa en modo operativo. Certificado en `apps/api-python/tests/test_auto_m8_durable_stores.py`
  (falta un seam ⇒ rechazo con la lista exacta; todos presentes ⇒ el turno pasa; en operativo un settlement sin libro
  no se marca `applied`).

### M10 — La intención del operador es un hecho durable y gana al env · ✅ Cerrado (`fix/auto-m8-m10-m14-durable-state`)
- **Fallo:** AUTO se habilitaba **sólo** por `AUTO_SIMULATION_WORKER_ENABLED`. Un operador que apagaba el motor y
  reiniciaba el proceso con la variable todavía puesta lo veía arrancar otra vez: «apagar» era un acto del proceso, no
  una decisión registrada.
- **Cerrado:** migración `065_auto_engine_intent` crea `auto_engine_intent` (una fila por `(account_id, engine_id)` con
  `desired_state`, `reason`, `actor`, `updated_at`, `version`), `AutoEngineIntentStore` (§ PG + gemelo in-memory) y
  `GET/POST /api/auto/engine-intent` para declararla. `AutoSimRuntime` la lee **antes** de componer stores: un `OFF`
  explícito gana al env y el turno se omite declarando `operator_intent_off`; una intención **ilegible** también
  detiene el turno (`operator_intent_unreadable`).
- **Asimetría declarada:** la **ausencia** de fila **no** es `OFF` —el env sigue decidiendo— porque inventar un apagado
  al desplegar apagaría motores que hoy funcionan; y un `desired_state` fuera de `ON`/`OFF` no se escribe ni se
  interpreta como permiso. La fila es durable: `OFF` sobrevive a un reinicio en otro proceso.
  Certificado en `apps/api-python/tests/test_auto_m10_engine_intent.py` (store y versionado, gate del runtime,
  fail-closed de lectura) y `test_auto_m10_engine_intent_pg.py` (migración, `OFF` leído desde otra sesión, última
  intención gana, estado inválido no persistido).

### M14 — `book_equity` como snapshot atómico con `as_of` · ✅ Cerrado (`fix/auto-m8-m10-m14-durable-state`)
- **Fallo:** `load_book_equity` escribía tres atributos mutables (`_book_equity`, `_book_equity_required`,
  `_book_equity_unreadable`). Una cancelación o excepción **entre** las escrituras dejaba visible el equity del tick
  anterior como si fuera el actual; y nada declaraba a qué instante correspondía.
- **Cerrado:** `BookEquitySnapshot(equity, as_of, unreadable)` inmutable sustituye a los tres atributos. La lectura
  **invalida antes** de esperar (`unreadable=True`), de modo que una `CancelledError` o un fallo del libro no puede
  heredar el valor previo, y el snapshot captura el `as_of` de la lectura. `_v2_equity` decide con la foto completa.
  Certificado en `apps/api-python/tests/test_auto_m14_book_equity_snapshot.py` (stampado, veto por lectura fallida,
  `CancelledError` sin fuga del valor anterior, inmutabilidad).

### M12 — Lock del vigía con dueño probado y latido atómico · ✅ Cerrado (`fix/auto-m12-m13-watch-monitor`)
- **Fallo:** `day_is_running()` sólo comprobaba que existiera el directorio `.run.lock`; un lock **huérfano** (proceso muerto, host apagado o `lock.json` corrupto) silenciaba el «día perdido» para siempre. El latido se escribía con `write_text`, que deja una ventana en la que un lector ve el fichero truncado y pierde también las marcas de aviso.
- **Cerrado:** el lector aplica la MISMA política que el runner (`lockDecision`): lee `lock.json` (`pid`, `host`, `startedAt`) y sólo calla si el dueño se puede probar vivo —mismo host + PID vivo, otro host dentro del TTL de 12 h, o lock ilegible dentro de la ventana de adquisición de 5 min—. Un lock sin dueño probado vuelve a avisar. `write_status` escribe en temporal + `os.fsync` + `os.replace` (atómico en POSIX y Windows) y limpia el temporal si falla. En Windows la sonda de PID usa `OpenProcess`/`GetExitCodeProcess`, nunca `os.kill(pid, 0)` (que allí termina el proceso).

### M13 — Estado `INCOMPLETE` explícito en el monitor · ✅ Cerrado (`fix/auto-m12-m13-watch-monitor`)
- **Fallo:** las consultas del monitor se degradaban en silencio: una lectura caída y una cuenta sin operaciones producían el MISMO DTO (`cycles: []` + notas de «no durable»). Además, las lecturas de reservas/posiciones/engine no estaban protegidas y podían tumbar la ruta entera.
- **Cerrado:** cada lectura declara su resultado en `readStatus` (`COMPLETE`/`FAILED`, orden canónico en `MONITOR_READ_SOURCES`). Si alguna cae, el DTO publica `state: "INCOMPLETE"`, la lista `incompleteReads` y la nota `read_failed:<fuente>`. El contrato HTTP y el view model (`@bolsa/shared`) exponen `state`/`readStatus`/`incompleteReads`, y la UI (monitor experto y la historia de la operación) rotula «Lectura incompleta» con las fuentes antes de cualquier lista vacía: un vacío por fallo deja de leerse como «sin operaciones». Un ámbito demostrablemente vacío (sin ciclos) sigue declarándose `COMPLETE`.

### M16 — La cuenta y el instrumento de una ACTIVE son ámbitos distintos · ✅ Cerrado (`fix/auto-m16-account-scope`)
- **Fallo:** `AutoSimRuntime` pedía la estrategia ACTIVE con `load_active_strategy_decider(instrument_id=effective_account)`, es decir, la **cuenta** viajaba por la ruta del **instrumento** (y el símbolo de reserva sin watch era la cuenta). Funcionaba sólo porque la semilla de la ventana escribía la cuenta en `strategy_promotions.instrument_id`: una promoción de estudio (`inst-v229-…`) y una activa atribuida a una cuenta quedaban indistinguibles, y cualquier lectura por instrumento podía devolver la de la cuenta.
- **Cerrado:** migración `064_strategy_account_scope` añade `strategy_promotions.account_id` (nullable, **sin backfill**: rellenarla desde `instrument_id` sería repetir la confusión) con índice `(account_id, promoted)`. `ActiveStrategy` declara `account_id`, el store expone `get_active_for_account()` y `get_active()` sigue siendo la ruta de instrumento; `load_active_strategy_decider` recibe `account_id` **o** `instrument_id` (sin ninguno: `ValueError`, no un `None` mudo) y el runtime pide la cuenta por cuenta. La fila histórica (`instrument_id = <cuenta>`, `account_id = NULL`) se sigue leyendo por la ruta de compatibilidad, pero la ACTIVE devuelta declara `account_id = None`: el ámbito ausente no se inventa. La semilla de la ventana y el runner forward siembran/leen el ámbito correcto.

### M7 — Los fallos del control plane y del turno dejan de ser mudos · ✅ Cerrado (`fix/auto-m7-m15-control-plane`)
- **Fallo:** `auto_sim_loop` envolvía en `try/except: logger.exception(...)` tres cosas distintas —el refresco del watch, el del decider y el turno— y seguía como si nada. Un watch roto dejaba el **universo** del día anterior (y el turno abría con él, indistinguible de un turno sano), un decider roto dejaba la **estrategia** anterior, y un turno que reventaba se reintentaba cada 60 s sin backoff y **sin dejar rastro durable**: el ledger seguía en `RUNNING` con el último tick bueno.
- **Cerrado:** el fallo se declara, se propaga y acota el daño en tres capas.
  1. **Frescura declarada y veto de aperturas.** El worker mantiene tokens de control plane caducado (`watch_refresh_failed`, `decider_refresh_failed`, `tick_failed`, `circuit_breaker_paused`). Con cualquiera vigente, `auto_turn` veta el `BUY` con el motivo propio `control_plane_stale` (no disfrazado de `position_reconciliation_not_ok`) y **el SELL sigue permitido**: reducir/cerrar nunca empeora el riesgo, así que una salida protectora no puede quedarse colgada porque el universo no refresque. Cada token se levanta **sólo** con el éxito de su propio refresco.
  2. **Backoff exponencial acotado.** `auto_sim_backoff_seconds(base, failures)` duplica la espera por fallo consecutivo hasta `AUTO_SIM_BACKOFF_MAX_SECONDS` (300 s por defecto) y vuelve al intervalo base con el primer turno bueno. Sin fallos devuelve el intervalo configurado (Δ = 0 respecto del loop anterior).
  3. **Circuit breaker a `PAUSED` y rastro durable.** `AutoSimRuntime.note_tick_failure(streak)` marca el turno como caducado y, al llegar a `AUTO_SIM_TICK_BREAKER_FAILURES` fallos consecutivos (3 por defecto; `0` desactiva el breaker), **pausa** el motor: `run_tick` no se intenta (`declare_skip` con el motivo) hasta un `resume()` explícito del operador —un motor que revienta tres turnos seguidos necesita que alguien mire—. Cada fallo se matricula en el ledger con el siguiente `seq`, `activity=BLOCKED` y estado `DEGRADED` (`PAUSED` al abrir el breaker) con `reason=tick_failed:<racha>`. **Desvío declarado del texto «persistir tick `ERROR`»:** el vocabulario de estado es cerrado (`RUNNING/PAUSED/BLOCKED/DEGRADED/REQUIRES_ATTENTION`) e inventar `ERROR` haría que `_state_of` lo degradara a `REQUIRES_ATTENTION` por desconocido; `DEGRADED` + `last_reason` es el mismo hecho, legible por el monitor y por un reinicio.
- **También la lane SAFE/dry:** `paper_auto_engine_loop` ya marcaba `DEGRADED` cuando el tick fallaba; ahora un `watch_refresher` que **lanza** también lo marca (antes sólo quedaba el log). Su resolución de watch ya era fail-closed (sin ESTUDIO ⇒ cache vacía ⇒ no opera), así que lo que faltaba era declarar la excepción, no cambiar la política.
- **Certificado** en `apps/api-python/tests/test_auto_m7_control_plane_health.py`: con el control plane caducado el turno **no abre** y **sí cierra**, el motivo declarado es `control_plane_stale`; el backoff da `[60, 120, 240, 300]` con rachas `[1, 2, 3]`; el breaker pausa al umbral y sólo `resume()` lo rearma; el turno fallido queda en `auto_engine_ticks`/`auto_engine_runs` (test PG). Contra el código previo fallan por construcción (los tokens, los hooks y el backoff no existían y el `BUY` se ejecutaba).

### M15 — El P&L parcial se mide contra el coste medio ponderado · ✅ Cerrado (`4d3082fd` + certificado)
- **Fallo:** al ampliar una posición viva, `_entry_price` conservaba el precio de la **primera** entrada, así que el P&L realizado (y el no realizado, y el trailing, que usan la misma referencia) se medían contra un coste que ya no era el de la posición.
- **Cerrado:** `_blend_entry_price(prior, held, price, qty)` mezcla el coste por cantidades en la rama de ampliación del fill `BUY`. La referencia sigue siendo **una sola** (`_entry_price`), que es exactamente lo que hace que la corrección llegue a todo lo que la usa: `entry_ref = self._entry_price.get(symbol)` en el P&L realizado de la venta parcial/total, el no realizado y la protección. `_canonical_entry_prices` reconstruye la base desde los fills aplicados del libro canónico, así que un reinicio también la readopta mezclada.
- **Alcance medido (por qué el impacto era bajo):** el turno **no apila** —`if action == "BUY" and held > 0: continue`—, de modo que la rama de ampliación no se alcanza decidiendo un segundo `BUY`; se alcanza cuando un fill se aplica sobre una posición ya viva (materialización de una orden pendiente de un turno anterior / re-liquidación idempotente). La mezcla sigue siendo la respuesta correcta en ese caso; lo que se corrige es que la base de coste no mintiera.
- **Certificado** en `apps/api-python/tests/test_auto_m15_blended_entry.py`: `100@100 + 100@110 ⇒ 105` (y `300@100 + 100@120 ⇒ 105`), total nulo conserva la base previa, el P&L de `200@115` sobre coste 105 son `2.000` (no los `3.000` del primer fill) y tres ampliaciones seguidas convergen al promedio directo `112,5`.

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
- **S1 — La máquina de estados admite `PROMOCION → ACTIVE` sin comprobar gates** (`strategy_lifecycle.py:769-770`, `can_transition` devuelve `allowed=True`). `evaluate_promotion()` sí exige los siete gates, COACH sin veto y shadow, pero un llamador directo puede saltárselos. **Debería ser:** que la transición exija `validation.passed`, COACH y shadow, centralizada en el resultado de `evaluate_promotion()`. · **✅ Cerrado (V2.35.1, verificado `2026-11-05`)** — ver cierre al final de la sección.
- **S2 — Umbrales de LAB triviales por defecto:** `min_oos_score=0.0`, `min_wfe=0.0`, `max_pbo=1.0`, y el gate de riesgo solo exige `max_drawdown_pct >= 0` (`strategy_lab_phase.py:228-235`, `:356-365`). **Debería ser:** umbrales no triviales, límite máximo de drawdown, muestra mínima de operaciones y retorno neto de costes. · **✅ Cerrado (verificado `2026-11-05`)** — ver cierre al final de la sección.
- **S3 — Sin corrección por pruebas múltiples en discovery** (`strategy_lab_phase.py:237-305`): se elige un campeón y se evalúa su OOS sin registrar el número de configuraciones. Riesgo de data snooping. **Debería ser:** registrar el universo probado y aplicar DSR, PBO o un hold-out intocable. · **✅ Cerrado (`fix/auto-s3-multiple-testing`)** — ver cierre al final de la sección.
- **S4 — Lookahead potencial por contrato:** `SignalEventV1` publica la señal con `closes[index]` y el timestamp de la barra `t` (`rules_engine.py:639-692`). El simulador lo evita (`rules_grid.py:91-96`: señal en `index-1`, ejecución al `open(index)`). El worker usa la barra cerrada anterior para decidir y el `open` actual para ejecutar, lo cual es correcto, pero el contrato general no lo impone. **Debería ser:** `signal_bar=t` y `execution_bar=t+1` explícitos en el contrato. · **✅ Cerrado (`fix/auto-s4-signal-timing`)** — ver cierre al final de la sección.

### Media
- **S5 —** El avance de fase solo exige que exista algún `GateResult` sin fallo, no que sean los gates requeridos de esa fase (`strategy_lifecycle.py:727-755`). Definir `estado → gates obligatorios`; `NOT_EVALUATED` bloquea. · **🟡 Parcial (verificado `2026-11-05`):** el mecanismo existe (`required_gates` + `gates_no_evaluados`), pero **ningún llamador de producción pasa `required_gates`** y no hay tabla `estado → gates obligatorios` en el dominio: en la ruta real la obligación sigue sin cablear.
- **S6 —** `PROMOCION` no comprueba que la evidencia corresponda a la misma versión, definición y dataset (`:758-766`). Verificar identidad por `version_id`, hash y fingerprint. · **🟡 Parcial (verificado `2026-11-05`):** `_evidence_identity_reasons` compara `version_id` (validación y shadow contra el finalista) y veta `evidencia_*_otra_version`; **no** compara definición ni dataset porque `StrategyValidation` no transporta `strategy_definition_hash`/`bars_hash`/`data_snapshot_id` — el fingerprint viaja en `ShadowValidationResult` pero no hay con qué cruzarlo.
- **S7 —** La vigilancia trata una métrica ausente como "sin degradación" y no valida su frescura (`strategy_vigilance_phase.py:107-178`). Una estrategia activa con el feed roto sigue operando. Distinguir `unmeasured/stale/healthy` con TTL y `version_id`. · **✅ Cerrado (`fix/auto-s7-vigilance-freshness`, PR [#90](https://github.com/jvelasca/Bolsa_V1/pull/90))** — ver cierre al final de la sección.
- **S8 —** Contexto close-only: `open=high=low=close`, `volume=0` (`signal_feature_context.py:36-83`). ATR, VWAP y Stochastic se calculan con datos artificiales. Sin OHLCV completo, devolver HOLD con motivo `insufficient_data`.
- **S9 —** `NaN`/`inf` no se validan en indicadores (`indicators/legacy.py`, `signal_feature_context.py:49-55`); RSI sin validar `period > 0`.
- **S10 —** La identidad de señal no es un claim atómico (`signal_identity.py:50-117`); `build_signal_identity()` devuelve `None` ante campos faltantes y un llamador puede ignorarlo. Las alertas sí tienen claim atómico (`signal_alerts.py:174-195`).

### Baja
- `bar_window()` con epoch no coincide con la frontera del proveedor en timeframes no divisores de 24 h (`signal_identity.py:78-95`).
- El cruce usa `<=`/`>=` en la barra previa, así que la igualdad cuenta como cruce (`rules_engine.py:246-263`).
- Las métricas observadas usan una única cola FIFO para todos los instrumentos (`strategy_observed_metrics.py:116-125`).
- `profit_factor` sin pérdidas devuelve `None`, indistinguible de "no medido".

### Cierres de la sección de estrategia

#### S1 — `PROMOCION → ACTIVE` sin comprobar gates · ✅ Cerrado (V2.35.1, verificado `2026-11-05`)
- **Fallo:** `can_transition(PROMOCION)` devolvía `allowed=True` sin mirar la evidencia; un llamador que no pasara por `evaluate_promotion()` podía promocionar a `ACTIVE` sin los siete gates, sin COACH y sin shadow.
- **Cerrado:** la transición exige `validation` presente y `validation.passed` (los siete `PROMOTION_GATES` en PASS), COACH presente y sin veto, y `shadow.passed`; sin shadow o con shadow fallido responde `shadow_validation_requerida`. La ruta automática **no** acepta el override booleano `shadow_validated` (V2.35.1): el override administrativo vive solo en `evaluate_admin_promotion`. Pruebas: [`test_strategy_lifecycle_s1_s5_s6.py`](../../packages/py/domain/tests/test_strategy_lifecycle_s1_s5_s6.py) (sin evidencia ⇒ `validacion_ausente`; sin COACH ⇒ `coach_ausente`; COACH con veto ⇒ `coach_veto`; sin shadow o con shadow fallido ⇒ `shadow_validation_requerida`; con la evidencia completa ⇒ `ACTIVE`).

#### S2 — Umbrales de LAB triviales por defecto · ✅ Cerrado (verificado `2026-11-05`)
- **Fallo:** `min_oos_score=0.0`, `min_wfe=0.0`, `max_pbo=1.0` no filtraban nada y el gate de riesgo solo comprobaba `max_drawdown_pct >= 0`, así que un campeón con drawdown enorme y muestra anecdótica pasaba.
- **Cerrado:** `LabThresholds` publica `min_oos_score=0.1`, `min_wfe=0.5`, `max_pbo=0.5`, `min_dsr=0.7`, `max_drawdown_pct=25.0` (techo) y `min_trades=30` (muestra mínima de operaciones). El gate `risk` exige `0 ≤ drawdown ≤ techo` **y** `sample_trades ≥ min_trades`, y declara `drawdown_excede_techo` / `muestra_insuficiente` / `trades_ausentes` cuando no. Un `None` en `oos` o `risk` es gate no superado (`oos_ausente` / `risk_ausente`), no un pase.
- **Límite declarado:** "retorno neto de costes" **no** se re-verificó aquí: el `oos` mide el score del campeón tal como lo produce el LAB y el tratamiento de costes es materia de `AUTO-16/17`, no de este umbral.

#### S5 — Gates obligatorios por fase · ✅ Cerrado (`fix/auto-s5-required-gates`)
- **Fallo:** `can_transition` aceptaba cualquier `GateResult` sin fallo y `required_gates` era una opción que **ningún llamador de producción pasaba**; no existía tabla `estado → gates obligatorios`. Además el orquestador escribía `state='finalista'` sin consultar la máquina de estados: el embudo avanzaba por haber llegado, no por evidencia de la fase.
- **Cerrado:** el dominio declara `REQUIRED_GATES_BY_STATE` (gates que deben estar en PASS para **entrar** en cada estado, acumulativos) y `can_transition` los aplica **siempre**; `required_gates` del llamador solo **añade**, nunca rebaja. `NOT_EVALUATED` no es PASS y bloquea con `gates_requeridos_ausentes:<lista>`. `can_advance_to(current, target, …)` recorre todos los saltos intermedios —un ciclo real cruza varias fases— y el orquestador lo consulta **antes** de materializar el finalista: si falta un gate de la fase devuelve `transicion_refusada` con sus motivos y no ejecuta la evidencia shadow. El TOP3 (`select_top3`) deja de tener su propia lista paralela y usa `required_gates_for(FINALISTA)`, así que la barrera de entrada y el avance de fase hablan del mismo contrato.
- **Alcance declarado:** `can_advance_to` exige los gates **obligatorios** de las fases recorridas en PASS; un `FAIL` en un gate que la fase no exige (`dsr`/`risk` antes de `PROMOCION`) no corta el avance —de eso responde el Promotion Gate con los siete—, y `VALIDACION`/`PROMOCION`/`ACTIVE` no se deciden con gates sueltos (`can_advance_to` responde `validacion_ausente`). Con el LAB actual el TOP3 ya exige esos cuatro gates, así que el corte es defensa en profundidad para cualquier relajación futura (`min_gates`) o llamador que salte fases.

#### S6 — Identidad de la evidencia · ✅ Cerrado (`fix/auto-s6-evidence-identity`)
- **Fallo:** `_evidence_identity_reasons` solo comparaba `version_id`. El fingerprint del dataset existía en `ShadowValidationResult`, pero `StrategyValidation` no transportaba ninguno, así que una validación de otra **definición** o de otro **dataset** era indistinguible de la correcta, y nada demostraba que el tramo shadow no fuera el tramo del LAB.
- **Cerrado:** `StrategyValidation` **declara** su identidad (`strategy_definition_hash`, `data_snapshot_id`, `bars_hash` del tramo LAB) y el Promotion Gate la contrasta: definición de la validación y del shadow contra el hash inmutable del finalista (`evidencia_validacion_otra_definicion` / `evidencia_shadow_otra_definicion`), snapshot compartido validación↔shadow (`evidencia_shadow_otro_dataset`) y **anti-solape** (`evidencia_shadow_mismo_dataset`) cuando el `bars_hash` del shadow es el mismo que el del tramo LAB. `decide_promotion`/`decide_admin_promotion` estampan la identidad del finalista y aceptan `validation_bars_hash`; el orquestador calcula ese hash con `lab_window_bars_hash` (misma identidad de dataset y mismo algoritmo que el shadow) y lo aporta a la decisión.
- **Límite declarado:** un fingerprint **ausente no se compara** —no se inventa—: los finalistas históricos y el override administrativo no los llevan, y esa ausencia sigue siendo un hueco declarado. El hash de definición del shadow lo estampa el replay desde el finalista, así que la comparación **corrobora procedencia** (que la evidencia emparejada es de esta definición), no recalcula el hash desde las barras ejecutadas.

#### S7 — Vigilancia: ausencia de medida y frescura · ✅ Cerrado (`fix/auto-s7-vigilance-freshness`, PR [#90](https://github.com/jvelasca/Bolsa_V1/pull/90))
- **Fallo:** `VigilanceDecision` declaraba `unmeasured`, pero `fail_on_unmeasured` venía **apagado** (la ruta por defecto seguía sin degradar) y no había **ninguna** noción de caducidad: una evidencia predictiva de hace un año era indistinguible de una de ayer, así que una activa con el feed roto seguía operando sin que nada lo declarara.
- **Cerrado:** `health_state` gana el estado `stale` con precedencia `degraded` > `stale` > `unmeasured` > `healthy` (falta o vejez **nunca** es salud). `HealthThresholds.max_metric_age_days` fija el TTL de la evidencia **predictiva** —la del LAB que sostiene la activa, que es la que caduca porque no se re-mide cada ciclo— y `fail_on_stale` decide si degrada (default) o solo se declara; `VigilanceDecision` publica `stale` (`evidencia_caducada`, `evidencia_sin_fecha`, `evidencia_de_otra_version`) y `metrics_age_days`. La identidad por `version_id` **no depende del TTL**: evidencia de otra versión no describe esta activa. `fail_on_unmeasured` pasa a **fail-closed por defecto**, pero acotado al bloque predictivo: la ausencia de observado significa «aún no hay muestra» y su decisividad ya la gobierna `min_observed_trades`.
- **Cableado (lo que el cambio destapó):** el LAB publica el edge como `robust_score`, no como `edge` ⇒ `min_edge` **nunca** se aplicaba y se resuelve con alias explícito; `min_credibility` del worker era un veto fantasma sobre una métrica que el pipeline no produce (ahora solo se declara por env); `watch_active` **arrastra** la evidencia predictiva del último snapshot con su `as_of` (sin eso, fail-closed producía promoción → degradación → re-LAB en bucle) y el `as_of` del snapshot es el ancla del TTL, no la identidad de la pasada; `save_health` persiste `health.as_of` en vez de `now()` —el `INSERT` estampaba la hora de escritura, con lo que la edad de la evidencia nunca crecía y el TTL habría sido decorativo— y un `as_of` no temporal cae a `now()` sin inventar una fecha de medición. El worker deja de pasar `as_of=result.status` y pasa el id del ciclo.
- **Límite declarado:** el estado fino (`stale`/`unmeasured`) vive en la decisión y en el log del worker; el snapshot persistido conserva su forma (sin columnas nuevas) y el DTO de salud sigue derivando `degraded` de umbrales y valores. Persistir el estado exige migración y queda fuera de este hallazgo. El TTL es opt-in por env (`AUTO_ORCHESTRATOR_HEALTH_MAX_METRIC_AGE_DAYS`, default sin TTL) — igual que el resto de endurecimientos del proyecto, la declaración es siempre y el endurecimiento es explícito y reversible.

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

1. **Fail-open de configuración y datos:** P1, P2, P4, P9 (bajo riesgo de cambio, alto impacto) · ✅ cerrado.
2. **Persistencia fallida ignorada:** P5, P6, M5, M6, M9 · ✅ cerrado.
3. **Circuit breaker y estado durable:** P3, P8, M8, M10, M14 · ✅ cerrado.
4. **Concurrencia:** P7, M1 · ✅ cerrado.
5. **Gates de estrategia:** S1, S2, S5, S6, S7, S3 · ✅ cerrado.
6. **Validaciones de bordes:** M2, M3, M4, M11 · ✅ cerrado.
7. **Resiliencia del loop y coste de la posición:** M7, M15 · ✅ cerrado. Queda la severidad baja y `S8`-`S10`.

Cada corrección debería ir con un test que muerda (entrada `NaN`, `None`, valor desconocido o fallo de persistencia inyectado) para que el comportamiento fail-closed quede protegido.

## 7. Entorno de la auditoría

- Herramientas sobre el tag: ruff limpio; import-linter 4 contratos OK; mypy 583 ficheros, 0 errores; pytest dominio, aplicación y analítica 4614 passed, 5 skipped; `tsc` limpio; ESLint 0 errores, 23 avisos; vitest 2743 passed.
- Dependencias con avisos: pyjwt 2.13.0, pillow 12.3.0, urllib3 2.7.0, react-router y deepmerge-ts.
- Workflows de CI sin bloques `permissions:` y con acciones fijadas por tag, no por SHA.
- Ficheros muy grandes (3k–9k líneas), entre ellos `auto_simulation_worker.py`, lo que dificulta la revisión.
