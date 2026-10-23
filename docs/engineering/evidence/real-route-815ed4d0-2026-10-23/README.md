# Evidencia — RUTA REAL del productor AUTO sobre PostgreSQL (`815ed4d0`)

Cierre del bloqueo de certificación abierto por la auditoría de
`815ed4d0277376f565b6ea479d944f1a75065e80` (base auditada `26250187`): el E2E que existía
demostraba el **cableado** con un `price_script` inyectado, no que el **camino de producción** abra.

**`Δ motor = 0`**, **`Δ decisión = 0`**, **sin migración** (`alembic head` sigue
`057_top3_opportunity_identity`). No se mueve el sello `v2.88.160-beta`, AUTO sigue **OFF** y la
ventana sigue **`INCONCLUSIVE`**. Lo único que cambia es lo que se **mide**: tests de aislamiento,
un E2E de la ruta real y su gate de CI.

Medido el **2026-10-23** en local sobre PostgreSQL **16.14** (`x86_64-pc-linux-musl`, Alpine), base
`bolsa_v1` con la head de Alembic citada. Venue **PAPER virtual**: no se abre el bridge LIVE.

## 1. Fase 0 — el `precio AUSENTE` era una fuga de entorno de test

El `precio AUSENTE → HOLD` que bloqueaba la certificación **no era un defecto del worker**. La
corrida del 2026-10-23 07:44 mostraba `precio AUSENTE` sobre instrumentos sintéticos `inst-gd2-*`: el
interruptor de la ventana (`AUTO_ENGINE_SIM_REAL_PRICE=1`) gobernaba una suite que **inyecta**
`price_script`; el runtime componía `OhlcvPriceSource` y, sin barra para esos ids, `execution()`
devolvía `None` ⇒ HOLD fail-closed. El control seguro funcionando sobre una suite mal aislada.

| Cambio (solo tests) | Efecto |
| --- | --- |
| `apps/api-python/tests/conftest.py`: fixture `autouse` `_isolate_auto_real_price_switch` que fija `AUTO_ENGINE_SIM_REAL_PRICE=0` | Ninguna suite sintética hereda la configuración de la ventana |
| `tests/test_auto_v74_producer_pg_e2e.py`: `_configure_producer_env` fija `AUTO_ENGINE_SIM_REAL_PRICE=0` | El E2E con `price_script` no puede ser secuestrado por el flag |
| `tests/test_golden_day_v2_process_pg.py`: `_env_for` fija `AUTO_ENGINE_SIM_REAL_PRICE=0` en la base | A1 sintético estable; A2 ya lo sube a `1` explícitamente en su `extra` |

**Medición del aislamiento**, con el flag ambiental a `1` (la fuga original) exportado en la shell:

| Comando | Resultado |
| --- | --- |
| `$env:AUTO_ENGINE_SIM_REAL_PRICE='1'; python -m pytest tests/test_auto_v74_producer_pg_e2e.py tests/test_auto_real_route_producer_pg.py -q` | **8 passed** |
| `$env:AUTO_ENGINE_SIM_REAL_PRICE='1'; python -m pytest tests/test_golden_day_v2_process_pg.py -q` | **2 passed** |

Con el flag a `1` los sintéticos siguen verdes porque el pin por test los protege: la separación
**defecto de aislamiento de test** / **defecto de producto** queda demostrada sin tocar el
fail-closed del motor.

## 2. Fase 1 — E2E POSITIVO de la ruta real

Fichero nuevo: `apps/api-python/tests/test_auto_real_route_producer_pg.py`. **Nada inyectado**: no se
pasa `price_script`, `price_source`, `atr_source`, `sector_source`, `liquidity_source` ni
`edge_source`; no hay decider fake.

### 2.1 Preparación determinista (todo en PostgreSQL real)

| Pieza | Valor sembrado |
| --- | --- |
| Reloj PINNED | `2026-10-05T10:00:00Z` ⇒ barra corriente `B = 2026-10-05`, `as_of` de decisión `B-1 = 2026-10-04` (resueltas con `bar_window`/`last_closed_bar_day`, las mismas primitivas del worker) |
| Barras D1 en `ohlcv_bars` | 80 cerradas (`B-79 … B-1`): tendencia `96.00 → +0.12/barra`, retroceso de 4 barras y salto final `105.50` que produce el cruce SMA(2)/SMA(4) **en `B-1`**; + barra `B` (`open 105.60`, `close 105.80`); + barra `B+1` (`open 100.00`, hueco bajo el stop estructural) |
| Instrumento | `inst-rroute-0000000001` — id **elegido por sonda** (`fill_seed` + `simulated_fill_schedule`) para que la cola del venue SIM llene compra y venta; la sonda **no toca precios**, solo evita un rojo espurio por sorteo |
| Estrategia ACTIVE | `StrategyCandidateRow` + `StrategyVersionRow` (`definition.executable` = cruce SMA 2/4) + `StrategyPromotionRow`; versión `v-route-<uuid>` |
| Contexto de cartera | `InstrumentRow` con sector y `profile_snapshot.fundamentals` frescos + `EdgeReportRow` de la versión |
| Entorno | `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_ENGINE_SIM_V2=1`, `AUTO_ENGINE_SIM_ACTIVE_STRATEGY=1`, `AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL=1`, `AUTO_ENGINE_SIM_WATCH=<id>`, `AUTO_ENGINE_SIMULATED_WATCH=<id>`, `BROKER_VENUE=paper`, `AUTO_OPERATIONAL_AUDIT=1` |

El decider es el **de producción**: `load_active_strategy_decider(factory, instrument_id=…,
watch=…, lot_qty=…, signal_enabled=True, as_of=worker._v2_closed_bar_as_of())`, refrescado por tick
como el loop real. Aserción explícita antes de operar: `action == "BUY"` y
`source == "active-strategy:<version>::sma_crossover"` — nunca una caída silenciosa al spine.

### 2.2 Comando y resultado

```powershell
cd apps/api-python
$env:AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED='1'
python -m pytest tests/test_auto_real_route_producer_pg.py -q -rs
```

**`7 passed`** (1 positivo + 6 controles negativos), sin ningún `skipped`.

### 2.3 Hechos durables medidos (lectura desde conexión NUEVA)

Tras el cierre del ciclo se ejecuta `engine.dispose()` y se reconstruye todo desde un engine nuevo,
con el **lector real del CLI** (`scripts/paper_material_readiness.py::_read`,
`limit=2000`, `min_cycles=32`):

| Hecho | Valor |
| --- | --- |
| `price_source` del fill de compra | **`MARKET_CLOSE`** |
| `reference_mid` de la compra | **`105.600000`** = `open(B)` de la barra sembrada |
| `reference_mid` de la venta | **`100.000000`** = `open(B+1)` (hueco que rompe el stop) |
| Precios materializados | `105.678100`, `105.723300`, `105.741900`, `105.813300` (compra) · `99.912900`, `99.889600`, `99.857000`, `99.829000` (venta): fricción del venue SIM en bps sobre el mid, **sin** `100.0` fabricado por el motor |
| `strategy_version_id` del fill | `v-route-76737b7f10` (la ACTIVE real, sin el sufijo `::preset` en la identidad) |
| Fills | **8** (4 buy + 4 sell), **todos** con el mismo `cycle_id = cyc-d9fd4b3c96b3` |
| Reserva de entrada | `RES-dec-d9fd4b3c96b3` · `side=buy` · `reserved_risk=1000.000000` · `quantity=189.573500` · **mismo `cycle_id`** · `RELEASED_BY_FILL` |
| Reserva de salida | `exit:01M5MG784TQ65C7A6700TFCCEK` · `side=sell` · mismo `cycle_id` · enlazada al `exit_order_id` |
| Orden de salida | `01M5MG784TQ65C7A6700TFCCEK` · `state=FILLED` · `emergency=false` · `filled_qty=189.573500` · mismo `cycle_id` |
| Libro | `open_qty = 0` (`closed = true`) |
| `price_missing_counts` | `{}` — **ningún** `precio AUSENTE` en la ruta real |
| `auto_kill_state` | **0 filas** (un cierre normal no para el sistema) |

### 2.4 Gate reconstruido desde conexión nueva (§JSON real)

```json
{
  "verdict": "PRODUCER_READY",
  "producer_ready": true,
  "evidence_ready": false,
  "producer_blockers": [],
  "blockers": ["insufficient measurable cycles per strategy"],
  "facts": {
    "executionReality": "VIRTUAL — NO REAL MONEY",
    "durableFills": 8, "fillsWithCycle": 8, "fillsWithoutCycle": 0,
    "buys": 4, "sells": 4,
    "reservations": 2, "reservationsWithCycle": 2, "reservationsLive": 0,
    "closedCycles": 1, "measurableCycles": 1, "measurableCyclesWithIdentity": 1,
    "versionsMeetingMinimum": [],
    "perVersion": {"v-route-76737b7f10": {"closedCycles": 1, "measurableCycles": 1}}
  },
  "lineage": {
    "cycle": {"fillsWithCycle": 8, "fillsWithoutCycle": 0, "exitOrders": 1, "exitOrdersWithCycle": 1},
    "reservation": {"rows": 2, "withCycle": 2, "live": 0, "released": 2},
    "closure": {"closedCycles": 1, "closedCyclesWithIdentity": 1, "closedCyclesWithRisk": 1,
                "cyclesWithoutIdentity": 0}
  }
}
```

`PRODUCER_READY` con `producer_blockers == ()` es la afirmación estructural: el productor deja
material con **linaje completo** (fill → reserva → salida → cierre con riesgo). `evidence_ready`
sigue **falso** por **muestra** (`1 < 32` ciclos medibles), y se declara: este E2E **no** acredita
ventana ni rentabilidad.

## 3. Fase 2 — Controles negativos (stores PG reales, solo se envuelve el store bajo prueba)

| Test | Qué fuerza | Qué se mide |
| --- | --- | --- |
| `test_real_route_without_reservation_store_vetoes_the_entry` | `reservation_store=None` en `real_turn` | **0 fills**, **0 reservas**, sin apertura, gate **no** `PRODUCER_READY` (`RESERVATION_UNMEASURABLE`) |
| `test_real_route_rejected_claim_vetoes_the_entry_and_does_not_duplicate` | `save_claim` devuelve `False` (carrera perdida) | **0 fills** y **0** filas de reserva: el veto no deja rastro ni duplica |
| `test_real_route_claim_exception_leaves_no_orphan_fill` | `save_claim` lanza | **0 fills**: sin compromiso durable no queda contexto financiero huérfano |
| `test_real_route_missing_current_bar_fails_closed_to_hold` | se omite la barra `B` | `price_missing_counts[instrumento] > 0`, HOLD, **0 fills**: el motor **no** cae a `close(B-1)` ni a `100.0` (impide "arreglar" el E2E fabricando precio) |
| `test_real_route_exit_intent_falls_back_to_emergency_and_still_sells` | falla el primer `_v2_save_exit_order` | fila **`EMERGENCY`** con el **mismo `cycle_id`**, **venta emitida** y `auto_kill_state` sin HALT: reducir riesgo nunca se bloquea |
| `test_real_route_exit_intent_and_emergency_failure_halts_durably` | fallan INTENT y emergencia | **no** se emite la venta, la posición sigue abierta (`open_qty > 0`) y `auto_kill_state` queda en **`SYSTEM_ERROR` engaged**, leído desde **conexión nueva** |

## 4. Fase 3 — CI obligatorio por commit y por tag

| Workflow | Cambio |
| --- | --- |
| `.github/workflows/python-ci.yml` | `AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED: '1'` en el job `auto-v2-durable-pg`; **paso propio** `Pytest AUTO ruta REAL del productor PG` con `set -o pipefail`, log en `/tmp/auto-real-route-pg.log` y guarda `Fail on skipped …` (`if: always()`, falla si el log no existe o contiene `skipped`/`SKIPPED`); el fichero entra en `--ignore` del job hermético |
| `.github/workflows/release-tag-ci.yml` | mismo gate en `lifecycle-pg`, paso dedicado equivalente tras el Golden Day 2.0, y el fichero en `--ignore` del job offline del tag |

**Dos gates separados**, como pide el cierre: `AUTO_V74_PRODUCER_PG_REQUIRED` (precio sintético) y
`AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED` (ruta real). El fichero corre en **paso dedicado** en lugar de
sumarse al lote `run: >` del job: así un skip de la ruta real no queda diluido en un log mayor ni
compensado por los ficheros sintéticos, y cada gate conserva su propio log y su propia guarda.
Ambos workflows validan como YAML (`yaml.safe_load` OK) y la lista de rutas existe.

### 4.1 Gobierno honesto del gate (medido, no supuesto)

| Escenario | Resultado |
| --- | --- |
| `AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED=1` + PostgreSQL alcanzable | **7 passed** |
| `AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED=1` + `DATABASE_URL` inalcanzable (`127.0.0.1:1`) | **7 failed** con `AssertionError: PostgreSQL requerido para el E2E de la RUTA REAL del productor pero no disponible…` — el skip silencioso es **fallo duro** |
| Sin el gate + PostgreSQL inalcanzable | **7 skipped**, motivo explícito (`-rs`) — nunca una certificación fantasma |

## 5. Hallazgo colateral en `quality`: el commit auditado estaba rojo de lint

El primer CI de esta rama dejó **`auto-v2-durable-pg` en `success`** (el paso nuevo de la ruta real
corrió y no skipeó) y **`quality` en `failure`**, por **4 `I001`** en ficheros que **no** toca este
trabajo:

| Fichero | Último commit que lo tocó |
| --- | --- |
| `apps/api-python/tests/test_auto_simulation_worker.py` | `815ed4d0` |
| `apps/api-python/tests/test_auto_v88_durable_facts.py` | `815ed4d0` |
| `packages/py/application/src/bolsa_application/operability_window.py` | `815ed4d0` |
| `packages/py/application/tests/test_operability_window.py` | `815ed4d0` |

Es decir: **`815ed4d0` nunca corrió `quality` en verde** (`ruff check packages/py apps/api-python
--config pyproject.toml` fallaba en `main`). Se corrige en un **commit aparte**
(`style(lint): ordena los imports que dejó rojos 815ed4d0`) con `ruff check --fix` y **diff
verificado**: solo reordena imports y quita dos líneas en blanco; **cero** cambios de lógica. Tras el
fix, el gate exacto del CI queda en **`All checks passed!`**.

Se aísla en su propio commit para que el auditor pueda comprobar que es mecánico y que **no** forma
parte de la certificación de la ruta.

## 6. Límites declarados

- **PAPER virtual**: un instrumento y un día; **no** hay LIVE, **no** hay rentabilidad. El E2E
  certifica la **ruta** (precio → decisión ACTIVE → plan → reserva → fill → salida → gate), no que el
  mercado produzca señales ni que la estrategia gane.
- **Las barras están sembradas**: se siembran 80 barras cerradas, `B` y `B+1` para fijar el escenario.
  Lo que **no** se fabrica es el precio del fill ni la decisión: ambos salen de `OhlcvPriceSource` y
  del `SignalEvaluator` real sobre `<= B-1`, ejecutando en `open(B)`.
- El id del instrumento lo elige una **sonda de cola del venue SIM** (determinista) para evitar un
  rojo por sorteo; no altera ningún precio ni desactiva la fricción.
- Los **24 fills históricos** de la ventana siguen **sin identidad de ciclo** y **no** se backfillean;
  este trabajo no los reinterpreta.
- La ventana sigue **`INCONCLUSIVE`**; `evidence_ready` sigue falso por muestra.
- El sello **`.160` no se mueve**. Un bump `.161` exigiría, aparte, CI obligatorio verde y aprobación
  explícita.
- La suite nueva **borra su propio residuo** (cuenta, instrumento, barras, versión/candidata/promoción
  y tablas del motor) al terminar cada escenario: no comparte estado con otros tests PG.

## 7. Reproducir

```powershell
cd apps/api-python
$env:AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED='1'
python -m pytest tests/test_auto_real_route_producer_pg.py -q -rs      # 7 passed
python -m pytest tests/test_auto_v74_producer_pg_e2e.py -q             # 1 passed (sintético intacto)
python -m pytest tests/test_golden_day_v2_process_pg.py -q             # 2 passed (A1/A2)
```

Con PostgreSQL caído y el gate activo el fichero debe **fallar** (7 failed), no skipear.

## 8. CI y publicación

| Workflow | Run | `headSha` | Resultado |
| --- | --- | --- | --- |
| `Python CI` | [39964377178](https://github.com/jvelasca/Bolsa_V1/actions/runs/39964377178) | `9ab5ebed` | `auto-v2-durable-pg` **`success`** (el paso de la ruta real corre y **no** skipea) · `quality` **`failure`** por los 4 `I001` preexistentes de `815ed4d0` (§5) |
| `Python CI` | [39964791740](https://github.com/jvelasca/Bolsa_V1/actions/runs/39964791740) | `2aeb0d8d` | **`success`** (5/5 jobs), con `Pytest AUTO ruta REAL del productor PG` y `Fail on skipped AUTO ruta REAL PG` en **`success`** |

La segunda corrida es la que certifica: `quality`, `auto-v2-durable-pg`, `lifecycle-pg`,
`paper-forward-pg` y `grammar-discovery-pg` en verde, y el paso nuevo de la ruta real ejecutado (sin
`skipped`). `Fase 2 scientific` y `Optimize lab` del mismo `headSha` también quedaron en `success`.

Rama `fix/audit-815ed4d0-real-route` creada desde `815ed4d0` y tag anotado
`audit-815ed4d0-real-route` para el auditor. **`main` no se toca**: su puntero sigue en `815ed4d0`
(igual que el tag preexistente `audit-815ed4d0`), y el sello `.160` permanece intacto. Un bump
`.161` queda **pendiente de aprobación explícita**; esta rama no lo hace.
