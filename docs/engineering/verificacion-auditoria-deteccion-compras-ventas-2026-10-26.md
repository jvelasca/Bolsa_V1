# Verificación independiente de la auditoría de detección de compras y ventas

**Fecha:** 2026-10-26 · **Base:** `HEAD = 8ce53c3c` (`docs(evidence): corrige la composición de §8 (W-2)…`)
**Naturaleza:** verificación **read-only** del documento y del código. No modifica estado operativo,
`PROJECT_STATE.md`, pin PAPER, CI ni la nota del dictamen. **No** crea commit, tag, PR ni push.
Excepción declarada: la primera ejecución de PG-4 reescribió el latido del vigía sin cambiar su
contenido (§1.2); tras aislar el directorio de estado en el banco de pruebas, la **re-ejecución no
lo tocó** (§5.2 y §5.4), con `sha256` y `mtime_ns` idénticos antes y después.
**Objeto verificado:** [`auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md`](./auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md), **1 063 líneas** tras la corrección documental (890 en la lectura original).

**Qué es y qué no es este documento.** Es el contraste independiente de la auditoría: fija qué
afirmaciones se ratifican, cuáles se corrigen y cuáles siguen sin medirse. **No** sustituye la
clasificación P0/P1/P2 del documento auditado ni reordena su backlog: añade observaciones donde la
evidencia no sostiene la afirmación. **No** convierte una prueba hermética en validación operativa.

---

## 0. Veredicto de integridad

| Bloque | Veredicto | Detalle |
|---|---|---|
| Estado del repositorio (§8.0) | **CORREGIDO** | `git status --porcelain -- docs/engineering` devuelve **dos** entradas, no una: el dictamen modificado y el propio documento de auditoría sin seguimiento. |
| Anclajes `fichero:línea` | **RATIFICADO con reservas** | 112 referencias; 95 sin discrepancia detectada; 4 derivas de ±1–2 líneas; 5 rangos truncados; 7 irresolubles por basename ambiguo; 1 fuera de rango (§2). |
| Recuento de presets | **CORREGIDO** | El catálogo tiene **21** presets, no 20. La conclusión «4 presets inoperables» se mantiene; el denominador correcto es **4/21**. |
| SMA200 inalcanzable con 120 barras | **RATIFICADO** | Reproducido exacto: 120/120 `None` con 120 barras; primer valor en el índice 199. |
| `raw` frente a `gated` | **RATIFICADO** | Reproducido exacto: `['exit']` frente a `[]`. |
| Decisor close-only frente a scan OHLCV | **RATIFICADO, CUANTIFICADO Y CORREGIDO** | La magnitud publicada antes (**13/16**) **no se reproduce**: la divergencia de **acción** es **5/16** (4 `vwap_reclaim` + 1 `supertrend_follow`) y la de **eventos** `raw`/`gated` es **3/16**. El fix de procedencia está aplicado en el árbol (sin commit) y el contrato gated pasa **16/16** (§3.4, §5.4). |
| Escalera de vetos «18 familias / 16 pasos» | **MATIZADO** | El docstring tiene **19 entradas numeradas** (1–18 más 3.b) y 27 `reason_code`; el cuerpo emite 19 `_reject` literales más 5 familias dinámicas. |
| 11 disparadores de salida | **RATIFICADO** | 11 motivos; 9 en `_HARD_TRIGGER`; `TIME_STOP` queda `HINT` con `suggested_action=full_exit`. |
| «20 condiciones falsables de §9–§11» | **RETIRADO (no era una afirmación del original)** | El documento auditado **no** afirma «20 condiciones»: §9 tiene **18** filas con ID y §10–§11 no son criterios. La reconstrucción `B(6) + S(6) + O(6) + T(2) = 20` era una hipótesis de **esta** verificación, no un hecho del texto. Con `O-5`, `O-6` y `T-3` añadidos, la auditoría pasa a **21**. |
| Suites herméticas (319) | **AMPLIADO a 325 / 360** | Los grupos originales pasan de 319 a **325** (85+62+45+12+121, con 6 pruebas nuevas dentro de ellos); con las **35** de la iteración (contrato, alertas y guarda) el total es **360**, 0 saltadas, 0 fallidas (§5.1). |
| Contrato scan↔decisor | **CERRADO a nivel E1** | 16/16 pares preset×escenario coinciden con la proyección `gated` de la misma feature; Δ del fix = 5/16 acciones (§5.4). |
| PostgreSQL no ejecutado | **SUPERADO en esta verificación** | Se ejecutaron **38** pruebas PG en una base desechable (§5.2) y se **re-ejecutó PG-4** (7 pruebas) tras aislar el vigía (§5.2). |
| Efecto lateral sobre `day-watch` | **REATRIBUIDO Y AISLADO** | **No** lo produce `test_auto_scheduler_real_pg_zero_human_intervention` (no arranca el scheduler). Lo producían los tests que lanzan `python -m bolsa_api.workers.scheduler_worker` por `_spawn`/`_env_for` (§1.2). El banco ya fija `WINDOW_DAY_WATCH_ENABLED=0` y un `WINDOW_DAY_WATCH_DIR` temporal, y una guarda de sesión falla si el árbol cambia: la re-ejecución dejó hashes y `mtime_ns` idénticos. |
| Validación operativa | **NO DEMOSTRADA** | Sigue sin haber procesos vivos medidos ni ventana cerrada. Ningún `CERTIFICADO` de este anexo implica rentabilidad. |

---

## 1. Estado del repositorio y artefactos leídos

### 1.1 Repositorio

| Comprobación | Valor medido |
|---|---|
| `HEAD` (en la verificación) | `8ce53c3c68dedc192dbf1ab84df34885851b9f22` |
| Rama | `audit/c1-c4-integrity-fold-2026-10-25` |
| Upstream | `origin/audit/c1-c4-integrity-fold-2026-10-25` |
| Commits del bloque | `be1c1295`, `8ce53c3c` y el del sello `2.11.162-beta` |
| Tags en `HEAD` | 0 |
| `git status --porcelain` | **0 entradas** tras el commit del sello `2.11.162-beta` (antes: **18** — `11 M` + `7 ??`). 8 ficheros de código/prueba modificados + 5 nuevos, el dictamen `M`, los 2 documentos `??` y 2 rutas que git marca `M` **solo por fin de línea** (`test_auto_v44_exit_governance.py`, `hard_kill_switch.py`: `git diff` vacío). **Todo entra en el commit del sello `2.11.162-beta`.** |
| `operability_runs/` | No trackeado ⇒ `git status` no puede detectar reescrituras de `day-watch.*`; se auditan por `sha256` + `mtime_ns` (§1.2) |

**Límite de la comprobación:** `operability_runs/` **no está trackeado**, de modo que `git status`
**no puede** detectar una reescritura de `day-watch.json`/`day-watch.jsonl`. Esa limpieza se mide
por `sha256` + `mtime_ns` + tamaño (§1.2), no por git.

### 1.2 Artefactos de la ventana (read-only)

| Artefacto | `sha256` | Bytes | `mtime` | Hora de lectura |
|---|---|---|---|---|
| `operability_runs/window-runs/ledger.jsonl` | `69A25F1FCC24244717AB1AD7A7A279965641FFCE6E2AA370FE6833F13E26E175` | 26 499 | 2026-10-25T18:30:01+01:00 | 16:40:46, 16:52, 17:20 y 17:35 (sin cambios) |
| `day-watch.json` (1.ª lectura) | `E5BB15D1C350CC06BE9F8CD87396EDF8B7112672A4AD44C60EC9D50CF61027E0` | 659 | 2026-10-26T16:28:37+01:00 | 16:40:46 |
| `day-watch.json` (2.ª lectura) | `DB11882AD496B5037106A867B10ECE7241870D5338678FC91982C6888A9499B0` | 659 | 2026-10-26T16:47:06+01:00 | 16:52:24 |
| `day-watch.json` (**3.ª lectura**) | `0D14165A88CFA148275AF7C689753BD46E953450B27E387B3C6F6CB85071DA95` | 659 | 2026-10-26T17:05:56+01:00 | 17:15 y 17:35 |
| `day-watch.jsonl` (2.º recuento) | `0A8D1B19A4C26A615EFF679995BB422CB743B9CC98F4832BA3B9B323B5A2B5AD` | 433 073 | 2026-10-26T16:47:06+01:00 | **948** líneas |
| `day-watch.jsonl` (**3.ª lectura**) | `9AF8A3E259570021B81B073055191164F97E8930C077AC6F4634469DF77C5706` | 434 391 | 2026-10-26T17:05:56+01:00 | **950** líneas, 17:15 y 17:35 |

El documento auditado cita `day-watch.json` con marca `16:13:37`. El artefacto se reescribió a las
`16:28:37`, a las `16:45:09`, a las `16:46:30`, a las `16:47:06` y a las `17:05:56` (mismo día y
mismo contenido semántico: `NOT_DUE`, avisos `20261020:MISSED` y `20261023:MISSED`, `alerted`
incluye `20261025:NON_MARKET_DAY`). **Es un artefacto vivo**: la marca del documento no es
reproducible y debe citarse siempre con hash y hora de lectura. La escritura de las `17:05:56` es
del **proceso vivo** de la ventana, anterior a la re-ejecución de PG-4; el banco de pruebas ya no lo
toca (§5.4).

**Efecto secundario — atribución corregida.** Las tres últimas reescrituras (`16:45:09`, `16:46:30`,
`16:47:06`) coinciden con la ejecución del grupo **PG-4**, pero el productor **no** es
`test_auto_scheduler_real_pg_zero_human_intervention`: ese test construye `AutoSimRuntime` y
`AutoSimulationWorker` **directamente** y **no arranca el scheduler** (no hay `Popen` ni
`start_window_day_watch` en su cuerpo). Los procesos que escriben el latido son los tests que lanzan
`python -m bolsa_api.workers.scheduler_worker` mediante `_spawn`/`_env_for`
(`apps/api-python/tests/test_golden_day_v2_process_pg.py:792-841`, compartidos por
`test_auto_v46_multiprocess_pg.py`, `test_crash_recovery_day_process_pg.py` y
`test_auto_dia_d_trace_pg.py`). El scheduler arranca `start_window_day_watch`
(`apps/api-python/src/bolsa_api/workers/scheduler_worker.py:100-102`) y el vigía es **on-by-default**
(`WINDOW_DAY_WATCH_ENABLED`, default `True`), así que cada arranque deja un latido.

El contenido no cambia salvo `at`. El **ledger no se tocó**. Se documenta como efecto del banco de
pruebas, no como operación nueva: ningún test midió un día, solo reescribió el mismo `NOT_DUE`.

**Corrección aplicada.** El vigía acepta ahora un override de directorio (`WINDOW_DAY_WATCH_DIR`) y
el banco de pruebas lo apunta a un temporal con `WINDOW_DAY_WATCH_ENABLED=0` por defecto:
`conftest.py` (fixture `autouse` para el proceso de pytest), `_env_for`/`_spawn` de
`test_golden_day_v2_process_pg.py` y los dos `Popen` de
`test_a9_scheduler_process_pg_zero_human.py`. Además, una guarda de sesión
(`tests/_day_watch_guard.py`, con pruebas en `test_day_watch_repo_guard.py`) captura
`sha256`/tamaño/`mtime_ns`/líneas al empezar y falla al terminar si cambiaron, atribuyendo la
mutación por `runId`. Resultado medido en la re-ejecución: **hashes y `mtime_ns` idénticos**
(§5.2 y §5.4). El efecto queda cerrado como defecto de reproducibilidad; **no** convierte W-1 en
evidencia operativa.

### 1.3 Ledger: recuento verificado

| Métrica | Documento | Medido | Resultado |
|---|---|---|---|
| Filas | 12 | 12 | coincide |
| Días distintos | 9 | 9 | coincide |
| `MEDIDO` | 3 | 3 | coincide |
| `HARD_ERROR` | 2 | 2 | coincide |
| `NON_MARKET_DAY` | 3 | 3 | coincide |
| `NO_MEDIDO_REGIMEN` | 4 | 4 | coincide |
| Veto `regime_invalid` | — | 4 | coherente con `NO_MEDIDO_REGIMEN` |
| Gate de los `MEDIDO` | `episodes=0`, `cycles=0`, `INCONCLUSIVE` | idéntico en 20261019/21/22 | coincide |

Los tres días `MEDIDO` llevan `ready=False`, `measured=True`, `minEpisodes=2`, `minCycles=32`.
**Ningún dato del ledger acredita rentabilidad.**

---

## 2. Contraste de anclajes (§2–§6)

### 2.1 Método y política de tolerancia

Se extrajeron las **112** referencias `fichero:línea` sobre **53** ficheros distintos y se resolvió
cada ruta por coincidencia exacta y, si era basename, por sufijo con frontera de directorio
(excluyendo `.venv`, `node_modules` y cachés). Clasificación aplicada:

- **EXACTO**: el rango existe en el fichero y contiene el símbolo que la frase le atribuye (±1 línea
  se considera deriva formal, no error).
- **DERIVA**: el rango existe pero el símbolo citado cae 1–2 líneas fuera.
- **MISMATCH**: el rango apunta a otro símbolo.
- **IRRESOLUBLE**: la ruta no identifica un fichero único.

### 2.2 Resultado mecánico

| Estado | Referencias | Comentario |
|---|---|---|
| Rango válido y sin discrepancia detectada | 95 | la comprobación mecánica no encontró desajuste; no equivale a revisión semántica de las 95 |
| Deriva formal de ±1–2 líneas | 4 | el símbolo citado cae justo fuera del rango |
| Rango truncado | 5 | el tramo no cubre el bloque que la frase describe |
| IRRESOLUBLE por basename ambiguo | 7 | `scans.py` (3 candidatos) y `signal_alerts.py` (3 candidatos) |
| FUERA_DE_RANGO | 1 | `auto_simulation_worker.py:9270-9283`; el fichero tiene 9281 líneas |
| **Total** | **112** | |

Las cuatro derivas formales son: `active_strategy_signal_evaluator.py:115-199`,
`exit_plan.py:221-226`, `auto_v2_entry.py:1759-1760` y `position_manager.py:299-301`. Los cinco
rangos truncados son: `rules_engine.py:605-691`, `strategy-presets.json:1-740`, `:139-166`,
`:424-452` y `:454-500`. Ninguno invalida el hallazgo que sostiene la cita; se corrigen en §2.3.

### 2.3 Anclajes que deben corregirse en el documento auditado

| Ubicación | Cita actual | Problema | Corrección propuesta |
|---|---|---|---|
| §1, §2 y §3.5 | `rules_engine.py:605-691` | la función `evaluate_rules_signals` ocupa **606-692**; el rango omite el `return events` | `606-692` |
| §6.1 tabla | `auto_simulation_worker.py:9270-9283` | **MISMATCH**: ese tramo es `_sim_interval_seconds` y el fichero acaba en 9281. El bucle real es `auto_sim_loop` | `8722-8767` (bucle); `9268-9281` es el helper de intervalo |
| §5.3 | `exit_plan.py:221-226` | `fired.add("TIME_STOP")` está en **227** | `221-227` |
| §4.4 | `position_manager.py:299-301` | `regime_exit = regime_is_exit_only(regime)` está en **302** | `299-302` |
| §4.4 | `auto_v2_entry.py:1759-1760` | 1759 es `mark_price`; la normalización a `UNKNOWN` está solo en 1760 | `1760` |
| §3.1 | `strategy-presets.json:1-740` | el catálogo tiene **765** líneas: el rango omite 25 y no cubre «todo» el catálogo; además «20 estrategias» son 21 | `1-765` y corregir el recuento |
| §3.3 tabla | `strategy-presets.json:139-166` | el bloque `death_cross` llega a **172**: el rango omite su regla de salida (167-170) | `139-172` |
| §3.3 tabla | `strategy-presets.json:424-452` | el bloque `price_above_sma200` cierra en **453** | `424-453` |
| §3.3 tabla | `strategy-presets.json:454-500` | el bloque `ma_stack_bullish` cierra en **501** | `454-501` |
| §3.4–§3.8 | `scans.py:…`, `signal_alerts.py:…` | basename ambiguo: tres candidatos cada uno | `packages/py/application/src/bolsa_application/scans.py` y `…/signal_alerts.py` |
| §3.3 | `indicators/compute.py:99-108` | ruta parcial no resoluble desde la raíz | `packages/py/analytics/src/bolsa_analytics/indicators/compute.py:99-108` |
| §2 | `signals/strategy.py:113-170` | ruta parcial no resoluble desde la raíz; el rango omite el cierre de `evaluate_strategy` (171) | `packages/py/analytics/src/bolsa_analytics/signals/strategy.py:113-171` |

Ninguna de estas correcciones cambia el sentido de un hallazgo: son precisión de cita. La única que
sí afecta a una afirmación es la del bucle AUTO (§6.1), porque el documento citaba como prueba de
cadencia un tramo que no contiene el bucle.

### 2.4 Anclajes P0 verificados de forma manual

| Afirmación del documento | Evidencia real en `HEAD` | Veredicto |
|---|---|---|
| `_detect_cross` exige valor en `index-1` y `index`; si falta, `False` silencioso | `rules_engine.py:257-258` | RATIFICADO |
| El modo `gated` reinicia `has_long` en cada llamada | `rules_engine.py:636`, `:654-677` | RATIFICADO |
| El decisor ACTIVE construye barras solo con `timestamp` y `close` | `active_strategy_signal_evaluator.py:185-188` | RATIFICADO |
| Sin `indicator_context` se fabrican barras `open=high=low=close`, `volume=0` | `rules_engine.py:626-629` | RATIFICADO |
| El scan sí construye y pasa `indicator_context` | `scans.py:288-321`, `:400-407` | RATIFICADO |
| La alerta no pasa `indicator_context` | `signal_alerts.py:274-280` | RATIFICADO |
| Ventana por defecto 120 barras | `auto_simulation_worker.py:8591-8600`; `active_strategy_signal_evaluator.py:61-67` | RATIFICADO |
| Dos flags para la ACTIVE; sin el segundo, `fallback=None` | `auto_simulation_worker.py:8565-8588`, `:8644-8663` | RATIFICADO |
| Con `fallback=None`, `fallback(symbol)` lanza y se devuelve HOLD | `auto_orchestrator.py:774-781` | RATIFICADO |
| Reserva no durable ⇒ veto `reservation_failed` | `auto_v2_entry.py:1540-1573` | RATIFICADO |
| Sin reserva durable no hay orden | `auto_simulation_worker.py:7319-7333` | RATIFICADO |
| `_kill_active` fail-closed | `auto_simulation_worker.py:1983-1988` | RATIFICADO |
| `_settle` traga la excepción y devuelve settlement sin fill | `auto_simulation_worker.py:2261-2266` | RATIFICADO |
| `evaluate_exit_last_bar_gated` **no** está cableada al worker ni a `auto_v2_entry` | 0 apariciones en ambos; solo `position_exit_evaluator.py:209` | RATIFICADO |
| `check_exit_permission` **no** se consulta en el worker | 0 apariciones; sí en `evaluate_exit_plan.py:56-104` y `execute_position_policy_auto.py:236` | RATIFICADO |
| El journal de salida avanza el FSM **antes** de convertir la propuesta | `auto_simulation_worker.py:6614-6617` | RATIFICADO |
| `position_manager_package` devuelve `None` con `hold` | `auto_v2_entry.py:1791-1797` | RATIFICADO |
| `_v2_position_package` devuelve `None` sin adopción | `auto_simulation_worker.py:6495-6499` | RATIFICADO |
| `_settlement` estructural sin `finance_applier` | `auto_simulation_worker.py:2200-2204`, `:2286-2289` | RATIFICADO |
| `sim_worker_enabled()` solo se usa en el arranque y en el bucle | `:426`, `:8748`, `:9150` | RATIFICADO |

---

## 3. Recuentos y mediciones

### 3.1 Presets: 21, no 20

`packages/shared/src/strategy-presets.json` contiene **21** entradas, todas con `entries.rules` y
`exits.rules`, y `preset_strategy_keys()` devuelve las mismas 21. El documento auditado dice «20
estrategias» en §3.1 y «4/20 presets» en §0/§3.3.

| Warmup exigido | Presets | ¿Cabe en 120 barras? |
|---|---|---|
| 201 (cruce con SMA200) | `golden_cross`, `death_cross` | **No** |
| 200 (nivel con SMA200) | `price_above_sma200`, `ma_stack_bullish` | **No** |
| 51 (cruce SMA50) | `sma_crossover` | Sí, con 1 barra de margen |
| 50 | `pullback_in_uptrend` | Sí, justo |
| ≤ 27 | resto (15) | Sí |

Conclusión: **4/21** presets no pueden disparar con `AUTO_ENGINE_SIM_SIGNAL_BARS=120`. El hallazgo
B-1 se mantiene; el denominador debe corregirse. Añadido: `MIN_SCAN_BARS = 50` tampoco basta para
`sma_crossover` (necesita 51), de modo que **5** presets no pueden disparar sobre un instrumento que
solo tenga 50 barras.

### 3.2 SMA200

| Ventana | Valores `None` en `compute_sma(200)` | Primer valor |
|---|---|---|
| 120 | **120/120** | ninguno |
| 200 | 199/200 | índice 199 |
| 250 | 199/250 | índice 199 |

Reproducido exacto. Un cruce exige dos valores consecutivos ⇒ mínimo **201** barras.

### 3.3 `raw` frente a `gated`

`rsi_mean_reversion`, 120 barras monótonas crecientes: `raw -> ['exit']`, `gated -> []`. Reproducido
exacto. La causa estructural (replay de `has_long` desde cero) está en `rules_engine.py:636-677`.

### 3.4 Decisor close-only frente a scan con OHLCV real

El documento afirmaba la divergencia «por construcción» y declaraba la magnitud **no medida**. Aquí
se mide sobre cuatro escenarios deterministas (tendencia suave, tendencia con retroceso, lateral en
sierra y bajista) con barras OHLCV que tienen rango y volumen. La medición se hace con el banco de
contrato `packages/py/application/tests/test_scan_decider_contract.py`, que fija los pares.

> **Errata de magnitud.** Una lectura anterior de este anexo publicó **13/16** divergencias. Esa
> cifra **no se reproduce** con el banco publicado: se contabilizaban eventos, no acciones, y la
> comparación no era la misma (el camino close-only no se comparaba contra la proyección `gated` de
> la misma feature). La cifra correcta y reproducible es **5/16 acciones** y **3/16 eventos**.

| Preset | Acciones que cambian (de 4) | Escenarios | Lectura |
|---|---|---|---|
| `vwap_reclaim` | **4/4** | todos | sin volumen, `cum_vol=0` ⇒ VWAP `None`: el decisor devolvía HOLD/— donde el scan ve `entry_long`/`exit` |
| `supertrend_follow` | **1/4** | `flat_spike_up` | con `high=low=close` el ATR sintético dispara una entrada que el rango real no produce (BUY espurio → HOLD) |
| `cci_oversold` | **0/4** | — | el típico sobre cierres coincide en acción con el típico OHLCV en estos escenarios |
| `stoch_oversold` | **0/4** | — | ídem: coincide en acción; no se afirma que la serie sea idéntica |
| **Total** | **5/16 pares** | | **3/16** pares con `raw ≠ gated` sobre la misma feature (B-3) |

Esto **cierra la magnitud pendiente** de B-2 con el número reproducible y refuerza B-4: la alerta y
el scan podían discrepar porque la alerta evaluaba sin contexto, exactamente igual que el decisor.

**Δ del fix (medido).** Con el fix aplicado, el decisor pasa a consumir el mismo `indicator_context`
que el scan: **16/16** pares coinciden con la proyección `gated` y **5/16** cambian de acción frente
al camino close-only (las 4 de `vwap_reclaim` y 1 de `supertrend_follow`; el cambio de
`supertrend_follow` es una compra espuria que **desaparece**). El fix **no** cambia el modo `gated`
ni el fail-closed a HOLD, y **no** cierra B-3.

### 3.5 Escalera de vetos

| Métrica | Documento | Medido | Lectura |
|---|---|---|---|
| Entradas numeradas del docstring | «18 familias» | **19** (1–18 más 3.b) | falta contar 3.b |
| `reason_code` distintos citados en el docstring | — | 27 | — |
| Llamadas `_reject` con motivo literal | «16 pasos» | **19** | el «paso» no equivale a «motivo» |
| Motivos por tabla dinámica | — | 5 familias (`sector_*`, `*_measurement_*`, `governor_*`) | el journal puede emitir más motivos que ramas |

La conclusión del documento (escalera fail-closed, con prueba) se mantiene. El recuento «18 familias
/ 16 pasos» debe reformularse como «19 entradas de docstring / 19 rechazos literales / 5 familias
dinámicas», o justificarse explícitamente la agregación que produce 18 y 16.

### 3.6 Salida

| Comprobación | Resultado |
|---|---|
| `EXIT_REASON_PRECEDENCE` | 11 motivos, en el orden declarado |
| `_HARD_TRIGGER` | 9 motivos; **`TRAIL` y `TIME_STOP` no están** |
| Plan con `expires_at` vencido | `primary=TIME_STOP`, `status=HINT`, `suggested=full_exit` |
| `protective_fill_price` | solo para `STRUCTURAL_STOP`, `TARGET_1` y `TARGET_2` |

El par `HINT` + `suggested=full_exit` es exactamente la asimetría S-1: F5 resuelve `none` y deniega
con `not_actionable`, mientras el fallback de `exit_policy.py:165` convierte el motivo en
`full_exit`. **No es una inferencia: es el plan real devuelto por el motor.**

---

## 4. Criterios falsables (§9) y backlog (§10)

### 4.1 Recuento real (estado previo a la corrección documental)

| Bloque | Contenido | Número |
|---|---|---|
| Hallazgos con ID en todo el documento | B-1…B-6, S-1…S-6, O-1…O-6, T-1…T-3 | **21** |
| Criterios con ID en §9 (lectura verificada) | B-1…B-6, S-1…S-6, O-1…O-4, T-1…T-2 | **18** |
| Condiciones falsables en §10 | ninguna (es backlog) | 0 |
| Condiciones falsables en §11 | ninguna (es límites y reproducción) | 0 |
| Entradas del backlog | 4 P0 + 6 P1 + 3 P2 | **13** |

**Sobre las «20 condiciones» — errata de esta verificación.** El documento auditado **no afirma**
que haya 20 condiciones falsables. Buscado el literal en el original: **0 apariciones**. La cifra 20
era una **reconstrucción de esta verificación** (`B(6) + S(6) + O(6) + T(2)`), que exigía suponer
criterios para `O-5` y `O-6` y contar `T-3` sin que §9 los tuviera. Se retira: el hecho verificado es
que §9 tenía **18** filas con ID, no que el original dijera 20.

La corrección documental (§7.2 del anexo) añade `O-5`, `O-6` y `T-3`, de modo que la auditoría pasa a
**21 criterios** — uno por hallazgo.

### 4.2 Desajustes de cobertura (estado previo a la corrección)

| Tipo | IDs | Consecuencia |
|---|---|---|
| Hallazgos **sin criterio falsable** en §9 | `O-5`, `O-6`, `T-3` | no hay prueba propuesta para el vigía, la procedencia de la feature en el journal ni la cadencia de ejecución |
| Criterios **sin entrada de backlog** | `B-5`, `B-6` | dos defectos P0/P1 del documento no tienen tarea de cierre |
| Referencia **colgante** en el backlog | `O-6` (entrada 7) | el backlog cita un criterio que §9 no define |

**Resuelto en la corrección documental:** las cinco filas (`B-5`, `B-6`, `O-5`, `O-6`, `T-3`) tienen
ahora entrada de backlog, criterio con ID, nombre de prueba y fila en la matriz de trazabilidad
(§10 del anexo). Sigue en **0** el número de esas pruebas implementadas: tener criterio no es tener
evidencia.

### 4.3 Las 21 pruebas propuestas no existen

Verificado por búsqueda de los nombres `test_*` propuestos: **0 existen** en el árbol (18 en la
lectura original; 21 tras añadir `O-5`, `O-6` y `T-3`). La afirmación «no implementadas» de §9 es
correcta.

---

## 5. Pruebas ejecutadas

### 5.1 Herméticas (réplica de §1)

| Grupo | Ficheros | Resultado |
|---|---|---|
| S1 | `test_signal_evaluate`, `test_signal_strategy`, `test_rules_engine`, `test_exit_plan`, `test_exit_permission`, `test_active_strategy_signal_evaluator` (+2 nuevos), `test_position_manager`, más `test_scan_decider_contract` (21) y `test_signal_alerts_feature_context` (5) | **111 passed**, 0 skipped |
| S2 | `test_auto_sim_active_strategy_seam`, `test_window_day_watch` (54: +4 de override/aislamiento y O-5) y `test_day_watch_repo_guard` (9) | **71 passed**, 0 skipped |
| S3 | `test_auto_v2_lifecycle_clock_thesis`, `test_auto_v44_exit_governance`, `test_auto_v2_real_price_source`, `test_auto_v2_real_price_fail_closed` | **45 passed**, 0 skipped |
| S4 | `test_auto_v2_closed_bars_and_bar_idempotency`, `test_auto_v2_bar_short_circuit` | **12 passed**, 0 skipped |
| S5 | `test_portfolio_decision_engine`, `test_portfolio_reservation`, `test_portfolio_reservation_ledger`, `test_decision_contract_barricade`, `test_position_decision`, `test_position_policy_decision` | **121 passed**, 0 skipped |
| **Total** | | **360 passed, 0 skipped, 0 failed** (≈11 s) |

Ejecutado con `-q -rs`. Cero saltos: ningún verde oculta un «no ejecutado». La réplica estricta de
§1 del documento auditado (los grupos sin las pruebas nuevas) suma **325**
(85+62+45+12+121); las **35** restantes son las pruebas de la iteración
(21 de contrato + 5 de alertas + 9 de la guarda del vigía). El desglose por tanda está en §12.3.

### 5.2 PostgreSQL (extensión de esta verificación)

El documento declaraba «suites PG no ejecutadas; cero consultas». Esta verificación **sí** las
ejecutó, en una base **desechable** creada al efecto:

| Paso | Detalle |
|---|---|
| Contenedor | `postgres:16-alpine` propio, puerto 55432, usuario/base de verificación |
| Migraciones | `alembic upgrade head` ⇒ `058_estudio_daily_proposals`; 88 tablas en `public` |
| Base de la ventana | **no usada**; el `DATABASE_URL` apuntó solo a la base desechable |
| Contenedor al terminar | eliminado (`docker rm -f`) |
| `sha256` del ledger tras las pruebas | idéntico al de §1.2 |
| Efecto lateral (1.ª ejecución) | Los tests de PG-4 que lanzan `python -m bolsa_api.workers.scheduler_worker` (`_spawn`) reescribieron `day-watch.json` y añadieron 3 latidos idénticos a `day-watch.jsonl` (§1.2). `test_auto_scheduler_real_pg_zero_human_intervention` **no** es el productor: no arranca el scheduler. El ledger no se tocó. |
| Efecto lateral (**re-ejecución con el banco aislado**) | **Ninguno**: `day-watch.json` y `day-watch.jsonl` conservaron `sha256`, tamaño, `mtime_ns` y número de líneas (§5.4). |

| Grupo | Ficheros | Resultado |
|---|---|---|
| PG-1 | `test_auto_v2_durable_pg`, `test_auto_v2_lifecycle_pg`, `test_auto_v44_exit_identity_pg`, `test_portfolio_reservation_pg`, `test_financial_integrity_pg` | **23 passed** |
| PG-2 | `test_auto_v46_crash_recovery`, `test_auto_v46_concurrent` | **7 passed** |
| PG-3 | `test_auto_daily_chain_full_real_e2e_pg` | **1 passed** (17 s) |
| PG-4 | `test_auto_scheduler_real_pg_zero_human_intervention`, `test_auto_v46_multiprocess_pg`, `test_auto_v46_hardkill_recovery_pg`, `test_auto_v46_crash_injection_pg` | **7 passed** (115 s) |
| **Total** | | **38 passed, 0 skipped, 0 failed** |

**Re-ejecución de PG-4 tras aislar el vigía.** Se repitió el grupo PG-4 completo en un contenedor
**propio** (`postgres:16-alpine`, puerto 55433, `alembic upgrade head` ⇒ `058`), con el banco de
pruebas ya parcheado:

| Comprobación | Antes | Después | Resultado |
|---|---|---|---|
| PG-4 | — | **7 passed** (116 s), 0 skipped | igual que la 1.ª ejecución |
| `day-watch.json` | `0D14165A…DA95` · 659 B · `mtime_ns 1793030756482919600` | **idéntico** | no se reescribió |
| `day-watch.jsonl` | `9AF8A3E2…5706` · 434 391 B · 950 líneas · `mtime_ns 1793030756483497500` | **idéntico** | no se añadió ningún latido |
| `ledger.jsonl` | `69A25F1F…E175` · 26 499 B | **idéntico** | no se tocó |

**Nota de método (honestidad).** Un primer intento de re-ejecución usó el contenedor **compartido**
de la verificación anterior; falló de forma intermitente (1 de 7) porque **otra sesión de pytest**
estaba purgando residuos contra la misma base (el `conftest` purga al inicio y al final de sesión, y
el propio fichero advierte que la suite no admite ejecución paralela). El fallo no se reproduce en
una base dedicada: 7/7. Se deja escrito porque es exactamente el tipo de rojo que se atribuiría por
error al código.

**Qué cambia esto**: los cierres P-1, R-1, R-2, R-4 y W-1, que el documento auditado solo podía
apoyar en suites no ejecutadas, quedan ahora con **evidencia E1 + E2** en esta verificación. Lo que
**no** cambia: sigue sin medirse ningún proceso vivo, ni la ventana, ni la cadencia real.

### 5.3 Lo que estas pruebas no acreditan

- No acreditan que la cadena se ejecute en el despliegue: son procesos en un runner, no el scheduler
  de producción.
- No acreditan que el scan diario despierte: T-1 y T-2 siguen sin medición operativa.
- No acreditan ninguna ventaja estadística: el ledger sigue con 0 episodios y 0/32 ciclos.
- El e2e PG demuestra que la cadena señal→ciclo→DÍA-D funciona cuando se le da un reloj y una base;
  no demuestra que esa cadena se dispare sola cada día.
- PG-4 demuestra que el scheduler real **arranca** el vigía de ventana (escribió su latido), lo que
  es evidencia E2 de cableado; no demuestra que arranque el scan (T-1), que no aparece en el
  scheduler.
- **Higiene (atribución corregida y problema cerrado):** el artefacto lo escribía cualquier test que
  arrancase el `scheduler_worker`, no `test_auto_scheduler_real_pg_zero_human_intervention`. El banco
  ya **no** hereda el estado del repo: `WINDOW_DAY_WATCH_ENABLED=0` y `WINDOW_DAY_WATCH_DIR` temporal
  en el proceso de pytest y en cada subproceso, y una guarda de sesión por `sha256`+`mtime_ns` que
  falla si el árbol cambia. `operability_runs/` sigue sin trackear: la limpieza se mide por hash, no
  por `git status`. Esto **no** convierte a W-1 en evidencia operativa.

### 5.4 Contrato scan↔decisor (evidencia de la iteración)

Banco: `packages/py/application/tests/test_scan_decider_contract.py` (21 pruebas, 4 escenarios × 4
presets = 16 pares + caracterizaciones). Sin base de datos, sin ficheros, sin estado.

| Comprobación | Resultado |
|---|---|
| Decisor vs proyección `gated` de la **misma** feature | **16/16 pares** |
| Δ del fix (decisor close-only → decisor OHLCV) | **5/16** acciones cambian; todas en `vwap_reclaim` (4) y `supertrend_follow` (1) |
| `raw` vs `gated` sobre OHLCV | **3/16** pares difieren; se fija como **B-3** (sin fix en esta iteración) |
| Anti-no-op de la feature | con contexto close-only, `vwap_reclaim` no ve el VWAP (`4/4` HOLD) y `supertrend_follow` compra en falso (`1/4`) |
| Anti-no-op de los escenarios | ≥12 de 16 pares emiten señal y cada preset ejerce BUY y SELL en algún escenario |
| Alertas | el motor recibe `indicator_context` no vacío con la serie de VWAP real (`test_signal_alerts_feature_context`, 5 pruebas) |

**Matriz medida (16 pares).** `raw` es lo que publica el scan; `gated` es lo que consume el decisor
con la **misma** feature; «close-only» es el camino anterior (sin `indicator_context`).

| Escenario | Preset | `raw` | `gated` (OHLCV) | close-only | Decisor ahora |
|---|---|---|---|---|---|
| `flat_spike_up` | `vwap_reclaim` | `entry_long` | `entry_long` | HOLD | **BUY** |
| `flat_spike_up` | `supertrend_follow` | `entry_long` | — | BUY | **HOLD** |
| `flat_spike_up` | `cci_oversold` | `exit` | — | HOLD | HOLD |
| `flat_spike_up` | `stoch_oversold` | `exit` | — | HOLD | HOLD |
| `up_crash` | `vwap_reclaim` | `exit` | `exit` | HOLD | **SELL** |
| `up_crash` | `supertrend_follow` | `exit` | `exit` | SELL | SELL |
| `up_crash` | `cci_oversold` | `entry_long` | `entry_long` | BUY | BUY |
| `up_crash` | `stoch_oversold` | `entry_long` | `entry_long` | BUY | BUY |
| `down_spike` | `vwap_reclaim` | `entry_long` | `entry_long` | HOLD | **BUY** |
| `down_spike` | `supertrend_follow` | `entry_long` | `entry_long` | BUY | BUY |
| `down_spike` | `cci_oversold` | `exit` | `exit` | SELL | SELL |
| `down_spike` | `stoch_oversold` | `exit` | `exit` | SELL | SELL |
| `sawtooth_crash` | `vwap_reclaim` | `exit` | `exit` | HOLD | **SELL** |
| `sawtooth_crash` | `supertrend_follow` | `exit` | `exit` | SELL | SELL |
| `sawtooth_crash` | `cci_oversold` | `entry_long` | `entry_long` | BUY | BUY |
| `sawtooth_crash` | `stoch_oversold` | `entry_long` | `entry_long` | BUY | BUY |

Lectura: las **5** celdas en negrita son el Δ del fix. La fila `supertrend_follow`/`flat_spike_up`
cambia de **BUY a HOLD**: la compra era un artefacto del rango sintético, no una señal. Las 3 filas
con `raw ≠ gated` (`cci_oversold` y `stoch_oversold` en `flat_spike_up`; `supertrend_follow` en
`flat_spike_up`) son B-3 y **no** las arregla este fix.

Lo que **no** acredita: que el camino ACTIVE esté operativo (sigue detrás de dos flags y AUTO está
OFF), ni que la proyección `gated` sea la correcta para una cartera real (B-3 sigue abierto), ni
ninguna ventaja estadística.

---

## 6. Matriz de evidencia por hallazgo

Niveles: **E0** ancla estática o medición read-only · **E1** prueba hermética ejecutada · **E2**
integración PostgreSQL ejecutada · **E3** operación real medida.

| ID | Hallazgo | Nivel | Evidencia verificada |
|---|---|---|---|
| B-1 | 4/21 presets inoperables con 120 barras | **E0** | medición SMA200 + warmup por preset; sin prueba |
| B-2 | Decisor close-only frente a scan OHLCV | **E1** | contrato 16/16 con la feature OHLCV; Δ 5/16 frente a close-only (§5.4) |
| B-3 | `gated` suprime salidas sin entrada en ventana | **E1** de caracterización | `['exit']` vs `[]` + 3/16 pares `raw ≠ gated`; **sin fix** |
| B-4 | Alerta sin `indicator_context` | **E1** | `test_signal_alerts_feature_context`: el motor recibe el contexto con VWAP real |
| B-5 | Dos flags; sin el segundo, HOLD silencioso | **E0 + E1** | código + `test_auto_sim_active_strategy_seam` |
| B-6 | Scan con 50 barras frente a warmup del preset | **E0** | `MIN_SCAN_BARS=50`; 5 presets por encima |
| S-1 | TIME_STOP: F5 deniega, AUTO vende | **E0 + E1** | plan real `HINT/full_exit` + `test_exit_permission` + test AUTO de time exit |
| S-2 | `THESIS_INVALIDATION` fuera del conjunto protector | **E0 + E1** | `position_decision.py:82-91`, `:196-210` |
| S-3 | `EXIT_PENDING` sin orden emitida | **E0** | `6614-6617` + `1791-1797`; sin prueba |
| S-4 | `THESIS_EXIT` inalcanzable como motivo decisorio | **E0 + E1** | `position_state.py:419-429`, `test_v2_stop_out_is_not_declared_as_thesis_exit` |
| S-5 | Posición no adoptada sin gestión | **E0** | `6495-6499`; sin prueba |
| S-6 | El worker no consulta F5 | **E0** | 0 apariciones de `check_exit_permission` |
| O-1 | `_settle` no cuenta el fallo | **E0** | `2261-2266`; no existe contador `settlement_fail*` |
| O-2 | Modo estructural no publicado | **E0** | `2200-2204`, `2286-2289` |
| O-3 | Ceros donde falta el dato | **E0** | `dia-d-auto-panel.tsx:249-250`, `signal-alerts-section.tsx:494`, `auto_operational_monitor.py:194` |
| O-4 | `INCONCLUSIVE` estático en la UI | **E0** | `estudio-daily-ops-panel.tsx:1131-1137`, `estudio-chain-evidence.tsx:712-716` |
| O-5 | W-1 corregido, efecto no observado | **E1 + E2 parcial** | `window_day_watch_worker.py` con override de directorio + 54 tests del vigía, incluido `test_day_watch_alerts_on_measured_inconclusive_day` (fila real `20261019`, `MEDIDO`, `INCONCLUSIVE`, `cycles=0`, en `tmp_path`); PG-4 arrancó el vigía y escribió latido `NOT_DUE`, ya en directorio aislado. Ningún día `MEDIDO` de la **ventana real** pasó por él |
| O-6 | Journal sin procedencia de la feature | **E0** | no hay campo `featureSource`/`signalWindowBars` |
| T-1 | El scan no está en el scheduler | **E0** | `scheduler_worker.py:68-104` no incluye `start_scan_worker` |
| T-2 | El scan duerme antes del primer tick | **E0** | `opportunity_daily_scan_worker.py:150-153` |
| T-3 | Decisión diaria, ejecución cada 60 s | **E0 + E2** | `auto_sim_loop` `8722-8767`; el e2e PG valida fronteras de barra |

**Ningún hallazgo alcanza E3.** No hay una sola afirmación en este anexo que se apoye en operación
real medida: AUTO OFF es premisa y default de código, y los PIDs no se han inspeccionado.

---

## 7. Decisión: código, documento y operación

### 7.1 Cambios de código que la evidencia justifica

Estado a 2026-10-26 (tarde): la columna «Estado» distingue lo aplicado **en el árbol de trabajo sin
commit** de lo que sigue pendiente. Nada se ha publicado.

| Prioridad | Cambio | Hallazgos | Estado |
|---|---|---|---|
| P0 | Validar el warmup del preset ACTIVE contra `AUTO_ENGINE_SIM_SIGNAL_BARS`, con rechazo explícito | B-1, B-6 | **pendiente** |
| P0 | Unificar la procedencia de la feature: OHLCV real en decisor y alertas, o `featureSource` declarado | B-2, B-4, O-6 | **aplicado** en decisor y alertas (`signal_feature_context.py`) + contrato 16/16; `featureSource` en journal **pendiente** (O-6) |
| P0 | Resolver el contrato `gated`/`raw`: el gating no puede reiniciarse en cada llamada | B-3 | **pendiente**, con prueba de caracterización |
| P0 | Unificar el conjunto de motivos accionables entre F5 y AUTO, o consultar F5 | S-1, S-2, S-6 | **aplicado** F5+AUTO (§12.12, §12.13) y **S-6** cableado en el worker (§12.17) |
| P1 | `EXIT_PENDING` solo tras orden emitida | S-3 | **aplicado** (§12.14) |
| P1 | Contador durable de settlement fallido y publicación de `structural` | O-1, O-2 | **aplicado** (§12.15) |
| P1 | Declarar la posición no adoptada en el journal | S-5 | **pendiente** |
| P1 | Sustituir `?? 0` y el `INCONCLUSIVE` estático por lecturas del gate | O-3, O-4 | **pendiente** |
| P1 | Aislar el estado del vigía en pruebas (el banco no debe escribir el repo) | O-5 | **aplicado** (`WINDOW_DAY_WATCH_DIR`, `WINDOW_DAY_WATCH_ENABLED=0`, guarda de sesión) |
| P2 | `invalidationPrice` distinto del stop, o retirar `THESIS_EXIT` del contrato visible | S-4 | **pendiente** |

### 7.2 Correcciones documentales (aplicadas sobre el original el 2026-10-26)

1. **`git status` de §8.0**: hay **3** entradas (dictamen modificado + auditoría + esta verificación),
   no una. `operability_runs/` no está trackeado y no aparece.
2. **Presets**: 21, no 20; «4/20» → «4/21» en §0, §3.1, §3.3 y §10; añadido que `MIN_SCAN_BARS=50`
   también bloquea `sma_crossover` (**5** presets con 50 barras).
3. **Criterios falsables**: §9 tenía **18** (el original nunca dijo 20). Añadidos `O-5`, `O-6` y
   `T-3` ⇒ **21**.
4. **Backlog**: añadidas entradas para `B-5`, `B-6`, `O-5`, `O-6` y `T-3`; resuelta la referencia
   colgante a `O-6`; añadida la matriz de trazabilidad hallazgo → backlog → criterio → prueba →
   evidencia.
5. **Anclajes**: aplicadas las correcciones de §2.3, en especial el bucle AUTO (`8722-8767`).
6. **`day-watch.json`**: citado con hash y hora de lectura; la marca `16:13:37` ya no existe.
7. **Escalera de vetos**: reformulada como 19 entradas de docstring, 19 rechazos literales y 5
   familias dinámicas (antes «18 familias / 16 pasos»).
8. **Estado PG**: el documento dice «cero consultas»; esta verificación ejecutó 38 pruebas en una
   base desechable. Ambas cosas son ciertas si se fechan: la auditoría original no consultó
   PostgreSQL y esta verificación sí, en un contenedor aislado.
9. **Efecto sobre `day-watch`**: reatribuido a los tests que arrancan el `scheduler_worker`
   (`_spawn`/`_env_for`), no a `test_auto_scheduler_real_pg_zero_human_intervention`, y **corregido**:
   el banco aísla el directorio de estado y una guarda de sesión lo verifica (§1.2, §5.4).
10. **Magnitud de B-2**: retirada la cifra **13/16**; la medición reproducible es **5/16 acciones** y
    **3/16 eventos** `raw`/`gated` (§3.4). El original no publicaba magnitud: era una aportación de
    este anexo y se corrige aquí.
11. **Procedencia de la feature**: aplicado el fix en el commit del sello `2.11.162-beta` con
    `signal_feature_context.py`, usado por el decisor y por las alertas; el contrato queda fijado por
    16/16 pares. No se presenta como validación operativa.

### 7.3 Medición operativa pendiente (sigue sin resolver)

| Área | Qué falta | Por qué no se resuelve aquí |
|---|---|---|
| Procesos vivos | PIDs del scheduler, queue poll y AUTO | exige inspeccionar el despliegue real |
| Cadencia del scan | primer tick real, drenaje de la cola | exige stack vivo |
| Ventana | episodios y ciclos | `INCONCLUSIVE`, 0/32 |
| Régimen | cuántas liquidaciones provoca un fallo transitorio | exige serie operativa |
| W-1 | aviso real sobre días `MEDIDO` con gate `INCONCLUSIVE` | el artefacto no lo registra |

---

## 8. Pruebas que deben ejecutarse después

De las **21** pruebas de §9, **tres existen** ya (B-2, B-3 y B-4, en el commit del sello) y una
cuarta (O-5) existe a nivel E1 con fila real del ledger; las demás siguen sin implementar. Se
incluyen las tres que cubren los hallazgos que antes quedaban huérfanos:

| ID | Prueba propuesta | ¿Existe? | Evidencia actual |
|---|---|---|---|
| B-1 | `test_sma200_requires_201_bars_in_active_window` | no | E0: 120/120 `None` medido |
| B-2 | `test_decider_matches_the_gated_projection_of_the_same_signal` (16 pares) | **sí** | **E1**: 16/16; Δ 5/16 |
| B-3 | `test_raw_and_gated_diverge_on_a_sustained_trend` | **sí** (caracterización) | **E1**: 3/16 `raw ≠ gated`; contrato sin cambiar |
| B-4 | `test_the_alert_evaluates_with_the_ohlcv_context` | **sí** | **E1**: el motor recibe el contexto |
| B-5 | `test_active_signal_flag_off_blocks_buy_explicitly` | no | E1 parcial: HOLD cubierto, el motivo de journal no |
| B-6 | `test_scan_rejects_preset_below_warmup` | no | E0: `MIN_SCAN_BARS=50` |
| S-1 | `test_time_stop_permission_matches_auto_execution` | no | E1 parcial: F5 y AUTO probados por separado, no la coincidencia |
| S-2 | `test_thesis_invalidation_is_protective_under_critical_recon` | no | E1 parcial: `REVIEW` bajo `CRITICAL` está cubierto |
| S-3 | `test_exit_pending_requires_emitted_order` | no | E0: orden de llamadas `6614-6617` |
| S-4 | `test_thesis_exit_reachable_with_declared_invalidation_price` | no | E1 parcial: existe la prueba del caso contrario |
| S-5 | `test_unadopted_position_is_declared_in_journal` | no | E0: `return None` sin journal |
| S-6 | `test_auto_exit_ignores_stale_data_by_contract` | no | E0: sin consulta a F5 |
| O-1 | `test_settle_failure_is_counted` | no | E0: no existe contador |
| O-2 | `test_structural_settlement_is_published` | no | E0: `structural` no viaja al journal |
| O-3 | `test_absent_measurement_is_not_rendered_as_zero` | no | E0: `?? 0` en paneles y alertas |
| O-4 | `test_window_verdict_is_read_from_gate` | no | E0: texto constante |
| T-1 | `test_scan_worker_is_started_by_scheduler_or_its_own_process` | no | E0: el scheduler no lo arranca |
| T-2 | `test_daily_scan_runs_immediately_when_due` | no | E0: `sleep` antes del primer tick |

| ID | Prueba propuesta | Estado |
|---|---|---|
| O-5 | `test_day_watch_alerts_on_measured_inconclusive_day` (fila real del ledger) | **sí** (E1 con fila real del ledger en `tmp_path`); el latido de la ventana real sigue sin observarse |
| O-6 | `test_journal_records_feature_source_and_window_bars` | no existe (solo el contrato de datos está escrito) |
| T-3 | `test_auto_loop_decides_once_per_closed_bar_and_settles_intrabar` | no existe |

Además, y fuera del alcance de una prueba hermética: `test_auto_daily_chain_full_real_e2e_pg`
**ya pasa** en base desechable; lo que falta no es otra prueba, es ejecutar la cadena en el
despliegue y leer el ledger sin fabricar días.

---

## 9. Límites de esta verificación

- **AUTO: OFF.** Premisa del propietario y default de código; no se ha medido ningún proceso.
- **PAPER virtual.** Sin dinero real.
- **Ventana: INCONCLUSIVE.** 0 episodios, 0/32 ciclos.
- **Rentabilidad: no demostrada.** Ninguna prueba de este anexo la insinúa.
- **Repositorio: commit del sello `2.11.162-beta` en la rama, sin tag ni PR.** `HEAD` era
  `8ce53c3c` al medir; el sello publica la iteración de cierre completa (código, pruebas y
  documentos) y re-ancla el pin PAPER antes de cualquier etiqueta.
- **PostgreSQL**: 38 pruebas PG en base desechable (eliminada) + **7 de PG-4 re-ejecutadas** en un
  contenedor propio (eliminado). El **ledger no cambió** (mismo `sha256` antes y después). Los
  artefactos de `day-watch` **tampoco** cambiaron en la re-ejecución: el banco aísla el directorio de
  estado (`WINDOW_DAY_WATCH_DIR`), desactiva el vigía por defecto y una guarda de sesión falla si
  `day-watch.json`/`.jsonl` cambian. La 1.ª ejecución sí los reescribió; se declara en §1.2 y se
  conserva como antecedente del defecto corregido.
- **Evidencia máxima alcanzada: E2.** Ningún hallazgo llega a E3.

---

## 10. Reproducción

```powershell
# Estado
git log -1 --format='%H %ad %s'
git status --porcelain
git rev-list --count '@{u}..HEAD'

# Hashes de los artefactos (read-only)
Get-FileHash -Algorithm SHA256 operability_runs/window-runs/ledger.jsonl
Get-FileHash -Algorithm SHA256 operability_runs/window-runs/day-watch.json
Get-FileHash -Algorithm SHA256 operability_runs/window-runs/day-watch.jsonl

# Suites herméticas (5 invocaciones de §1, con -rs para ver saltos)
uv run --no-sync python -m pytest packages/py/analytics/tests/test_signal_evaluate.py `
  packages/py/analytics/tests/test_signal_strategy.py `
  packages/py/analytics/tests/test_rules_engine.py `
  packages/py/analytics/tests/test_exit_plan.py `
  packages/py/analytics/tests/test_exit_permission.py `
  packages/py/application/tests/test_active_strategy_signal_evaluator.py `
  packages/py/application/tests/test_position_manager.py -q -rs

# PostgreSQL en base desechable (credenciales de ejemplo, contenedor propio)
docker run -d --name bolsa-verify-pg -e POSTGRES_USER=verify -e POSTGRES_PASSWORD=verify `
  -e POSTGRES_DB=bolsa_verify -p 55432:5432 postgres:16-alpine
$env:DATABASE_URL = "postgresql://verify:verify@127.0.0.1:55432/bolsa_verify"
cd packages/py/infrastructure; uv run --no-sync alembic upgrade head; cd ../../..
uv run --no-sync python -m pytest apps/api-python/tests/test_auto_v2_durable_pg.py `
  apps/api-python/tests/test_auto_daily_chain_full_real_e2e_pg.py -q -rs

# PG-4 en un contenedor PROPIO (no compartir base: el conftest purga al inicio de sesión)
docker run -d --name bolsa-verify-pg-4 -e POSTGRES_USER=verify -e POSTGRES_PASSWORD=verify `
  -e POSTGRES_DB=bolsa_verify -p 55433:5432 postgres:16-alpine
$env:DATABASE_URL = "postgresql://verify:verify@127.0.0.1:55433/bolsa_verify"
cd packages/py/infrastructure; uv run --no-sync alembic upgrade head; cd ../../..
uv run --no-sync python -m pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py `
  apps/api-python/tests/test_auto_v46_multiprocess_pg.py `
  apps/api-python/tests/test_auto_v46_hardkill_recovery_pg.py `
  apps/api-python/tests/test_auto_v46_crash_injection_pg.py -q -rs
Get-FileHash -Algorithm SHA256 operability_runs/window-runs/day-watch.json
Get-FileHash -Algorithm SHA256 operability_runs/window-runs/day-watch.jsonl
docker rm -f bolsa-verify-pg-4

# Contrato scan<->decisor y guarda del vigía (sin base de datos)
uv run --no-sync python -m pytest packages/py/application/tests/test_scan_decider_contract.py `
  packages/py/application/tests/test_signal_alerts_feature_context.py `
  apps/api-python/tests/test_day_watch_repo_guard.py -q -rs
docker rm -f bolsa-verify-pg
```

Mediciones de presets, SMA200, `raw`/`gated`, close-only frente a OHLCV y motivos de salida: el
anexo se apoya en scripts `python -c` de solo lectura equivalentes a los de §3 y §11 del documento
auditado; ninguno escribe estado.

---

## 11. Cierre

La auditoría original identifica defectos reales y su arquitectura de veredictos es honesta: separa
comportamiento implementado de resultado de mercado. Esta verificación **ratifica** sus cuatro
prioridades provisionales y **corrige** afirmaciones de hecho: recuento de presets (21, no 20),
estado del árbol (3 entradas), atribución del efecto sobre `day-watch` y la cifra «20 condiciones»,
que era una reconstrucción de esta verificación y no un texto del original. Además precisa anclajes.

Tras la corrección documental, la auditoría tiene **21 hallazgos, 21 criterios falsables, 21 entradas
de backlog y 21 pruebas propuestas**, con una fila de trazabilidad por hallazgo. Tener criterio no es
tener evidencia: **0 de esas 21 pruebas existen** y la evidencia máxima sigue en **E2**.

> **Actualización del mismo día (ver §12):** el recuento de arriba es el estado **antes** de la
> remediación. Después de ella existen **3** de esas 21 pruebas propuestas (B-2, B-4 y O-5); además,
> B-3 tiene una prueba de **caracterización** que no es la propuesta, y las otras 17 siguen sin
> existir. La evidencia máxima **no** sube de E2.

Lo que no cambia, y conviene repetir sin adornos: **AUTO OFF, PAPER virtual, ventana INCONCLUSIVE,
0 episodios, 0/32 ciclos, rentabilidad no demostrada.** Una auditoría estática y 360 pruebas
herméticas más 45 ejecuciones de integración (38 + 7 de la re-ejecución de PG-4) describen cómo está
construido el sistema; no acreditan que el sistema gane dinero ni que se esté ejecutando todos los
días.

*Anexo de verificación del documento auditado. Las correcciones se aplican sobre él; este anexo deja
constancia de qué cambió y por qué, y se publica con el sello `2.11.162-beta`. Sin cambios de estado
de AUTO/PAPER.*

---

## 12. Addendum (2026-10-26, tras el reinicio): remediación aplicada y re-ejecución

Este addendum se escribe **después** de §11 y no reescribe lo ya medido: §5, §8 y §9 conservan el
registro de lo que se ejecutó **antes** de la remediación. Aquí se documenta qué se cambió en el
código, qué queda fijado por prueba y qué se ha re-ejecutado. Sigue sin haber commit, tag, PR ni
push: `HEAD` continúa en `8ce53c3c` y todo lo descrito vive **solo en el árbol de trabajo**.

### 12.1 Cambios en código

| Fichero | Cambio | Hallazgo que atiende |
|---|---|---|
| `packages/py/application/src/bolsa_application/signal_feature_context.py` *(nuevo)* | `to_ohlcv_bars()` normaliza barras (una barra sin rango usa el cierre como OHLC y volumen 0, *fail-closed*); `build_signal_indicator_context()` construye el contexto de indicadores desde los **mismos** OHLCV. | B-2, B-4 |
| `packages/py/application/src/bolsa_application/active_strategy_signal_evaluator.py` | El decisor pasa `indicator_context` construido desde las barras reales a `evaluate_strategy_last_bar`; deja de evaluar sobre barras sintéticas close-only. | B-2 |
| `packages/py/application/src/bolsa_application/signal_alerts.py` | Mismo camino para las alertas. | B-4 |
| `apps/api-python/src/bolsa_api/background/window_day_watch_worker.py` | `WINDOW_DAY_WATCH_DIR` redirige el directorio de estado; el latido publica `pid` y `runId`. | O-5 / higiene |
| `apps/api-python/tests/conftest.py` | Fixture autouse: `WINDOW_DAY_WATCH_ENABLED=0` y `WINDOW_DAY_WATCH_DIR=<tmp_path>`, con `BOLSA_DAY_WATCH_RUN_ID` propio. Fixture de sesión que compara `(sha256, bytes, mtime_ns, líneas)` de `day-watch.json` y `day-watch.jsonl` antes y después. | higiene |
| `apps/api-python/tests/_day_watch_guard.py` *(nuevo)* | `fingerprint()`, `writers()`, `polluted_by()`: atribuye las líneas nuevas a su `runId`. | higiene |
| `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`, `test_golden_day_v2_process_pg.py` | `_env_for`/`_spawn`/`Popen` propagan el aislamiento a los subprocesos reales. | higiene |
| `apps/api-python/tests/test_window_day_watch.py` | **+4** pruebas: override de directorio (×3) y O-5 contra una fila real del ledger. | O-5 |
| `packages/py/application/tests/test_active_strategy_signal_evaluator.py` | **+2** pruebas: regresión OHLCV con volumen y control negativo close-only. | B-2 |
| `packages/py/application/tests/test_scan_decider_contract.py` *(nuevo, 21 pruebas)* | 16 pares escenario×preset, antino-op, dependencia de rango, Δ del fix y caracterización `raw` vs `gated`. | B-2, B-3 |
| `packages/py/application/tests/test_signal_alerts_feature_context.py` *(nuevo, 5 pruebas)* | El helper conserva rango/volumen y la alerta entrega `indicator_context` no vacío al motor. | B-4 |

La guarda distingue tres desenlaces: escritura con **nuestro** `runId` ⇒ la sesión **falla**; escritura
sin `runId` o de otra corrida (latido del stack de desarrollo) ⇒ **aviso**, nunca rojo; sin cambios ⇒
silencio. Es la diferencia entre «la suite ensució el repo» y «el repo ya estaba vivo».

### 12.2 Criterios de §8 y §9 que pasan a estar cubiertos

| ID | Prueba que ahora existe | Alcance real |
|---|---|---|
| B-2 | `test_signal_evaluator_uses_the_real_ohlcv_not_close_only`, `test_a_close_only_context_would_change_the_answer`, los 16 pares de `test_scan_decider_contract` | Decisor y referencia `gated` coinciden sobre la misma feature OHLCV. **No** demuestra que el scan diario despierte. |
| B-4 | `test_the_alert_evaluates_with_the_ohlcv_context` (+ control negativo `test_the_alert_without_context_would_miss_the_vwap`) | La alerta evalúa con el mismo contexto que el scan. **No** demuestra entrega real de la notificación. |
| O-5 | `test_day_watch_alerts_on_measured_inconclusive_day` | Fila `20261019`/`MEDIDO`/`INCONCLUSIVE` copiada **literal** del ledger a `tmp_path`; se prueba el mapeo veredicto→alerta sobre datos reales sin escribir el ledger del repo. |
| B-3 | `test_raw_and_gated_diverge_on_a_sustained_trend` | Caracteriza la divergencia, pero **no** es la prueba propuesta («salida `gated` alcanzable sin entrada en ventana»), que sigue sin existir. |

Quedan **17 de 21** criterios sin prueba propuesta (B-3 tiene solo caracterización). El Δ del fix
queda fijado por aserción: **5/16 acciones** cambian respecto al decisor close-only
(`vwap_reclaim`, `supertrend_follow`) y `raw` frente a `gated` diverge en **3/16** eventos con el
contexto compartido. Son las cifras de §3.4, ahora reproducibles por el banco y no por un script ad
hoc.

### 12.3 Re-ejecución

| Tanda | Resultado |
|---|---|
| S1 (7 ficheros de §5.1 + contrato + alertas) | **111 passed**, 0 skipped |
| S2 (`test_auto_sim_active_strategy_seam`, `test_window_day_watch`, `test_day_watch_repo_guard`) | **71 passed**, 0 skipped |
| S3 | **45 passed**, 0 skipped |
| S4 | **12 passed**, 0 skipped |
| S5 | **121 passed**, 0 skipped |
| **Herméticas** | **360 passed, 0 skipped, 0 failed** (319 previas + 41 nuevas) |
| **PG-1…PG-4** (base desechable **recién migrada**) | **38 passed, 0 skipped, 0 failed** (136 s) |
| **Golden Day 2.0** (`test_golden_day_v2_process_pg`, `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`) | **3 passed, 0 skipped** (18,5 s) |

**Confirmación en una sola sesión (cierre de la iteración).** La unión de los cinco grupos más las
pruebas nuevas se ejecutó junta para que la guarda de sesión fuese única: **360 passed, 0 skipped,
0 failed** (7,44 s). Al terminar, `day-watch.json` seguía en `0D14165A…DA95` (659 B,
`mtime_ns 1793030756482919600`) y `day-watch.jsonl` en `9AF8A3E2…5706` (434 391 B, 950 líneas,
`mtime_ns 1793030756483497500`); el `ledger.jsonl`, en `69A25F1F…E175`. La guarda no avisó ni falló.

Una corrida intermedia de PG-1…PG-3 sobre la base **ya usada** por PG-4 dio **1 failed / 30 passed**,
reproducible; sobre base limpia fueron **31 passed**. El fallo estaba en el estado residual del banco
desechable, no en el código: no se ha ocultado, se declara aquí y se corrige usando base nueva por
tanda. **No** se ha ejecutado el runner de la ventana ni el certificador.

### 12.4 Artefactos del repo: antes y después

Medidos antes de la primera tanda y después de la última (360 herméticas + 38 PG + 3 Golden Day):

| Fichero | `sha256` (antes = después) | Bytes | Líneas | `mtime` UTC |
|---|---|---|---|---|
| `window-runs/day-watch.json` | `0D14165A…5071DA95` | 659 | 1 | `2026-10-26T16:05:56.4829196Z` |
| `window-runs/day-watch.jsonl` | `9AF8A3E2…7C5706` | 434 391 | 950 | `2026-10-26T16:05:56.4834975Z` |
| `window-runs/ledger.jsonl` | `69A25F1F…F13E26E175` | 26 499 | 12 | `2026-10-25T17:30:01.5416532Z` |

**Cero latidos nuevos.** Antes de la remediación, PG-4 añadía 3 líneas idénticas y reescribía
`day-watch.json` (§1.2, §5.2); ahora el vigía de los subprocesos apunta a `tmp_path` y no toca el
repo. La guarda de sesión convierte cualquier reincidencia en rojo cuando la escritura es atribuible
a la propia corrida de pytest.

> **Errata de ventana (2026-10-26, 18:32 — posterior a esta verificación).** Las huellas de arriba
> son el estado **en el momento de medir**. Después, el **runner programado de la ventana**
> (`window:run-day`, no la suite) añadió la **fila 13** al `ledger.jsonl`: día `20261026`,
> `status: HARD_ERROR`, `reason: API_NOT_READY` (`sha256 71390655…`, 30 432 B, 13 líneas,
> `mtime 2026-10-26T18:32:14`). `day-watch.json`/`.jsonl` **no** cambiaron (siguen en
> `0D14165A…`/`9AF8A3E2…`, 17:05). Es un día **perdido** de la ventana por el API apagado tras el
> reinicio del equipo: se declara, **no** se reintenta ni se imputa a las pruebas. La guarda de
> sesión sólo cubre los artefactos del vigía; el ledger lo escribe el proceso de la ventana y su
> huella **debe** cambiar cuando ese proceso corre.

### 12.5 Gates de CI reproducidos

| Gate (comando de `.github/workflows/python-ci.yml`) | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` | **no issues found in 571 source files** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 contracts kept, 0 broken** |

`ruff check --config pyproject.toml .` deja **14 errores preexistentes en `scripts/`** (I001 y UP/F
en ficheros no tocados): quedan fuera del gate de CI, que no analiza `scripts/`, y no se han
«arreglado» para no ensanchar el diff con ruido ajeno a esta remediación.

### 12.6 Lo que este addendum no cambia

- **AUTO OFF, PAPER virtual, ventana INCONCLUSIVE, 0 episodios, 0/32 ciclos, rentabilidad no
  demostrada.** Nada de lo anterior es operación nueva.
- **Evidencia máxima: E2.** Las pruebas nuevas son E1; las de PG siguen siendo E2 (procesos en un
  runner, no el despliegue). Ningún hallazgo llega a E3.
- **Ningún dato de mercado se ha fabricado**: la fila O-5 es una copia literal del ledger real y el
  ledger no se ha escrito en ninguna tanda.
- **Sin etiqueta**: ni tag, ni PR, ni cambio de estado de AUTO/PAPER; el commit del sello queda en la
  rama `audit/c1-c4-integrity-fold-2026-10-25` hasta que el CI por commit esté verde.

### 12.7 Epílogo de publicación (2026-10-26, posterior al cuerpo del documento)

> **Este epílogo supersede, como afirmación de estado presente, las frases «nada se ha publicado»,
> «sin commit, tag, PR ni push» y «`HEAD` continúa en `8ce53c3c`» de §12.6 y §11.** Aquellas frases
> eran ciertas **en el instante de redacción** (`HEAD = 8ce53c3c`); el cuerpo se conserva sin
> reescribir porque es un parte fechado, no un documento vivo.

**Lo que ocurrió después y sí está publicado:**

| Hecho | Valor verificado |
|---|---|
| Sello | `2.11.163-beta` (commit `9b91f472`) |
| `HEAD` de rama | `cdf06bdb` (`docs(evidence): certifica el cierre POST-TAG…`) |
| Tag en `HEAD` | `v2.88.163-beta` → `84f58d0f` |
| `git status --porcelain` | **0 entradas** |
| `@{u}...HEAD` | **0 / 0** (sin commits pendientes de publicar) |
| CI por commit `84f58d0f` | run **40372006755** — **5/5 success** |
| CI por tag `v2.88.163-beta` | run **40372630308** — **14/14** jobs no saltados, 1 `skipped` |
| CI del tag histórico `v2.88.162-beta` | run **40364412142** — **failure** en `playwright (live AUTO daily chain)`, conservado como rojo histórico |

**Causa del rojo `.162` y su remedio (`.163`).** El worker AUTO_OPS no arrancaba porque
`alembic/env.py` invocaba `fileConfig`, que degradaba el **root logger a `WARN`** aunque se pasara
`disable_existing_loggers=False`; el `logger.info("Worker AUTO_OPS_JOB iniciado")` quedaba silenciado
y el paso de CI esperaba ese marcador hasta agotar el timeout. La migración en proceso
(`ensure_migrated()`) ahora marca `config.attributes["configure_logger"] = False` y `env.py` respeta
la marca, de modo que el bootstrap por CLI conserva su logging y el bootstrap embebido **no toca** el
logging del proceso anfitrión. Cubierto por `test_alembic_logging_isolation.py` (5 pruebas).

**Estado de la ventana PAPER tras el re-anclaje del pin (`84f58d0f`).**

- Pin re-anclado a `9b91f472` (`apps` `d7e698cf`, `packages` `26ec8a8e`) porque el sello `.163` mueve
  `packages` y el tag debe apuntar a un commit con **freeze OK**.
- `pnpm window:status` → gate **`STALE`** con motivo `apps_hash_no_congelado`,
  `packages_hash_no_congelado`. **No es una regresión del re-anclaje**: los 3 días `MEDIDO`
  (`20261019`, `20261021`, `20261022`) se corrieron sobre un árbol cuyo hash **nunca** estuvo
  congelado, así que **jamás contaron** para la certificación. Por eso el recuento sigue en
  **0 episodios / 0/32 ciclos** y el veredicto es **INCONCLUSIVE**, igual que antes del sello.
- `pnpm window:certify` → **BLOQUEADO** (`OperationalError: connection timeout` contra
  `localhost:5432`): el demonio de Docker no está levantado tras el reinicio del equipo. Es un
  bloqueo **de infraestructura local**, no de código ni de datos.
- Día `20261026` en `operability_runs/window-runs/ledger.jsonl`: **`HARD_ERROR` /
  `API_NOT_READY`**, registrado como día perdido por indisponibilidad de la API y **no** como
  resultado de mercado.

**Backlog del dictamen: estado real, sin adornos.**

| Ítem | Estado verificado en `HEAD` |
|---|---|
| **B-1 / B-6** (warmup por preset) | **NO implementado.** `scans.py:245` sigue comparando contra `MIN_SCAN_BARS=50` plano. Existe `bolsa_analytics/warmup_matrix.py` con `WarmupInsufficientError` y `min_bars_for`, pero **solo lo consumen** `optimize/{sma,rsi,macd}_grid.py`, `orchestrator_lab_runner.py` y `scripts/research/*`; **ningún** camino de scan lo importa. Además su `_sma_min` devuelve `max(slow, fast)` y **no suma +1** que exige la detección de cruce. |
| **B-3** (estado gated) | **NO implementado**; solo existe la prueba de **caracterización** que documenta la divergencia `raw ≠ gated`. |
| **P1-12b** (UI «no evaluable») | **NO iniciado.** |
| **O-6** (`featureSource`, `signalWindowBars`) | **NO implementado.** Los campos aparecen **solo** como propuesta en la auditoría y en §12; no existen en el journal. |

**Consecuencia operativa declarada.** El warmup por preset es el único de los cuatro que puede
producir **silencio falso** (cero señales publicado como «sin señal» cuando en realidad el preset
**no era evaluable**). B-3, P1-12b y O-6 degradan **explicabilidad**, no corrección del recuento.

**Nada de este epílogo cambia:** AUTO OFF, PAPER virtual, ventana INCONCLUSIVE, 0 episodios,
0/32 ciclos, rentabilidad no demostrada, evidencia máxima E2.

### 12.8 Cierre de B-1 / B-6 (posterior al epílogo §12.7)

> **Supersede, para esos dos ítems, la fila «NO implementado» de la tabla de §12.7.** El epílogo era
> exacto en su commit; esto ocurre después, en el árbol de trabajo.

**Qué se implementó.** El warmup por preset deja de ser una promesa y pasa a decidirse sobre la
**serie real** que el motor lee (`bolsa_analytics.signals.preset_evaluability`): profundidad `1` para
comparaciones y `2` para cruces, medida por el primer índice definido de cada serie. No se usa
`period + 1` porque es falso ya con el catálogo actual (Ichimoku paga el desplazamiento: 78; MACD
`slow + signal`; el cruce necesita la barra anterior).

- **B-6 (scan).** `RunScan.execute` emite `ScanSkippedInstrument` con motivo
  `warmup_insufficient: …` en vez de dejar al instrumento fuera del recuento.
- **B-1 (decisor ACTIVE).** Sigue **fail-closed a HOLD**, pero el motivo viaja en
  `DecisionPackage.memo` (campo preexistente: sin cambio de contrato).

**Umbrales medidos** (los 21 presets, detalle en §9.1 de la auditoría): 1 · 10 · 14 · 15 (×3) ·
20 (×4) · 26 · 27 (×2) · 35 · 50 · 51 · **78** · 200 (×2) · **201** (×2).

**Errata que la medición obliga a declarar.** §3.8 de la auditoría afirmaba que con `bar_limit = 50`
quedaban bloqueados **5** presets. Son **6**: falta `ichimoku_tk_cross` (78 barras). La cifra anterior
suponía un warmup de `senkouBPeriod = 52` e ignoraba el desplazamiento de 26.

**Verificación (E1, hermética).**

| Suite | Resultado |
|---|---|
| `packages/py/analytics/tests/test_preset_evaluability.py` | **28 passed** |
| `packages/py/application/tests/test_scan_preset_warmup.py` | **5 passed** |
| `packages/py/application/tests/test_active_strategy_warmup.py` | **6 passed** |
| `packages/py/application/tests` + `packages/py/analytics/tests` | **4208 passed, 5 skipped** |
| `ruff check packages/py apps/api-python` | **All checks passed** |
| `mypy` (los 5 directorios del gate) | **571 ficheros, sin incidencias** |
| `lint-imports` | **4 contratos, 0 rotos** |
| `apps/api-python/tests/test_auto_sim_active_strategy_seam.py` | **8 passed** |

**CI por commit** [`40387427120`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40387427120) sobre
`51c976b8` ⇒ **`success`** (`quality` + `auto-v2-durable-pg` + `grammar-discovery-pg` +
`lifecycle-pg` + `paper-forward-pg`). Los tres jobs PG son la parte que aquí importa: ejercitan la
ruta AUTO real contra PostgreSQL.

**Lo que NO se ha hecho, y queda declarado.**

- **`AUTO_ENGINE_SIM_SIGNAL_BARS` sigue en 120.** Subirlo multiplica las barras por símbolo y turno
  del AUTO: es una decisión de **coste**, no de corrección. Hoy esos presets se declaran no
  evaluables en vez de publicar cero señales.
- **`MIN_SCAN_BARS = 50` no se toca.** Es el mínimo de datos del instrumento, no el warmup del preset.
- **`warmup_matrix.py` no se reutiliza** en este camino: es por familia (campañas/optimizador) y su
  `_sma_min` no paga la profundidad del cruce. Se deja intacto como fuente de verdad de **ese** camino.
- **P1-12b (UI) sigue sin hacer**: el titular del scan puede seguir diciendo «sin señales» aunque el
  motivo ya esté en `skipped`.
- **`B-3` y `O-6` siguen abiertos** tal como los describe §12.7.
- **Sin sello, sin tag y sin bump**: esto vive en el commit de trabajo, no en `CHANGELOG` ni en
  `PROJECT_STATE`. Su entrada corresponde al sello que lo recoja.

**Ningún dato de mercado se ha fabricado** y **ninguna ventana se ha medido** con esto: la evidencia
es **E1** (pruebas herméticas), no E2 ni E3.

### 12.9 Cierre de B-3 (posterior a §12.8)

> **Supersede el bullet «`B-3` y `O-6` siguen abiertos» de §12.8** en lo que respecta a `B-3`. `O-6`
> sigue abierto. §12.8 era exacto en su commit; esto ocurre después, en el árbol de trabajo.

**Qué se implementó.** El estado `gated` deja de inferirse de la ventana y se lee del **libro real**:

- **Motor** (`evaluate_rules_signals` / `evaluate_strategy` / `evaluate_strategy_last_bar`):
  `assume_long: bool = False`. Arranca la posición abierta y **suprime las entradas** —dentro no se
  vuelve a comprar, ni siquiera tras consumir una salida a mitad de ventana—.
- **Decisor ACTIVE** (`make_active_strategy_decider`): `long_by_symbol: Callable[[str], bool] | None`.
  Es un **callable**, no un booleano, porque el libro cambia dentro del turno.
- **Worker** (`AutoSimulationWorker.holds_long`): consulta `_open`, el libro real; se cablea en
  `start_auto_sim_worker` y viaja por `load_active_strategy_decider` / `_build_signal_decider`.

**El matiz que la medición obligó a añadir.** El motor responde a **transiciones**; la pregunta del
portador es de **nivel** («¿cierro ahora?»). Si la salida ya se cumplía al empezar la ventana, el
replay la consume en el índice 0 y la última barra no emite nada aunque la condición siga vigente.
Por eso el decisor evalúa el grupo de `exits` en la última barra con el `indicator_context` real
(`_exit_rule_holds`) —no `evaluate_exit_last_bar_gated`, que reconstruye barras close-only—.
Presentar `assume_long` como «el motor ya vende solo» habría sido **falso**.

**Comportamiento medido** (series deterministas; detalle en §9.2 de la auditoría):

| Escenario | Sin libro | Con libro |
|---|---|---|
| Sin entrada en la ventana y salida al final | `[]` | `exit` |
| Todo el tramo por debajo del VWAP | `HOLD` | `SELL` |
| Última barra mantiene la entrada, posición abierta | `BUY` | `HOLD` |
| Salida a mitad de ventana + entrada al final | `entry_long` | `exit`, sin reentrada |
| Libro ilegible | — | `HOLD` (fail-closed) |

**Verificación (E1, hermética), re-ejecutada en el árbol de trabajo.**

| Suite / gate | Resultado |
|---|---|
| `packages/py/analytics/tests/test_signal_strategy.py` | **9 passed** (4 de B-3) |
| `packages/py/application/tests/test_active_strategy_signal_evaluator.py` | **15 passed** (4 de B-3) |
| `apps/api-python/tests/test_auto_sim_active_strategy_seam.py` | **9 passed** (1 de B-3) |
| `packages/py/application/tests` + `packages/py/analytics/tests` | **4216 passed, 5 skipped** |
| `ruff check packages/py apps/api-python` | **All checks passed** |
| `mypy` (los 5 directorios del gate) | **571 ficheros, sin incidencias** |
| `lint-imports` | **4 contratos, 0 rotos** |

**CI por commit** [`40408610263`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40408610263) sobre
`5ef9354d` ⇒ **`success`** (`quality` + `auto-v2-durable-pg` + `grammar-discovery-pg` +
`lifecycle-pg` + `paper-forward-pg`).

**Lo que NO se ha hecho, y queda declarado.**

- **No se persiste el estado `gated` en base de datos.** `_open` ya es la fuente de verdad; una copia
  sería una segunda verdad que puede desincronizarse.
- **La ventana sigue en 120 barras** (B-1/§9.1) y **`mode="raw"` sigue sin estado**: la divergencia
  `raw`/`gated` es contractual, y ahora el decisor declara de qué lado pregunta.
- **Sin sello, sin tag y sin bump**: vive en el commit de trabajo.
- **La evidencia es E1.** Ninguna ventana ni operación real se ha medido con esto; falta el frente
  `S-1` (TIME_STOP/F5) y `O-6` (journal con `featureSource`/`signalWindowBars`).

### 12.10 P1-12b: el titular del scan deja de decir «sin señales» sin haber evaluado

> **Cierra el ítem P1-12b** de §7.4 y §10 de la auditoría. No cierra ningún hallazgo con ID: es la
> consecuencia visible de B-1/B-6 en la UI.

**Qué se implementó.** `apps/web/src/lib/scan-silence.ts` clasifica los `skipped` por el **prefijo
estable** que el backend ya declaraba (`WARMUP_INSUFFICIENT`), exportado al frontend en
`packages/shared/src/scan-api.ts`. El panel pinta un titular que separa lo evaluado de lo no
evaluable:

| Situación | Titular antes | Titular ahora |
|---|---|---|
| Nada evaluado | «Sin señales en la última barra de la lista.» | «Ningún instrumento pudo evaluarse» + causa |
| Mixto | «Sin señales…» | «K sin señal · N instrumentos no evaluables» |
| Todo evaluado | «Sin señales…» | igual |

`K` cuenta **solo** lo evaluado (`scannedCount - skipped.length`, acotado a `>= 0`): antes el titular
mezclaba dos universos en una sola frase.

**Verificación (E1, frontend hermético).**

| Gate | Resultado |
|---|---|
| `apps/web/src/lib/scan-silence.test.ts` | **14 passed** |
| `vitest run` (suite completa de `apps/web`) | **2371 passed / 317 ficheros** |
| `pnpm --filter @bolsa/web typecheck` | limpio |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes, ajenos al cambio) |
| `pnpm --filter @bolsa/shared lint` | limpio |

**CI por commit** [`40421274862`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40421274862)
sobre `e5192326` ⇒ **`success`** (`Frontend CI` → `quality`).

Las pruebas fijan explícitamente los **falsos positivos** que importan: «Menos de 50 barras» **no** es
warmup, «Instrumento no encontrado» y el filtro fundamental **no** son «no evaluable», y la palabra
`warmup_insufficient` a mitad de frase **no** activa la clasificación.

**Lo que NO se ha hecho, y queda declarado.**

- **No se añade `cause` al DTO de `skipped`.** Obligaría a regenerar `openapi.json` y `schema.d.ts` y
  a versionar el contrato para un dato que el prefijo estable ya transporta.
- **No se toca el recuento «N escaneados»** de la cabecera: ese número sí incluye los omitidos y
  cambiarlo es una decisión de contrato distinta.
- **La UI no tiene pruebas de render en este repo**: el titular se fija en la función pura que lo
  produce; el componente solo lo pinta.
- **Sin sello, sin tag y sin bump.** La evidencia es **E1**.

### 12.11 O-6: el journal declara `featureSource` y `signalWindowBars`

> **Cierra el ítem P1-8** de §7.7 y §10 de la auditoría, y el criterio `O-6` de §9.

**Qué se implementó.** Dos claves aditivas del `payload` JSONB del journal —sin migración, sin
columna, sin tocar `openapi.json`—, siguiendo la doctrina ya establecida por `strategyPresetKey`:

| Clave | Valores | Omisión |
|---|---|---|
| `featureSource` | `real` / `synthetic` | si el productor no la declara |
| `signalWindowBars` | entero > 0 | si no hay dato **o** la ventana es 0 |

Cadena: `feature_source(bars)` (puro) → `DecisionPackage` → `V2Signal` → `_journal_entry` →
`payload`. Se declara **también en el `HOLD`**, que es la fila que el hallazgo señalaba como
indistinguible.

**Verificación (E1, herméticas).**

| Gate | Resultado |
|---|---|
| `test_active_strategy_feature_provenance.py` | **9 passed** |
| `test_auto_v2_entry.py` (+2 de O-6) | **71 passed** |
| `test_auto_sim_active_strategy_seam.py` (+1 de O-6) | **10 passed** |
| `application` + `analytics` | **4232 passed** |
| `application` + 4 suites de worker AUTO | **2996 passed** |
| `ruff` / `lint-imports` / `mypy` | limpio / 4 contratos / **571 ficheros sin issues** |

**CI por commit** [`40464917112`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40464917112)
sobre `7c491690` ⇒ **`success`**: `quality` (ruff + mypy + lint-imports + pytest) y los cuatro jobs
PG (`auto-v2-durable-pg`, `grammar-discovery-pg`, `lifecycle-pg`, `paper-forward-pg`) en verde. Los
jobs PG importan aquí porque `_journal_entry` corre en la ruta AUTO real: el payload gana dos claves
y sus aserciones siguen pasando.

**Lo que NO se ha hecho, y queda declarado.**

- **No se publica en el DTO del monitor ni en `openapi.json`.** Las claves viven en el `payload` que
  el journal ya expone; elevarlas a campo de primera clase obliga a regenerar `schema.d.ts` y a
  versionar la API. La lectura en la UI queda como deuda declarada.
- **No se relee ninguna ventana real** con las claves: E1, no E2/E3.
- **Sin sello, sin tag y sin bump.**

### 12.12 S-1: un plan vencido es accionable en F5, igual que en el AUTO

> **Cierra el ítem S-1** de §5.3 y §10 de la auditoría, y el criterio `S-1` de §9.

**Qué se implementó.** `_resolve_action` de `check_exit_permission` resolvía la acción **por el
status** y exigía `TRIGGERED`. Un plan vencido es `HINT` —no es un disparador duro de riesgo— pero
el propio plan ya declara `suggested_action = full_exit`, así que F5 lo denegaba con
`not_actionable` mientras el worker AUTO vendía la posición completa por el mismo motivo.

Se resuelve ahora por una tabla explícita `_ACTIONABLE_BY_STATUS`:

| Estado | Sugerencias que se resuelven |
|---|---|
| `TRIGGERED` | `full_exit`, `reduce` |
| `ARMED` | `protect` |
| `HINT` | `full_exit`, `reduce` |

`protect` sigue exigiendo `ARMED` y `hold` no es accionable en ningún estado: el `HINT` no se
convierte en permiso en blanco. `TIME_STOP` es hoy el único motivo que produce `HINT`, de modo que
la tabla no relaja otros caminos.

**Lo que la equivalencia NO toca.** `TIME_STOP` sigue **fuera** de `_is_protective`: con datos
rancios o mercado cerrado F5 lo vuelve a denegar. Esa asimetría es **S-2** y sigue abierta. Y
`check_exit_permission` seguía sin consultarse en el worker AUTO (**S-6**): se había igualado el
veredicto sobre el mismo plan, no el cableado (cerrado después en §12.17).

**Verificación (E1).**

| Gate | Resultado |
|---|---|
| `test_exit_permission.py` | **23 passed** (4 nuevas; `test_deny_hint` codificaba el defecto y se retira) |
| `analytics` + `application` | **4235 passed** |
| Suites de salida de `apps/api-python` | **63 passed** |
| `ruff` / `lint-imports` / `mypy` (gate CI) | limpio / 4 contratos / **571 ficheros** |

Las dos pruebas que importan son la del criterio —`perm.action == suggestion_from_exit_policy(...)`
sobre el **mismo** plan— y los dos controles negativos: `HINT` + `protect`/`hold` sigue denegado, y
`TIME_STOP` con datos rancios sigue denegado.

**CI por commit** [`40465967324`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40465967324)
sobre `b48cc407` ⇒ **`success`** (`quality` + los cuatro jobs PG).

**Lo que NO se ha hecho, y queda declarado.**

- **No** se hace que el AUTO consulte F5: es **S-6**, cambio de cableado y no de veredicto.
- **No** se cambia `TIME_STOP` a `TRIGGERED`: `HINT` es correcto y cambiarlo alteraría la precedencia
  visible en la UI.
- **El gate de mypy no cubre `packages/py/analytics`**: el cambio queda sostenido por `ruff` y por
  las pruebas, no por tipos.
- **Sin sello, sin tag y sin bump.** La evidencia es **E1**.

### 12.13 S-2: una sola tabla de salidas protectoras

> **Cierra el ítem S-2** de §5.4 y §10 de la auditoría, y el criterio `S-2` de §9.

**Qué se implementó.** El conjunto de «salidas que deshacen riesgo» pasa a tener **un solo origen**,
`exit_plan.PROTECTIVE_EXIT_REASONS`, consumido por `position_decision` y por
`exit_permission._is_protective`. Antes había dos copias y ya habían divergido: F5 incluía
`THESIS_INVALIDATION`, la decisión de posición no, así que bajo `CRITICAL` la posición sobrevivía a
su propia invalidación.

| Entra | No entra |
|---|---|
| `STRUCTURAL_STOP`, `TRAIL`, `PORTFOLIO_RISK`, `KILL_SWITCH`, `REGIME_EXIT`, `RISK_EXIT`, `THESIS_INVALIDATION` | `TIME_STOP` (vencer no es cubrirse), `MANUAL` (orden humana), `TARGET_1`/`TARGET_2` (tomar beneficio puede esperar) |

**Efecto declarado en F5.** `check_exit_permission` pasa a eximir también `TRAIL`, `RISK_EXIT`,
`REGIME_EXIT` y `KILL_SWITCH` de los vetos JIT. No es lateral: esos cuatro ya estaban declarados como
protectores en la capa de decisión y F5 era la que discrepaba. Un `ALLOW` de salida no autoriza
ninguna apertura, y el flag de *halt* del sistema sigue denegando según H2.

**Verificación (E1).**

| Gate | Resultado |
|---|---|
| `test_position_decision.py` | **12 passed** (4 nuevas/reemplazadas) |
| `test_exit_permission.py` | **26 passed** (3 nuevas) |
| `test_position_manager.py` | **22 passed** (1 reemplazada) |
| `analytics` + `application` + 4 suites de salida api | **4281 passed** |
| `ruff` / `lint-imports` / `mypy` (gate CI) | limpio / 4 contratos / **571 ficheros** |

La prueba estructural compara la tabla por **identidad** (`is`), no por contenido: si alguien
reintroduce una lista local en cualquiera de las dos capas, se rompe antes de que vuelvan a
discrepar. Los controles negativos fijan lo que **no** debe entrar: `TIME_STOP` y `MANUAL` siguen
vetados por datos rancios, y `TIME_STOP`/`TARGET_2` siguen degradando a `REVIEW` bajo `CRITICAL`.

**CI por commit** [`40467379256`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40467379256)
sobre `e82ff02d` ⇒ **`success`** (`quality` + los cuatro jobs PG); `Optimize lab`
([`40467379448`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40467379448)) y `Fase 2
scientific` ([`40467379334`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40467379334)) también
en verde sobre la misma cabecera.

**Lo que NO se ha hecho, y queda declarado.**

- **No** se mete `TIME_STOP` ni `MANUAL` ni los objetivos en la tabla: su exclusión está declarada y
  probada.
- **No** se cierra aquí **S-3**: siguen existiendo caminos que producen `hold` (p. ej. `TIME_STOP` bajo
  `CRITICAL`); se cierra en §12.14 (el estado deja de fingirse, aunque la política no cambia).
- **Sin sello, sin tag y sin bump.** La evidencia es **E1**.

### 12.14 S-3: `EXIT_PENDING` sólo cuando la orden existe

> **Cierra el ítem S-3** de §5.5 y §10 de la auditoría, y el criterio `S-3` de §9.

**Qué se implementó.** El turno separa **intención** de **transición**, igual que ya separaba
decisión de orden:

| Momento | Antes | Ahora |
|---|---|---|
| Al decidir salir | `advance_lifecycle` a `EXIT_PENDING` | `_v2_note_exit_intent` guarda `PendingExitIntent` y **no toca el FSM** |
| Al materializar la venta | — | `_v2_confirm_exit_emitted` aplica la transición, sella la `revision_id` y journaliza el motivo con `emitted: true` |
| Turno sin orden | silencio (estado fantasma) | `_v2_flush_unemitted_exits` declara `exit_not_emitted` con motivo y `plannedEvent` |

`exit_not_emitted` se añadió a `POSITION_LIFECYCLE_REASONS` (⇒ `POSITION_ATTRIBUTION_REASONS`): es
atribución de gestión, nunca veto de entrada.

**Verificación (E1).**

| Gate | Resultado |
|---|---|
| `test_auto_v2_lifecycle_clock_thesis.py` | **12 passed** (incluye `test_exit_pending_requires_emitted_order`) |
| `test_auto_v2_worker_integration` · `test_auto_simulation_worker` · `test_auto_v44_exit_governance` · `test_auto_v2_golden_day_evidence` · `test_auto_sim_active_strategy_seam` | **90 passed** |
| `test_auto_operational_monitor` · `test_auto_v2_entry` (application) | **143 passed** |
| `ruff` / `mypy` (api + application) | limpio / **409 ficheros sin issues** |

**CI por commit** [`40470621587`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40470621587)
sobre `a9429465` ⇒ **`success`** (`quality` + los cuatro jobs PG). El commit de código (`a4a29e59`)
quedó rojo **sólo** en `quality` por el orden de imports exigido por `ruff --config pyproject.toml`
(localmente pasaba con la config del paquete); `a9429465` es ese reordenamiento. `Optimize lab`
([`40470100721`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40470100721)) y `Fase 2 scientific`
([`40470100724`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40470100724)) ⇒ `success` sobre
`a4a29e59`.

Además, la suite offline completa de `api-python` (`-m "not integration"`) ⇒ **1385 passed, 12
deselected** (8 min 14 s), incluida la prueba nueva.

La prueba es un **control negativo de S-2** en el mismo turno: techo vencido (`TIME_STOP`) con
reconciliación `DIVERGENT` ⇒ `CRITICAL` ⇒ `REVIEW` ⇒ `hold`. Se afirma que (a) no hubo venta, (b) el
`lifecycleState` **no** es `EXIT_PENDING` y (c) el journal dice `exit_not_emitted` y **no** `time_exit`.
El caso positivo —la venta real— ya estaba cubierto y sigue journalizando `time_exit`.

**Lo que NO se ha hecho, y queda declarado.**

- **No** se cambia la política que produce el `hold`: `TIME_STOP` bajo `CRITICAL` sigue degradando a
  `REVIEW` (es S-2 y está probado). Ahora se **declara** en vez de fingir una salida.
- **No** se consulta F5 desde el AUTO en este paso (**S-6**, cerrado después en §12.17).
- **Sin sello, sin tag y sin bump.** La evidencia es **E1**.

### 12.15 O-1/O-2: el settle fallido se cuenta y el modo estructural se publica

> **Cierra los ítems O-1 y O-2** de §7.2/§7.3 y §10 de la auditoría, y los criterios `O-1`/`O-2`
> de §9.

**Qué se implementó.**

| Silencio | Antes | Ahora |
|---|---|---|
| Settlement que lanza | `except Exception` ⇒ log; el día no lo distinguía de «no hubo fill» | cuenta `settlement_failures`, journaliza `settlement_failed` (lado, cantidad, venue, modo, tipo de error) y el informe publica `settlementFailures` + `settlement_failed` en `errors` |
| Modo sin caja | `structural=True` sólo en memoria | `payload.structural = true` en la orden de entrada y en la liquidación del ciclo; `SimJournalRow.structural` en el día y `structuralOrders` en el informe |

`settlement_failed` entra en `MATERIALIZATION_REASONS` (⇒ atribución de gestión), no en las causas
de veto de entrada. Las claves son **aditivas**: sin `structural` cuando hay `finance_applier`, así
que el camino normal no cambia de payload (Δ = 0) y no hay migración.

**Verificación (E1).**

| Gate | Resultado |
|---|---|
| `test_auto_simulation_worker.py` | **25 passed** (incluye `test_settle_failure_is_counted` y `test_structural_settlement_is_published`) |
| `test_auto_daily_journal` · `test_auto_operational_audit` · `test_auto_m2_operational_audit_seam` · `test_auto_v2_golden_day_evidence` · `test_auto_v2_worker_integration` · `test_auto_engine_full_day_zero_human_intervention` | **123 passed** |
| `application` + `analytics` | **4241 passed** |
| `ruff` / `mypy` (api + application) | limpio / **409 ficheros sin issues** |

Las dos pruebas son de **control negativo**: la de O-1 hace fallar `submit_simulated_order` y exige
que el día lo diga (y que **no** quede posición abierta a medias); la de O-2 corre sin
`finance_applier` y exige que el hecho durable declare el modo. Ninguna de las dos eleva el modo
estructural a «modo válido de producción».

**La suite completa de `api-python` no se podía certificar en esta máquina, y no por este cambio.**
`pytest -m "not integration"` ⇒ **1261 passed, 71 failed, 55 skipped**; los 71 fallos estaban todos
en ficheros que necesitan PostgreSQL (`*_pg`, `test_workspaces*`, `test_health`, `test_lifecycle_golden*`)
y la causa raíz era la **base de desarrollo**, no el código: quedó en `035_paper_forward_evidence`
cuando el código espera `058_estudio_daily_proposals` (una corrida anterior murió a mitad de un
`roundtrip` de migraciones), y `signal_alert_subscriptions` arrastraba **1580 atributos *dropped***
(los cuenta PostgreSQL aunque `information_schema` sólo muestre 17 columnas vivas), así que el primer
`ADD COLUMN` de la 054 reventaba con `TooManyColumns` — el desgaste ya descrito en
[`evidence/v2.88.136`](./evidence/v2.88.136/README.md) §«límites». **Decisión del owner aplicada:**
la BD se **reconstruyó** con el respaldo previo
(`db-backups/bolsa_v1-20261027-094148-256.sql`) ⇒ drop/create → `alembic upgrade head` (`058`) →
`pnpm db:seed` (35 instrumentos + catálogo IBEX + portfolio virtual). Tras la reconstrucción:
`test_signal_alerts_v111_pg` + `test_workspaces*` + `test_unique_natural_keys_pg` +
`test_trackers_policies_isolation` ⇒ **35 passed**; `test_lists.py` + `tests/integration` ⇒
**48 passed**; suite completa (`-m "not integration"`) ⇒ **1390 passed, 7 failed, 1 skipped,
12 deselected** (6 min 37 s). Los **7** fallos son de **interferencia en la BD de desarrollo
compartida**, no del código: los tests de *roundtrip* de migraciones **mutan** el esquema que el
resto de ficheros asume (el log muestra `DuplicateColumn: column "reference_mid" … already exists`),
y la propia corrida deja `sim_fill_finance_context` con **87 atributos *dropped*** (el desgaste de
§v2.88.136). Los siete, re-ejecutados **en aislamiento**, pasan: **6 passed** (`test_auth`,
`test_auto_dia_d_trace_pg`, `test_auto_v88_28_protection_exactly_once_pg`), **2 passed**
(`chaos/live_a7` C3b + `test_auto_v46_multiprocess_pg`) y **1 passed**
(`test_auto_daily_chain_full_real_e2e_pg`). En CI esos ficheros corren en jobs PG dedicados sobre
BD **recién creada**, que es justo lo que evita el acoplamiento. Ningún fichero del diff toca
esquema ni migraciones.

**Lo que NO se ha hecho, y queda declarado.**

- El contador **no** se acumula en PostgreSQL entre procesos: se deriva del journal del día (que es
  lo que el informe agrega). Persistirlo exigiría migración y no cambia el criterio.
- **No** se exige `finance_applier` ni se prohíbe el modo estructural: sigue siendo el modo smoke,
  ahora **declarado** en cada fila.
- **Sin sello, sin tag y sin bump.** La evidencia es **E1**.

**CI por commit** [`40472943847`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40472943847)
sobre `18f59fdc` ⇒ **`success`** (`quality` + los cuatro jobs PG). `Optimize lab`
([`40472943891`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40472943891)) y `Fase 2 scientific`
([`40472943856`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40472943856)) ⇒ `success` sobre el
mismo commit.

### 12.16 T-1/T-2: la cola de scan se declara y el scan diario no espera 24 h

> **Cierra los ítems T-1 y T-2** de §6.1 y §10 de la auditoría, y los criterios `T-1`/`T-2` de §9.

**Qué se implementó.**

| Silencio | Antes | Ahora |
|---|---|---|
| Nadie decía quién drena `scan_jobs` | el scheduler arrancaba 20 crons y callaba | declara `authority=` al arrancar (`arq_worker` \| `queue_poll_worker`) |
| Cola atascada | invisible | `scan_queue_stalled` (ERROR) con `pending`, antigüedad y la acción `bolsa-queue-poll-worker`; si no se puede leer ⇒ `scan_queue_unknown` (WARNING, no aborta) |
| Primer tick del scan diario | `sleep(86 400)` **antes** de trabajar | primer tick **inmediato**; el `sleep` va al final del bucle |
| Reinicio del worker | el dedupe era una variable de módulo | dedupe **durable** por día UTC sobre `scan_jobs` (`opportunityDiscovery`) |

**Verificación (E1 + E2 parcial).**

| Gate | Resultado |
|---|---|
| `test_queue_poll_worker` + `test_scheduler_worker` + `test_opportunity_daily_scan_worker` + `test_logging_redaction` | **51 passed** |
| `test_scan_queue_health_pg` (PG real, `SCAN_QUEUE_PG_REQUIRED=1`) | **3 passed** |
| `ruff` / `mypy` (api + application + repositorio) | limpio / **411 ficheros sin issues** |

El test de T-2 es de **orden de eventos**: registra `run` y `sleep` y exige que el primer evento sea
`run` y que el `sleep` posterior sea el intervalo completo. El de T-1 es de **nivel y contenido**:
ERROR con `reason=scan_queue_stalled` y la cadena `bolsa-queue-poll-worker` en el mensaje, para que
el operador sepa qué arrancar y no sólo que algo va mal.

**Lo que NO se ha hecho, y queda declarado.**

- El scheduler **sigue sin** drenar la cola: duplicar la autoridad sería un segundo consumidor.
- El umbral de atasco (300 s) es constante del módulo, no un flag.
- **No** se toca la cadencia del AUTO ni el reloj de barras (**T-3** sigue abierto).
- **Sin sello, sin tag y sin bump.** La evidencia es **E1** + **E2** parcial.

**CI por commit** [`40479567239`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40479567239)
sobre `bc8c60ab` ⇒ **`success`**. `quality` corrió el offline completo: **5531 passed, 50 skipped**
(mypy 572 ficheros, ruff limpio). `lifecycle-pg` corrió con `SCAN_QUEUE_PG_REQUIRED=1`: **17 passed**
y **0 skips**, así que `test_scan_queue_health_pg` se midió contra PostgreSQL real (E2) y no quedó
fuera del veredicto. `Fase 2 scientific`
([`40479567203`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40479567203)) ⇒ `success`.

### 12.17 S-6: el AUTO consulta F5 antes de una salida (y el veredicto deja de ser mudo)

> **Cierra el ítem S-6** de §5.8 y §6 de la auditoría, y el criterio `S-6` de §9.

**Qué se implementó.**

| Pieza | Antes | Ahora |
|---|---|---|
| Consulta de F5 en el AUTO | **0** apariciones de `check_exit_permission` en el worker | el worker llama `review_auto_exit(...)` en **cada** salida, antes de reservar/emitir |
| Objeto juzgado | no existía (el plan vivía dentro de `build_position_decision`) | el **mismo** `ExitPlan` de la decisión viaja en `PositionManagerResult.exit_plan` |
| Declaración del veredicto | nada | fila `exit_permission` en el journal con `verdict`, `reasons`, `protective`, `exemption`, `exitPlanId`, `primaryReason` y el contexto JIT (incluido `marketClosed: null` = **no medido**) |
| Efecto sobre la salida | (no había consulta) | **ninguno**: `blocksExit: false` es contrato declarado y probado; el contador `TurnReport.exit_permission_denied` publica cuántas salidas salieron con un `DENY` |
| Camino legacy sin `PositionState` | — | F5 responde `missing_exit_plan` y así queda escrito: no se fabrica un plan para poder decir `ALLOW` |

**Decisión de arquitectura, ahora escrita.** El AUTO **no** bloquea salidas por F5: (1) una salida
protectora reduce riesgo; (2) el venue es el simulador paper; (3) vetar un objetivo por dato rancio
cambia la serie de fills sin reducir exposición. Lo que cambia no es el veredicto, es que **se
publica** con su exención (`auto_sim_exit_precedence`).

**Verificación (E1).**

| Gate | Resultado |
|---|---|
| `packages/py/application/tests/test_auto_exit_gate.py` (nuevo, 7) | **7 passed** — objetivo con dato rancio ⇒ `DENY`/`data_stale` + exención y la intención sigue en `reduce`; stop con el **mismo** dato ⇒ `ALLOW` (control positivo); sin plan ⇒ `missing_exit_plan`; drift veta objetivo y no stop; el plan expuesto es el de la decisión; `exit_permission` es atribución y no veto |
| `apps/api-python/tests/test_auto_exit_permission_s6.py` (nuevo, 2) | **2 passed** — de extremo a extremo: `TARGET_1` con `_v2_data_timestamps` rancio se vende igual, `exit_permission_denied >= 1` y la fila declara `DENY`/`data_stale`/`auto_sim_exit_precedence`/`jit.marketClosed = null`; el stop con el mismo dato declara `ALLOW` y deja el contador en **0** |
| `apps/api-python` completo | **1412 passed** |
| `packages/py/application` completo | **2922 passed** |
| `analytics` (`position_decision`/`exit_plan`/`exit_permission`) | **59 passed** |
| `ruff` / `mypy` (gate de CI: application + api-python) | limpio / **411 ficheros sin issues** |

El control positivo es la pieza que hace falsable el test: sin él, un `review_auto_exit` que
devolviera siempre `DENY` pasaría el caso de S-6 sin haber consultado nada.

**Lo que NO se ha hecho, y queda declarado.**

- **No** se bloquea ninguna salida: bloquear sería otro cambio de arquitectura (y otro riesgo), y no
  es lo que el hallazgo pedía. El contrato está en un punto único (`AutoExitReview.blocks_exit`).
- `market_closed` sigue **sin medirse** en el worker: se publica `null`, no `false`.
- El camino `AUTO_ENGINE_SIM_V2=0` no tiene `PositionState`; su salida declara `missing_exit_plan`
  en vez de recibir un plan sintético.
- **Sin sello, sin tag y sin bump.** La evidencia es **E1** + **E2** en CI.

**CI por commit** [`40484067176`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40484067176)
sobre `4d4060e8` ⇒ **`success`**. `quality` corrió el offline completo: **5541 passed, 50 skipped**
(mypy **573 ficheros** sin issues, `ruff` limpio, import-linter **4 kept / 0 broken**). Los cuatro
bancos PG por commit pasaron sin skips: `lifecycle-pg` **17 passed**, `grammar-discovery-pg` **21
passed**, `auto-v2-durable-pg` **7 + 1 passed**, `paper-forward-pg` **2 passed**. El banco durable ejecuta el worker AUTO contra PostgreSQL real
(arranque, tick y reinicio), pero **no** fuerza un `data_stale` sobre una salida: ese caso lo fija la prueba E1 de arriba, no el banco. Lo que sí certifica es que el worker con F5 consultado arranca, opera y reinicia sin romper la cadena.
`Fase 2 scientific` ([`40484067190`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40484067190))
y `Optimize lab` ([`40484067256`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40484067256)) ⇒
`success`.

