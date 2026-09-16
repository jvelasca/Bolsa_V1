# Changelog

All notable releases of Bolsa V1.

## [1.65.4-beta] — V2.40.4 · AUTO Safety & Accounting (TOP_N real, measurement status, órdenes pendientes y validación de TradePlan) — 2026-09-16

**Sin migración** (head sigue en `041_unique_natural_keys`). Cierra los cuatro agujeros de
seguridad/contabilidad de AUTO que destapó la auditoría de `v2.40.2-beta`. Ninguno es cosmético: los
cuatro podían hacer que AUTO gastara dinero que ya estaba comprometido, decidiera sobre un número que
era un suelo disfrazado de total, o emitiera un plan que se contradecía a sí mismo.

| #      | Qué                                                                                                                                                                                                                                                                                                                                         |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | `TOP_N` era un tope de **prioridad**, no de **evaluación**: los candidatos fuera del TOP llegaban sin score y el journal los reportaba como `edge_below_threshold` (**un motivo falso**). Ahora es un tope de evaluación y los excluidos se journalizan con `top_n_excluded` y su score/rank **reales** (`approved <= top_n` es invariante) |
| **F2** | `risk_used` y la exposición agregada se publicaban como un número "completo" sumando solo lo que sabían medir (**un suelo**). Nuevo `MeasurementStatus` (`COMPLETE`/`PARTIAL`/`UNKNOWN`): un agregado incompleto **veta** la apertura                                                                                                       |
| **F3** | `open_orders: int` era un contador **muerto** (siempre 0): el sistema podía gastar dos veces el mismo cash. Nuevo libro de órdenes pendientes (`OpenOrder`) con `reserved_cash`/`available_cash`/`pending_risk`/`pending_exposure` y veto `open_orders_unmeasurable`                                                                        |
| **F4** | `TradePlan` **sin validación**: un plan incoherente se serializaba, viajaba por el journal y acababa dimensionando una orden real. Nuevo `validate_trade_plan` + veto `plan_invalid` con las violaciones en el journal                                                                                                                      |

### F1 — `TOP_N` (tope de evaluación) y journal honesto

`plan_v2_tick` rankeaba todo pero **solo puntuaba el top-N**: los de fuera llegaban con `score=None` y
el motor los rechazaba con `edge_below_threshold`. Es decir, el journal afirmaba una causa falsa (su
edge era válido; simplemente no compitieron) y la semántica real era "solo el top-N es operable".

Ahora `TOP_N` es el **máximo de oportunidades evaluadas** (Opción A de la auditoría, lectura literal):
se decide solo contra la cartera el subconjunto del TOP, y las candidatas fuera de él emiten una
entrada de journal `top_n_excluded` que **porta su `OpportunityScore` y su `rank` reales**, así que el
motivo del no-trade es el verdadero y el ranking completo queda auditable. `run_auto_cycle` usa la
misma regla (`build_top_n_excluded_payload`). `top_n = 0` excluye todo (fail-closed).

### F2 — `MeasurementStatus`: un agregado incompleto es un SUELO

Caso de la auditoría: `Position A → risk_amount = 100`, `Position B → risk_amount = UNKNOWN` producía
`risk_used = 100` cuando la verdad es `risk_used >= 100` y el total es **desconocido**. Lo mismo con
`aggregate_exposure` (saltaba las posiciones sin `market_value`).

Módulo puro nuevo `bolsa_analytics.cognitive.measurement` (`MeasurementStatus`, `coerce_measurement`,
`measurement_from_counts`, `is_complete`, `combine_measurements`). `AutoPortfolioSnapshot.risk_measurement`
y `ExposureBreakdown.measurement` derivan el tri-estado del dato real, el motor veta con
`risk_measurement_partial`/`risk_measurement_unknown`/`exposure_measurement_partial`/
`exposure_measurement_unknown` y el gate se puede apagar **explícitamente**
(`require_complete_measurement=False`), nunca por omisión. Un measurement incompleto **no** bloquea
una salida protectora (invariante con test).

### F3 — Órdenes pendientes: capital y riesgo comprometidos (sin migración)

`Cash = 50.000 €` con `BUY pending = 40.000 €` **no** significa 50.000 € disponibles. AUTO SIM liquida
en el mismo tick, así que el productor real de "órdenes en vuelo" son las filas de `execution_events`
que **no** están `APPLIED` (sobreviven a un crash), con su lado/cantidad/precio en
`sim_fill_finance_context`.

- Módulo puro `bolsa_analytics.cognitive.open_order`: `OpenOrder`, `OpenOrderSummary`,
  `build_open_order`, `summarize_open_orders`, `coerce_open_order`. Honestidad: una **venta** no
  reserva cash ni añade riesgo; una **compra** reserva su notional y su riesgo **solo si alguien lo
  declara** (no se inventa).
- `AutoPortfolioSnapshot.open_orders: int → tuple[OpenOrder, ...]` (**breaking declarado en beta**),
  con `order_book_measurement`, `reserved_cash`, `available_cash`, `pending_risk`, `pending_exposure`
  y `risk_remaining = budget − (risk_used + pending_risk)`.
- `ExecutionEventStore.list_unapplied(account_id, *, statuses, limit)` en el protocolo, in-memory y
  PostgreSQL (`WHERE status IN (...) ORDER BY captured_at DESC LIMIT`).
- `auto_simulation_worker._v2_refresh_open_orders()`: lee el libro una vez por tick **antes** de
  construir la foto, descarta lo ya reconocido por el worker (no cuenta dos veces el mismo dinero) y
  declara `UNKNOWN` ante fallo de lectura, `limit` alcanzado o store sin soporte ⇒ **veta aperturas**
  (nunca "no hay pendientes porque no pude leer").
- `RiskAllocator` acepta `reserved_cash` y resta el capital comprometido del poder de compra, con
  motivo propio `CAP_RESERVED_CASH` (distinto de `CAP_BUYING_POWER`: no es "no queda dinero", es
  "el dinero está comprometido"). La reserva intra-tick descuenta también el notional ya aprobado.

**Deuda declarada:** no hay índice parcial `execution_events(account_id, status)`; la lectura queda
acotada con `LIMIT` + orden por captura y la migración se asigna a la fase Reservation Engine.

### F4 — El plan que sale del motor no puede contradecirse

`TradePlan` no tenía `__post_init__` ni `validate()`: solo el factory armaba la máquina de estados, así
que un plan incoherente (qty > 0 sin geometría de riesgo, stop del lado malo, targets cruzados,
`initialRiskR` que no es `|entry − stop|`, `positionValue` que no es `qty × entry`, `status` distinto de
`TRIGGERED` con ejecución) se serializaba y viajaba.

Nuevo `validate_trade_plan(plan) -> tuple[str, ...]` (puro; vacío = válido) con códigos
`PLAN_VIOLATION_*`; `decide_portfolio` valida antes de devolver la decisión aprobada (**`plan_invalid`**
con las violaciones publicadas en el journal: `PortfolioDecision.plan_violations` →
`planViolations`) y `trade_plan_to_decision_package` devuelve `None` si el plan es incoherente
(defensa en profundidad en el seam que consume el worker). Los planes no ejecutables
(`WATCH`/`ARMED`/`BLOCKED`/`EXPIRED`) no se validan contra geometría que no necesitan.

### Certificación y gate CI

- Suites herméticas nuevas con nombre propio en el job `quality` (`python-ci.yml`) y en el job `python`
  del Release-tag CI: `test_trade_plan.py` (validación del plan) y `test_execution_event.py`
  (`list_unapplied`).
- Test nuevo con **PostgreSQL real** en el job `auto-v2-durable-pg`: un fill `CAPTURED` que dejó un
  proceso muerto aparece como **capital reservado** al reiniciar y **veta** la entrada nueva
  (`open_orders_unmeasurable`), en vez de gastar dos veces la caja.
- **Matriz de mutaciones medida** (cada mutación aplicada, suite corrida y revertida): quitar
  `top_n_excluded` ⇒ 3 suites rojas; volver `buying_power` a cash bruto ⇒ 1; desactivar los escalones
  de measurement ⇒ 12; saltarse `validate_trade_plan` ⇒ 1.
- **Límite declarado (pre-existente, NO introducido aquí)**: `test_auto_scheduler_real_pg_zero_human_intervention.py`
  es no determinista. Medido A/B a 30 ejecuciones por lado (revirtiendo en memoria los 9 ficheros de
  código del slice y restaurando byte a byte): **4/30 en el commit base** y **8/30 con el slice**.
  Mecanismo: el entry solo materializa parte de sus chunks y el exit se dimensiona por la **orden** (no
  por la posición materializada), así que los chunks cola quedan en `RETRY` (`apply_ineffective`)
  **conservando fila en `sim_fill_finance_context`**, y la aserción de equity del test las cuenta como
  realizado. Por eso esa puerta puede ponerse roja con el código base **y** con este tip: el criterio es
  re-ejecutar el job. Causa raíz asignada a `AUTO-1`; detalle en §5.6 del audit-pack.
- Plan de implementación y roadmap por fases (`V2.40.4` → Adaptive AUTO) en
  [`docs/engineering/plan-v2-40-4-auto-safety-accounting-2026-09-16.md`](./docs/engineering/plan-v2-40-4-auto-safety-accounting-2026-09-16.md)
  y [`docs/engineering/roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./docs/engineering/roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md),
  con los P1 diferidos mapeados a su fase.
- **Sellado de CI (GitHub, posterior al commit):** tag anotado **`v2.40.4-beta` → `1127d010`**
  (`main` == `1127d010`; el commit docs-only de este sellado es posterior y **no** entra en el tag).
  `Release-tag CI` **GREEN** run [`35155027506`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35155027506)
  (9 jobs requeridos + `certify`) y `Python CI` **GREEN** run
  [`35154788932`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35154788932) (5/5, `quality`
  1734 passed). **Un rojo real, arreglado y declarado:** el primer `Python CI` (run
  [`35150808768`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35150808768)) dejó `quality` en rojo
  con `test_list_unapplied_filters_by_status`, que afirmaba el orden de inserción en vez de
  `captured_at DESC` (en local empataban los sellos de tiempo del reloj y pasaba); se corrigió en
  `1127d010` y el tag apunta al commit verde. Detalle en §7.1 del audit-pack.

## [1.65.3-beta] — V2.40.3 · Hotfix de la clave de idempotencia financiera (colisión por recorte) + invariante del A9 sobre el ledger real — 2026-09-16

**Sin migración** (head sigue en `041_unique_natural_keys`). Tres cambios independientes, y el
primero es un **bug de dinero**, no de cosmética:

| #      | Qué                                                                                                                                                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | `simulated_idempotency_key` (SIM) y `recovery_idempotency_key` (recovery LIVE) dejaban de ser inyectivas por el **recorte con pérdida** del `execution_id` ⇒ los N fills de una misma orden colapsaban en **una** clave y el libro no cerraba |
| **F2** | El invariante de equity del test de certificación del día AUTO leía la posición de **`position_states`** (tabla que el camino AUTO SIM **no** escribe) ⇒ el término no realizado era siempre 0                                                |
| **F3** | Gate nuevo: al cerrar el día AUTO, **libro plano** y **ningún fill sin materializar** (`execution_events` todos `APPLIED` y todo `sim_fill_finance_context` con su transacción en el ledger)                                                  |

### La incidencia: el tag `v2.40.2-beta` dejó `lifecycle-pg` en rojo

El Release-tag CI del tag anterior falló en el job `lifecycle-pg`, en el test de certificación del
día AUTO completo (`test_a9_scheduler_process_full_day_pg_zero_human`), con el invariante de equity:

```
AssertionError: equity ... != initial + realized + unrealized ...
```

El mensaje apuntaba al sitio equivocado: el desajuste **no** era de la aritmética del ledger (que
está certificada) sino de **tres fills que nunca llegaron a materializarse**. Ningún test lo decía,
porque no existía un gate que mirara el estado de los `execution_events` al cerrar el día.

### Causa raíz (F1): el recorte se comía justo el `#fill_seq`

La identidad financiera de un fill es `execution_id = f"{venue_order_id}#{fill_seq}"`, y desde
P1-03 el `venue_order_id` del AUTO va **namespaced** (engine + UUID de cuenta + instrumento + lado +
secuencia lógica): medido, el `execution_id` de una orden AUTO realista mide **126-128 caracteres**.
Las dos derivaciones históricas recortaban el slug **por la cola**:

```python
return f"sim-fin-{slug[:120]}"[-128:]          # SIM
return f"recovery-fin-{slug[:100]}"[-128:]     # recovery LIVE
```

y la cola es exactamente donde vive el `#fill_seq`. Medido con la identidad del worker: **4 fills →
1 clave distinta** (en ambos lados y en ambos caminos), cuando el contrato pide 4. Consecuencia
medida en el camino real:

1. La primera trancha se asienta con la clave `sim-fin-…`.
2. La segunda llega a `ExecuteTrade` con la **misma** clave y **otro** payload ⇒
   `IdempotencyKeyReused` (409 en la capa HTTP, excepción en la de aplicación).
3. `apply_execution_financial_once` la captura y la degrada a
   `mark_retry(error="apply_exception")` ⇒ `retry_scheduled`.
4. El worker AUTO absorbe el fallo por símbolo (`auto_sim settle failed` ⇒ "sin fill este tick") y
   esa fila se queda en `RETRY` **para siempre**: la clave es función del mismo `execution_id`, así
   que el reintento vuelve a chocar. El lado vendedor no liquida y el día termina con el libro
   abierto y dinero sin mover.

Es un fallo **permanente y silencioso** (no un 500 transitorio): el sistema parece operar, cierra el
día "sin incidencias" y deja tranchas sin materializar. Detectarlo requería mirar el estado de los
eventos, que es justo lo que añade F3.

### Fix (F1): recorte SIN pérdida en un módulo propio

Nuevo `packages/py/application/src/bolsa_application/idempotency_key.py` con
`bounded_idempotency_key(prefix, execution_id, *, legacy_budget)`:

- `len(slug) <= legacy_budget` ⇒ `f"{prefix}{slug}"`: **byte a byte** la clave histórica (el
  `[-128:]` histórico era inoperante porque el total nunca superaba 128) ⇒ **compatibilidad exacta**:
  un fill en vuelo de un deploy anterior re-deriva LA MISMA clave y no se re-aplica dinero.
- `len(slug) > legacy_budget` ⇒ `f"{prefix}{slug[:head]}~{sha256(execution_id)[:32]}"`, 128 chars
  exactos. El marcador `~` **no puede** aparecer en un slug (`re.sub` manda todo lo que no sea
  `[A-Za-z0-9_]` a `-`), así que ninguna clave "larga" puede coincidir con una "corta"; y el digest
  del `execution_id` **completo** discrimina exactamente lo que el recorte tiraba (el `#fill_seq`).
- Slug degenerado (p.ej. `unknown`) ⇒ se rellena hasta el mínimo de 16 con la **misma** marca.

`simulated_idempotency_key` y `recovery_idempotency_key` pasan a delegar (presupuestos 120 y 100
respectivamente). El contrato R-11 C2 (`16 <= len(key) <= 128`, sin whitespace, estable por
`execution_id`) se mantiene para **todo** el rango.

### Fix (F2): el invariante lee el estado canónico real

El invariante anterior reconstruía la contabilidad desde el ledger, pero tomaba la **posición
abierta** de `SqlAlchemyPositionStateRepository` (`position_states`). El camino AUTO SIM **no escribe
esa tabla** (escribe `sim_auto_positions` y la canónica `positions`), así que `remaining = 0` y el
término no realizado era **siempre 0**: el invariante se degradaba a una identidad de caja y era
**ciego** a una posición a medio liquidar. La versión nueva (`_assert_full_day_closed`) reconstruye
la identidad desde el **estado canónico** (`positions`) y el P&L cerrado desde
`sim_fill_finance_context` (fuente independiente) contra el ledger real.

### Fix (F3): gate nuevo de cierre del día

El mismo test, antes de certificar, exige las tres cosas juntas:

1. Todos los `execution_events` de la cuenta en `APPLIED` (**cero** `RETRY`/`CAPTURED`/`APPLYING`).
2. Todo `sim_fill_finance_context` con su transacción correspondiente en el ledger (**ningún fill sin
   materializar**).
3. Posición final **plana** (libro cerrado) y el invariante de equity del dominio sobre el ledger.

Es el gate que habría nombrado el fallo del tag en una línea: _"el día AUTO deja 3 ExecutionEvents
sin materializar (RETRY/CAPTURED)"_.

### Determinismo del test (y un verde falso retirado)

Con F1 arreglado apareció el siguiente rojo, esta vez en
`test_a9_scheduler_process_restart_with_open_protected_position_pg`:

- **Instrumento aleatorio ⇒ lotería determinista.** El simulador rechaza la orden entera
  (`fills=()`) según un ruido determinista por `(seed, instrument_id, lado)`: medido con la sonda,
  **12,36 %** de los identificadores aleatorios no llenan nunca, así que el test fallaba por sorteo
  (`el proceso debe abrir (BUY durable) antes del restart`). Ahora el instrumento se elige de forma
  **determinista** entre los que sí llenan (`_filling_instrument_id`), y el test del día completo usa
  una identidad fija.
- **Se contaban tranchas en vez de órdenes.** El invariante del restart es "no **re-comprar**", pero
  el test contaba filas de `execution_events` (tranchas de fill) filtradas por lado: materializar
  tras el restart la trancha que quedó en vuelo al matar el proceso es lo **correcto** y se contaba
  como re-compra. Ahora cuenta `count(distinct venue_order_id)` ⇒ una re-compra real es una
  `venue_order_id` **nueva**. El contador anterior solo pasaba porque el bug de F1 lo congelaba en 1.

### Tests

- **Nuevo** `packages/py/application/tests/test_idempotency_key_budget.py` (hermético, sin PG ni
  broker, entra en la batería offline del job `quality`): regresión del colapso (4 fills ⇒ 4 claves,
  ambos lados, con la identidad del worker), comprobación de que el recorte histórico **sí** colapsaba
  (para que el test no pueda "arreglarse" solo), compatibilidad **exacta** con las claves cortas,
  disjunción estructural de las largas (`~`), contrato 16..128 sin whitespace, inyectividad entre
  lados/órdenes/secuencias y caso degenerado.
- `test_a9_scheduler_process_pg_zero_human.py`: invariante sobre el estado canónico, gate de libro
  plano / sin fills pendientes, instrumento determinista que llena y conteo de órdenes en el restart.

### Verificación (local)

- **A/B del bug, sin tocar el código del repo**: restaurando la derivación histórica en runtime (un
  `sitecustomize` por `PYTHONPATH` que también ve el subproceso del scheduler), el día AUTO falla con
  `AssertionError: el día AUTO deja 3 ExecutionEvents sin materializar (RETRY/CAPTURED)` — los 4 fills
  de la orden colapsan en 1 clave, 1 se asienta y 3 quedan en `RETRY` permanente. Con el fix, el
  fichero A9 queda verde (día completo + restart, 2 passed).
- Batería **exacta** del job `lifecycle-pg` sobre PostgreSQL real en una BD scratch recreada y
  **pre-migrada a `head`** (mismos gates fail-if-skipped que CI): **132 passed in 106,55 s**
  (0 failed, 0 errors, 0 skipped). En el tag rojo, el mismo job registró `1 failed, 131 passed`.
- Baterías offline **exactas** de CI (comandos extraídos del propio YAML, para que no se
  desincronicen): job `quality` → **1626 passed**; job `python` del tag (la lista grande sin
  `apps/api-python/tests` completo) → **1634 passed**.
  `ruff check packages/py apps/api-python --config pyproject.toml` → **0** · `lint-imports` →
  **4/4 contratos KEPT**.
- El test hermético nuevo se **cablea** en los dos jobs offline (`quality` y `python` del tag): pasó
  a estar fuera de la red de CI cuando se escribió, y esa es justo la clase de test que debe correr
  en cada push, no solo en el job con PostgreSQL.
- **`mypy` no se pudo ejecutar en la máquina de verificación** (política de control de aplicaciones
  de Windows bloquea el DLL `mypyc` del binario: `ImportError: DLL load failed while importing
…__mypyc`). **No se afirma localmente**: lo cubre el step _Mypy_ del job `quality` y el job `python`
  del tag, ambos verdes en CI (abajo). El cambio de F1 es un módulo nuevo pequeño con firmas
  anotadas y sin dependencias nuevas.

### Sellado de CI (GitHub, posterior al commit)

| Gate                          | Run                                                                                                         | Resultado                                                                                                                                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Python CI del push a `main`   | [`35068139514`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068139514) (`581067c4`)                 | **success**: `quality`, `lifecycle-pg`, `grammar-discovery-pg`, `paper-forward-pg`, `auto-v2-durable-pg`                                                                                                     |
| Release-tag CI del tag movido | [`35068488972`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068488972) (`581067c4`, `v2.40.2-beta`) | **success**: `certify` ✓ con `python` (ruff/imports/**mypy**/pytest offline), `lifecycle-pg` (auth + golden restart), `dr-verify`, `a7-gate`, `playwright` (mock), `frontend`, `shared`, `spine`, `security` |

El tag `v2.40.2-beta` se **movió** (borrado + re-tag) desde `11e2cb83`, cuyo CI quedó rojo por el bug
que esta fase corrige, al commit del fix `581067c4`. **Nota declarada:** el tag apunta a un commit
cuya versión es `1.65.3-beta`, así que el nombre del tag no coincide con la versión del código que
señala; es el precio de que "el tag" siga significando "commit certificado".

## [1.65.2-beta] — V2.40.2 · Claves naturales únicas (reconciliación Prisma→Alembic + upsert atómico) — 2026-09-15

Migración nueva **`041_unique_natural_keys`** (head `040` → **`041`**): las **8 claves naturales
que Prisma declaraba y el baseline Alembic nunca creó** pasan a existir como índice único, y los
**tres `upsert` que escriben sobre ellas** resuelven el conflicto dentro de PostgreSQL. El ledger,
el settlement, el `RiskGate`, la reconciliación y el AUTO **no cambian** (cambio aditivo de DDL +
tres escrituras que pasan de `SELECT`+`INSERT` a `INSERT … ON CONFLICT`).

### El incidente que lo motiva (visible en la consola del dev server)

`GET /api/instrument-daily-opinions` quedó en **`MultipleResultsFound` permanente**:

```
instrument_strategy_top_repository.py:60  row = (await self._session.execute(stmt)).scalar_one_or_none()
sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required
```

La causa raíz es **doble**, y ninguna de las dos mitades basta sola:

1. **Sin backstop en la BD.** La migración Prisma `20260727160000_instrument_strategy_tops`
   declaró `UNIQUE (instrument_id, timeframe)`, pero el baseline Alembic (003) solo copia columnas
   y constraints de FK/`UniqueConstraint` de `tables.py`: al **no estar declarada en el modelo**,
   el índice nunca se creó. Verificado contra la BD viva: solo existían `_pkey` y la FK.
2. **Escritura no atómica.** `instrument_strategy_top_repository.upsert` era un
   _check-then-insert_ (`get()` → `INSERT`): dos escritores concurrentes ven `None` e insertan
   ambos. Resultado medido: **12 grupos duplicados / 24 filas**, con pares a 7-8 ms de distancia
   (`created_at` 19:32:20.065952 vs 19:32:20.071963), del barrido del **2026-09-14**.

Lo que lo hacía **irrecuperable** (no un 500 transitorio): `get()` usa `scalar_one_or_none()` y el
propio `upsert` empieza llamando a `get()`, así que el instrumento duplicado quedaba envenenado
para siempre.

### Inventario medido antes de tocar nada (BD de desarrollo, 2026-09-15)

De las 10 claves naturales de `schema.prisma`, **8 faltaban** en la BD. Duplicados reales:

| tabla                                                              |  filas | grupos dup | filas implicadas |
| ------------------------------------------------------------------ | -----: | ---------: | ---------------: |
| **`instrument_strategy_tops(instrument_id, timeframe)`**           |     46 |     **12** |           **24** |
| `instruments(symbol, exchange)`                                    |    243 |          0 |                0 |
| `ohlcv_bars(instrument_id, timeframe, timestamp)`                  | 95 224 |          0 |                0 |
| `instrument_daily_opinions(instrument_id, as_of_bar_date, source)` |    160 |          0 |                0 |
| `instrument_list_items(list_id, instrument_id)`                    |    112 |          0 |                0 |
| `positions(portfolio_id, instrument_id)`                           |      0 |          0 |                0 |
| `transactions(portfolio_id, idempotency_key)`                      |      0 |          0 |                0 |
| `data_snapshots(instrument_id, timeframe, data_version)`           |      0 |          0 |                0 |
| `position_policies(account_id, instrument_id)`                     |      0 |          0 |                0 |
| `instrument_narratives(instrument_id, scope)`                      |      0 |          0 |                0 |

Solo `instrument_strategy_tops` tenía duplicados ⇒ las otras 7 claves se pudieron crear **sin
borrar un solo dato**.

### Dedupe conservador (fail-closed: nunca borrar datos financieros en automático)

- **`instrument_strategy_tops`**: se deduplica conservando la fila más reciente
  (`updated_at`, `created_at`, `id`). Es una caché derivada del embudo coach: la más nueva es la
  vigente por construcción. **46 → 34 filas** en la BD de desarrollo.
- **Las otras 7: no se borra nada.** Si alguna tuviera duplicados al aplicar, la migración
  **aborta nombrando tabla, columnas y filas de muestra**. Borrar un `instruments`/`positions`
  duplicado cascadea a datos financieros, y `position_policies`/`instrument_narratives` son
  contenido de usuario: esa decisión no es de una migración. Mejor un bloqueo visible que una
  pérdida silenciosa.

### Escrituras atómicas (las tres que podían duplicar)

| repositorio                                  | clave                                     | antes                   | ahora                            |
| -------------------------------------------- | ----------------------------------------- | ----------------------- | -------------------------------- |
| `instrument_strategy_top_repository.upsert`  | `(instrument_id, timeframe)`              | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |
| `instrument_narrative_repository.upsert`     | `(instrument_id, scope)`                  | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |
| `instrument_daily_opinion_repository.upsert` | `(instrument_id, as_of_bar_date, source)` | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |

Semántica de datos **preservada**: `version` sigue incrementándose en conflicto, el `symbol` de
tops se conserva si el llamante no aporta uno (`coalesce`), y el `idempotency_key` del dictamen no
se reescribe. `instrument_daily_opinion_repository.upsert` mantiene además su `idempotency_key`
único como segunda red.

Las otras 5 tablas **no cambian de writer**: tienen guarda propia y el índice les queda de
backstop (`positions` → lock de cartera + savepoint R-8A; `position_policies` → `ValueError` del
caso de uso; `instruments` → `yahoo_symbol` único + import de usuario; `instrument_list_items` →
dedupe en memoria + delete/insert en una transacción; `data_snapshots` → upsert por `id`).

### Detalle que atrapó PostgreSQL (no el test)

El nombre de índice que declaró Prisma para el dictamen diario
(`instrument_daily_opinions_instrument_id_as_of_bar_date_source_key`) tiene **65 caracteres** y
PostgreSQL **lo habría truncado en silencio** (límite 63): el `CREATE INDEX` falló con
`IdentifierError` en el primer intento de `alembic upgrade head`. Se usa
`instrument_daily_opinions_instrument_id_asof_source_key` (55), explícito y sin truncamiento. Es
la única clave que no converge al nombre de Prisma.

### Cambio de comportamiento observable (a tener en cuenta)

- **Un `INSERT` crudo duplicado sobre cualquiera de las 8 claves ahora falla** con
  `IntegrityError` en vez de crear una fila corrupta. Es el objetivo (fail-closed), y es
  precisamente por eso que las tres escrituras atómicas **tenían que entrar en el mismo cambio**:
  el índice solo, sin arreglar el `upsert`, habría convertido el duplicado silencioso en un 500.
- **Bases con duplicados en las 7 tablas no deduplicadas bloquean el `upgrade`** con un error
  explícito. La BD de desarrollo está limpia (0 grupos en todas); la migración se aplicó sin
  incidencias.

### Tests (job `auto-v2-durable-pg`, gate fail-if-skipped `UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`)

`apps/api-python/tests/test_unique_natural_keys_pg.py` (**7 tests nuevos**):

- guardia **anti-deriva**: las 8 claves existen como índice único en `pg_indexes` (sin ella, la
  reconciliación se vuelve a perder en la siguiente tabla que alguien añada "solo en Prisma");
- **regresión del incidente**: dos `upsert` concurrentes del mismo `(instrument_id, timeframe)`
  ⇒ UNA fila, sin excepción;
- **backstop real**: un `INSERT` crudo duplicado lanza `IntegrityError` (certifica la propiedad
  fail-closed sin pasar por el repositorio);
- semántica de `version`/`symbol` conservada en el upsert de tops;
- concurrencia de narrativas y de dictamen diario ⇒ una fila por clave;
- **roundtrip de la 041 con duplicados preexistentes**: `downgrade` a `040`, se insertan a mano dos
  filas de la misma clave con distinto `updated_at`, `upgrade` a `head` ⇒ queda **la más reciente**
  y el índice vuelve a existir (reproducción exacta de las 24 filas del incidente). El test es
  consciente del **linaje** del nombre —_constraint_ del baseline `003` en una BD nueva, _índice
  plano_ de la 041 en una BD antigua—: comprueba el contrato del `downgrade` en cada caso y retira
  el backstop explícitamente para poder sembrar los duplicados (que es el escenario real: la BD en
  la que la 041 aún no había corrido).

Se actualizó `_ALEMBIC_HEAD` en `test_discovery_evidence_snapshot_pg.py` (`040` → `041`): los tests
de roundtrip existentes ya lo usan como única fuente.

### CI: los comandos plegados ejecutaban menos de lo que declaraban (sellado 2026-09-15)

Tres cosas que la certificación daba por verdes sin serlo, encontradas al revisar por qué el job
`grammar-discovery-pg` se puso rojo tras el push:

1. **`run: >` con comentarios intercalados (comentario de shell = truncación).** En un bloque
   plegado YAML cada línea es _texto del comando_, no un comentario de YAML. Un `#` intercalado en
   medio de la lista de pytest convertía **todo lo que venía después en comentario de shell**:
   - `quality` (`python-ci.yml`) ejecutaba **936 tests** y nunca llegaba a `apps/api-python/tests`;
     los ficheros nuevos de `packages/py/application/tests` (`test_auto_v2_entry.py`,
     `test_auto_investment_system.py`, `test_portfolio_decision_engine.py`,
     `test_position_manager.py`, `test_discovery_evidence.py`, …) estaban **listados pero no
     corrían** en CI. Verde falso.
   - `python` / `Pytest offline` y `lifecycle-pg` de `release-tag-ci.yml` (la certificación de
     release) tenían el mismo corte: el job de release ejecutaba 11 y 10 ficheros respectivamente de
     los ~40 declarados.
2. **`... | tee log` sin `pipefail`.** El step devolvía el exit code de `tee` (**0**): el run
   `35009780076` publicó `6 failed, 22 passed` en el job `auto-v2-durable-pg` **con el job en verde**.
   Ahora los dos steps con `tee` hacen `set -o pipefail` y el guard anti-skip exige que el log exista
   y no esté vacío (antes un log ausente hacía fallar el `grep` en mudo y el guard no guardaba nada).
3. **`downgrade` de la 041 contra índices que respaldan una constraint.** En una BD recién migrada
   el baseline `003` crea los 8 nombres como _constraint_ (copia los `UniqueConstraint` de
   `tables.py`) y `upgrade` los detecta como existentes y los omite; en una BD antigua son _índices
   planos_ creados por la 041. El `downgrade` hacía `DROP INDEX` siempre y PostgreSQL aborta con
   `DependentObjectsStillExist` cuando el índice implementa una constraint: tumbaba los roundtrips
   036→041 en CI. Ahora `downgrade` consulta `pg_constraint.conindid` y solo retira los planos.

Los comentarios de procedencia de las listas de pytest se movieron **encima** del step (donde sí son
YAML) en los tres sitios: `quality` de `python-ci.yml`, y `python`/`lifecycle-pg` de
`release-tag-ci.yml`. Verificado con un parser YAML de verdad (jobs, tokens del comando resultante,
cero tokens `#`) y comprobando que la lista de tests actual es subsecuencia exacta de la anterior
—no se perdió ni se duplicó ningún fichero.

De regalo, el job offline de release gana los `--ignore` de `test_instrument_trade_context_pg.py` y
`test_unique_natural_keys_pg.py` que ya tenía el job equivalente de `python-ci.yml` (los certifica el
job con PG; sin `--ignore` se recolectarían sin BD y skipearían en silencio).

**Lo que destapó el arreglo (y no estaba verde):** con el `pipefail` real, el job
`auto-v2-durable-pg` dejó de mentir y apareció `1 failed, 27 passed` — el roundtrip de la 041
(`assert _index_present(connection) is False` tras bajar a 040). La causa es de linaje, no de
lógica del dedupe: en CI la BD se migra desde cero, así que el baseline `003` (construido desde
`tables.py`) crea las 8 claves como **constraint** y el `downgrade` de la 041 —correctamente— no
las toca (no son suyas; `DROP INDEX` sobre ellas aborta), mientras que en la BD de desarrollo son
**índices planos** de la 041 y sí desaparecen. El test asumía un solo linaje. Ahora comprueba el
contrato en los dos (constraint ⇒ sobrevive; índice plano ⇒ desaparece) y retira el backstop
explícitamente para poder sembrar los duplicados.

Reproducido en local **por el camino de la app** (`ensure_migrated`, no el CLI: el CLI de alembic
construye el engine desde `alembic.ini` e ignora `DATABASE_URL` — en CI coinciden por casualidad),
con una BD vacía migrada a head: las 8 claves quedan como constraint, y el job
(`test_auto_v2_durable_pg` + `test_instrument_trade_context_pg` + `test_unique_natural_keys_pg` +
`test_discovery_evidence_snapshot_pg`) pasa **28 passed** en el linaje de CI y **7 passed** el
roundtrip en el linaje antiguo. También se comprobó que ninguna FK referencia las 8 claves (23 FKs
hacia esas tablas, 0 hacia la clave natural).

### Verificación

- `ruff check packages/py apps/api-python --config pyproject.toml` → **0**
- `ruff format` sobre los ficheros tocados → aplicado
- `mypy domain/market/infrastructure/application/apps-api-python` → **0 errores** (482 ficheros)
- `lint-imports` → **4/4 contratos**
- Batería offline `quality` → **2793 passed**
- `packages/py/infrastructure/tests` → **138 passed, 1 xfailed**
- Job `auto-v2-durable-pg` (4 ficheros, PG real) → **28 passed, 0 skipped**
- Migración aplicada en la BD de desarrollo: head `041`, las 8 claves presentes y
  `instrument_strategy_tops` **46 → 34 filas / 0 grupos duplicados**
- Run Python CI `35018635017` (tras el sellado): `quality` **en verde con la batería completa**
  (2m29s), `lifecycle-pg`, `paper-forward-pg` y `grammar-discovery-pg` en verde; `auto-v2-durable-pg`
  destapó el fallo de linaje del roundtrip (arriba), que el job ocultaba con el `tee` sin `pipefail`
- Run Python CI `35019474204` (tras el fix del linaje): **5/5 jobs en verde** (`quality`, `lifecycle-pg`,
  `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`). `quality` ejecuta ahora
  **1579 passed, 37 skipped** donde el step truncado corría 936 tests y nunca llegaba a
  `apps/api-python/tests`
- Lista de `release-tag-ci.yml` (la que el `#` truncaba) ejecutada en local con el comando exacto del
  workflow: job `python` / `Pytest offline` → **1624 passed**; job `lifecycle-pg` → **131 passed,
  1 failed**, y el fallo es el flaky **conocido y preexistente**
  `test_a9_scheduler_process_restart_with_open_protected_position_pg` ("el proceso debe abrir (BUY
  durable) antes del restart", con `reconciliation=UNKNOWN`/aperturas vetadas): hasta ahora **no se
  ejecutaba en ningún job de release** porque el `#` cortaba la lista ~30 ficheros antes. Queda
  declarado como deuda (no se toca en este sellado): al etiquetar `v2.40.2-beta` ese test entra por
  primera vez en la certificación de release

## [1.65.1-beta] — V2.40.1 · AUTO Safety Hardening (fail-closed real + fuentes reales) — 2026-09-15

Endurecimiento de **AUTO 2.0** sobre `v2.40-beta`: los siete P0 de la auditoría de esa versión
quedan **cerrados** en el pipeline de decisión, y las fuentes que lo alimentan (sector, liquidez,
edge, régimen) dejan de ser inyecciones de test y pasan a estar **cableadas en producción**. La
regla que gobierna todo el incremento es una sola: **la ausencia de dato no puede aprobar nada**.

Sin migración nueva (Alembic head se queda en **`040_auto_v2_durable_state`**). El ledger, el
settlement, el `RiskGate` y la reconciliación **no cambian**: toda intención sigue pasando por el
mismo _Single Decision Spine_. El flag sigue siendo `AUTO_ENGINE_SIM_V2` (**OFF por defecto**; con
OFF el comportamiento es el de `v2.39.3-beta`).

### Matriz de gates fail-closed (solo el estado explícito permite entrar)

Nuevo módulo puro `bolsa_analytics.cognitive.trade_context` con tri-estados deterministas
(`SectorResolutionStatus`, `LiquidityStatus`, `CorrelationStatus`) y `TradeContext`, que resuelve
sector declarado vs. catálogo, ADV notional y frescura de fundamentales:

| Estado                 | Cuándo                                                      | Efecto en el motor                                                             |
| ---------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `KNOWN` / `CALCULATED` | Dato presente, coherente y fresco (≤ `sector_max_age_days`) | Único estado que permite **ENTRY**                                             |
| `UNKNOWN`              | No hay dato                                                 | Veto `sector_unknown` / `liquidity_unknown`                                    |
| `CONFLICTING`          | El `memo sector=` y `instruments.sector` difieren           | Veto `sector_conflicting`                                                      |
| `STALE`                | `fetchedAt` de fundamentales supera la edad máxima          | Veto `sector_stale`                                                            |
| `UNAVAILABLE`          | Correlación no calculable con el gate activo                | Veto `correlation_unknown`                                                     |
| Posición abierta opaca | Cualquier posición abierta con sector no-`KNOWN`            | Veto `sector_exposure_unverifiable` (no se sube exposición sobre estado opaco) |

- **P0-1 · Correlación fail-open.** `_correlation_conflict()` devolvía `False` con
  `correlation is None` ⇒ "el dato no existe" se aprobaba como "sin conflicto". Ahora, con el gate
  de correlación activo, solo `CALCULATED` pasa; el resto veta con `correlation_unknown`.
- **P0-2 · Concentración sectorial sobre cajas opacas.** `build_worker_snapshot()` **no
  transmitía el `sector`** de las posiciones abiertas, así que todas caían al sentinel `<unknown>`
  de `portfolio_fit.py` y el sector del candidato se medía **solo contra sí mismo**. Ahora el
  snapshot lleva los sectores **conocidos** y una posición de sector no fiable se publica
  **deliberadamente opaca**: el motor lo detecta y veta `sector_exposure_unverifiable` en vez de
  asumir que la cartera está limpia.
- **P0-3 · Sobre-gasto de riesgo intra-tick.** `_committed_position()` no propagaba
  `risk_amount`, así que `risk_used` no subía dentro del tick y todas las candidatas del mismo tick
  se evaluaban contra la **misma** foto inicial. Ahora cada aprobación reconstruye una **foto de
  trabajo** (`_working_snapshot`) que acumula riesgo y exposición comprometidos: A → reserva → B →
  reserva → C. Invariante: 6 candidatas de riesgo 1 % con presupuesto 6 % ⇒ exactamente 6
  aprobadas, `risk_remaining == 0` y la 7ª veta por `risk_budget_exceeded`.
- **P0-4 · Edge y liquidez inventados.** `V2Tunables.default_edge = 0.9` convertía "la estrategia
  no declara edge" en "oportunidad excelente", y `_score_from_signal()` puntuaba
  `liquidity = 1.0` cuando el notional era `None`. **Breaking (en beta):** se elimina el env
  `AUTO_ENGINE_SIM_V2_DEFAULT_EDGE` y el campo `default_edge`; el edge ausente vale **0** (por
  debajo de `min_edge` ⇒ NO ENTRY) y la liquidez ausente veta. El edge **real** pasa a ser un dato
  persistido y auditable: `EdgeReportRow.edge_score` de la versión de estrategia vía
  `latest_edge_report()` (prioridad `memo edge=` > EdgeReport > nada).
- **P0-5 · Identidad de señal opcional y dedupe dependiente del orden.** `_signal_rejection()` no
  descartaba sin `signal_id` y el dedupe usaba `deduped.setdefault(...)`, de modo que el conjunto
  aprobado dependía del **orden de entrada**. Ahora `signal_id` vacío ⇒
  `SIGNAL_IDENTITY_MISSING` ⇒ NO ENTRY, y la selección usa una clave canónica
  (`canonical_candidate_key`: edge desc → versión → barra → `signal_id` → instrumento) con
  `min(...)` por instrumento: el mismo conjunto de señales produce el mismo veredicto en cualquier
  orden.
- **P0-6 · `EXIT_ONLY` no era absoluto.** `manage_position()` solo forzaba la venta total por
  régimen si `order_action == "hold"`, así que `REDUCE`/`TAKE_PROFIT`/trailing ganaban al
  exit-only. Ahora `EXIT_ONLY` tiene **precedencia absoluta**: liquida el remanente e ignora el
  resto de vías de decisión.
- **P0-7 · AUTO V2 ciego en producción.** `AutoSimRuntime` construía el worker **sin**
  `regime_source` ni `sector_source` (solo los tests los inyectaban) y no existía
  `liquidity_source` ⇒ en producción el régimen era `UNKNOWN` ⇒ exit-only ⇒ **nunca abría nada**.
  Ahora el runtime compone los lectores sobre la sesión viva del tick: régimen con
  `DiscoveryRegimeSource` + `bars_provider` sobre `SqlAlchemyOhlcvRepository`, contexto de cartera
  con `CatalogTradeContextSource` (nueva lectura en una query
  `list_trade_context_by_ids` → `sector`, `advUsd` y `fetchedAt` del catálogo) y edge con
  `EdgeReportSource` sobre `SqlAlchemyCognitiveRepository`. El override
  `AUTO_ENGINE_SIM_V2_REGIME` sigue teniendo prioridad.

**Consecuencia operativa (documentada, no un bug):** AUTO solo entrará si hay **sector + ADV
frescos** (≤ `sector_max_age_days`, 30 días por defecto) y un `EdgeReport` vigente de la versión
ACTIVE. Si los fundamentales están caducados, AUTO queda en **NO ENTRY** (no en "asumir válido").

- **Verificación.** `ruff check` **limpio** (el comando que gatea CI: `E/F/I/UP/B` sobre
  `packages/py` + `apps/api-python`) · `mypy` **0 errores** en 482
  ficheros · _import-linter_ **4/4 contratos KEPT** · batería exacta del job `quality`
  **1616 passed** · `packages/py` (application + analytics + domain) **2347 passed** · job
  `auto-v2-durable-pg` (PG real, `fail-if-skipped`) **21 passed**, incluido el test nuevo
  `test_instrument_trade_context_pg.py` (contrato del contexto de cartera: clave por `id` y por
  `symbol`, dato ausente ⇒ `None` explícito, nunca un default). Tests nuevos de los gates:
  `test_plan_v2_tick_unknown_sector_is_rejected`, `_unknown_liquidity_is_rejected`,
  `_sector_conflict_with_catalog_is_rejected`, `_stale_observation_is_rejected`,
  `_unknown_correlation_blocks_when_gate_on`,
  `_open_position_without_sector_blocks_new_entries`, `_dedupe_is_order_independent`,
  `edge_from_package_has_no_default`, `test_plan_v2_tick_without_identity_is_rejected` y la
  precedencia `EXIT_ONLY` sobre `REDUCE`/`TAKE_PROFIT`; en integración,
  `test_v2_without_trade_sources_is_fail_closed` (sin liquidez/edge/sector el worker real no abre
  nada: cascada `liquidity_unknown` → `edge_below_threshold` → `sector_unknown`).
- **CI:** el test nuevo de PG entra en el job `auto-v2-durable-pg` de `python-ci.yml` (con
  `INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED=1` y el paso _fail-if-skipped_ ya existente) y en el job
  de certificación de `release-tag-ci.yml`; en el job `quality` (sin PostgreSQL) queda
  explícitamente ignorado, como el resto de las suites PG-gated.

## [1.65.0-beta] — V2.40 · AUTO 2.0 — Investment Operating System — 2026-09-15

AUTO deja de ser un _orquestador de investigación + promoción de estrategias_ conectado a un
simulador y pasa a ser un **sistema operativo de inversión**: decide **qué** comprar, **cuándo**,
**cuánto**, **cómo gestionar la posición** y **cuándo salir**. El settlement, el ledger y la
reconciliación **no cambian**: AUTO 2.0 solo decide qué intención emitir, y todo sigue pasando por
el mismo _Single Decision Spine_ (kill switch → Simulation Gate → RiskGate → settlement SIM).

Toda la capa nueva vive detrás de un **flag de entorno**, `AUTO_ENGINE_SIM_V2=1`, **OFF por
defecto**: sin el flag, AUTO se comporta exactamente como en `v2.39.3-beta`.

- **P0 — Espina cognitiva (paquete `bolsa_analytics.cognitive`).**
  `AutoPortfolioSnapshot` (foto canónica e inmutable del libro: posiciones, stops, exposición
  bruta/neta, efectivo, régimen, `as_of`), `OpportunityRanker` (score determinista de cada
  oportunidad: edge, R:R, liquidez y penalización por concentración), `RiskAllocator` (sizing por
  presupuesto de riesgo y SL/TP derivados de ATR) y `SignalIdentity` (identidad estable de señal +
  frescura). Todos **deterministas, puros y sin red** (contrato
  `analytics-market-independence` intacto).
- **P1 — Motor de decisión de cartera.** `PortfolioDecisionEngine`: decide **ENTRY/NO-ENTRY** a nivel
  de cartera, con vetos **fail-closed** y motivo registrado (sin régimen operable, `position_exists`,
  presupuesto de riesgo agotado, correlación, stop inválido, `min_edge`/`min_risk_reward`…). Publica
  un `TradePlan` (el contrato del camino caliente) con stop estructural, objetivos y dirección, y
  propaga el **sector** de la decisión.
- **P2 — Gestión de posición por estado.** `PositionState` + `ExitPlan` + `PositionDecision` vía
  `PositionManager`: stop estructural, T1/T2 (parciales), trailing, exit-only por régimen y cierre
  de sesión — la gestión deja de depender de una `ProtectionConfig` global y pasa a ser **por
  operación**.
- **P3 — Regime gate direccional.** `MarketRegimeGate` veta entradas por régimen y **dirección**
  (un `BULL_TREND` no autoriza cortos). `DiscoveryRegimeSource` conecta el régimen operativo real al
  clasificador determinista de barras (`discovery_market_regime_v0`), con `fail-closed` (régimen
  desconocido ⇒ `UNKNOWN` ⇒ **exit-only**, nunca entradas a ciegas).
- **P4 — Durabilidad del estado V2 (migración nueva, head `040_auto_v2_durable_state`).** Un crash ya
  no degrada la operativa:
  - `sim_auto_positions.position_state` (JSONB): el **plan operativo** de cada posición se persiste
    en cada cambio de cantidad y se **rehidrata exacto** al readoptar (`position_state_from_dict`) —
    mismo stop, mismos objetivos, mismas parciales — en vez de reconstruirlo por ATR. Sin plan
    durable (espejo legado) el fallback reconstruido se marca `adopted` (auditoría explícita).
  - `sim_consumed_signals`: las **señales consumidas por barra** son durables, de modo que tras un
    reinicio el motor no re-emite la MISMA oportunidad sobre la MISMA barra (anti-_churn_: stop-out
    y re-entrada inmediata en la misma vela). La tabla se poda a la barra corriente.
  - `SimDurableUnitOfWork` incorpora el store de señales: el espejo del fill y su dedupe o quedan
    juntos, o no queda ninguno.
- **Cableado en el worker.** `AutoSimulationWorker` incorpora el pipeline (`auto_v2_entry.py`):
  snapshot → ranker → decisión → `TradePlan` → adaptador `trade_plan_to_decision_package` → spine.
  El readopt durable, la marca de señal consumida (solo tras fill confirmado) y la poda de barras
  viejas viven aquí.
- **Verificación.** `ruff` / `ruff format` limpios · `mypy` sin incidencias · `packages/py/application/tests`
  **1546 passed** · `packages/py/analytics` + `infrastructure` **816 passed, 1 xfailed** · suites
  V2/worker/AUTO/PG/migraciones **82 passed** (incluye el roundtrip de la 040 y el reinicio real
  sobre PostgreSQL). Tests nuevos: `test_auto_v2_entry.py`, `test_auto_investment_system.py`,
  `test_portfolio_decision_engine.py`, `test_position_manager.py`,
  `test_active_strategy_runtime_state.py`, `test_sim_durable_v2_state.py`,
  `test_auto_portfolio_snapshot.py`, `test_opportunity_ranker.py`, `test_risk_allocator.py`,
  `test_signal_and_regime.py`, `test_auto_v2_worker_integration.py`, `test_auto_v2_durable_pg.py`.
  Los herméticos entran en la batería offline de CI y el de PG real en el job nuevo
  `auto-v2-durable-pg` con **gate fail-if-skipped**.
- **CI (verificado antes del tag):** `release-tag-ci` **GREEN** — run `34972246205` (10/10 jobs
  requeridos verdes + `certify` aggregate `success`; único skip: `playwright` integrado, opt-in) ·
  `python-ci` **GREEN** — run `34972246101` con el job nuevo `auto-v2-durable-pg` en `success`.

## [1.64.3-beta] — V2.39.3 · Cierre P1/N1 (lock de cuenta) + P2/N2 (secuenciador forzado) + fix `totalSamples` — 2026-09-15

Tercera pasada de la auditoría interna, esta vez sobre `v2.39.2-beta`. Cierra los dos hallazgos
del **secuenciador del ledger** (AUDITORIA 1), el bug de `totalSamples` en `discovery_evidence.py`
(AUDITORIA 2) y confirma un detalle del script de limpieza que **no** es fallo. Alembic head sigue
en **`039_research_trials_regime`** (sin migraciones nuevas).

- **P1/N1 — `next_executed_at` es por cuenta pero el lock que lo protegía era de cartera.**
  `next_executed_at(account_id)` lee `MAX(executed_at)` **por cuenta**, pero el lock era
  `with_for_update` sobre `PortfolioRow` (por `legacy_portfolio_id`). Dos carteras de la **misma
  cuenta** no comparten `legacy_portfolio_id`, así que sus escritores **no se excluyen entre sí** y
  pueden leer el mismo `MAX(executed_at)` antes del commit del otro, emitiendo asientos con
  **idéntico instante** (el desempate por `id`, UUID v4 aleatorio, no rescata el orden real).
  **Fix**: nuevo `SqlAlchemyAccountRepository.lock_account(account_id)` (`SELECT ... FOR UPDATE`
  sobre `investment_accounts`), cableado como lock externo antes del lock de cartera en `trade.py`,
  `cash.py` (deposit + withdraw) y `custody.py` (orden determinista **cuenta → cartera**). El
  docstring de `next_executed_at` pasa a exigir el lock de **cuenta**.
- **P2/N2 — `append_*` aceptaba `executed_at` externo.** `append_trade`, `append_fee`,
  `append_custody_fee` y `append_cash_movement` aceptaban `executed_at: datetime | None = None` con
  fallback `executed_at or now`, permitiendo saltarse el secuenciador. **Fix**: se elimina el
  parámetro y cada método obtiene internamente `await self.next_executed_at(account_id)`; la
  secuencia es ahora obligatoria por infraestructura, no por disciplina del caller. En `trade.py` se
  eliminan `_ledger_ordering`/`_FEE_ORDER_GAP` y la llamada manual al secuenciador (trade → X,
  fee → X+1 µs natural).
- **Auditoría 2 — `totalSamples` inflado.** `compute_lane_weights()` y el payload `"totalSamples"`
  sumaban `sample_sizes.values()` sin filtrar, contando familias descartadas por `min_samples`.
  **Fix**: nuevo `_effective_total_samples(family_weights, sample_sizes)` que suma solo las familias
  con peso, usado en ambos sitios para unificar la puerta de decisión con lo publicado al operador.
- **Test de concurrencia multi-portfolio (N3).** Nuevo
  `packages/py/infrastructure/tests/chaos/test_multi_portfolio_ledger_sequence.py`: dos carteras de
  la misma cuenta, ráfagas concurrentes, `executed_at` estrictamente creciente y cadena
  `balance_after` encadenada. Se valida localmente contra `bolsa_v1_chaos` (los chaos no entran en
  CI, deuda anotada).
- **Detalle del script de limpieza (no es fallo).** `custody_obligation` (005) y
  `custody_obligations` (006) **coexisten** legítimamente: la 006 no borra la 005. La lista
  `ACCOUNT_CHILD_TABLES` es correcta tal cual.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `mypy` full-tree
  **Success (477 ficheros)** · `import-linter` **4 contratos OK** · batería offline del job
  `quality` **en verde** · chaos `test_multi_portfolio_ledger_sequence` **passed** contra PG real.

## [1.64.0-beta] — V2.39 · Régimen de mercado por trial (incremento 4) — 2026-09-11

Cuarto incremento de **Strategy Intelligence**: la evidencia gana la segunda dimensión de
granularidad que V2.38 dejó apuntada, el **régimen de mercado** bajo el que se evaluó cada trial.
Se deriva de las **propias barras del trial** (as-of, determinista y versionado), se persiste en una
columna nueva nullable `research_trials.regime` (migración aditiva) y se publica como dimensión
observable y agregable. **No** entra en el reparto de cupos ni en la clave `familia|region`.

- **Por qué un régimen derivado de barras y no el macro cognitivo.** `bolsa_analytics.cognitive.market_state`
  se alimenta de `fetch_macro_snapshot_dict`, que usa valores _live_ de Yahoo (`date.today()`,
  `closes[-1]`) y **no persiste serie histórica**: no es calculable as-of. Etiquetar un trial pasado
  con el régimen de hoy sería inventar dato — exactamente lo que V2.38 evitó. El régimen de barras, en
  cambio, es derivable en el punto del LAB que ya tiene las barras del trial.
- **Núcleo determinista y puro.** Nuevo módulo `bolsa_application.discovery_market_regime`
  (`math_version=discovery_market_regime_v0`): un solo eje con etiquetas `trend_up` / `trend_down` /
  `range` / `high_vol`. Tendencia por pendiente normalizada por volatilidad; volatilidad por rango
  relativo medio (high-low-close). `high_vol` tiene prioridad (en mercado revuelto la dirección es
  poco fiable). **Fail-closed**: menos de `MIN_REGIME_BARS`, NaN/inf, high-low ausentes o ventana
  degenerada ⇒ sin régimen (`""`); nunca se aproxima. Sin LLM, sin red, sin BD.
- **Persistencia por trial.** Migración aditiva **`039_research_trials_regime`** (columna
  `regime String NULL`, sin backfill, `downgrade()` completo): los trials históricos quedan `NULL`.
  Write-path completo: `OptimizeSmaGridResult.regime` se calcula en los 4 constructores del dataclass
  (con la ventana real de cada camino) y `optimization_runs` lo persiste (entidad + Protocol + repo
  SQL + `_regime_for_trial` fail-closed con fallback a `params`/`blocks`).
- **Agregación y evidencia.** `family_evidence_summary` y `posterior_evidence_summary` amplían su
  `GROUP BY` con `regime`; el snapshot publica el desglose aditivo **`regimeGranularity`** (fuera del
  `snapshot_hash`, dentro del `evidence_fingerprint`) y la evidencia posterior añade `regimeCounts`.
  **La clave de granularidad `familia|region` NO cambia**: el régimen es una **dimensión paralela**;
  meterlo en la clave habría roto `_collapse_regions` y la compatibilidad V2.37/V2.38.
- **Rollout reversible.** Nuevo flag **`AUTO_ORCHESTRATOR_ADAPTIVE_REGIME`** (OFF por defecto). Con
  OFF el LAB **no calcula ni persiste régimen** (`emit_regime=False`, fijado por el composition root,
  no por la candidata): los trials quedan a `NULL` y la evidencia es **idéntica** a la de V2.38.1.
  La lección del P2-01 de V2.38.1 se aplica aquí de raíz: la equivalencia se garantiza por la vía del
  write-path, no por un colapso posterior.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  H1/H2; long-only; gates CPCV/PBO/DSR/WFE/OOS sin relajar; anti-explosión `1784` intacto; la clave
  compuesta `familia|region` y `_collapse_regions` **sin modificar**; con el flag OFF, comportamiento
  idéntico a V2.38.1. Alembic head pasa a **`039_research_trials_regime`**.
- **Verificación (local)**: `ruff` con invocación CI exacta (`--config pyproject.toml`) **All checks
  passed** · `mypy` Success en los módulos tocados · suites V2.39 offline **212 passed** · PG
  `test_discovery_evidence_snapshot_pg.py` **18 passed** (migración 039 upgradable/downgradable +
  agregación por régimen + roundtrip).

## [1.64.1-beta] — V2.39.1 · Hotfix de la auditoría interna de V2.39 — 2026-09-13

Hotfix sobre `1.64.0-beta` (auditoría interna previa a la externa). Cierra dos **P2** de Discovery, un
**P1** de arranque, un **P1** de integridad del ledger y la deuda de hermetismo de los tests PG que
hacía el CI no determinista. **Sin cambios de semántica funcional** ni de migraciones (Alembic head
sigue en **`039_research_trials_regime`**).

- **P2-01 — La gramática no consumía su cupo completo (A14).** El orquestador repartía el presupuesto
  entre planes, pero `grammar_variants_for_plan` se invocaba siempre con el mismo eje, así que un plan
  con varios bloques opcionales **no rotaba la variante** y el cupo del allocator quedaba
  subconsumido. **Fix**: `grammar_emission_cap` se calcula sobre el cupo real y la llamada pasa
  `axis_index=emitted_for_grammar`, de modo que cada emisión avanza de eje. Se reordena además la
  enumeración para que el **trigger varíe antes que el exit** (antes el exit agotaba el presupuesto de
  variación y el trigger quedaba con una sola forma).
- **P2 — La evidencia fusionada por clave compuesta perdía y sesgaba datos.** `compute_family_weights`
  agregaba las filas por `familia|region` con un `GROUP BY` que **descartaba en silencio** las filas
  con la misma clave procedentes de regímenes distintos, y ponderaba `avgScore` por número de filas en
  vez de por muestra. **Fix**: nuevo `_merge_aggregates_by_key` que fusiona por clave compuesta con
  semántica explícita — contadores por suma, ratios por **media ponderada por cobertura**,
  `bestScore` por máximo y `kConsumed` por suma. El productor (`family_evidence_summary`) expone
  `is_score_n` para poder ponderar `avgScore` por muestra real. `evidence_fingerprint` sigue
  detectando reescrituras retrospectivas.
- **P1 — El arranque de la API moría con `MultipleResultsFound`.** `_load_default_scope` /
  `_ensure_default_account` filtraban solo por `is_default` con `scalar_one_or_none()`: en cuanto
  existía **otra** cuenta por defecto (otro tenant, o residuo de tests de integración) el bootstrap
  reventaba. **Fix**: ambas consultas filtran por `owner_principal()` (el tenant propietario), que es
  la semántica correcta en un modelo multi-tenant. Regresión:
  `test_migration_survives_foreign_tenant_default_account`.
- **P1 — Perfiles de inversor invisibles (404) al abrir cuenta.** `EnsureDefaultInvestorProfile` /
  `EnsureAccountInvestorProfile` creaban el perfil **sin `user_id`**, así que el control de acceso
  owner-scoped no lo encontraba y la ruta devolvía 404 sobre un recurso propio. **Fix**: se propaga
  `user_id` (el principal de la request) por las tres ramas de creación.
- **P1 — Mandatos con instrumentos huérfanos tumbaban el `PUT`.** Un `instrument_id` inexistente en el
  payload provocaba `ForeignKeyViolation`. **Fix**: `sync_account` valida los `instrument_id` contra el
  catálogo y **descarta** las tenures y links huérfanos en vez de estampar la transacción.
  Regresión: `test_mandate_sync_orphan_instrument.py`.
- **P1 — El worker de custodia abortaba el job entero por una sola cuenta rota.** `RunCustodyJob`
  procesaba las cuentas en serie sin aislar fallos: una cuenta sin cartera legacy (`ValueError`)
  mataba el lote completo. **Fix**: cada cuenta se procesa en su propio `try/except`, con rollback
  best-effort, marcado como `skipped` con motivo en el resumen y continuación del job. Regresión:
  `test_job_cuenta_rota_no_aborta_el_resto`.
- **P2 — El replay idempotente de trade pasaba por el gate de apertura (403 → 200).** `ExecuteTrade`
  evaluaba el gate **antes** de comprobar la `idempotencyKey`: un reenvío legítimo quedaba vetado con
  403 en vez de devolver el 200 original, y un payload divergente daba 403 en vez de 409. **Fix**: la
  comprobación de idempotencia ocurre primero — replay con payload idéntico ⇒ 200; payload divergente
  ⇒ `IdempotencyKeyReused` (409). Regresiones en `test_execute_gated_portfolio_trade.py`.
- **P2 — El ledger perdía el orden real bajo concurrencia.** `append_trade` y `append_fee` tomaban
  cada uno su propio `datetime.now(UTC)`: bajo concurrencia caían en el mismo microsegundo y el
  consumidor que ordena por `(executed_at, id)` desempataba por un **`id` aleatorio**, intercalando la
  fee antes del trade y rompiendo `balance_after[n] == balance_after[n-1] + amount[n]`. El cash era
  correcto, pero el ledger dejaba de ser **reproducible y auditable**. **Fix**: ambos asientos derivan
  del `executed_at` de la transacción (fijado bajo `with_for_update`), con el trade 1 µs antes de la
  fee para que el orden sea el de aplicación real. Verificado por mutación.
- **Hermetismo de tests PG (sin esto el CI era no determinista).** Varias suites dejaban residuos en
  la BD compartida y otras no eran inmunes a ellos: cuentas `AUTO-*`/`lc-*`, barras OHLCV sintéticas y
  filas `live_orders` `UNKNOWN`. Como `claim_unknown_batch` es una barrida **global** (por diseño: un
  worker de recuperación atiende cualquier cuenta), un residuo de una pasada hacía fallar el test de
  concurrencia de otra. **Fix**: fixture `autouse` de limpieza por sesión en `conftest.py`, purga
  explícita en las suites que commitean filas, purga de las `UNKNOWN` de prueba antes de sembrar, y
  limpieza de las suites que crean cuentas. Además se corrigieron 4 hallazgos de `ruff` (orden de
  imports y un `l` ambiguo) que habrían dejado el job `quality` en rojo.
- **Estabilidad de la certificación por proceso del scheduler (A9).** Los dos tests que levantan el
  **proceso real** `scheduler_worker` esperaban actividad con un plazo fijo de 90 s _sin comprobar si
  el subproceso seguía vivo_: bajo un job completo (miles de tests, máquina cargada) el arranque
  —import de la app + `database_bootstrap` con advisory lock + primer tick— podía excederlo, y el
  fallo se reportaba como «0 eventos» sin diagnóstico. **Fix**: la espera es por **progreso real** con
  un margen de arranque explícito (`_STARTUP_GRACE_S`) y **falla al instante con el log del
  subproceso** si el proceso muere, en vez de agotar el plazo a ciegas. Se documenta el hallazgo de que
  `_reconcile_before_trusting` marca `UNKNOWN` (y por tanto **veta aperturas**) cuando el lector
  canónico falla o devuelve `None`, que es la vía por la que el día AUTO podía quedar sin fills.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `import-linter`
  (4 contratos) OK · `mypy` full-tree **Success, 0 errores en 477 ficheros** · job `quality` del CI
  reproducido **2589 passed** · flaky de concurrencia de `live_orders` **10/10** en verde ·
  `test_a9_scheduler_process_pg_zero_human` **6/6** aislado y **3/3** junto al resto de PG.

## [1.64.2-beta] — V2.39.2 · Cierre de flaky: el ledger se secuencia por estado, no por reloj — 2026-09-13

Segunda pasada de la auditoría interna, centrada en los **flaky** que quedaban antes de la auditoría
externa. Tres causas distintas, una de ellas un **bug real de producción** que la primera pasada no
alcanzó a cerrar. Alembic head sigue en **`039_research_trials_regime`** (sin migraciones nuevas).

- **P1 — El `executed_at` del ledger se derivaba del reloj de pared.** La primera pasada (V2.39.1)
  hizo que trade y fee compartieran el instante de la **transacción**, pero ese instante se sigue
  tomando con `datetime.now(UTC)`. Bajo concurrencia eso **no ordena**: dos transacciones serializadas
  por el `with_for_update` de la cartera pueden leer el reloj en orden **invertido** respecto al de
  commit, y el consumidor que ordena por `(executed_at, id)` reconstruye una secuencia falsa (el
  desempate por `id` es un UUID v4 **aleatorio**, no rescata el orden real) → la cadena
  `balance_after[n] == balance_after[n-1] + amount[n]` se rompe de forma intermitente. Capturado con
  instrumentación forense: el salto real entre dos asientos consecutivos **no coincidía con su
  `amount`**, prueba de que el asiento se había aplicado en otra posición del orden.
  **Fix — secuenciador por cuenta:** nuevo `SqlAlchemyLedgerRepository.next_executed_at(account_id)`,
  que devuelve `max(now, último_executed_at_de_la_cuenta + 1 µs)`, leído en la **misma transacción**
  que el llamador (que ya retiene el lock de la cartera). El instante se deriva del **estado
  persistido**, no del reloj, así que es **estrictamente creciente con el orden de aplicación**. Se
  conecta en las cuatro rutas que escriben asientos: trade (`ExecuteTrade`), custodia
  (`ApplyCustodyFees`, que además arrastraba el bug simétrico de calcular `balance_after` desde un
  `get_summary` **pre-lock**) y depósito/retiro (`cash.py`). El paso de 1 µs convierte el desempate
  por `id` en irrelevante: dos asientos nunca comparten instante y el orden es determinista.
- **P1 — `ApplyCustodyFees` calculaba `balance_after` con el cash PRE-lock.** Mismo patrón que
  `ExecuteTrade` ya había corregido (EXEC-B-CONC), pero la custodia nunca lo recibió: leía
  `get_summary().portfolio.cash` **antes** de `deduct_cash` (que es quien toma el `with_for_update`) y
  escribía ese balance desfasado. **Fix**: el `balance_after` se toma del cash **POST-lock** que ya
  devolvía `deduct_cash`, en las dos ramas (liquidación de PENDING y periodo actual).
- **Flaky de entorno — `pool_size=64` agotaba las conexiones del PostgreSQL local.** El escenario de
  estrés abría un pool de 64 conexiones por test; con `max_connections=100` y la convivencia con otros
  engines (otras suites, workers, API) el servidor respondía `FATAL: sorry, too many clients already`
  y los tests fallaban **en ráfaga** con un error de entorno que **enmascaraba el veredicto real**.
  **Fix**: `pool_size=24`. El escenario serializa igual sobre la fila de cartera, así que el pool
  grande no aceleraba nada y sí monopolizaba el servidor. Resultado: **0/10 fallos y ~38 s** por
  pasada (antes ~45 s con fallos intermitentes).
- **Honestidad del test `test_two_workers_claim_disjoint_unknown_batch`.** Hacía `asyncio.gather` de
  dos `claim_unknown_batch` con **rollback inmediato** de cada uno y exigía que fueran disjuntos: eso
  **no certificaba** la exclusión mutua, la refutaba — en PostgreSQL real el segundo `SELECT ... FOR
UPDATE SKIP LOCKED` puede correr **después** del rollback del primero y ver las filas liberadas (el
  resultado dependía del entrelazado del event loop). La propiedad real y determinista que garantiza
  el lease es «**mientras el lease está vivo y no expirado, otro worker no reclama la misma fila**».
  El test ahora retiene las dos transacciones abiertas, afirma que el segundo worker obtiene **vacío**
  y, tras liberar el primero, comprueba el **relevo** cubriendo el lote completo.
- **Certificación por proceso del scheduler (A9): el bucle de vigilancia antirrecompra agotaba el
  presupuesto siempre.** Tras el crash+restart, el test esperaba «a que ocurra una re-compra» para
  fallar; pero el camino **correcto** es que nunca ocurra, así que el bucle agotaba el plazo completo
  en cada pasada (de ahí los ~518 s y, con el margen recortado, fallos intermitentes de «no abrió
  posición»). **Fix**: ese sondeo usa un plazo **corto y acotado** (`_RESTART_WATCH_S = 20 s`) —una
  re-compra aparecería en los primeros ticks, no al final— y los tres bucles comprueban `proc.poll()`
  para **fallar al instante con el log del subproceso** si el worker muere, en vez de esperar a
  ciegas. Pasada: **~28 s** (desde ~518 s) y **8/8 en verde**.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `mypy` sobre las
  fuentes tocadas **Success (272 ficheros)** · `import-linter` **4 contratos OK** · suite de aplicación
  **1468 passed** · infraestructura **137 passed, 1 xfailed** · recovery + idempotencia **8 passed** ·
  chaos de ledger/concurrencia **10/10 pasadas en verde (0 fallos)** · A9 **8/8 (~28 s)** · regresión
  del secuenciador verificada **por mutación** (revertir el fix hace fallar el test nuevo) ·
  `test_two_workers_claim_disjoint_unknown_batch` **5/5** estable.
- **Nota de entorno (no del código).** Los flaky restantes se reprodujeron **solo** bajo ejecuciones
  back-to-back masivas: el PostgreSQL local agotaba conexiones (`FATAL: sorry, too many clients
already`) y los tests que dependen del arranque de un subproceso agotaban su plazo. Con el pool de
  los chaos acotado a 24 y la BD en reposo, **20/20 pasadas del chaos y 8/8 del A9 fueron verdes**. El
  CI (máquina limpia, un job) no reproduce esa saturación, pero se deja anotado para no confundirla
  con una regresión de código.

### Tercera pasada — la gramática de Discovery emitía planes inoperables

Al correr la batería exacta del CI apareció un fallo que **no** era flaky: la certificación A14
(`test_a14_grammar_discovery_pg`) fallaba con _«ningún plan gramatical produjo evidencia CPCV/PBO
real»_. La investigación cerró una cadena de **tres** causas, todas medidas, y una de ellas convertía
el `P2-01` anterior en un colapso silencioso del grid.

- **P1 — El 100 % de los planes gramaticales producía menos de 2 columnas operables.** El PBO CSCV
  exige `len(candidates) >= 2`; con **1 solo trial** (o 0) `build_lab_pbo_summary` devuelve `None` y
  los gates `robustness`/`walk_forward` quedan **sin evidencia** sobre candidatas gramaticales, en
  silencio. Medido sobre los 1784 planes: **1184 con 1 columna y 600 con 0** — ninguno alcanzaba 2.
  El LAB registraba «0 trials» y el orquestador real pasa exactamente la misma ruta, así que el
  defecto era **de producción**, no del test.
- **Causa 1 — el trigger y el filtro de tendencia Donchian eran matemáticamente inalcanzables.** El
  canal `dc:upper` es `max(high)` de la ventana **incluyendo la barra actual**, así que
  `close > upper` es imposible: el máximo de la ventana es siempre `≥ high[i] ≥ close[i]`. Medido:
  **0 disparos incluso en una serie estrictamente creciente**. **Fix**: trigger y trend filter usan la
  banda **media** (`dc:mid`), igual que el preset `donchian_breakout` de producción (que sí opera:
  381/400 barras con `close > mid`). La banda `upper` de la gramática quedaba inerte.
- **Causa 2 — el eje de permutación podía romper el par trigger/exit homónimo.** Al rotar el eje sobre
  el trigger (lo introdujo `P2-01`), el `exit_ema10_cross_ema50` (bajista) seguía mirando las **mismas
  EMAs** que el trigger nuevo: un cruce alcista y otro bajista de las mismas series **no coinciden
  nunca**, así que el trigger quedaba inalcanzable. **Fix**: el exit homónimo se permuta **con** el
  trigger, por par (`_AXIAL_TRIGGER_EXIT_PAIRS`), y el eje rota **preferentemente** sobre los bloques
  opcionales (regime/trend/momentum), cayendo en los axiales solo si el plan no tiene ninguno. Se
  conserva la rotación de ejes que arreglaba el `P2-01`.
- **Causa 3 — incompatibilidad estructural entre bloques, no vetada.** `trigger_ema10_cross_ema50` +
  `trend_ema20_gt_ema50`: el cruce de EMA10 sobre EMA50 es **necesariamente anterior** a que EMA20
  confirme por encima de EMA50, y los gates del plan se exigen **simultáneamente**. Medido: 210 barras
  cumplen ambas condiciones, **0 cruces**. **Fix**: dos vetos de inanición deterministas y fail-closed
  (`_mutually_unreachable_trigger_exit`, `_conjunctive_ema_starvation`) sacan esas combinaciones de la
  enumeración en vez de emitirlas sin evidencia posible. 1684 planes, **0 degenerados**.
- **El test de integración A14 sembraba una serie donde sus propios disparadores no existían.** La
  rampa descendente dejaba `close > sma200` y `close > max(high, n)` en **0 barras**. **Fix**: la serie
  ahora son ciclos con tramo alcista **más largo que el período del canal** (60 > 40) y retrocesos que
  cruzan las EMAs. El test pasa de **fallar a los 146 s** a pasar en **5,8 s**.
- **Regresión**: dos tests nuevos en `test_discovery_grammar.py` exigen **≥2 columnas operables por
  plan** sobre la serie de integración y que el trigger Donchian sea alcanzable.

### Tercera pasada — dos fallos que solo aparecían en la batería completa

- **P1 (producto) — una lista con instrumentos no se podía borrar.** `SqlAlchemyListRepository.delete`
  borraba la fila de `instrument_lists` **sin vaciar antes** `instrument_list_items`; la FK `list_id`
  no es `ON DELETE CASCADE`, así que cualquier lista **con** instrumentos violaba la integridad
  referencial y `DELETE /api/lists/{id}` devolvía **500 en vez de 204**. **Fix**: los items se borran
  en la misma transacción justo antes que la lista. Regresión:
  `test_delete_list_with_items_does_not_violate_fk`.
- **P2 (hermeticidad) — la tabla `lifecycle_outbox` envenenaba suites entre sí.** `claim_batch` es una
  barrida **global** (FIFO por posición, sin filtrar por posición) con sanitizado de huérfanas;
  `test_financial_integrity_pg` dejaba una cabeza FIFO `dead` sin limpieza y otras suites filas
  `pending`/`processing`, de modo que el worker de `test_lifecycle_outbox_worker_pg` reclamaba filas
  **ajenas** y el hook inyectado (`on_before_apply_commit`) consumía su **único** disparo antes de que
  la fila propia pasara a `processing` → _«status=applied expected=processing»_. **Fix**: el test de
  integridad limpia su fila en `finally` y el fichero del worker aísla la tabla (purga
  `pending`/`processing` antes y después de cada test). **Verificado**: `apps/api-python/tests` +
  `packages/py/infrastructure/tests` pasan **521 en dos pasadas consecutivas** (antes 2 failed en cada
  intento de la batería completa).
- **Verificación (local) de la tercera pasada**: `ruff` **All checks passed** · `mypy` **Success (477
  ficheros)** · batería completa del job _quality_ **1306 passed, 0 failed** · gramática + A14
  **40 passed**.

## [1.63.1-beta] — V2.38.1 · Hotfix de los 2 P2 de la auditoría de V2.38 — 2026-09-11

Hotfix de la **auditoría externa de `v2.38-beta`** (commit `41b96a41`, CI GREEN). Cierra dos P2
conceptuales sin cambiar la semántica funcional del incremento 3.

- **P2-01 — La equivalencia "byte-idéntica a V2.37 con el flag OFF" no se cumplía.** El write-path
  etiquetaba `discovery_param_region` **siempre, sin consultar el flag**; con OFF el snapshot contenía
  regiones y `_collapse_regions` colapsaba con `max(peso)` en vez de re-derivar la fuerza sobre el
  agregado familiar (el snapshot solo persiste `family_weights`/`sample_sizes`, así que el colapso no
  puede recomputarla). Divergencia medida: `0.747` (V2.37) vs `0.803` (colapsado) ≈ **7,4 %**.
  **Fix**: el motor recibe la decisión como dependencia inyectada
  (`discover_for_instrument_with_summary(..., emit_param_region: bool = True)`) y el worker pasa
  `adaptive_param_region_enabled()`. Con OFF **no se genera región**, la evidencia es idéntica a la de
  V2.37 y el colapso es un no-op: **equivalencia real, no aproximada**. `_collapse_regions` se
  conserva, pero reencuadrado como puente para **evidencia histórica** ya persistida con región
  (transición ON→OFF), con su docstring corregido para no prometer equivalencia numérica.
- **P2-02 — `evidence_fingerprint` no ordenaba por clave compuesta.** `compute_family_weights` ordenaba
  por `(presetKey, paramRegion)` pero el fingerprint solo por `presetKey`; con varias regiones de una
  misma familia el orden quedaba a merced del orden de entrada (`sorted` estable ⇒ fragilidad latente
  en un valor que es identidad del dataset). **Fix**: orden canónico por clave compuesta + tests de
  orden adverso (familias y regiones barajadas producen el mismo fingerprint).
- **P3 — Versionado de la search policy.** `MATH_VERSION_SEARCH_POLICY_V0` tenía el valor
  `"discovery_search_policy_v1"` (reescrito in-place), de modo que una política histórica no se
  distinguía de la nueva. **Fix**: coexisten `_V0` = `"discovery_search_policy_v0"` y `_V1` =
  `"discovery_search_policy_v1"`, con alias `MATH_VERSION_SEARCH_POLICY` para la vigente.
- **P3 — Test mal nombrado.** `test_granularity_does_not_change_snapshot_hash_vs_plain_family` era
  tautológico; se documenta y se añade la comprobación real (recalcular `snapshot_hash` sobre los
  componentes declarados reproduce el hash almacenado ⇒ el payload/granularidad no participa).
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  H1/H2; gates sin relajar; anti-explosión `1784` intacto; Alembic head sigue en
  `038_research_trials_param_region` (el hotfix no añade migración).
- **Verificación (local)**: `ruff` con invocación CI exacta (`--config pyproject.toml`) **All checks
  passed** · `mypy` Success en los módulos tocados · offline **1497 passed** (suites relevantes).

## [1.63.0-beta] — V2.38 · Granularidad por región de parámetros (incremento 3) — 2026-09-11

Tercer incremento de **Strategy Intelligence**: la evidencia adaptativa deja de agregarse solo por
familia H0 (`preset_key`) y pasa a granularidad por **región de parámetros**, con bucket determinista
y versionado, columna nueva nullable en `research_trials` (migración aditiva) y consumo en la search
policy. Régimen e **instrument class quedan explícitamente fuera**: no existen hoy como dato
persistido (ver más abajo).

- **Núcleo determinista y puro.** Nuevo módulo `bolsa_application.discovery_param_region`
  (`math_version=discovery_param_region_v0`): `param_region_for_point` deriva una clave estable del
  punto dentro del grid de su familia (ordinal en el producto cartesiano determinista + hash corto de
  los valores), `compose_granularity_key`/`split_granularity_key` definen la clave compuesta canónica
  `familia` o `familia|region`. **Fail-closed**: un punto fuera del grid no recibe región (`""`), no se
  aproxima. Sin LLM, sin red, sin BD.
- **Persistencia por trial.** Migración aditiva **`038_research_trials_param_region`** (columna
  `param_region String NULL`, sin backfill, `downgrade()` completo): los trials históricos quedan
  `NULL` (no se inventa su región). Write-path completo: el motor etiqueta la candidata
  (`discovery_param_region`), el runner la propaga (`_REGION_KEYS`, antes se descartaba) y
  `optimization_runs` la persiste (`ResearchTrial.param_region`, entidad + Protocol + repo SQL).
- **Agregación por clave compuesta.** `family_evidence_summary` y `posterior_evidence_summary` agrupan
  por `preset_key + param_region` y devuelven `paramRegion`; el job batch mergea por clave compuesta.
  **Retrocompatible**: si todas las regiones son `NULL`, la clave colapsa a la familia y el
  `snapshot_hash` es **idéntico** al de V2.37.
- **Snapshot y fingerprint.** `compute_family_weights` mintea la clave compuesta; `familyGranularity`
  deja de estar vacío y publica `{family, paramRegion}` reales (aditivo, **fuera del `snapshot_hash`**,
  dentro de `evidence_fingerprint`).
- **Search policy y motor.** `SearchPolicy` sube a `discovery_search_policy_v1` e incluye
  `granularityKeyVersion` en su hash (la fórmula de reparto no cambia: ya era agnóstica a la clave).
  El motor resuelve la clave compuesta y **filtra `param_points()` a la región** indicada; clave
  desconocida o región inexistente ⇒ no emite (fail-closed).
- **Rollout** — Flag nuevo `AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION` **OFF por defecto**: con OFF
  el write-path no genera región y el sistema es **equivalente a V2.37** (ver V2.38.1/P2-01: el
  colapso `_collapse_regions` solo normaliza evidencia histórica y no es equivalencia numérica).
  Observabilidad aditiva: `DiscoveryEmissionSummary` gana `adaptive_region_emissions`/
  `adaptive_region_count`; los contadores de ciclo/proceso suman `adaptive_region_emissions` y los
  logs reportan `adaptive_regions=N/M`.
- **Por qué NO régimen ni clase de instrumento.** Régimen solo existe como clasificación en memoria en
  la capa cognitiva (`bolsa_analytics.cognitive.market_state`) y jamás se persiste; `instruments.type`
  es un enum con un único valor (`stock`) y `sector` es texto libre sin poblar. Incorporarlos exige
  primero persistirlos como fuente de verdad; la clave compuesta está diseñada para admitir nuevos
  componentes sin romper el contrato.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  long-only; H1 y H2 intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; test anti-explosión
  `len(plans) == 1784` intacto (solo se etiqueta, no se añade espacio de búsqueda); con el flag OFF,
  salida equivalente a V2.37 (ver V2.38.1 para la corrección del claim de byte-identidad).
- **Tests**: `test_discovery_param_region.py` (determinismo, estabilidad ante reordenación,
  fail-closed, ida y vuelta de la clave compuesta, anti-explosión intacta),
  `test_discovery_evidence.py` (claves compuestas aíslan regiones, hash estable y sensible a región,
  `familyGranularity` poblado/vacío, coexistencia histórica+regionada),
  `test_discovery_search_policy.py` (claves compuestas + `granularityKeyVersion`, filtrado por región,
  región desconocida fail-closed), worker (flag de región OFF/ON, `_collapse_regions`),
  PG (columna `param_region` + roundtrip, agregación por región, posterior por clave compuesta,
  roundtrip `038`).
- **Alembic head**: `038_research_trials_param_region`.
- **Verificación (local)**: `ruff` OK (ficheros tocados) · `mypy` Success en los módulos tocados ·
  offline **1703 passed** · PG con gates `A14_GRAMMAR_PG_REQUIRED=1` **14 passed** · anti-explosión
  `1784` intacto · `--dry-run` OK · sin región, `snapshot_hash` idéntico a V2.37.

## [1.62.0-beta] — V2.37 · Hardening de V2.36 (P2-01/02/03) + Adaptive Discovery Generation — 2026-09-11

Segundo incremento de **Strategy Intelligence**: cierra los tres P2 de la auditoría externa de
`v2.36-beta` y pasa de "cuánto presupuesto recibe una familia" a **"qué hipótesis merece
explorarse"**, sin relajar ningún gate y manteniendo el aprendizaje **fuera del hot path**.

- **P2-01 — Evidencia estadística rica (LAB + posterior).** La v0 saturaba el score en 1.0
  (`clamp(avgScore,0,1) × success_ratio`) y perdía toda la información por encima de 1. Aplicación:
  nueva señal compuesta `discovery_evidence_v1` con componentes monótonos (`1 - exp(-x)` para el
  `is_score`, `tanh` para el Sharpe, `1 - exp(-(pf-1))` para el profit factor, `exp(-dd/50)` para el
  drawdown y la evidencia posterior ponderada por nivel ADR-012), combinados por media ponderada con
  **_shrinkage_ por cobertura** hacia un ancla neutral 0.5: una métrica ausente **no** puntúa como 0
  (ni premia la ausencia). `family_evidence_summary` agrega ahora Sharpe/PF/drawdown medios con
  `metricCoverage` explícita y nunca inventa ceros; nuevo `posterior_evidence_summary` agrega
  shadow/paper forward por familia vía `research_evidence` (join por `trial_id`). La **v0 se conserva
  reproducible** (`--math-version discovery_evidence_v0`).
- **P2-02 — Política formal exploración/explotación.** `DiscoveryBudgetAllocator` gana
  `exploration_floor_ratio` (default 0.5): fracción mínima del presupuesto de candidatas reservada a
  los carriles exploratorios (catálogo + gramática) que el carril `adaptive` **nunca** puede absorber.
  Materializa el invariante "champion cannot teach itself" en el reparto. Con ratio 0 el reparto es
  el histórico de v2.36 (test de regresión).
- **P2-03 — Freshness y fingerprint del snapshot.** `DiscoveryEvidenceSnapshot` gana
  `evidence_fingerprint` (huella del research dataset agregado, determinista y sin reloj) y
  `is_fresh(now, max_staleness_days)`; la entidad documenta las **tres identidades** (`snapshot_hash`
  = conocimiento, `id` = instancia, `created_at` = persistencia — "más nuevo" ≠ "más reciente en
  conocimiento"). Migración aditiva **`037_discovery_evidence_freshness`** (columna nullable, sin
  backfill, `downgrade()` completo). El worker descarta por **fail-closed** un snapshot `stale`
  (`AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS`, default 30 días): el reparto vuelve al histórico
  en vez de gobernar con aprendizaje viejo. `0` desactiva la validación (compatibilidad v2.36).
- **V2.37 incremento 2 — Adaptive Discovery Generation.** Nuevo módulo de aplicación
  `discovery_search_policy` (`SearchPolicy` determinista y versionado `discovery_search_policy_v0`):
  convierte el prior por familia en **cuotas de emisión por familia**, repartidas en dos tramos
  (explotación top-k por peso + exploración uniforme garantizada, `exploration_ratio` default 0.25).
  El carril `adaptive` con cupo **emite candidatas reales** en `strategy_discovery_engine`
  (prefijo `ADAPTIVE_FAMILY_PREFIX`), reutilizando el catálogo curado — sin añadir espacio de búsqueda
  nuevo. Determinismo: mismo `(instrument_id, snapshot, budget)` ⇒ mismas candidatas en mismo orden;
  el motor sigue sin consultar BD ni reloj. Fail-closed: sin política o sin snapshot ⇒ carril no emite
  (byte-idéntico a v2.36).
- **Rollout** — Flag nuevo `AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION` **OFF por defecto**: con OFF el
  carril solo recibe cupo observable (v2.36). El provider de snapshot se cablea si **cualquiera** de
  los dos flags está ON. Observabilidad aditiva: `DiscoveryEmissionSummary` gana
  `adaptive_candidates`/`adaptive_policy_hash`/`adaptive_exploration_quota`/`adaptive_families` y los
  contadores de ciclo/proceso suman `adaptive_candidates`/`adaptive_discoveries`.
- **Granularidad progresiva (P2-03 del audit)** — El payload del snapshot publica un desglose
  aditivo `familyGranularity` (régimen / región de parámetros / clase de instrumento) cuando el repo
  los aporte, sin romper el esquema ni participar en el hash.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  long-only; H1 y H2 intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; test anti-explosión
  `len(plans) == 1784` intacto; con los flags OFF, salida **byte-idéntica a v2.36**.
- **Tests**: `test_discovery_evidence.py` (v1 sin saturación, cobertura neutral, drawdown/PF/posterior,
  fingerprint, suelo de exploración, cota adaptive), `test_discovery_search_policy.py` (determinismo,
  fail-closed, exploración garantizada, emisión adaptativa dentro del presupuesto global y
  determinista), worker (freshness fail-closed, staleness 0, flag de generación), PG (métrica rica +
  cobertura, posterior por familia, fingerprint persistida, roundtrip `037`).
- **Alembic head**: `037_discovery_evidence_freshness`.
- **Verificación (local)**: `ruff` OK · `lint-imports` 4/4 · `mypy` **475 files** Success · offline
  **1547 passed** · PG discovery/snapshot **12 passed** + snapshot detallado **10 passed** +
  lifecycle **6 passed**.

## [1.61.0-beta] — V2.36 · Strategy Intelligence adaptativa (incremento 1: carril `adaptive`) — 2026-09-11

Primer incremento de la **V2.36 Strategy Intelligence adaptativa**: cerrar el bucle
`evidence → aprender → ajustar búsqueda` activando el carril `adaptive` del
`DiscoveryBudgetAllocator` (hoy peso `0.0`, un hueco semántico) con pesos derivados de
**evidencia real ya persistida del LAB**. El aprendizaje NO ocurre dentro del motor: se
materializa en un **snapshot determinista, versionado y persistido**, calculado fuera del
hot path por un job batch/CLI, e **inyectado** como dependencia. El discovery sigue siendo
una **función pura dada la tupla `(instrument_id, snapshot)`**.

- **Dominio** — entidad `DiscoveryEvidenceSnapshot` (dominio puro, `frozen`/`slots`) con
  `snapshot_hash`, `math_version`, ventana temporal, `family_weights` (familia H0 →
  peso), `lane_weights` (catálogo/gramática/adaptive), `sample_sizes` y `payload`; más el
  contrato `DiscoveryEvidenceSnapshotRepository` (`save`/`get_latest`/`get_by_hash`/
  `list_recent`). Método de lectura agregada nuevo `family_evidence_summary` (por
  `preset_key`, orden canónico) en el protocolo de trials.
- **Aplicación** — `bolsa_application.discovery_evidence` (nuevo): builder determinista
  `build_discovery_evidence_snapshot` + `compute_family_weights`/`compute_lane_weights` +
  `snapshot_hash`. Aritmética con redondeo fijo, orden canónico por familia y hash estable
  (`sort_keys`+separadores compactos, patrón `definition_hash`). `math_version`
  `discovery_evidence_v0` audita la fórmula. **Fail-closed**: sin muestra mínima por
  familia (`min_samples`) ni total (`min_total_samples`) el peso adaptativo es `0.0`
  explícito — nunca un peso inventado. Peso acotado a `[0, max_adaptive_weight]` (0.5 por
  defecto) contra overfitting a familias con suerte (multiple testing documentado).
- **Persistencia** — migración aditiva **`036_discovery_evidence_snapshots`**
  (`down_revision=035_paper_forward_evidence`), tabla nueva con `snapshot_hash` único,
  `math_version`, ventana y `payload` JSONB; sin backfill, `downgrade()` completo.
  Repositorio `SqlAlchemyDiscoveryEvidenceSnapshotRepository` inmutable por hash
  (`save` idempotente).
- **Job batch/CLI** — `apps/api-python/scripts/build_discovery_evidence_snapshot.py`:
  lee evidencia → construye snapshot → persiste. **Idempotente de verdad** por
  `snapshot_hash`: el corte `window_to` por defecto es el `created_at` del trial más
  reciente (dato-dependiente, no reloj), de modo que dos ejecuciones sobre la misma
  evidencia dan el mismo hash y la segunda no reescribe. `--dry-run` para auditar la
  fórmula sin tocar la BD. No se ejecuta desde el worker ni el request path.
- **Worker (inyección, sin tocar el hot path)** — flag nuevo
  `AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR` **OFF por defecto**: con OFF no se lee la BD y
  todo es **byte-idéntico a v2.35.1**. Con ON, el bucle lee el snapshot vigente **una vez
  por ciclo** (`_refresh_adaptive_snapshot` + `_make_adaptive_snapshot_provider`, una
  sesión por operación) y lo inyecta en el allocator de todos los instrumentos del ciclo.
  `_discovery_allocator(snapshot)` toma el peso del snapshot (fail-closed: sin snapshot o
  sin evidencia ⇒ `0.0`, nunca el env por accidente).
- **Alcance del incremento 1 (explícito)** — se asigna **cupo real y observable** al
  carril `adaptive`; NO se añade espacio de búsqueda nuevo ni emisión adaptativa (eso es el
  incremento 2). No confundir "peso asignado" con "capacidad de búsqueda": debe quedar
  escrito. Catálogo, gramática simple y gramática compuesta quedan intactos.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path;
  fail-closed; long-only; H1 (`require_holdout=True` inviolable) y H2 (identidad de
  dataset) intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar. Test anti-explosión
  `len(plans) == 1784` intacto.
- **Tests**: `test_discovery_evidence.py` (determinismo, orden-insensibilidad del hash,
  fail-closed, cotas, reproducibilidad por hash, cupo adaptativo sin romper el global);
  worker (flag OFF por defecto, peso del snapshot vs env, fail-closed),
  lectura única por ciclo, no-op sin provider); PG (tabla/índices a head, `save`
  idempotente por hash, `get_latest`/`get_by_hash`, agregación por familia, roundtrip
  `up/down` de la migración `036`).
- **Verificación (tres bloques, local)**: `ruff` + `lint-imports` (4/4) + `mypy` (474
  ficheros) verdes; offline `1518 passed` (domain + application + worker); PG con gates
  `A14_GRAMMAR_PG_REQUIRED`/`LIFECYCLE_PG_REQUIRED`/`AUTO_ORCHESTRATOR_PG_REQUIRED`
  `10 passed` + snapshot PG `6 passed` + lifecycle `57 passed` (incluye anti-explosión).
- **Alembic head**: `036_discovery_evidence_snapshots`.
- **Elevación**: `main == cb147d89` == tag **`v2.36-beta`**. Release-tag CI **GREEN
  verificado** (run [`34604803938`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34604803938),
  conclusión `success`, 2026-09-11): `python`, `lifecycle-pg`, `dr-verify`, `a7-gate`,
  `security`, `decision-spine`, `shared`, `frontend`, `playwright (mock E2E)` y `certify`
  en verde; `playwright (integrated E2E, opt-in)` correctamente skipped.

## [1.60.1-beta] — V2.35.1 · ESTUDIO hard gate (P1-01) — 2026-09-11

Cierra el único hallazgo P1 de la auditoría externa de v2.35-beta: el AUTO podía
**abandonar ESTUDIO** y operar la allowlist CSV como universo cuando ESTUDIO fallaba
o estaba vacío. El contrato pasa a ser literal: **ESTUDIO es obligatorio para AUTO;
la allowlist solo intersecta; nunca lo sustituye.**

- **Hard gate en `_instruments_for_cycle`**: los cinco caminos que antes devolvían la
  allowlist (`resolver` ausente, excepción del resolver, `resolution is None`,
  `status != "ok"` —cubre `unavailable`/`empty`/desconocido— e `instrument_ids` vacío)
  ahora devuelven `()` ⇒ **no se opera**. El worker no muere: reintenta el ciclo
  siguiente (fail-closed, no fail-stop).
- **Allowlist como intersección pura**: con ESTUDIO `ok` y CSV configurado, el cálculo
  sigue siendo `ESTUDIO ∩ allowlist`; nunca `ESTUDIO falla → CSV se convierte en
universo`.
- **Sin vía de escape hermética**: el gate es estricto también cuando el orquestador no
  expone `resolve_universe` (antes los tests/dobles caían a la allowlist). Los dobles de
  test migran a un universo ESTUDIO real.
- **Documentación coherente**: se corrige la contradicción entre el docstring del worker
  ("`empty`/`unavailable` nunca inventa candidatas") y su comportamiento previo, y el
  comentario de `orchestrator_universe.py` deja de llamar a la allowlist "fallback".
- **Tests**: nuevos `test_unavailable_estudio_never_falls_back_to_allowlist`,
  `test_estudio_empty_never_falls_back_to_allowlist`,
  `test_estudio_error_never_falls_back_to_allowlist` y
  `test_loop_does_not_operate_when_estudio_unavailable_with_allowlist` (no se ejecuta
  ningún ciclo); se retiran los que certificaban el fallback.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`, LIVE bloqueado, sin LLM en hot path,
  fail-closed, long-only y gates CPCV/PBO/DSR/WFE/OOS + coach sin cambios. Sin
  migración (head Alembic sigue en `035_paper_forward_evidence`).
- **Elevación**: `main == 5348bee0` == tag **`v2.35.1-beta`**. Release-tag CI **GREEN
  verificado** (run [`34599471123`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34599471123),
  conclusión `success`, 2026-09-11): `python` (ruff/imports/mypy/pytest offline),
  `lifecycle-pg`, `dr-verify`, `a7-gate`, `security`, `decision-spine`, `shared`,
  `frontend` y `playwright (mock E2E)` en verde.

### Deuda P2 de la auditoría v2.35-beta, resuelta en la misma versión

- **P2-01 — Promotion Gate automática separada de la admin/manual.** El override humano
  `shadow_validated` sale del API genérico: `decide_promotion`/`evaluate_promotion` son la
  vía **automática** (solo evidencia shadow ejecutada, sin parámetro de override) y
  `decide_admin_promotion`/`evaluate_admin_promotion` la **única** vía admin con override.
  Se elimina `OrchestratorDeps.shadow_override` y el parámetro `shadow_validated` de
  `run_cycle`. H1 intacto (`require_holdout=True` inviolable, sin escape hatch; sin
  `lab_end` no hay replay). El AUTO productivo nunca podía usar el override; ahora la
  frontera es explícita también en el tipo. Sin migración.
- **P2-02 — Contadores de ciclo separados de los de proceso.** Nuevo
  `CycleGrammarCounters` efímero (reiniciado al inicio de cada iteración) para que
  `cycle_summary` reporte **solo** el ciclo vigente; se añade `process_summary` con los
  acumulados desde el arranque del worker. `grammar_counters()` sigue devolviendo el
  acumulador de proceso (compatibilidad). Observabilidad pura: no altera ninguna decisión.
- **P2-03 — Allocator explícito de presupuesto del Discovery.** Nuevo
  `DiscoveryBudgetAllocator` (pesos por carril: catálogo / gramática simple / gramática
  compuesta / adaptive-placeholder) con reparto determinista por **resto mayor** y suelos
  por carril, que sustituye la reserva secuencial `_grammar_reserve` y elimina el sesgo de
  orden catálogo→gramática (el catálogo ya no puede dejar sin presupuesto a la gramática, ni
  al revés). Con gramática OFF la salida sigue siendo byte-idéntica a A13 (test de
  regresión). `adaptive` queda a peso 0 (placeholder; **no** implementa aprendizaje). Pesos
  configurables por env `AUTO_ORCHESTRATOR_ALLOCATOR_*`. Sin migración.
- **Integración**: el bump de P2-03 da cupo real a la gramática y destapó que
  `RunSmaGridOptimizeAndSave.execute` no reenviaba `grammar_variants` (A14 lo añadió al
  optimizador y a `_GRID_KEYS`, pero no al wrapper de persistencia) ⇒ corregido. Los tests
  A14 PG admiten además el corte honesto `sin_evidencia_top3` (fail-closed previo al gate
  shadow) ahora que la gramática ya no queda muerta.

## [1.60.0-beta] — V2.35 / A15 · Observabilidad y gobernanza de la gramática de Discovery — 2026-09-11

Hace **gobernable el rollout** de la gramática controlada de A14 (`AUTO_ORCHESTRATOR_GRAMMAR`,
OFF por defecto) sin cambiar ninguna semántica de decisión: ahora se mide cuánto aporta la
gramática frente al catálogo curado y cuántos planes llegan de verdad al LAB y al shadow.
Todo es **observabilidad de solo lectura** — no altera presupuestos, gates ni el reparto
catálogo↔gramática, y **no hay migración** (head Alembic sigue en
`035_paper_forward_evidence`).

- **Resumen determinista de emisión (`DiscoveryEmissionSummary`)**: nueva API aditiva
  `discover_for_instrument_with_summary(...)` en `strategy_discovery_engine.py` que devuelve
  `(candidatas, resumen)`. El resumen cuenta `catalog_candidates`, `grammar_candidates`,
  `total_candidates`, `trials_used`, los cupos reservados (`catalog_cap`/`grammar_cap`), el
  flag `grammar_enabled` y el warm-up (`bar_count_ok`). Se calcula sobre lo ya emitido (el
  prefijo `grammar:` es la fuente de verdad); **no añade estado al motor**.
- **API estable intacta**: `discover_for_instrument(...)` delega en la nueva función y
  descarta el resumen, de modo que con `grammar_budget=None` la salida es **byte-idéntica**
  a la de A13 (test de regresión explícito).
- **Procedencia en el orquestador**: `OrchestratorResult` gana campos aditivos de conteo
  (`catalog_candidates`, `grammar_candidates`, `lab_grammar_evaluated`, `shadow_started`,
  `shadow_grammar_started`) derivados de la evidencia real del ciclo (evaluaciones del LAB y
  replay shadow ejecutado). Sin provider de barras, `shadow_started` es 0 (fail-closed
  honesto: no se inventa evidencia).
- **Logs estructurados en el worker AUTO**: una línea de observabilidad por instrumento
  (procedencia, presupuesto y cupos) y un `cycle_summary` agregado por ciclo, más
  `GrammarObservabilityCounters` acumulados por proceso (`grammar_counters()` para
  inspección/tests). Solo `logging`: sin persistencia en DB.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`, LIVE bloqueado, sin LLM en hot path,
  fail-closed (ausencia de evidencia ≠ aprobación), long-only y gates CPCV/PBO/DSR/WFE/OOS
  - coach sin cambios.
- **Tests**: herméticos de resumen OFF/ON, cuadre catálogo+gramática=total, determinismo,
  warm-up y regresión A13 (`test_discovery_grammar.py`); contadores y `cycle_summary` del
  worker (`test_auto_orchestrator_worker.py`); procedencia LAB/shadow del orquestador
  (`test_auto_orchestrator.py`).

> Verificación: `ruff`, `lint-imports` (4/0), `mypy` (470 ficheros) verdes; job `quality`
> offline (1243 passed) y E2E PG de certificación (`grammar-discovery-pg`,
> `paper-forward-pg`, `lifecycle-pg`) sin skips.
>
> **Deuda preexistente que NO se toca aquí**: `packages/py/infrastructure/tests/chaos/
test_load_concurrency_flow.py` (fallos de carga preexistentes) y el flake ambiental de
> `test_a9_scheduler_process_pg_zero_human` sobre BD local sucia (documentado en el audit-pack
> de V2.32.1).

## [1.59.0-beta] — V2.34 / A14 · Strategy Intelligence (gramática controlada de Discovery) — 2026-09-11

Discovery deja de ser un catálogo de familias técnicas fijas y pasa a ser una **gramática
controlada**: una estrategia se compone de bloques funcionales (`REGIME` + `TREND FILTER`

- `MOMENTUM` + `ENTRY TRIGGER` + `EXIT`, con `TRIGGER`/`EXIT` obligatorios y máx. 2–3
  opcionales), acotada por un presupuesto determinista. **Sin segundo motor de trading ni
  segundo FSM**, **sin migración** (head Alembic sigue en `035_paper_forward_evidence`) y sin
  tocar las barreras LIVE.

* **Gramática controlada (`discovery_grammar.py`)**: vocabulario de bloques, variantes
  declaradas, vetos de redundancia y materialización a `StrategyDefinitionV1` con los
  helpers existentes. La composición es la **conjunción plana** de reglas
  (`operator="all"`), exactamente lo que el motor declarativo ya evalúa; no se añade
  sintaxis ni nesting al motor.
* **`GrammarBudget`**: envuelve `DiscoveryBudget` (un único presupuesto global por
  instrumento), acota `max_components ∈ [1, 3]` y `max_per_component_variant`, con
  enumeración determinista (cero azar, cero IA). El techo exacto queda fijado por test
  anti-explosión (1784 planes con el presupuesto por defecto).
* **Cierre del gap bloqueante de promoción**: la vía declarativa del LAB
  (`_run_cpcv`/`_run_walk_forward`) gana una rama que reutiliza `split_cpcv_paths` y
  `_simulate_rules_strategy`, produciendo **CPCV/PBO/DSR/WFE reales**. Antes de A14,
  `robustness`/`walk_forward` quedaban `NOT_EVALUATED` para toda familia declarativa y
  **ninguna candidata de Discovery podía promocionar**.
* **Grid gramatical**: cada candidata gramatical lleva variantes hermanas
  (`grammar_variants`) para que el LAB re-optimice de verdad y el PBO CSCV tenga columnas
  que rankear; la reserva de presupuesto garantiza que el catálogo no deja a la gramática
  sin candidatas.
* **Sanación de familias inertes**: se cablean en `_series_for_spec` los ids causales que
  faltaban (`roc`, `srsi`, `mom`, `wma`, `sd`, `obv`, `mfi`, `aroon`, `bears`, `bulls`,
  `sar` vía `compute_psar` con `maxAf`). Las plantillas `roc_momentum`,
  `stoch_rsi_reversion` y `sar_flip` del catálogo, que referenciaban ids no cableados
  (reglas silenciosamente inertes), ahora producen señales reales.
* **Propagación del campeón**: el `executable` promocionado se **re-materializa con los
  parámetros ganadores** del campeón (no con el punto plantilla de la candidata), evitando
  que shadow/forward repliquen parámetros obsoletos.
* **Rollout reversible**: la gramática está tras `AUTO_ORCHESTRATOR_GRAMMAR` (OFF por
  defecto); con OFF el Discovery es idéntico al de A13 (test de regresión).
* **Invariantes intactas**: H1 (`require_holdout=True` inviolable; fail-closed sin
  `lab_end`), H2 (identidad `instrument_id/timeframe/source/adjusted` en `bars_hash`) y las
  barreras LIVE (`AUTO ⇒ SIMULATED`; cero publicaciones al bridge real).
* **Tests**: herméticos de gramática/determinismo/techo/vetos/wiring/gates declarativos
  (entran en el job `quality`) y E2E PG `grammar-discovery-pg` (gate
  `A14_GRAMMAR_PG_REQUIRED=1`, fail-if-skipped; negativo fail-closed e invariante LIVE=0).

> Verificación: `ruff`, `lint-imports`, `mypy` verdes; job `quality` offline
> (`apps/api-python` 201/201, `packages/py` 2276/2278) y E2E PG de certificación
> (`grammar-discovery-pg`, `paper-forward-pg`, `lifecycle-pg`) sin skips.
>
> **Deuda preexistente que NO se toca aquí**: `packages/py/infrastructure/tests/chaos/
test_load_concurrency_flow.py` (2 fallos de carga preexistentes).

## [1.58.1-beta] — V2.32.1 · Hardening H1+H2 (hold-out inviolable + identidad de dataset) — 2026-09-11

Cierra los dos contratos que la auditoría V2.32.1 dejó pendientes y que se acordó **no**
mezclar con A13. Cambio de contrato, **sin migración** y sin tocar las barreras LIVE
(siguen doblemente bloqueadas).

- **H1 — `require_holdout=True` inviolable en la ruta de promoción**: el orquestador
  fuerza el hold-out estricto al construir el `ShadowReplayConfig` del shadow. El flag
  `OrchestratorDeps.shadow_require_holdout` **se elimina** (ya no existe vía de escape).
  Sin `lab_end` demostrable no se construye el replay (fail-closed en el orquestador,
  antes de invocar la fase). Ya no existe ninguna ruta de promoción que replique sin
  hold-out estricto ni sin frontera LAB.
- **H2 — identidad de dataset en el `bars_hash`**: `ShadowReplayConfig` y
  `PaperForwardConfig` ganan `instrument_id`/`timeframe`/`source`/`adjusted`, que se
  incorporan a la cabecera del hash en shadow y forward. Dos series con el mismo OHLCV
  pero distinto instrumento o marco temporal ya **no** comparten identidad de evidencia.
  Si el config no fija `instrument_id`, se cae al del finalista/ACTIVE (compatibilidad).
  Se mantiene la semántica «mismo dataset ⇒ mismo hash».
- **Wiring AUTO**: el worker puebla `instrument_id`/`timeframe`/`source` en la evidencia
  shadow y forward desde la lectura diaria del instrumento; `adjusted` no se inventa.
- **Tests**: orquestador (fuerza del hold-out, fail-closed sin `lab_end`) y fases shadow/
  forward (mismo OHLCV con distinta identidad ⇒ hash distinto; identidad estable).
- **Correcciones de arranque del CI (deuda preexistente saldada en esta release)**:
  - `alembic/env.py`: `fileConfig(..., disable_existing_loggers=False)`. Al correr Alembic
    **en proceso** (`ensure_migrated` en el bootstrap de workers y en tests PG), el default
    de `fileConfig` deshabilitaba los loggers de la app ya creados — silenciando el logging
    del proceso y rompiendo por orden `test_queue_poll_worker::test_run_con_arq_es_noop`.
  - `test_scheduler_worker`: el set esperado no incluía `start_auto_orchestrator` (A10).
  - `test_auto_scheduler_real_pg_zero_human_intervention`: la reconstrucción de equity
    llamaba a `reconstruct_accounting_from_state` sin `closed_pnl`, provocando un descuadre
    cuando el día cerraba con pérdida realizada (`cash` ya la incorporaba). Ahora deriva el
    P&L cerrado del libro de fills (`sim_fill_finance_context`) — fuente independiente del
    `cash`, invariante no tautológica.

> Verificación: `ruff`, `lint-imports`, `mypy` verdes; job `quality` offline
> (`apps/api-python` 201/201, `packages/py` 2276/2278) y E2E PG de certificación
> (`paper-forward-pg` / `lifecycle-pg`) en verde.
>
> **Deuda preexistente que NO se toca aquí** (ajena al hardening; falla igual en el baseline
> `5fcd0224`): `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` (2
> tests de carga 500+500; el invariante de orden por `(executed_at, id)` se rompe por empates
> de timestamp a alta concurrencia — el invariante contable Σ ledger == cash sí es correcto).
>
> **Compatibilidad de evidencia**: el `bars_hash` cambia de semántica (incluye identidad). La
> evidencia _shadow/forward_ persistida **antes** de este commit conserva su hash almacenado,
> pero no coincide con un recálculo bajo la nueva cabecera. No hay migración ni backfill (la
> evidencia histórica no se reescribe); el cambio afecta a la reproducibilidad de aquí en
> adelante.

## [1.58.0-beta] — V2.33 / A13 · Paper Forward (ACTIVE → forward P&L → vigilancia) — 2026-09-11

Cierra el salto que V2.32/A12 deja abierto: la evidencia de una estrategia deja de ser
solo **histórica** (shadow sobre un hold-out del LAB) y pasa a incluir **forward** real
sobre mercado nuevo posterior a la promoción. Sin dinero real, sin cambios en las
barreras LIVE (siguen doblemente bloqueadas) y sin tocar la ruta SIM-only.

- **Forward paper determinista**: nuevo `paper_forward_phase.run_paper_forward` que
  reutiliza el **mismo** motor declarativo de reglas que el LAB/shadow (causalidad
  `index-1 → open(index)`, sin look-ahead) pero sobre barras con timestamp
  **estrictamente posterior** a la promoción de la ACTIVE. No hay un segundo motor de
  trading: la definición ejecutable de la ACTIVE es la única fuente de señal.
- **Frontera temporal fail-closed**: sin barras nuevas post-promoción no hay evidencia
  (`forward_sin_barras`, `passed=False`); nunca se inventa un P&L forward.
- **Fingerprint reproducible**: dominio `PaperForwardResult` + `PaperForwardPolicy`
  (guarda de muestra en `min_closed_round_trips`, DD fail-closed) con
  `forward_start`/`forward_end`/`bars_hash`/`strategy_definition_hash`/`engine_version`/
  `config_hash`/`data_snapshot_id`/`promoted_at`.
- **Persistencia**: migración **035** (`paper_forward_results`, aditiva y nullable, sin
  backfill) + `save_forward_result`/`list_forward_results` en el store (InMemory y
  Postgres). La evidencia queda atribuida a la `version_id` de la ACTIVE.
- **Wiring AUTO (default OFF)**: `AUTO_ORCHESTRATOR_FORWARD=1` activa el forward tras
  cada ciclo y antes de la vigilancia (`AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS`, default
  400). Con OFF el comportamiento es idéntico a V2.32.1 (rollout reversible).
- **Certificación PG por commit**: nuevo job `paper-forward-pg` en `python-ci.yml` que
  aplica `alembic upgrade head` (hasta 035) y ejecuta el E2E A13 con
  `PAPER_FORWARD_PG_REQUIRED=1` (un skip es fallo duro). El E2E certifica
  ACTIVE → barras nuevas → señal → fills/round-trips → P&L → evidencia persistida →
  vigilancia, y el caso negativo sin barras nuevas.

> Cierre: `docs/engineering/cierre-v2.33-a13-paper-forward-2026-09-11.md`.

## [1.57.0-beta] — V2.32.1 / A12.1 · Audit Remediation (P1 + promotion-hardening P2) — 2026-09-11

Remedia los hallazgos verificados de la auditoría V2.32 contra HEAD `854dc86`, sin
cambios de arquitectura ni en las barreras LIVE (siguen doblemente bloqueadas) y sin
tocar la ruta SIM-only. Endurece la honestidad estadística y la certificación continua.

- **P1-01 — Hold-out estricto LAB/shadow**: la ventana del shadow ya no se solapa con la
  del LAB. El orquestador resuelve el corte (`lab_end`), lo inyecta en las candidatas
  (`date_to`) y el replay parte las barras en LAB vs hold-out estricto
  (`split_holdout`), con _fail-closed_ (`shadow_solape_lab` /
  `shadow_barras_holdout_insuficientes`). El worker lee `bar_limit + shadow_window`
  barras para que exista un hold-out real posterior.
- **P1-02 — E2E PG por commit**: nuevo job `lifecycle-pg` en `python-ci.yml` que arranca
  `postgres:16`, aplica `alembic upgrade head` (032/033/034) y ejecuta la suite A12
  crítica con gates `*_PG_REQUIRED=1` (un skip es fallo duro). El E2E
  `test_a11_discovery_to_auto_sim_pg.py` deja de estar `--ignore`d en la certificación.
- **P1-02 — E2E determinista (sin SKIPPED)**: dataset sembrado que produce un cruce SMA
  real en la última barra ⇒ `ACTIVE → SIGNAL → SIM BUY → FILL` certificado como
  aserción dura. Se corrige además un fallo preexistente de lectura de gates
  (`walkForwardEfficiency`/`dsr` anidados en `edge_report["suite"]`) que dejaba
  `robustness`/`walk_forward`/`dsr` en `NOT_EVALUATED` e impedía promocionar.
- **P2-01 — Drawdown fail-closed**: `ShadowPolicy.evaluate` falla cerrado si
  `max_drawdown_pct` está configurado y la métrica es `None` (`shadow_drawdown_ausente`).
- **P2-02 — Sin override en AUTO**: se elimina `shadow_validated`/`shadow_override` de la
  ruta AUTO real; la promoción en AUTO es solo por evidencia. El parámetro se mantiene
  para llamadas manuales/admin/test.
- **P2-03 — Fingerprint del dataset shadow**: migración **034**
  (`round_trips`, `data_snapshot_id`, `shadow_start`, `shadow_end`, `bars_hash`,
  `strategy_definition_hash`, `engine_version`, `config_hash`, `lab_end`), todas
  nullable y sin backfill (la ausencia de evidencia no se inventa).
- **P2-04 — Semántica de round-trips**: la guarda de muestra es `min_closed_round_trips`
  (operaciones cerradas), no piernas ejecutadas.
- **P2-05 — Identidad por ciclo**: `run_id` por ciclo (`orchestrator:{instrument}:{ts}-{rnd}`)
  en vez de constante, para distinguir retries/re-LAB/shadow.
- **Auditoría 2a — `can_transition` fail-closed**: transicionar sin gates evaluados se
  bloquea (`gates_no_evaluados`) en vez de permitirse.
- **Auditoría 2b — `HealthThresholds` predictivos**: `min_edge`/`min_wfe`/`min_dsr`/
  `min_credibility` pasan a `None` por defecto (sin fabricar un `0.0`); la vigilancia
  solo degrada con umbrales calibrados.

> Cierre: `docs/engineering/cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md`.

## [1.56.0-beta] — V2.32 / A12 · Shadow Validation & Autonomous Attribution — 2026-09-11

Cierra los **dos P2 diferidos a V2.32** por la auditoría V2.31. Sin cambios en las
barreras LIVE (siguen doblemente bloqueadas) ni en la ruta SIM-only.

- **Shadow real (evidencia ejecutada, no flag)**: nuevo `strategy_shadow_phase.py`
  (`run_shadow_replay`) que ejecuta la definición del finalista con el motor real de
  reglas sobre una ventana separada del LAB. Dominio: `ShadowValidationResult` +
  `ShadowPolicy`; `evaluate_promotion` pasa a exigir evidencia (`shadow=...`) y la
  ACTIVE queda enlazada a `shadow_validation_id`. `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`
  deja de ser autoridad y pasa a **override explícito** del operador.
- **Persistencia**: migración **032** `strategy_shadow_validations` +
  `strategy_promotions.shadow_validation_id`; `save_shadow_result`/`list_shadow_results`.
  El marcador engañoso de `save_active` (escribía `shadow_validated=True` sin evidencia)
  queda corregido.
- **Atribución post-crash**: migración **033** (`sim_auto_positions.strategy_version_id` +
  `ledger_entries.strategy_version_id`). `readopt_positions` restaura la versión ⇒ los
  cierres readoptados vuelven a atribuirse; el ledger recibe la versión por
  `ExecuteTrade.execute(..., strategy_version_id=...)` (aditivo, sin tocar importes).
- **E2E A11 en PG**: nuevo `test_a11_discovery_to_auto_sim_pg.py`
  (DISCOVERY → SHADOW → PROMOTION → ACTIVE → SIM → LEDGER → VIGILANCIA + caso negativo
  sin evidencia + readopt con atribución), en el job `lifecycle-pg`.
- **CI simétrico**: discovery + shadow añadidos también a `python-ci.yml` (el job diario
  no los listaba).

> Cierre: `docs/engineering/cierre-v2.32-a12-shadow-attribution-2026-09-11.md`.

## [1.55.0-beta] — V2.31 / A11 · Intelligent Strategy Discovery — 2026-09-10

Cierra los **dos P1** de la auditoría V2.30. Sin cambios en las barreras LIVE (siguen
doblemente bloqueadas) ni en la ruta SIM-only.

- **P1-01 — `StrategyDiscoveryEngine`**: nuevo search space **curado y acotado** sobre los
  33 `definitionId` reales de `bolsa_analytics.indicators` (antes solo 3 familias fijas:
  SMA/RSI/MACD). `discovery_catalog.py` declara 14 plantillas en tres ramas
  (trend / momentum / volatility) con parámetros pequeños; `strategy_discovery_engine.py`
  emite candidatas **deterministas** con presupuesto global (`DiscoveryBudget`).
- **LAB declarativo**: `run_rules_grid_search` evalúa las plantillas con el motor real de
  reglas (`evaluate_rules_signals`, gated, sin look-ahead); `RunSmaGridOptimize.execute`
  acepta `definition=` y despacha a `rules_grid_h0` sin colapsar la familia a SMA/RSI/MACD.
  `LabOptimizeRunner` propaga la definición.
- **Orquestación**: `OrchestratorDeps.discovery` + flag `AUTO_ORCHESTRATOR_DISCOVERY`
  (default OFF) con presupuesto por env. Discovery vacío ⇒
  `status="sin_candidatas_discovery"` (fail-closed: no se inventa la candidata única).
- **P1-02 — ACTIVE fail-closed (NO TRADE)**: se elimina el fallback al spine en
  `active_strategy_signal_evaluator.py`. Sin señal evaluable (sin `executable`, sin barras,
  fuera de `watch`, error) ⇒ `HOLD`; el único camino a BUY/SELL es la señal propia de la
  estrategia promocionada. La procedencia real deja de ser invisible.
- **Sin migraciones nuevas**: catálogo y motor son puros; el discovery reutiliza
  `strategy_candidates`.

> Cierre: `docs/engineering/cierre-v2.31-a11-discovery-engine-2026-09-10.md`.

> **Diferido a V2.32 (deuda de producto):** shadow real (evidencia ejecutada en vez del
> flag `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) y atribución de versión tras crash en
> posiciones readoptadas.

## [1.54.0-beta] — V2.30 / A10 · Higiene auditable (CI que ejecuta lo que certifica) — 2026-09-10

Cierra la **deuda de higiene** que impedía una auditoría limpia en GitHub. Sin cambios
de comportamiento de producto: el núcleo de decisión A10 y el LIVE real quedan igual.

- **Guardias de head de Alembic derivadas** (causa raíz): nuevo `alembic_head()` en
  `bolsa_infrastructure.database.migrations`, que lee la head del filesystem de
  migraciones (no se hardcodea). Sustituye las guardias que había que parchear a mano
  en cada migración (`029→030`, `030→031`, ...).
- **Drift de 27 migraciones corregido**: `test_f3b_alembic_data_epoch` y
  `test_ledger_entries_reference_unique` seguían anclados a `004_ledger_reference_unique`
  y **no se ejecutaban en ningún job** — el CI daba verde sobre tests que no corrían.
- **Test de concurrencia PG hermético**: `test_live_order_recovery_concurrency_pg`
  commiteaba filas y no limpiaba, envenenando la suite entre pasadas. Ahora purga por
  `account_id` en `finally`.
- **Hueco de CI cerrado**: 7 tests PG que estaban fuera de todos los jobs se incorporan
  al job `lifecycle-pg` con gates fail-if-skipped (`LIVE_PG_REQUIRED`, `E2_PG_REQUIRED`,
  `EXECUTION_FENCE_PG_REQUIRED`); el job `python` los ignora explícitamente.
- **Marcador shadow documentado**: `shadow_validated=True` en `save_active` es un
  localizador de la activa, no evidencia de validación (aclarado en código).

> Cierre: `docs/engineering/cierre-v2.30-higiene-auditable-2026-09-10.md`.

> **Diferido a V2.31 (deuda de producto):** `StrategyDiscoveryEngine` (selector sobre
> los 30+ indicadores), shadow automático (evidencia ejecutada en vez del flag
> `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) y atribución de versión tras crash en posiciones
> readoptadas.

## [1.53.0-beta] — V2.27 + V2.28 + V2.29 / A10 · Cierre del núcleo de decisión — 2026-09-10

Cierra los P2 del A10 que tocaban el **núcleo de decisión**, acumulados desde V2.26:

- **V2.27 — Wiring real**: el universo ESTUDIO y el LAB (`RunSmaGridOptimizeAndSave`) se
  cablean en la composición real (`_default_orchestrator`), sin inyectar dependencias.
- **V2.28 — Vigilancia real**: `sim_fill_finance_context` gana `strategy_version_id`
  (Alembic `031_sim_fill_strategy_attr`) y la vigilancia calcula métricas observadas
  (PnL, drawdown, win rate, profit factor) desde fills SIM atribuidos a la versión.
- **V2.29 — COACH comparativo + SignalEvaluator real**: el COACH dictamina el TOP3 entero
  (eligiendo el primer candidato sin veto, sin reordenar la evidencia); la versión
  promocionada persiste los **parámetros del campeón** y su **definición ejecutable**; y
  la estrategia ACTIVE puede evaluar **su propia señal** sobre barras reales
  (`AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL`, default OFF ⇒ se conserva el spine).

AUTO sigue **estrictamente SIMULATED**; **LIVE real intacto**. La vigilancia observada
está separada de las métricas predictivas (`edge`/`wfe`/`dsr`) y usa una guarda de
muestra mínima para no degradar por ruido.

> Cierres: `docs/engineering/cierre-v2.27-a10-real-wiring-2026-09-10.md`,
> `cierre-v2.28-vigilancia-real-2026-09-10.md`,
> `cierre-v2.29-coach-comparativo-signal-real-2026-09-10.md`.

> **Diferido a V2.30:** `StrategyDiscoveryEngine` (selector sobre los 30+ indicadores),
> shadow automático (evidencia ejecutada en vez del flag `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`)
> y atribución de versión tras crash en posiciones readoptadas.

## [1.52.0-beta] — V2.25 + V2.26 / A10 · Strategy Lifecycle + Auto Orchestrator — 2026-09-10

Construye el **ciclo de vida autónomo de estrategia (A10)** sobre la infraestructura
LAB/optimización/OOS ya existente y lo cablea al AUTO **exclusivamente** por el seam
`DecisionProvider`. Núcleo financiero LIVE congelado; **LIVE real sigue doblemente
bloqueado** y AUTO es **estrictamente SIMULATED**.

> **Nota de reciclaje de nombres:** los identificadores **V2.25** y **V2.26** se usaron
> el 4-sep-2026 para _polish_ de UI (docs de `docs/engineering/`). Aquí se **reutilizan**
> con el significado canónico del plan A10: **V2.25 = Strategy Lifecycle** y
> **V2.26 = Auto Orchestrator**. Las referencias antiguas a V2.25/V2.26 de UI quedan
> superadas por esta entrada.

### V2.25 — Strategy Lifecycle (A10)

- **Dominio** (`bolsa_domain/entities/strategy_lifecycle.py`): `StrategyCandidate`,
  `StrategyEvaluation`, `StrategyFinalist`/`StrategyVersion` (inmutable, hash de
  definición), `StrategyPromotion`, `ActiveStrategy`, `StrategyHealth` y la máquina de
  estados `StrategyLifecycleState` con transiciones fail-closed (un gate previo debe
  PASS; el COACH **solo veta/degrada**, nunca aprueba por encima de los gates).
- **Persistencia** (Alembic **`030_strategy_lifecycle`**, head pasa de `029`): tablas
  `strategy_candidates`, `strategy_versions`, `strategy_evaluations`,
  `strategy_promotions`, `strategy_health_snapshots`. Reutiliza `strategy_definitions`,
  `research_trials`, `research_evidence` y `edge_reports` como evidencia enlazada (no
  duplica). Store: `InMemoryStrategyLifecycleStore` (hermético) y
  `PostgresStrategyLifecycleStore` (PG).
- **Fases** (módulos de aplicación, reutilizando el LAB existente):
  - **ESTUDIO/LABORATORIO** (`strategy_lab_phase.py`): universo reproducible con
    `data_snapshot_id` sellado; `evaluate_optimize_result` traduce
    `RunSmaGridOptimize` (holdout/WF/CPCV/PBO) a `StrategyEvaluation` con gates.
  - **TOP 3 / COACH** (`strategy_top3_coach_phase.py`): selección por evidencia (score +
    gates + PBO) y `assess_with_coach` determinista y _advisory_ (veta, no promociona).
  - **FINALISTA + Promotion Gate** (`strategy_promotion_phase.py`): `StrategyVersion`
    inmutable y `decide_promotion` con los seis gates (`backtest`, `robustness`,
    `walk_forward`, `oos`, `risk`, `coach`) + coach + **shadow validation**; reglas
    anti-strategy-chasing (el LAB no sustituye la activa sin promoción).
  - **Vigilancia** (`strategy_vigilance_phase.py`): `evaluate_active_health` compara
    edge/WFE/DSR/credibilidad con umbrales; la degradación ⇒ **re-LAB** (nunca swap).
- **API**: `GET /research/strategy/{version_id}/health` expone estado e histórico de
  salud de la estrategia activa (DTOs en `schemas/research.py`).

### V2.26 — Auto Orchestrator (A10)

- **`auto_orchestrator.py`**: ciclo completo
  ESTUDIO→LAB→TOP3→COACH→FINALISTA→VALIDACIÓN→PROMOCIÓN→ACTIVE→vigilancia, determinista
  e inyectable. Sin shadow no promociona; sin evidencia, no hay TOP3; el COACH puede
  vetar.
- **Worker** (`background/auto_orchestrator_worker.py`, registrado en
  `scheduler_worker.py`): bucle env-gated **default OFF** —
  `AUTO_ORCHESTRATOR_ENABLED`, `AUTO_ORCHESTRATOR_INSTRUMENTS`,
  `AUTO_ORCHESTRATOR_INTERVAL_SECONDS`, `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`.
- **Seam ACTIVE→AUTO**: `active_strategy_decider` traduce la estrategia activa a un
  `DecisionProvider`. El worker AUTO lo instala vía `AutoSimRuntime.set_decider` cuando
  `AUTO_ENGINE_SIM_ACTIVE_STRATEGY=1` (**default OFF**). No se toca RiskGate ni
  SimulationGate y **no se abre LIVE**; sin activa fiable se conserva el spine
  determinista.

### Gates CI

- `python-ci.yml` / `release-tag-ci.yml`: entran al pytest offline los tests herméticos
  de las fases A10 + orquestador (`test_strategy_*_phase.py`, `test_auto_orchestrator.py`,
  `test_sim_durable_unit_of_work.py`).
- `release-tag-ci.yml > lifecycle-pg`: nuevo **`AUTO_ORCHESTRATOR_PG_REQUIRED=1`** y el
  test `test_auto_orchestrator_full_cycle_pg` sobre el store Postgres real (promoción con
  shadow y degradación→re-LAB). Un skip silencioso es fallo duro.

## [1.51.1-beta] — V2.24.2 / A9.1-hardening — P2 residuales (equity real, UoW, recon global, restart) — 2026-09-10

Endurecimiento de la certificación V2.24/A9.1 (run `34470214388`, GREEN) cerrando los
**P2 residuales** señalados por la auditoría externa. Sin features de trading nuevas;
núcleo financiero LIVE congelado y **LIVE real sigue doblemente bloqueado**.

### Qué cambia

- **P2-A — equity invariant REAL:** `reconstruct_accounting_from_state` reconstruye el
  `LifecycleAccounting` desde las filas reales del ledger (depósitos/compras/ventas/fees),
  coste medio y precio actual. El test de la Reina por proceso ya no pasa
  `last_price=0`/`realized_pnl=0` (invariante tautológica): ahora `total_equity ==
initial + realized + unrealized` es una afirmación financiera no degenerada.
- **P2-B — unidad-de-trabajo proyección + finance:** `SimDurableUnitOfWork` y el flag
  `autocommit=False` en `PostgresSimFillFinanceContextStore`/`PostgresSimAutoPositionStore`
  permiten componer ambos espejos en UNA transacción. El commit autónomo sigue siendo
  el default (durabilidad-e-idempotencia intacta); la proyección no cambia de naturaleza
  (sigue siendo reconstruible, P1-01).
- **P2-C — reconciliación GLOBAL de cuenta:** `reconcile_sim_account` agrega todos los
  símbolos (unión eventos/canónico/proyección) y detecta posiciones fantasma solo en la
  proyección; cualquier `DIVERGENT`/`UNKNOWN` bloquea aperturas en toda la cuenta
  (fail-closed). El worker expone `reconciliation_status` y
  `reconciliation_blocks_openings`.
- **P2-D — restart con posición/protección abierta:** nuevo test PG-gated que arranca el
  proceso real `scheduler_worker`, lo mata con la posición abierta y lo reinicia sobre la
  misma BD: el proceso readopta la posición durable y **NO re-compra** (los BUY no se
  doblan). Retén del spine parametrizable por `AUTO_ENGINE_SIM_EXIT_AFTER_TICKS` para
  poder certificar el escenario.

### Gates CI

- `lifecycle-pg` añade `AUTO_SCHEDULER_RESTART_PG_REQUIRED=1`; el test de restart corre en
  `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (un skip sin PG sigue
  siendo fallo duro con los gates activos).

## [1.51.0-beta] — V2.24-beta / A9.1 · Durable Autonomous Simulation Integrity — 2026-09-10

Cierre de los **4 P1 de durabilidad/aislamiento** que la auditoría V2.23 detectó en
el AUTO SIM-ONLY, más el endurecimiento de los P2 de integridad y la primera
**Reina real** (proceso scheduler, no `run_turn` manual). El núcleo financiero sigue
congelado y **LIVE real continúa doblemente bloqueado** (`LIVE_EXECUTION_AUTHORIZED`

- `LIVE_EXECUTION_UNLOCKED`, false por defecto e independientes).

### ¿Qué cambia?

- **P1-01 — proyección, no autoridad:** `sim_auto_positions` pasa a ser un espejo de
  recuperación **reconstruible** desde el estado financiero canónico. Una proyección
  no puede autorizar por sí sola una compra; ante divergencia se reconstruye y, si no
  hay datos, se vetan aperturas (fail-closed).
- **P1-02 — aislamiento por cuenta:** migración `029_sim_auto_positions_account_scope`
  añade `account_id` a `sim_auto_positions` y rehace la PK a
  `(account_id, engine_id, symbol)`. Dos cuentas con el mismo engine/símbolo ya no
  colisionan en la misma fila.
- **P1-03 — identidad de ejecución namespaceada:** `venue_order_id` incorpora
  `engine_id` + `account_id` + `logical_order_id` único por intención
  (`auto_venue_order_id`). Dos cuentas no pueden compartir `execution_id`. La
  aleatoriedad del book deja de depender de la identidad del order (solo del contexto
  de mercado).
- **P1-04 — cuenta obligatoria:** sin `AUTO_ENGINE_SIM_ACCOUNT_ID` inequívoco el
  motor AUTO **no arranca** (fail-closed) y `auto_turn` veta con
  `account_id_required`; nunca una traza con `account_id=None`.
- **P2-01 — estado de protección durable:** la proyección persiste
  `entry_price`/`high_watermark`/`stop_price`/`t1_state`/`trailing_state`; tras un
  crash el worker readoptado no olvida el máximo (trailing correcto).
- **P2-02 — reconciliación SIM:** nuevo `sim_reconciliation.reconcile_sim_position`
  exige `ExecutionEvents == posición canónica == proyección`
  (`OK`/`REBUILT`/`DIVERGENT`/`UNKNOWN`).
- **P2-03 — batería de crash:** escenarios C3-F/G/H/I sobre las nuevas ventanas
  (finance/sim_position/journal/contexto/readopt).
- **P2-04 — Reina real:** test que arranca `python -m bolsa_api.workers.scheduler_worker`
  como proceso real con el spine determinista (sin `run_tick()` manual ni decider
  scripteado) e intervalo parametrizable por `AUTO_ENGINE_SIM_INTERVAL_SECONDS`.
- **P2-05 — invariante de equity:** el día AUTO se certifica con
  `assert_equity_invariant` sobre el ledger real (nuevo gate CI
  `AUTO_EQUITY_INVARIANT_PG_REQUIRED`).
- **P2-06 — honestidad de etiquetas:** `ProtectionConfig.exit_reason` evalúa el
  trailing antes que T1 cuando el máximo rebasó T1 (no etiqueta un trailing real como
  toma en T1); T1 **parcial** (`AUTO_ENGINE_SIM_T1_FRACTION`); `AutoDecisionEngine`
  lleva la edad **por símbolo** (no un contador compartido), de modo que
  `exit_after_ticks` es comparable entre watches de distinto tamaño.

### Estado

AUTO SIM-ONLY end-to-end con durabilidad/aislamiento cerrados. La siguiente capa
(ESTUDIO→LAB→COACH autónomo) es A10.

## [1.50.0-beta] — V2.23-beta / A9 · AUTO SIM-ONLY end-to-end — 2026-09-09

Composición real scheduler → `AutoSimRuntime` (stores PG + finanzas SIM por sesión),
Decision Spine determinista, RiskGate/SimulationGate en el camino AUTO, kill switch
fail-closed, posición durable básica (migración 028), protección SL/T1/trailing
inicial, journal tri-estado (`NOT_CHECKED` ≠ PASS) y gates PG fail-if-skipped.

## [1.49.0-beta] — V2.20-beta / A7 Iter-3 · hardening — 2026-09-09

Elevación de **hardening (Iter-3 de LIVE Certification / A7)** que cierra la
verificación **P1-01 — CAS no atómico** en `PostgresExecutionEventStore`
(`start_apply` no era un Compare-And-Swap real) y los huecos de concurrency /
recuperación que abría (dos-worker, C3-E, reaper de `APPLYING` stale,
contrato de cantidad en parciales, identidad de release). Núcleo financiero
congelado **intacto**: no añade features de trading.

### ¿Qué cambia?

- **P1-01 — CAS real atómico:** `PostgresExecutionEventStore.start_apply` /
  `mark_*` / `reclaim_stale_apply` pasan a un ÚNICO `UPDATE ... WHERE
execution_id AND status IN (orígenes-legales)` atómico con `rowcount`, sin la
  secuencia `SELECT → check-in-memory → ORM-mutate → commit`. `start_apply`
  incrementa `attempt_count` solo cuando gana y **NO acepta** el auto-origen
  `APPLYING` (`_cas_sources_of`), de modo que dos workers sobre el MISMO
  `CAPTURED` → exactamente uno `True` (`winner=1`) y otro `False` (`loser=0`).
- **Diseño single-owner por lease (1b):** migrate `025_execution_events_lease`
  añade `lease_owner` + `updated_at` a `execution_events` y un índice
  `(status, updated_at)`; un `APPLYING` huérfano (dueño caído, lease vencida)
  solo se retoma vía `reclaim_stale_apply` / `reclaim_stale_applying_batch`
  (reaper).
- **C3-E — crash tras commit financiero:** nueva escenario de la batería
  `live_a7` (worker SIGKILLeado tras `ExecuteTrade COMMIT` pero antes de
  `mark_applied`) → la traza queda `APPLYING` con dinero durable y la
  recuperación lo retoma por lease **sin segundo efecto** (`APPLIED`, no doble
  `ledger/position`).
- **Two-worker real-PG test:** `test_v220_two_workers_cas_exactly_one_owner`
  en `live_a7` demuestra sobre Postgres real que una sola de dos pasadas
  simultáneas de `start_apply` gana (`winner=1, loser=0`).
- **P2-02 — reaper de `APPLYING` stale (mecanismo + orquestador):**
  `reclaim_stale_applying_batch` (barrido atómico por lease vencido / dueño
  muerto) + orquestador `reap_stale_applying`: sobre un dueño garantizado-muerto
  lleva `APPLYING → APPLIED` (apply idempotente, UNA materialización) o a
  `RETRY` honesto cuando el candidato no es aún re-derivable, sin robar un
  `APPLYING` de lease VIVA. **Decisión safe-by-default (V2.20):** el substrato de
  lease + escenario real-PG se entregan verificados, pero **NO** se auto-enciende
  un sweep de fondo en el worker — reclamar por mera edad a un apply en curso
  (que no hace heartbeat entre `start_apply` y su `mark_applied`) podría robarle
  el APPLYING a un dueño vivo (lost-/double-apply). Cerrar la gestión automática
  plena requiere lease-renewal/heartbeat per-apply (Iter-4).
- **P2-03 — contrato de cantidad en parciales:** `filled_quantity` documentado
  y testeado como **delta por `fill_seq`** (no cumulativo): `40+30+30=100` son
  3 trazas idempotentes y suman el total. Sin cambio de comportamiento en
  espera del ruling del broker (puente XTB cumulativo-vs-delta sin confirmar).
- **P2-04 — identidad de release:** package `1.48.0-beta → 1.49.0-beta`.

### Verificación

- **Live (Postgres real dedicado):** la batería `apps/api-python/tests/chaos/live_a7`
  validada de nuevo con las semánticas de lease — **7 escenarios passed**:
  C3-A/B/C/D/E + `test_v220_two_workers_cas_exactly_one_owner`
  - `test_v220_stale_reaper_converges_orphaned_apply` (reaper real-PG).
- Ruff `apps/api-python packages/py` → limpio en los ficheros tocados. Suita
  unitaria de dominio (`test_execution_event.py` incl. los 2 nuevos de reaper,
  `test_recovery_apply.py` con el contrato `40+30+30`) → sin regresiones.

## [1.48.0-beta] — V2.18 / A7 Iter-1 · C3 — 2026-09-09

Elevación (completada: **Release-tag CI `#34341628713` GREEN** sobre `v2.18-beta` `conclusion: success`,
certify ✓, tag remoto en `bd2bd163`) de la **Iter-1 de LIVE Certification / A7**, **gated exclusivamente
al gap C3** (crash-injection): una batería **real-PG** de crash de **proceso real** sobre el worker de
recovery/scheduler que cierra el hueco que la Iter-0 (V2.17) dejó mapeado como 🔴.
Núcleo financiero congelado **intacto** (Alembic head `023_ohlcv_bars_unique_reconcile`, sin migración).
Como se decidió en V2.18 (`fsm_only`), C3 valida invariantes de **order-state/FSM** (≈ una resolución exacta,
sin doble transición ni doble materialización) y **NO** cash/position: la vertiente financiera del crash queda
reservada a Iter-2 bajo el roadmap XL-3 (A3/B2/P2-01 son los puentes hacia ella).

### ¿Qué cambia?

- **Home real-PG C3:** `apps/api-python/tests/chaos/live_a7/` con `test_c3_crash_injection_recovery_worker.py`
  (escenarios A/B) y harness de proceso `_crash_recovery_probe.py`. La batería lanza un **subproceso Python
  real** que reclama y resuelve UNKNOWN sobre `PostgresLiveOrderStore` + `live_order_recovery_worker.resolve_one_unknown`
  (el núcleo no se toca): en C3-A el proceso A es **SIGKILLeado con el claim FOR UPDATE en vivo** y un segundo
  proceso reaparece y resuelve **exactamente una vez**; en C3-B relanzar la recuperación tras un resolve durable
  no duplica (idempotencia del `put` + terminal-not-UNKNOWN). Falla-quieto → `financial_apply_count=0` en ambos.
- **CI:** job **`a7-gate`** en `.github/workflows/release-tag-ci.yml` — Postgres service + BD dedicada
  `bolsa_v1_a7` (drop+create, esquema a head por `ensure_migrated` idempotente en la propia batería) + pytest
  `chaos/live_a7` con `LIVE_A7_PG_REQUIRED=1` (fail duro si skip). `a7-gate` se suma a `needs` de `certify` y al
  resumen del artefacto.
- El job offline `python` (tag y `python-ci.yml`) y `lifecycle-pg`/iso quedan intactos; se añade
  `--ignore=.../chaos/live_a7` al pytest offline para mantenerlo hermético (A7 corre en `a7-gate`).

### Verificación

- **Elevación en GitHub:** **Release-tag CI `#34341628713` GREEN** sobre el tag remoto `v2.18-beta`
  (`conclusion: success`; `origin/main` en `bd2bd163`, sin ahead/behind). Jobs: `security (gitleaks)` ✓ ·
  `shared` ✓ · `decision-spine` ✓ · `python (ruff/imports/mypy/pytest offline)` ✓ · `frontend` ✓ ·
  `playwright (mock E2E)` ✓ · `dr-verify` ✓ · `lifecycle-pg` ✓ · [`a7-gate` (dedicated real-PG)] ✓ ·
  `certify (aggregate + artifact)` ✓. `playwright (integrated E2E)` skipped (opt-in, correcto para GREEN).
- Live (Postgres real dedicado): `apps/api-python/tests/chaos/live_a7` → **2 passed** (C3-A y C3-B) tanto en
  primera ejecución (migrando de cero) como en repetición.
- Ruff `apps/api-python packages/py` → limpio. Suites unitarias de worker:
  `test_live_order_recovery_worker.py` + `test_scheduler_worker.py` → **12 passed**.
- Relevo del ciclo (nuevo): `docs/engineering/traspaso-relevo-a7-iter1-c3-v2-18-beta-2026-09-09.md`;
  estado C3 actualizado en `docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md` (§1-ter/§3/§4/§5).

## [1.47.0-beta] — 2026-09-09

Elevación a `main` de la **Iter-0 de LIVE Certification / A7** (ciclo `v2.17-beta`), de acuerdo con el
veredicto de la **auditoría externa de V2.16.1**: P0=0 / P1=0 / Global 9.3 → abrir A7 y **no añadir
features**. Esta iteración es **SÓLO marco y mapa de gaps documental** (sin código ni tests nuevos):
mapea los 16 escenarios de certificación del auditor contra la cobertura ya existente y registra el home
futuro de la batería. Núcleo financiero congelado **intacto**. Alembic head `023_ohlcv_bars_unique_reconcile`.
Package **`1.47.0-beta`** (bump desde `1.46.1-beta`).

### Iter-0 A7 — entregable documental

- **Marco + gap-map:** [`docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md`](./docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md)
  — escenario a escenario (`🟢/🟡/🔴`) con evidencia ruta:línea y dobles a reutilizar.
- **Hallazgo P2-05 cerrado:** la incoherencia documental que marcó la auditoría (doc de relevo aún decía
  "sin push") ya fue resuelta por `b8858c2f` (SHA `1596f4ad`, tag `v2.16.1-beta`, CI `#34331846887` GREEN).
- **Home de la batería (Iter-1):** `packages/py/infrastructure/tests/chaos/live_a7/` (PG-real) con gate en
  el job `lifecycle-pg` del release-tag CI.
- **Backlog A7 (Iter-1+):** C3 crash-injection sobre `scheduler_worker` 🔴; A3 broker timeout/network
  real; B2 partial-fill → materialización; P2-01 Applied durable (APPLYING/APPLIED/FAILED).
- Deuda P3 C2 del núcleo sigue ACCEPTED sin tocar; la deuda pos-p3 `[runtime/aislamiento] LIVE A7` pasa a
  "Iter-0 en curso → Iter-1 backlog" (actualizado en `deuda-p3-nucleo-aceptada-c2-2026-09-09.md`).

### Verificación

Sin cambios de código: **Release-tag CI `#34334824584` GREEN** sobre `v2.17-beta` (`conclusion: success`,
certify ✓), tag remoto apuntando a `79df594c`. Relevo del ciclo:
[`docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md`](./docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md).

## [1.46.1-beta] — 2026-09-09

Elevación a `main` (tag **`v2.16.1-beta`**, commit `1596f4ad`, push a `origin/main`) del ciclo de
cierre de hallazgos residuales de la auditoría sobre `v2.16-beta`: owner-scoping de cuenta por
defecto (**P1-02/03**), **Auditoría 2** (fill_unseen tapado por cancel en el incidente `live_drift`) y
**Auditoría 3** (consentimiento del operador de ExecutionEvent en dos fases, sin salida).
Núcleo financiero congelado **intacto** (deuda P3 C2 aceptada como riesgo medido, ver
[`docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md`](./docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md)).
Package **`1.46.1-beta`** (bump desde `1.46.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**
(sin migración nueva).

### P1-02/P1-03 — owner-scoping del account default (`set_default_account`/`delete_simulated_account`)

- `set_default_account` y `delete_simulated_account` ya no tratan el `is_default` y la promoción
  de siguiente default de forma global-cuenta: se ciñen al **owner** que hace la operación
  (`owner_user_id` desde el principal autenticado en rutas), evitando sobrescribir el default de
  otro tenant o promover una cuenta activa ajena tras borrar un default.
- Rutas `accounts.py` pasan `owner_user_id` resuelto del principal; el purge administrativo
  del ciclo de vida usa `for_purge=True` (scope de sistema) pero la promoción de default sigue
  siendo owner-local (P1-03).
- CI iso: gate `account-isolation` real-PG **43 passed**.

### Auditoría 2 — el incidente `live_drift` ya no tapa un `fill_unseen` posterior

- Cuando una cuenta ya tiene un `live_drift` activo (abierto p. ej. por `cancel_broker_side`) y
  en un tick posterior el recovery entregar un drift de **firma nueva** (order/venue/subtipo,
  p. ej. `fill_unseen`), el snapshot del incidente vigente se **amplía** de forma idempotente
  por firma (`publish_order_live_drifts`, campo `merged`) en lugar de descartarlo con un
  `already_active` silencioso. Un drift ya registrado sigue siendo replay no-op. Nunca se crea
  un 2º OPEN ni se auto-heal.

### Auditoría 3 — consentimiento del operador de ExecutionEvent con salida real (dos fases)

- `apply_fill_idempotent` captura con idempotencia (1ª fase, `permit=False` no materializa).
  Nueva `apply_pending_execution(execution_id, apply_finance)` (2ª fase) retoma la traza ya
  capturada cuando llega el "go" y materializa Position/Ledger sin chocar con
  `duplicate_skipped`; `event_not_found` si la traza no existe (fail-closed) y
  `captured_not_applied` si el apply no fue efectivo (reintentable).

### Verificación

Unit (18 drift + execution) + regresión (60) verdes; e2 PG real en scratch `bolsa_c1_scratch`
(head 023, dedicated) **5/5**, incluido el merge `fill_unseen`; ruff CI-parity 0; mypy src 0.
Shared `bolsa_v1` intacta en 023.

**Release-tag CI `#34331846887` GREEN** sobre `v2.16.1-beta` (`conclusion: success`, certify ✓):
security · shared · decision-spine · lifecycle-pg · dr-verify · python (ruff/mypy/pytest) ·
frontend (+contract) · playwright (mock E2E). Integrated E2E opt-in skipped (no requisito de
GREEN). Repo dispuesto para **auditoría externa** sobre el tag `v2.16.1-beta`.

## [1.46.0-beta] — 2026-09-09

Elevación a `main` de `V2.15.4` (aislamiento account-less) + `V2.15.5` (DR industrial OHLCV/backup 3-2-1) en **un solo tag `v2.16-beta`**; núcleo financiero congelado intacto; sin migración nueva. Producto **BETA / no producción**.
Package **`1.46.0-beta`** (**bump** desde `1.45.3-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Tip: **`302a3220`** (V2.15.5) == código elevado; este commit es el bump/elevación.

### V2.15.4 — aislamiento account-less fiable (P1 C2-06)

Reads/writes **account-less no degradan a global**; sin cuenta propia quedan fail-closed, nunca asumen tenant del owner ajeno:

- `account_repository.resolve_default_account_for_owner`: el default activo visible al owner F7c (evita colapso `is_default` entre tenants).
- `resolve_account_scope_or_default`: `account_id` ajeno → 404; ausente → default del principal; sin cuenta propia → `None` (fail-closed).
- `ai_governance` reads (effectiveness, decision-sessions, learning-summary) y writes (decision-memory, trials, edge-reports, propose): account-less → default del principal; filas huérfanas `NULL` excluidas de listados.
- `investor_profiles` refresh-observed: valida el owner del account; account-less → default.
- CI: gate `account-isolation` real-PG en `lifecycle-pg` (fail-closed vía `certify`).
- Tests: 4 account-less 2-owners (23 ISO + ai_authoring 26 verdes real-PG).

### V2.15.5 — DR industrial: snapshot atómico + digest por bloques + OHLCV + C2-01 + backup 3-2-1/RPO-RTO

Alcance SOLO infraestructura DR (`scripts/`), núcleo financiero congelado:

- **Snapshot atómico `REPEATABLE READ`**: TODAS las tablas (financieras + mercado) se leen en **UNA** transacción `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; … COMMIT;` → imagen consistente. Parser arreglado (psql `-A` emite `|`, no tab) → el digest de tablas no vacías ya reporta cuenta real (antes 0/vacío y el cheque pasaba en vacío).
- **Digest por BLOQUES** (`CHUNK_SIZE=5000`, md5 por bloque ordenado + concat) en vez de `md5(string_agg total)` → memoria acotada y determinista; añade `MARKET_ENTITIES`: `ohlcv_bars` (167k, fuente de verdad), `instruments`, `data_sync_log`.
- **RTO** medido del restore + cobertura volcada a `logs/agent/db-dr-verify.json`.
- **C2-01** (`db-restore`): `--target-db` validado (`^[A-Za-z0-9_.-]+$`) **ANTES** del DDL destructivo.
- **Backup 3-2-1 + RPO/RTO**: espejo a dir env `DB_BACKUP_MIRROR_DIR` (2º medio/árbol) + manifest registra `mirror`; `db-backup-list` muestra RPO y estado espejo. (3er medio off-site: guía MVP de set-up, ver [`docs/engineering/guia-off-site-3er-medio-2026-09-09.md`](./docs/engineering/guia-off-site-3er-medio-2026-09-09.md).)
- `db-backup-cron-win`: tarea programada de **restore-test DR diario** (`db:dr:test` con volumen real) junto al backup diario.

### Verificación real

Batería DR local con volumen real (dump → checksum → restore a scratch → integridad md5 por bloques financiero+mercado) **verde** + aislamiento **43 passed** real-PG + `node --check` OK + C2-01 rechaza inyección antes del DDL (`bolsa_v1` intacta). Gate industrial del tag: job `dr-verify` del Release-tag CI (TCP, fail-closed vía `certify`).

## [1.45.3-beta] — 2026-09-08

Hardening de la auditoría **V2.15.1 C2** (delta en **scripts DR + CI del tag**; núcleo financiero congelado sin tocar; sin migración nueva). Producto **BETA / no producción**.
Package **`1.45.3-beta`** (**bump** desde `1.45.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Cierra tres hallazgos de la pasada anterior:

- **C2-02 (P2-alto)** — `scripts/db-dr-verify.mjs` extiende la batería DR con **invariantes financieras de datos**: inventario canónico de 18 tablas (`FINANCIAL_ENTITIES`, fuente `tables.py`), snapshot `COUNT(*)` + digest md5 del contenido canónico ordenado **BEFORE** sobre la principal y comparación **AFTER** sobre la scratch; checks `dr-snapshot-financiero-leido` y `dr-datos-financieros-integridad`. El restore deja de ser solo "estructural ↔ head" y pasa a ser **financieramente verificable**. (md5 en vez de sha256: `sha256()/encode` viven en `pgcrypto`, no en PostgreSQL 16 core por defecto al restaurar la scratch; md5 built-in basta como guard no-adversarial.)
- **C2-12 / C2-13 (P2/P3)** — la faena DR y el readiness schema-aware se elevan al **release-tag CI** para que certifiquen en el runner, no solo en local:
  - transport layer TCP opt-in `BOLSA_DR_TCP=1` (psql/pg*dump de host por `PGHOST/PGPORT/PGUSER/PGPASSWORD`/`DB*\*`) en `docker.mjs`/`backup.mjs`/`db-restore.mjs`/`db-dr-verify.mjs`, con **default Docker intacto** para dev.
  - job nuevo **`dr-verify`** en `release-tag-ci.yml` (`services: postgres:16-alpine` + `postgresql-client` + `alembic upgrade head` + batería DR por TCP), incorporado a `needs:`/fail-if/summary de `certify` → **un DR rojo rompe el tag**.
  - `apps/api-python/tests/test_health.py` (readiness `/health/ready` 200/503 schema-aware) entra en el pytest PG de `lifecycle-pg`.
    Validación local: `pnpm db:dr:test` (Docker) → **8/8 PASS**, incluidas las 2 checks nuevas C2-02. Certificación final del path TCP (runner) vía **Release-tag CI** de este tag.

## [1.45.2-beta] — 2026-09-08

Auditoría externa **V2.15.1 C2** (delta exclusivamente **documental/audit**; núcleo financiero sin tocar). Producto **BETA / no producción**.
Package **`1.45.2-beta`** (**bump** desde `1.45.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
V2.15.1 C2 re-certificada ≈ **9.1/10 Beta** (ver [`auditoria-v2-15-1-c2`](./docs/engineering/auditoria-v2-15-1-c2-2026-09-08.md)): los tres P1 de V2.15 cerrados; deudas P2/C2-12+13 (DR+readiness no corren en tag-CI) y C2-02 (invariantes financieras en batería DR) decididas antes del "OK final"; account isolation **P2-latente** (no P1-activo, single-owner). Cierres de esta pasada: C2-08 (cash paper/ledger idempotente real-PG, no P1 de doble-abono), C2-06 (sin path de creación por JWT; ops-self-eval cerrado), contrato FE↔BE núcleo **limpio**.

## [1.45.0-beta] — 2026-09-08

V2.15 **C2 · cierre de certificación** a `main` (restore seguro + readiness schema-aware + batería DR). Producto **BETA / no producción**.
Package **`1.45.0-beta`** (**bump** desde `1.44.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
Núcleo financiero (FSM/live_orders/ExecutionEvent/ledger/outbox/reconciliation) **congelado e intacto**. Relevo [`traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md`](./docs/engineering/traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md).

### Cierre certificación — restore 100 % seguro (P1 V2.15-01/02)

- **`db:restore`**: psql con `-v ON_ERROR_STOP=1` (cualquier error SQL ⇒ failed). Alembic tras el restore se dirige **siempre a `--target-db`** (reescritura de `DATABASE_URL` vía `redirectDatabaseUrlTo`), nunca a `bolsa_v1`. Aborta si el sidecar `.sha256` no coincide.
- `scripts/lib/db.mjs`: `runAlembicUpgrade({ databaseUrl })` + `redirectDatabaseUrlTo(db)`.

### Cierre certificación — readiness schema-aware (P1 V2.15-03)

- **`/api/health/ready`** exige `READY = PostgreSQL AND alembic_version == expected_head` (Alembic): 200/ready solo si ambos; 503 si la BD responde pero el esquema no está al head (fail-closed, nunca "ready" contra una BD vieja). Campo nuevo `schema_status`.
- `session.py::read_db_schema_current` (lee `alembic_version`, mensajes redactados).

### Batería DR y hardening de backups (P2)

- **`pnpm db:dr:test`** (`scripts/db-dr-verify.mjs`): vuelca, verifica checksum, restaura a scratch vía `db-restore --target-db`, comprueba head/esquema consultable y que `bolsa_v1` no cambia; limpia la scratch. GREEN en local.
- `backup.mjs`: sello con ms + escritura exclusiva (O_EXCL), sidecar `<file>.sha256`, `backups-manifest.json`, `DB_BACKUP_KEEP` mínimo ≥1.

### Tests y contrato

- `test_health.py`: ready 200-at-head + 503 schema-mismatch + 503 unmigrated. Contrato `openapi.json`/`schema.d.ts` regenerados (solo `schema_status` + descripciones).

## [1.44.0-beta] — 2026-09-08

V2.15 **1er ciclo de hardening** a `main` (PREVENCIÓN backups + provenance/readiness). Producto **BETA / no producción**.
Package **`1.44.0-beta`** (**bump** desde `1.43.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
**≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado. Relevo [`traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md`](./docs/engineering/traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md).

### Prevention — backups de `bolsa_v1` (faena 1)

- **`pnpm db:dump` / `db:backup`**: volcado local `db-backups/bolsa_v1-<stamp>.sql[.gz]` vía `docker exec pg_dump`
  (por fuera del contenedor) + poda por retención (`DB_BACKUP_KEEP`, default 14). `db:backup:list` lista.
- **`pnpm db:restore --file … --yes`**: recrea la BD destino y aplica el dump por stdin, re-aplicando Alembic head `023`.
  `--target-db` y `--no-alembic` para pruebas seguras. `db:backup:cron:win` genera tarea `schtasks` diaria.
- `.gitignore db-backups/` (no versiona), `.env.example DB_BACKUP_KEEP`, doc en `docs/DEV_STARTUP.md`.
  Motivo: [incidente pérdida de listas](./docs/engineering/traspaso-incidente-perdida-list-2026-09-08.md).
  Helpers [`scripts/lib/backup.mjs`](./scripts/lib/backup.mjs) · scripts `db-dump/db-restore/db-backup-list/db-backup-cron-win`.

### Hardening V2.15 — first cycle (provenance + readiness)

- **Readiness operacional**: nuevo `GET /api/health/live` (liveness sin BD) y `GET /api/health/ready`
  (readiness, PostgreSQL requerido → 200/ready o 503/not_ready). `/api/health` agregado compatible.
- **Provenance obligatoria en producción**: `require_release_identity_env()` eleva en `create_app` cuando
  `PRODUCT_VERSION`/`API_CONTRACT_VERSION` faltan en `ENVIRONMENT=production` (allowlist dev/test/staging
  las mantiene opcionales para no romper CI/local).
- Tests offline `test_provenance_gate.py` + tests `live/ready` en `test_health.py`; `openapi.json`/`schema.d.ts`
  regenerados (solo aditivo). Rama `stage/v2.15-backups-prevencion-2026-09-08` → merge PR **#59**.
  Núcleo congelado (FSM/live_orders/ExecutionEvent/ledger/outbox/recon) intacto.

## [1.43.2-beta] — 2026-09-08

V2.14.2 **elevation** (cierre A1: account-isolation ampliada a rutas de LECTURA/estudio) a `main`. Producto **BETA / no producción**. Package **`1.43.2-beta`** (**bump** desde `1.43.1-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Close — A1 account-isolation extendida a rutas de LECTURA/estudio (2026-09-08)

- **Cierre A1 residual (deuda del cierre V2.14.1).** Además de los gates de EJECUCIÓN ya aplicados
  (confirm/evaluate-exits/execute-auto/paper-desk-cycle), quedó la deuda de que los endpoints de
  **lectura/estudio/acount-scope** operaban sin `require_account_access` (solo explotable con ≥2.º
  owner real; hoy single-owner bootstrap). Al añadirse `require_owned_account_if_present`
  (`dependencies.py`), se bloquea (404) toda lectura/estudio que declare una `account_id` que no
  pertenezca al principal del request; `account_id` ausente (demo/global) se preserva para la UI.
- **Rutas gateadas con cuenta visible:**
  - `ai_governance.py`: `GET /ai/effectiveness`, `POST /ai/decision-memory`, `GET /ai/decision-sessions`,
    `GET /ai/decision-sessions/learning-summary`, `GET /ai/decision-sessions/{id}` + `/replay`,
    `POST /ai/decision-sessions/{id}/outcome`, `POST /ai/trials`, `POST /ai/edge-reports`,
    `POST /ai/recommendations/propose`.
  - `instrument_daily_opinions.py`: `POST /instrument-daily-opinions/query`,
    `GET /instrument-daily-opinions/auto-telemetry`, `POST /instrument-daily-opinions/auto-propose`,
    `POST /instrument-daily-opinions/eod-batch`.
  - `paper_desk.py`: `GET /paper-desk/daily-report`.
  - `risk.py`: `GET /risk/ops-self-eval`.
- Tests de aislamiento por cuenta añadidos en `apps/api-python/tests/test_account_isolation.py`
  (effectiveness/decision-sessions/ops-self-eval/daily-report → 404 cuenta ajena). En el informe de
  lectura A1 (`audit-interno-lectura-v2-14-2026-09-08.md`) el hallazgo A1 pasa de **[cerrado parcial]**
  a **[cerrado]** (la nota cross-account multi-owner sigue `[runtime-aislamiento]`: hoy único owner real).

## [1.43.1-beta] — 2026-09-08

V2.14.1 **hotfix elevation** (`provenance self-reported + contract G12/G13` · `A1 account-isolation` · `schema 023 reconcile`) a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`da181b76`](https://github.com/jvelasca/Bolsa_V1/commit/da181b76)** (cierre auditoría V2.14 · +hotfixes 2026-09-08). Package **`1.43.1-beta`** (**bump** desde `1.43.0-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Hotfix interno — reconciliación upsert OHLCV → schema `023_ohlcv_bars_unique_reconcile` (2026-09-08)

- **Schema-drift (auditoría interna V2.14):** `ohlcv_repository.upsert_bars` (`ON CONFLICT (instrument_id,timeframe,timestamp)`, cd451fea) exigía un índice único que las migraciones Alembic no creaban (solo PK id) → todo el sync de mercado abortaba (500, `InvalidColumnReference`), la BD quedaba sin barras y la UI mostraba listas vacías e "histórico no disponible". Añadida migración **`023_ohlcv_bars_unique_reconcile`** (+índice único declarado en `OhlcvBarRow`) y repoblado el histórico (44.7k barras 1d, 2021→hoy, para los 35 activos IBEX; freshness `current`). Guards tests real-PG/provenance actualizados a head `023`.

### Hotfix interno — provenance self-reported + contract gate G12/G13 (2026-09-08)

- `GET /api/health → provenance` (PRODUCT/PACKAGE/GIT_SHA/DB_SCHEMA/API_CONTRACT desde fuentes únicas, sin DB) · `bolsa_api.provenance` · `contract-check.ts` **G12** `OperationalIncidentV1` + **G13** `SubmitIntentListItemV1` · openapi.json/schema.d.ts regenerados y sincronizados.

### Hotfix interno — A1 account-isolation en rutas de EJECUCIÓN (2026-09-08)

- `require_account_access` en `POST /ai/intents/confirm`, `/position-policies/evaluate-exits`, `/position-automation/execute-auto`, `/paper-desk/cycle`. Rutas de LECTURA/estudio quedan sin gate (deuda residual A1, explotable solo con ≥2º owner real).

## [1.43.0-beta] — 2026-09-08

V2.14 **Financial Execution Core** elevation a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942)** (V2.14 elevation · 08/09 09:23 UTC). Package **`1.43.0-beta`** (**bump** desde `1.42.0-beta`). Tip previo **`v2.13-beta` → `da5c4b2a`** / `1.42.0-beta`. Alembic head **`022_live_orders_exec`**. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital · cancel XTB real **PARKED** (honest-boundary, cero POST en cancel). Capacidad técnica ≠ permiso operativo (separación deliberada). Provenance auto-reportada vía `GET /api/health → provenance`.

### V2.14 — Financial Execution Core

- **D0 foundation** [`b54c92d8`](https://github.com/jvelasca/Bolsa_V1/commit/b54c92d8): decree Financial Execution & Full Reconciliation.
- **B1** [`462a30cb`](https://github.com/jvelasca/Bolsa_V1/commit/462a30cb): `Decimal` al boundary financiero (order/cash/position query + drift) — P1-03/P2-02/P2-03.
- **B2** [`67867a04`](https://github.com/jvelasca/Bolsa_V1/commit/67867a04): lease configurable por env (P2-04) + cancel XTB **PARKED** (P2-05).
- **E1** [`f29e452c`](https://github.com/jvelasca/Bolsa_V1/commit/f29e452c): `ExecutionEvent` scaffold idempotente **GATED** (P1-01) + migración **`022_live_orders_exec`** + observabilidad `live_orders` (`attempt_count`/`last_error`/`claim_expires_at`).
- **E2 P2-2** [`2942fec1`](https://github.com/jvelasca/Bolsa_V1/commit/2942fec1): dedup **OPEN** multi-worker en `OperationalIncidentStore` PG (1 incidente, no 2).
- **E2 P2-01** [`0a44764b`](https://github.com/jvelasca/Bolsa_V1/commit/0a44764b): durable order-drift → `OperationalIncident` `live_drift` (gated).
- **E2 P1-02** [`660fbd83`](https://github.com/jvelasca/Bolsa_V1/commit/660fbd83): reconcile **POSICIÓN continuo** (LR-1) en tick recovery, gated.
- **E2 C1 real-PG** [`96778854`](https://github.com/jvelasca/Bolsa_V1/commit/96778854): batería REAL-PG dedup OPEN/drift frente a PostgreSQL.
- **C1 Release-tag CI** [`095a5ab1`](https://github.com/jvelasca/Bolsa_V1/commit/095a5ab1) → [`78dd3f9a`](https://github.com/jvelasca/Bolsa_V1/commit/78dd3f9a): head real-PG `022` + ruff-I001 whole-tree + fix mypy gate (3 errores) hallados por Release-tag CI real.
- **Elevation** [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942): V2.14 + bump `1.43.0-beta` — tip auditable desde GitHub.
- Docs: arranque auditor externo [`08cada82`](https://github.com/jvelasca/Bolsa_V1/commit/08cada82) (veredicto V2.13 sin P0/P1) · deuda hallazgos P2/P3 del audit ampliado V2.13 [`0a217468`](https://github.com/jvelasca/Bolsa_V1/commit/0a217468) · relevo de cierre [`c24bbb67`](https://github.com/jvelasca/Bolsa_V1/commit/c24bbb67).

## [1.42.0-beta] — 2026-09-07

V2.13 **live execution gates** + tip formal `v2.13-beta`. Producto **BETA / no producción**. Tip **`v2.13-beta` → `da5c4b2a`**. Package **`1.42.0-beta`** (**bump** desde `1.41.0-beta`). Alembic head **`021_live_orders_fin`**. Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.13 — live execution gates (concurrency + financial invariants + honest cancel + reconcile)

- **Baseline** [`34285584`](https://github.com/jvelasca/Bolsa_V1/commit/34285584): live execution gates — XL-3 concurrency + financial invariants + honest cancel + reconcile.
- **V2.13.1 rc** [`0dce2fa9`](https://github.com/jvelasca/Bolsa_V1/commit/0dce2fa9): honesty remediation (audit H1/H2/H4/H5) post-baseline.
- **V2.13.2 rc** [`656c8b37`](https://github.com/jvelasca/Bolsa_V1/commit/656c8b37): broker-query real (H6) + reconcile máquina `live_orders` (H7); docs cierre H3 [`0983391c`](https://github.com/jvelasca/Bolsa_V1/commit/0983391c).
- **Tip formal** [`da5c4b2a`](https://github.com/jvelasca/Bolsa_V1/commit/da5c4b2a): release `v2.13-beta` (`1.42.0-beta`) — broker-query real H6 + reconcile live_orders H7.
- **V2.13.3 rc CI fix** [`4039087f`](https://github.com/jvelasca/Bolsa_V1/commit/4039087f) · [`4c5dee57`](https://github.com/jvelasca/Bolsa_V1/commit/4c5dee57) · [`e4cfbabd`](https://github.com/jvelasca/Bolsa_V1/commit/e4cfbabd) · [`6e279e2d`](https://github.com/jvelasca/Bolsa_V1/commit/6e279e2d): lifecycle-pg fixtures head-guard a `021_live_orders_fin` (set-membership, no prefijo) + mock E2E live-virtual confirm seed a TRIGGERED tradePlan (CTA sandbox cero POST bridge) + revision corta `varchar32`.

## [1.41.0-beta] — 2026-09-07

V2.12 **XL-3 durable core** + scope-out `list_open_orders` / `cancel_order`. Producto **BETA / no producción**. Tip **`v2.12-beta`** → commit de release de esta entrada. Package **`1.41.0-beta`** (**bump** desde `1.40.0-beta`). Tip previo **`v2.11-beta` → `80e891c4`** / `1.40.0-beta` (**inmutable**). Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.12 — XL-3 durable core (live_orders PG + UNKNOWN recovery)

- **Tabla `live_orders`** (PK `order_id` · account_id · indicadores 8×) · migración **`020_live_orders`** idempotente (guards table/index; down `019_outbox_position_fifo`).
- **`PostgresLiveOrderStore`** durable cross-PID: put (insert/update) / get / delete / `list_unknown` / `list_open_orders` / `cancel_order`. Mapeo dominio↔fila 1:1 con `account_id`.
- **Worker `live_order_recovery_worker`** (por defecto ON · `LIVE_RECOVERY_WORKER_ENABLED`): cada tick relee `UNKNOWN` y resuelve vía `query_broker` (no re-POST). Fail-closed: sin cliente / `unavailable` / intraducible → la fila queda `UNKNOWN` (refresca `updated_at`). **Nunca** sintetiza `execute_trade`/ledger.
- **Scope-out V2.12:** `list_open_orders` (no terminales via `NON_TERMINAL_LIVE_STATUSES`, ordena `updated_at`, limita) y `cancel_order` (`CANCELLED` solo si el grafo lo permite; idempotente; `reason` documental). Real cancel round-trip XTB **PARKED** (honest-boundary; cero POST en cancel).
- Wiring: `scheduler_worker` arranca el worker; `dependencies.get_confirm_intent_use_case` inyecta `PostgresLiveOrderStore(session)`.
- Dominio `LiveOrder` (PY+TS) UNKNOWN first-class · no re-POST · PARTIAL qty · `account_id` en PY+TS.
- OR-6 fail-closed: live recon no medido → `LIVE_BLOCKED` / `live_unavailable`; adapter `None` → `live_adapter_not_wired` (vocab LR-1 `clean`).
- OE-1 cablea LR-1 + `liveAdapterWired` (bridge URL) en OR-6.
- Sandbox VIRTUAL: `XtbBrokerAdapter` sin unlock → `live_virtual_sandbox` (cero POST bridge); kill switch reconsultado en adapter.
- **Confirm wiring persist-only:** `LiveOrderCoordinator` registra la máquina tras submit LIVE `submitted`/`unknown` y la expone en `result["liveOrder"]`; PAPER/sandbox/rejected/executed(XL-2) no la tocan. Confirm orquestador sigue `<1100` líneas.
- Docs: [roadmap LIVE Execution](./docs/engineering/roadmap-live-execution-core-2026-09-07.md) · [honesty bridge](./docs/engineering/honesty-pack-xtb-bridge-external-2026-09-07.md) · relevo durable core [`traspaso-relevo-xl3-durable-core-2026-09-07.md`](./docs/engineering/traspaso-relevo-xl3-durable-core-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-12-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-12-beta-2026-09-07.md).

## [1.40.0-beta] — 2026-09-07

V2.11 Confirm LIVE VIRTUAL (UI honesty). Producto **BETA / no producción**. Tip **`v2.11-beta` → `80e891c4`**. Package **`1.40.0-beta`**. Tip previo **`v2.10.1-beta` → `a060af37`** / `1.39.1-beta` (inmutable). Release-tag CI tip **CERTIFICABLE** — [run 34027601775](https://github.com/jvelasca/Bolsa_V1/actions/runs/34027601775) `conclusion=success`. Confirm = firma. CTA live = **Firmar · Ejecutar en LIVE VIRTUAL (simulado)**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE capital. **NO MÁS PANELES** (híbrido dentro de Confirm · excepción owner). **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.11 — Confirm LIVE VIRTUAL

- Pasarela híbrida telegrama + por qué + banner **LIVE VIRTUAL · SIMULADO** en Confirm (`live-virtual-*`).
- CTA TS+PY honesty; badge manual ticket alineado.
- E2E mock `gp-e2e-live-virtual-confirm-mock`.
- Pack [`audit-pack-v2-11-live-virtual-confirm-2026-09-07.md`](./docs/engineering/audit-pack-v2-11-live-virtual-confirm-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-11-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-11-beta-2026-09-07.md) · arranque auditor [`arranque-auditor-v2-11-live-virtual-2026-09-07.md`](./docs/engineering/arranque-auditor-v2-11-live-virtual-2026-09-07.md).

## [1.39.1-beta] — 2026-09-05

V2.10.1 CI certification hotfix + tip de provenance. Producto **BETA / no producción**. Tip **`v2.10.1-beta` → `a060af37`**. Hotfix código **`7156169f`** (tests/selectores; **no** motor). Package **`1.39.1-beta`**. Tip previo **`v2.10-beta` → `6495dd5f`** (inmutable; Release-tag CI [33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `failure`). Código hotfix CI [33981998373](https://github.com/jvelasca/Bolsa_V1/actions/runs/33981998373) `success`. Release-tag CI tip **CERTIFICABLE** — [run 33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) `conclusion=success`. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. **PRODUCT FREEZE** en V2.10.1.

### V2.10.1 — CI GREEN / Certification Fix

- **Cluster A:** expand Daily Desk `no_operar` antes de assert deny stale.
- **Cluster B:** `sr-only` `position-decision-stop` / t1 / t2 con Journey HUD.
- Vitest copy alineado a cabina actual.
- Relevo [`traspaso-relevo-v2-10-1-ci-green-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-1-ci-green-2026-09-05.md) · relevo tag [`traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).

## [1.39.0-beta] — 2026-09-05

V2.9 Visual and Operational Certification + V2.10 Seed Ops. Producto **BETA / no producción**. Tip **`v2.10-beta`** (sin tip `v2.9-beta` aparte). Partida **`v2.8-beta` → `a9ec6424`**. Package **`1.39.0-beta`**. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. Release-tag CI **NO CERTIFICABLE** — [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure`.

### V2.9 — Visual and Operational Certification (2026-09-05)

- **V2.46–V2.51:** ARM chrome `autoActive` · `orphan_recovery_failed` visible · touch 44px · layout zoom 100/125/150 · snapshots/contraste `gp-e2e-v29` (pixel skip CI linux) · teclado cabina.
- Relevo [`traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md).

### V2.10 — Seed Ops (2026-09-05)

- **V2.52–V2.53:** seed birth Confirm + `signedStop` estructural → `PROTECTED` / Planificado · Journal `runtime.mfeMae` · `scripts/ops_seed_cabin_smoke`.
- Relevo [`traspaso-relevo-v2-10-seed-ops-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · runbook [`runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md`](./docs/engineering/runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).
- Relevo tag [`traspaso-relevo-tag-v2-10-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-beta-2026-09-05.md).

## [Unreleased]

### V1.60 — UX Mercado (tarjeta estrella DECISIÓN) (2026-09-02)

- **GP-V160-01..04:** tarjeta estrella `PositionOperationalStarCard` + `usePositionOperationalView` — POV canónico en panel DECISIÓN; T2_READY/T2_EXECUTED · RECONCILIATION_DRIFT · stopHistory colapsable · vitest + testids.
- Wire: `operativa-cockpit-card` · `mercadoCockpitPosicionPhaseLabel` · recon chip POV-aware.
- Spec [`spec-v160-ux-mercado-2026-09-02.md`](./docs/engineering/spec-v160-ux-mercado-2026-09-02.md) · relevo [`traspaso-relevo-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-60-ux-mercado-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-60-ux-mercado-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.60-beta` → `7ac8ad9b`**.

### V1.59 — E2E Integrated (FastAPI + PostgreSQL) (2026-09-02)

- **GP-V159-01..07:** suite integration pytest + `httpx.AsyncClient` + PG real (`@pytest.mark.integration`): trade/portfolio operational · paper-desk dry-run/gate · ops-self-eval recon · decision-journal · incident resolve/clear HTTP · execute-auto dry_run.
- **Harness:** `v159_harness.py` + skip sin PostgreSQL; complementa Golden Session pytest (no sustituye).
- **Fix colateral:** `opening_gate_seed` siembra serie plana 120d (elimina veto sanity split/dividendo en DS-05).
- Spec [`spec-v159-e2e-integrated-2026-09-02.md`](./docs/engineering/spec-v159-e2e-integrated-2026-09-02.md) · relevo [`traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-59-e2e-integrated-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.59-beta` → `b5c5c6ab`**.

### V1.58 — Adversarial Execution (2026-09-01)

- **GP-GOLDEN-DAY-ADV-01:** día PAPER encadenado (BUY → dup fill → T1 → crash replay → TRAIL → T2 network skip → retry → dup event → EXIT → recon clean) en `test_paper_desk_golden_day_adversarial.py`.
- **AdversarialSell:** `fail_next(n)` → `skipped`/`network_failure` sin consumir fill id; retry ejecuta.
- **P0b:** `execute_position_policy_auto` marca leg `failed` solo en `blocked`/`rejected`, no en transport skip.
- **GP-V158-STOP-CLOSED:** STRUCTURAL_STOP + `session=CLOSED` vende; T1 + CLOSED → `queue_next_session`. Hallazgo 22 rondas cerrado como contrato PAPER (sin encolar stop a apertura).
- Spec [`spec-v158-adversarial-execution-2026-09-01.md`](./docs/engineering/spec-v158-adversarial-execution-2026-09-01.md) · relevo [`traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-58-adversarial-execution-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.58-beta`**.

### V1.57 — Operational Truth (2026-09-01)

- **GP-V157-01:** `T2_EXECUTED` distinto de `T2_READY`; eventos T2 simétricos a T1; desk map `T2_*` → reduced.
- **GP-V157-02:** `buildStopHistory` incluye `protect` / `trail` / `reduce` / `override` / `stop`.
- **GP-V157-03:** `reconStatus === "drift"` → `RECONCILIATION_DRIFT` (TS + Python); cubo Mesa `requiere_accion`.
- **INV-01..10:** batería `test_inv_operational_truth.py`. Exhaustividad `assertNever` en proyección cognitiva.
- Spec [`spec-v157-operational-truth-2026-09-01.md`](./docs/engineering/spec-v157-operational-truth-2026-09-01.md) · relevo [`traspaso-relevo-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-57-operational-truth-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-57-operational-truth-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.57-beta`**.

## [1.56-beta] — 2026-09-01

Hardening Residuals post-V1.55. Producto **BETA / no producción**. Tag **`v1.56-beta`**. Partida **`v1.55-beta` → `c23091d9`**. Package congelado **`1.35.0-beta`**. Confirm/DEX/SubmitIntent **intactos**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE.

### V1.56 — Hardening Residuals (2026-09-01)

- **GP-SESSION-07e:** assert estricto `target2Leg.status == executed`; fix `apply_position_reduce` promueve T2 `triggered`→`executed` en cierre.
- **GP-SESSION-10r:** pytest drift → human `resolve` → `clear` solo recon clean; sin auto-heal.
- **GP-E2E-01..02:** Playwright smoke Journal (`/decision-journal`) + Consola (`/operational-console`); script `pnpm --filter @bolsa/web e2e`; skip default · `E2E_RUN=1` → 2/2.
- Relevo [`traspaso-relevo-tag-v1-56-beta-2026-09-01.md`](./docs/engineering/traspaso-relevo-tag-v1-56-beta-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-56-beta-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-56-beta-2026-09-01.md).
- Pre-flight: pytest GP **26** · shared **34** · web **29** · ruff OK · tsc OK.

## [1.16-beta] — 2026-08-26

Mesa desk V1.16–V1.19 (ADR-037 extensiones) + backend paralelo auditoría V1.15. Producto sigue **BETA / no producción**. Tag **`v1.16-beta` → `f16119b`**. Partida: **`v1.15-beta` → `fc2ed753`**. Spine **`pnpm test:decision-spine` = 485**. Pack: [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md). Confirm/DEX/SubmitIntent **intactos**. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. AUTO **off**.

### Docs — Pack auditor v116 Mesa desk (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md): stamp global · scorecard MD-1…5 · limitaciones P1/P2.
- Relevo tag [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-16-beta-2026-08-26.md) — tag `v1.16-beta` → `f16119b`.
- Spine verificado **485**. Limitaciones: chip DS-05 P1 · sanity E2E P1 · what-if sin gates · Libro showRoute post-tag.

### MD-1 — V1.16 Mesa desk cierre (Operational UX II)

- Cabecera operativa · matriz semántica 10 estados · FeatureErrorBoundary Mesa/Confirm/F3.
- Tests shared + web GREEN · smoke browser 5/5 documentado.
- Pendiente P1: chip DS-05 honesto (F1-H).
- Relevo [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v116-2026-08-26.md).

### MD-2 — V1.17 Posición + ticket Confirm

- `showRoute` cableado en `/mesa` · invalidación qty/precio F3 · ticket riesgo primero.
- Libro (`/operaciones`) fuera scope — post-tag.
- Relevo [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v117-2026-08-26.md).

### MD-3 — V1.18 Evolución + alertas

- Deltas Journal relevantes · panel alertas decisión · orden ADR-037 en `/mesa`.
- Relevo [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v118-2026-08-26.md).

### MD-4 — V1.19 What-if + ranking operable

- `sortMesaCandidatesOperable` · `projectMesaWhatIf` read-only · tests ranking.
- Gates reales what-if **fuera** tag (documentado).
- Relevo [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v119-2026-08-26.md).

### MD-5 — Backend paralelo (auditoría V1.15)

- Pickle SHA256 · prod allowlist · `PAPER_D_EXECUTE` Router gate · sanity→DS-05 API · EdgeReport · `require_role` doc.
- pytest **72** passed. `sanity_warnings` E2E runtime **P1 post-tag**.
- Relevo [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-backend-2026-08-26.md).

## [1.15-beta] — 2026-08-26

Operational UX — **Mesa · Hoy** (ADR-037). Home diaria `/mesa` compone Decision Board, portfolio, studies e incidentes sin endpoints nuevos. Nav: Mesa · Hoy → Trading → … · Consola ops → Herramientas. Journal: vista tabla simplificada + status 3 dimensiones. **BETA / no producción.** Sin cambios en Confirm, TradePlan, SubmitIntent ni DEX.

### Mesa · Hoy (V1.15 Operational UX)

- Ruta `/mesa` · redirect `/` → `/mesa` · ADR [`037-mesa-hoy-operational-ux.md`](./docs/adr/037-mesa-hoy-operational-ux.md).
- Compositor shared `mesa-hoy-model` · `mapMesaStatusDimensions` · tests.
- Secciones: incidentes → sesión → KPIs → atención → posiciones → candidatos → salud ops.
- Deep-links Journal ficha · Hoy strip adelgazado (top-3 + link Mesa).
- Plan [`plan-mesa-hoy-v115-2026-08-26.md`](./docs/engineering/plan-mesa-hoy-v115-2026-08-26.md).

## [1.13-beta] — 2026-08-26

Durable Execution v1.13 (D0 + DEX-1…DEX-5). Producto sigue **BETA / no producción**. Tag anotado **`v1.13-beta` → `c8d5800`** (Release tag CI GREEN). Partida: **`v1.12-beta` → `369b5d1`**. Spine **`pnpm test:decision-spine` = 483**. Pack: [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md). OR-2 cerrado vía DEX-1+DEX-2. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**. AUTO **off**.

### Docs — Pack auditor v113 Durable Execution (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md): stamp global · scorecard DEX-1…5 · candidatas post-v1.13.
- Relevo tag [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-13-beta-2026-08-26.md) — tag `v1.13-beta` al stamp.
- Spine verificado **483**. Cero thaw · cero UI Mesa · cero AUTO · cero broker.

### DEX-5 — Operational invariants (V1.13 Durable Execution)

- Kernel `paper_order`: qty > 0 en build · FILLED rechaza filled < 0 o filled > ordered.
- Predicados `operational_invariants.py` (qty · filled≤ordered · terminal · adverse_exposure).
- Property suite spine `test_dex5_operational_invariants.py` (6 invariantes; sin `hypothesis`).
- Spine **`pnpm test:decision-spine` = 483** (465 → 483).
- Pack v113 stampado en Unreleased Docs · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/plan-dex5-operational-invariants-2026-08-26.md) · relevo [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex5-operational-invariants-2026-08-26.md).

### DEX-4 — Confirm = orquestador (V1.13 Durable Execution)

- Paquete `bolsa_application/confirm/`: Identity · RiskGate · OpeningGate · ExitGate · Execution · SubmitIntent · PositionSync.
- `ConfirmRecommendationIntent` = orquestador fino (~922 líneas; pre ~1531). API pública y semántica OR-1…OR-4 / DEX-1…3 intactas.
- Tests spine `test_dex4_confirm_orchestrator.py` (2). Spine **`pnpm test:decision-spine` = 465**.
- Sin property suite (DEX-5) · sin pack v113 · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/plan-dex4-confirm-orchestrator-2026-08-26.md) · relevo [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

### DEX-3 — OperationalIncident / resolución recon (V1.13 Durable Execution)

- Kernel `OperationalIncident`: open → in_review → resolved → cleared. Resolve exige nota; clear solo si recon `clean`. Sin auto-heal.
- Alembic `014_operational_incidents` + `PostgresOperationalIncidentStore`. Un activo por `(account, kind)`.
- Opening veto `incident:unresolved` (incluso si el drift ya se fue). Exits ALLOW. Confirm / Fill / HTTP / Router cableados.
- Tests spine `test_dex3_operational_incident.py` + kernel analytics. Spine **`pnpm test:decision-spine` = 463**.
- Sin Confirm split · sin UI Mesa · sin pack v113.
- Plan [`plan-dex3-operational-incident-2026-08-26.md`](./docs/engineering/plan-dex3-operational-incident-2026-08-26.md) · relevo [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex3-operational-incident-2026-08-26.md).

### DEX-2 — Crash/restart cross-PID (V1.13 Durable Execution)

- Certificación: store/sesión A persiste → kill → store B fresco → Confirm `UNKNOWN` · 0 re-POST · mismos ids / mapeo venue.
- Tests spine `test_dex2_crash_restart_cross_pid.py` (5). Spine **`pnpm test:decision-spine` = 440**.
- Sin Incident UI · sin Confirm split · sin pack v113.
- Plan [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/plan-dex2-crash-restart-cross-pid-2026-08-26.md) · relevo [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

### DEX-1 — PostgreSQL SubmitIntent (V1.13 Durable Execution)

- Alembic `013_submit_intents` + `SubmitIntentRow` + `PostgresSubmitIntentStore` (commit en put/delete).
- Fases `recorded` → `send_attempted` → `venue_bound`/`filled` + `send_attempted_at`; espejo TS.
- Confirm: put recorded → mark send_attempted → `adapter.submit`; fila durable ⇒ no re-POST.
- DI Confirm → store PG; InMemory en unit tests. Sin DEX-2 kill · sin Incident · sin Confirm split.
- Plan [`plan-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/plan-dex1-pg-submit-intents-2026-08-26.md) · relevo [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

### Docs — Auditoría v1.12 → V1.13 Durable Execution (2026-08-26)

- Triage externo post-`v1.12-beta`: OR-2 **PARTIAL** (InMemory ≠ cross-PID). Tag `v1.12-beta` intacto.
- Roadmap V1.13 DEX-1…DEX-5 · plan DEX-1 PG `submit_intents` · relevo apertura.
- ADR-035 §8 post-audit · `CURRENT_SYSTEM` next = DEX-1 (cerrado en Unreleased DEX-1; DEX-2 cerrado → next DEX-3).

## [1.12-beta] — 2026-08-26

Operational Reliability v1.12 (D0 + OR-1…OR-6). Producto sigue **BETA / no producción**. Tag anotado **`v1.12-beta` → `369b5d1`** (Release tag CI GREEN). Partida: **`v1.11-beta` → `76d0f951`**. Spine **`pnpm test:decision-spine` = 433**. Pack: [`audit-pack-estado-global-2026-08-26-v112.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v112.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**.

### OR-6 — SEMI operational certification (v1.12)

- Readiness discreto `PAPER_READY` / `PAPER_DEGRADED` / `LIVE_EXPERIMENTAL` / `LIVE_BLOCKED` (un FAIL crítico no se promedia; AUTO no entra).
- CTA firma `Ejecutar en PAPER|LIVE` + badge LIVE; chip mesa aparte del Autoeval OE-1.
- UI preferencia Paper|Live por cuenta (PA-1 API).
- Spine **`pnpm test:decision-spine` = 433** (post-OR-5 = 418).
- ADR-035 · plan [`plan-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/plan-or6-semi-operational-certification-2026-08-26.md) · relevo [`traspaso-relevo-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/traspaso-relevo-or6-semi-operational-certification-2026-08-26.md).
- **No** thaw estricto · **no** AUTO on · **no** Alembic · **no** `contract:gen`.

### OR-5 — Broker execution scenario suite (v1.12)

- Certificación spine A–L + retry (OR-1) + crash (OR-2) en `test_or5_broker_execution_scenarios.py`.
- Ancla en `pnpm test:decision-spine`. Paper/mock; sin live accepted; sin mass sim.
- Spine **`pnpm test:decision-spine` = 418** (post-OR-4 = 403).
- ADR-035 · plan [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/plan-or5-broker-execution-scenario-suite-2026-08-26.md) · relevo [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md).
- **No** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen` · **no** simulación 1k–10k.

### OR-4 — Reconciliation → opening veto (v1.12)

- `check_opening`: OI-6 `drift` → DENY aperturas; LR-1 `drift`/`unavailable` → DENY solo venue **live**; exits (`exit`/`exit_hint`/`reduce`) ALLOW.
- Confirm / Fill / HTTP gated / Router cablean puertos recon; fail-closed si lookup lanza. Sin auto-heal · sin UI resolución.
- OE-1: OI-6 status honesto (`ok`/`drift`/`error`/`unavailable`; ya no `not_wired` fijo).
- Spine **`pnpm test:decision-spine` = 403** (post-OR-3 = 387).
- ADR-035 · plan [`plan-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/plan-or4-recon-opening-veto-2026-08-26.md) · relevo [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/traspaso-relevo-or4-recon-opening-veto-2026-08-26.md).
- **No** suite A–L (OR-5) · **no** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen`.

### OR-3 — Full order state machine (v1.12)

- `PaperOrderStatus`: `CREATED` | `SUBMITTED` | `ACK` | `PARTIAL` | `FILLED` | `REJECTED` | `CANCELLED` | `EXPIRED` | `UNKNOWN` + grafo `ALLOWED_TRANSITIONS` (PY/TS).
- PaperBroker: `CREATED` → `SUBMITTED` pre-send → `FILLED` ok; boom → `UNKNOWN` (no deja CREATED «como si no enviada»).
- Crash recovery OR-2: `paperOrder.status = UNKNOWN`. Campo opcional `filledQuantity` para PARTIAL.
- Spine **`pnpm test:decision-spine` = 387** (post-OR-2 = 382).
- ADR-035 · plan [`plan-or3-order-state-machine-2026-08-26.md`](./docs/engineering/plan-or3-order-state-machine-2026-08-26.md) · relevo [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./docs/engineering/traspaso-relevo-or3-order-state-machine-2026-08-26.md).
- **No** veto recon (OR-4) · **no** suite A–L (OR-5) · **no** OCO · **no** `contract:gen`.

### OR-2 — Crash/restart recovery (v1.12)

- Confirm: `DurableSubmitIntent` persistido **antes** de `adapter.submit` (fail-closed si `put` falla).
- Sin fill local y con intento durable → `ExecutionRecord unknown` reconstruido (`crashRecovery`); **no** segundo `adapter.submit`.
- Mapeo `intent_id` ↔ `venue_order_id` (retry live `submitted` = 1 send). Fill local (OR-1) sigue ganando.
- Store = puerto + InMemory de proceso (sin Alembic). Tabla PG / Redis multi-worker parked en v1.12.
- **Post-audit `v1.12-beta`:** estado **PARTIAL** — no sobrevive al PID; PG = DEX-1 (V1.13).
- Spine **`pnpm test:decision-spine` = 382** (post-OR-1 = 372).
- ADR-035 · plan [`plan-or2-crash-restart-2026-08-26.md`](./docs/engineering/plan-or2-crash-restart-2026-08-26.md) · relevo [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./docs/engineering/traspaso-relevo-or2-crash-restart-2026-08-26.md).
- **No** OR-3 state machine · **no** veto recon (OR-4) · **no** `contract:gen`.

### OR-1 — End-to-end idempotency (v1.12)

- Confirm paper: clave canónica = `decision_id` (sin fallback `confirm-{uuid}`); sin `decision_id` → `error` / `decision_id_required` pre-send.
- `intent_id` / `PaperOrder.order_id` estables (`INT-{slug}` / `ORD-{slug}`) derivados de `decision_id`.
- Short-circuit pre-`adapter.submit` si ya hay fill local (`ExecuteTrade.find_existing_by_idempotency`); replay sin segundo submit ni journal `executed` duplicado.
- Spine **`pnpm test:decision-spine` = 372** (partida v1.11 = 367).
- ADR-035 · plan [`plan-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/plan-or1-e2e-idempotency-2026-08-26.md) · relevo [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/traspaso-relevo-or1-e2e-idempotency-2026-08-26.md).
- **No** Alembic · **no** `contract:gen` · **no** OR-2/OR-3/OR-4 en esta rebanada.

## [1.11-beta] — 2026-08-26

Operational Integrity v1.11 (OI-1…OE-1). Producto sigue **BETA / no producción**. Tag anotado **`v1.11-beta` → `76d0f951`** (Release tag CI GREEN). Partida: **`v1.10-beta` → `047ddb6`**. Spine **`pnpm test:decision-spine` = 367**. Pack: [`audit-pack-estado-global-2026-08-26-v111.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v111.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**.

### OI-1 — Continuidad operativa (v1.11)

- **Manual trade:** `POST /portfolio/trade` y pending sin plan nacen PositionState con override `human_manual`.
- **Pending SELL / manual sell:** cierran o reducen Position persistida vía `post_fill_position_sync`.
- **Confirm honesty:** fill ejecutado no se reporta como error si falla persist/journal posterior (`positionPersist`).
- **Proteger:** Confirm persiste stop operativo (H2); botón «Confirmar protección»; cero ledger.
- **Lab:** `evaluate-exits` con `executeTrades` persiste exit si `trade_executed` (Lab ≠ mesa).
- ADR-034 · plan [`plan-oi1-continuity-2026-08-26.md`](./docs/engineering/plan-oi1-continuity-2026-08-26.md) · spine **273**.

### OI-2 — Risk signature honesty (v1.11)

- **SEMI opening:** `risk_signature` con `require_triggered_plan` — sin TradePlan TRIGGERED → `rejected_by_gate` / `no_tradeplan`.
- **Manual HTTP:** sin cambio (no pasa por `risk_signature`).
- **UI:** copy `no_tradeplan` en F3 risk block y supervised panel.
- Plan [`plan-oi2-risk-signature-honesty-2026-08-26.md`](./docs/engineering/plan-oi2-risk-signature-honesty-2026-08-26.md) · spine **274**.

### OI-3 — ExecutionRecord UNKNOWN ≠ ERROR (v1.11)

- **Confirm:** excepción de `execute_trade` → `trade.status=unknown` + `executionRecord.outcome=unknown` (nunca `error`, nunca `rejected_by_gate`).
- **Gate/skip** antes de enviar → `not_executed`. Fill OK + persist falla → `executed` (OI-1).
- **UI/HELP:** copy «no asumir que no se ejecutó».
- Plan [`plan-oi3-execution-record-2026-08-26.md`](./docs/engineering/plan-oi3-execution-record-2026-08-26.md) · spine **283**.

### OI-4 — PaperOrder CREATED→FILLED (v1.11)

- **Confirm / FillPending:** al enviar nace `paperOrder` CREATED; fill → FILLED. Gate/skip → no hay orden. Excepción de envío → CREATED (fill no confirmado).
- **UI/HELP:** CREATED ≠ FILLED; orden creada no es fill. Venue PAPER ≠ broker.
- Plan [`plan-oi4-order-lifecycle-2026-08-26.md`](./docs/engineering/plan-oi4-order-lifecycle-2026-08-26.md) · spine **291**.

### OI-5 — Position revisions (v1.11)

- **PositionRevision:** historia append-only de stop/status en `PositionState.revisions` (JSON snapshot).
- **applyCurrentStop / applyReduce:** append solo si hay cambio real; mark no; protect → `origin=protect`.
- **UI/HELP:** stop/status con historia auditada; Proteger deja huella.
- Plan [`plan-oi5-position-revisions-2026-08-26.md`](./docs/engineering/plan-oi5-position-revisions-2026-08-26.md) · spine **306**.

### OI-6 — Portfolio reconciliation (v1.11)

- **PortfolioReconciliation:** detect/report cash ↔ ledger ↔ holdings ↔ PositionState (OPEN). Add-on / holding sin OPEN → `expected`.
- **No** auto-heal · **no** broker · **no** Alembic · ≠ ADR-021 DÍA D.
- Use-case `ReconcilePortfolioIntegrity` + spine tests.
- Plan [`plan-oi6-reconciliation-2026-08-26.md`](./docs/engineering/plan-oi6-reconciliation-2026-08-26.md) · spine **317**.

### PaperBroker — venue PAPER (v1.11)

- **PaperBroker.submit:** CREATED → ledger fill → FILLED; excepción → CREATED + `unknown`.
- Confirm / FillPending adjuntan `paperOrder` + `paperBroker` (`venue: PAPER`, ≠ broker live).
- **No** `IBrokerAdapter` · **no** broker live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-paperbroker-2026-08-26.md`](./docs/engineering/plan-paperbroker-2026-08-26.md) · spine **322**.

### BrokerAdapter — puerto Paper | Live (v1.11)

- **IBrokerAdapter:** Confirm / FillPending envían por el puerto (default paper = PaperBroker).
- **Mock LIVE:** `not_wired` — nunca llama `execute_trade` (≠ broker live / XTB).
- Receipt `brokerAdapter` (`venue: PAPER|LIVE`). Gate/skip → sin receipt.
- **No** live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-brokeradapter-2026-08-26.md`](./docs/engineering/plan-brokeradapter-2026-08-26.md) · spine **331**.

### PH-1 — Confirm protect honesty (v1.11)

- **Proteger:** si H2/`persist` → `None` (o excepción), Confirm no dice `protect_applied`. `skipped` / `stop_not_applied`. Cero ledger: el éxito es persistir.
- **UI:** log «stop no aplicado»; no saca de cola ni graba mandato.
- Plan [`plan-confirm-protect-honesty-2026-08-26.md`](./docs/engineering/plan-confirm-protect-honesty-2026-08-26.md) · spine **334**.

### XL-1 — Broker live XTB (v1.11)

- **XtbBrokerAdapter:** `venue: LIVE`, `adapter: xtb`; POST bridge `/orders`.
- Fail-closed: mock `live_orders_disabled`; `submitted` ≠ fill.
- Confirm/FillPending: rejected→skipped; submitted→unknown `live_submitted_no_fill`; pending intacta.
- **No** thaw `PAPER_D_EXECUTE` · mesa default paper.
- Plan [`plan-broker-live-xtb-2026-08-26.md`](./docs/engineering/plan-broker-live-xtb-2026-08-26.md) · spine **341**.

### LR-1 — Live reconciliation (v1.11)

- **LiveLedgerReconciliation:** live cash/positions ↔ ledger; `clean`/`drift`/`unavailable`.
- Detect/report only · **no** heal · **no** trade · bridge `GET /account/cash|positions`.
- Plan [`plan-lr1-live-reconciliation-2026-08-26.md`](./docs/engineering/plan-lr1-live-reconciliation-2026-08-26.md).

### XL-2 — XTB fill → ledger (v1.11)

- Bridge `filled` (opt-in FILL) → `execute_trade` → Confirm/FillPending `executed`.
- `submitted` sigue ≠ fill · boom → `unknown` (OI-3).
- Plan [`plan-xl2-xtb-fill-ledger-2026-08-26.md`](./docs/engineering/plan-xl2-xtb-fill-ledger-2026-08-26.md).

### VS-1 — Venue selector Paper | Live (v1.11)

- `BROKER_VENUE` + runtime · DI Confirm/FillPending · mesa toggle Paper|Live.
- Live → Xtb (sin URL → `not_wired`) · default paper · ≠ thaw `PAPER_D_EXECUTE`.
- Plan [`plan-vs1-venue-selector-2026-08-26.md`](./docs/engineering/plan-vs1-venue-selector-2026-08-26.md) · spine **362**.

### RV-1 — Redis persist broker venue (v1.11)

- Key `bolsa:risk:broker_venue` · coalesce `memory ?? redis ?? env ?? paper` · DI async.
- Per-account venue **parked**. Plan [`plan-rv1-redis-venue-2026-08-26.md`](./docs/engineering/plan-rv1-redis-venue-2026-08-26.md).

### JP-1 — PositionState JSONB → columnas hot (v1.11)

- Alembic `012`: `direction` · `current_stop` · `remaining_quantity` · `quantity` · `initial_stop` · `actual_entry`.
- Dual-write + backfill; JSONB `position_state` sigue SoT. Plan [`plan-jp1-position-jsonb-columns-2026-08-26.md`](./docs/engineering/plan-jp1-position-jsonb-columns-2026-08-26.md).

### Thaw stamp — `PAPER_D_EXECUTE` DEMO opt-in (v1.11)

- Docs/ops: DEMO opt-in **autorizado**; repo default **OFF**; ≠ venue Live · ≠ thaw estricto P1–P5.
- Plan [`plan-thaw-paper-d-execute-stamp-2026-08-26.md`](./docs/engineering/plan-thaw-paper-d-execute-stamp-2026-08-26.md).

### PA-1 — Preferencia venue por cuenta (v1.11)

- `settings_json.brokerVenue` (`paper`|`live`); coalesce `memory ?? redis ?? account ?? env ?? paper`.
- Lazy Confirm/Fill; mesa/API risk = override **global**. UI preferencia cuenta **opcional**.
- Plan [`plan-pa1-per-account-venue-2026-08-26.md`](./docs/engineering/plan-pa1-per-account-venue-2026-08-26.md).

### OE-1 — Ops Autoeval SEMI·AUTO (v1.11)

- `GET /api/risk/ops-self-eval` + `scripts/ops_operativa_self_eval.mjs` + chip mesa. Measure ≠ Accept.
- Recon OI-6 en informe `not_wired`. Plan [`plan-oe1-ops-autoeval-2026-08-26.md`](./docs/engineering/plan-oe1-ops-autoeval-2026-08-26.md).

## [1.10-beta] — 2026-08-25

Operational Authority v1.10 (H1→P4 Consola de Mesa P4.1+P4.2). Producto sigue **BETA / no producción**. Tag anotado **`v1.10-beta` → `047ddb6`** (Release tag CI GREEN). Partida: **`v1.9-beta` → `7d90d965`**. Spine **`pnpm test:decision-spine` = 260**. Shared **156**. Pack: [`audit-pack-estado-global-2026-08-25-v110.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v110.md). **No** broker · **No** auto-exit CTA producto · thin 5.x/8.x congelados · Confirm = única firma.

### P4 — Consola de Mesa (P4.1 + P4.2)

- Operaciones enriquecido (R, stop, T1/T2, salida advisory); CTAs Revisar/Reducir/Salir → cola Confirm; barra operativa; cola entradas read-only; «No operar hoy» → Journal; barra estado global; filtros cola; Proteger + preview stop en Confirm.
- Plan: [`plan-p4-consola-mesa-2026-08-25.md`](./docs/engineering/plan-p4-consola-mesa-2026-08-25.md) · ADR-033 §7.

### P3 — Una cadena de salida

- Confirm SEMI `exit_hint`/`reduce`: ExitPlan (`manual`) → ExitPermission → fill. Motivo `exit_permission`. Persist `applyReduce`. Operaciones: columna Salida advisory (sin CTA). Lab `evaluate-exits` intacto.
- Plan: [`plan-p3-cadena-salida-2026-08-25.md`](./docs/engineering/plan-p3-cadena-salida-2026-08-25.md) · ADR-033 §4.

### P2 — Riesgo al firmar

- Ticket F3: qty/stop/pérdida €/R del TradePlan TRIGGERED. % caja deja de ser SoT. Override con motivo. Gate Confirm `risk_signature`.
- Plan: [`plan-p2-riesgo-al-firmar-2026-08-25.md`](./docs/engineering/plan-p2-riesgo-al-firmar-2026-08-25.md) · ADR-033 §6.

### P1 — Position durable + wire fill

- Alembic `011`: tabla `position_states` (snapshot TradePlan + PositionState + `open_transaction_id`). Ledger `positions` intacto.
- Wire: Confirm SEMI apertura y FillPendingOrder (si hay snapshot) → `from_fill` (H2). Operaciones muestra stop / T1 / T2.
- Plan: [`plan-p1-position-durable-2026-08-25.md`](./docs/engineering/plan-p1-position-durable-2026-08-25.md) · ADR-033 §2.

### H2 — Invariantes factories

- Guards ADR-033 §5 en factories TS+Py: `from_fill` exige TRIGGERED (o override); stop no empeora; T2 no ataja T1; short close=`buy`; kill switch asimétrico.
- Cero Alembic · cero wire Confirm · cero UI mesa.
- Plan: [`plan-h2-invariantes-factories-2026-08-25.md`](./docs/engineering/plan-h2-invariantes-factories-2026-08-25.md) · ADR-033.

### H1 — Honesty pending ≠ stop

- UI/HELP: «Orden pendiente a precio» (antes Stop/Limitada). Solo `limitPrice`; no es stop de posición.
- Plan: [`plan-h1-honesty-pending-2026-08-25.md`](./docs/engineering/plan-h1-honesty-pending-2026-08-25.md) · ADR-033.

### Docs — Operational Authority v1.10 (D0)

- Triage auditoría de discontinuidad decisión→posición: factories F1–F4 ≠ autoridad viva; ADR-033 + roadmap v1.10.
- [ADR-033](./docs/adr/033-operational-authority-position-persistence.md) docs-only · [roadmap v1.10](./docs/engineering/roadmap-v110-operational-authority-2026-08-25.md) · fase v1.10 cerrada en tag.

## [1.9-beta] — 2026-08-25

Operational Core v1.9 (modelo post-entrada) + INFRA CI-by-tag. Producto sigue **BETA / no producción**. Tag anotado **`v1.9-beta` → `7d90d965`**. Partida: **`v1.8.1-beta` → `e78fbb9`**. Spine **`pnpm test:decision-spine` = 217**. Shared **134**. Pack: [`audit-pack-estado-global-2026-08-25-v19.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v19.md). **No** broker · **No** auto-exit producto · thin 5.x/8.x congelados.

### ExitPermission (Operational Core)

- Gate puro `checkExitPermission` / `check_exit_permission` (TS + Py): ALLOW/DENY post-ExitPlan.
- Reasons: `not_actionable` · `position_closed` · `kill_switch` · `broker_not_allowed` · `paper_auto_env_blocked` · `execution_blocked` · `missing_exit_plan`.
- **≠** `check_opening` · **≠** auto-exit · **≠** ExecuteTrade · sin wire Confirm / EvaluatePositionExits.
- Plan: [`plan-exit-permission-2026-08-25.md`](./docs/engineering/plan-exit-permission-2026-08-25.md).

### INFRA — CI reproducible por tag

- Workflow [`.github/workflows/release-tag-ci.yml`](./.github/workflows/release-tag-ci.yml): `on: push tags v*` **sin** path-filter + `workflow_dispatch`.
- Gates: gitleaks · shared · `test:decision-spine` · frontend · python offline · job `certify` + artefacto summary.
- Path-filters diarios (`frontend-ci` / `python-ci`) **intactos**.
- Plan: [`plan-infra-ci-by-tag-2026-08-25.md`](./docs/engineering/plan-infra-ci-by-tag-2026-08-25.md).

### F4 — ExecutionPlan → PAPER (Operational Core)

- Objeto nuevo `ExecutionPlan` (TS + Py): factory `buildExecutionPlanFromExitPlan` / `build_execution_plan_from_exit_plan`.
- `venue: PAPER` · status `DRAFT`/`PAPER_READY`→`JOURNALED`→`REPLAYED`→`VALIDATED` · broker → `BLOCKED`.
- Stages puros (refs opcionales, sin I/O). **No** ExecuteTrade · **No** `PAPER_D_EXECUTE` on · **No** OCO.
- Plan: [`plan-f4-execution-plan-paper-2026-08-25.md`](./docs/engineering/plan-f4-execution-plan-paper-2026-08-25.md).

### F3 — ExitPlan (Operational Core)

- Objeto nuevo `ExitPlan` (TS + Py): factory `buildExitPlanFromPosition` / `build_exit_plan_from_position`.
- Razones canónicas · status `IDLE`/`HINT`/`ARMED`/`TRIGGERED`/`DONE` · `suggestedAction` advisory.
- Plan: [`plan-f3-exit-plan-2026-08-25.md`](./docs/engineering/plan-f3-exit-plan-2026-08-25.md).

### F2.1 — PositionState transitions

- API pura `applyMark` / `applyReduce` / `applyCurrentStop` (TS + Py).
- Plan: [`plan-f2-1-position-state-transitions-2026-08-25.md`](./docs/engineering/plan-f2-1-position-state-transitions-2026-08-25.md).

### F2 — PositionState (Operational Core)

- Factory `build_position_state_from_fill` / `buildPositionStateFromFill` → `OPEN`.
- Plan: [`plan-f2-position-state-2026-08-25.md`](./docs/engineering/plan-f2-position-state-2026-08-25.md).

### F1 — TradePlan v1 (Operational Core)

- Campos gap ADR-032 §1 **dentro** de TradePlan.
- Plan: [`plan-f1-tradeplan-v1-2026-08-25.md`](./docs/engineering/plan-f1-tradeplan-v1-2026-08-25.md).

### Docs — auditoría externa v1.8.1 + diseño v1.9

- Consolidación v1.8.1 **cerrada** por auditoría externa. Triage: [`audit-ext-v181-triage-2026-08-25.md`](./docs/engineering/audit-ext-v181-triage-2026-08-25.md).
- ADR-032 + gap + roadmap v1.9. **F1–F4 + ExitPermission + INFRA** en este tag; broker adapter sigue no.

## [1.8.1-beta] — 2026-08-25

Operational Consolidation post-`v1.8.0-beta`. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.1-beta` → `e78fbb9`**. Partida: **`v1.8.0-beta` → `8c8b789`**. Spine battery **`pnpm test:decision-spine` = 161**. Pack: [`audit-pack-estado-global-2026-08-25-v181.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v181.md). **No** módulos thin nuevos. **No** PositionState/ExecutionPlan (ADR-032 docs-only).

### Ciclo C4 — TradePlan shape canónico

- Hoy `readCanonicalTradePlan`: canónico sesiones = `session.tradePlan`; F3 = `extra.payload.tradePlan`. Fallbacks (`extra.tradePlan`, payload top-level) marcados `legacy`, no borrados.
- `HoyQueueItem.planSource`: `live` (objeto TradePlan en canónico o fallback permitido) | `projection` (sin plan → C1 WATCH, nunca BUY/ARMED).
- **No** Pydantic DTO · **no** OpenAPI · **no** `contract:gen` (contrato fuerte = ADR-032 / v1.9). Confirm/propose/spine/`check_opening` intactos. C1/C3/C5 intactos.

### Ciclo C5 — MFE/Expectancy honesty

- `MfeMae.source`: `bars` | `close_proxy` | `none`. Hoy Excursión añade sufijo `proxy` si close_proxy. Proxy no se presenta como peak de barras.
- Expectancy `sampleQuality`: insufficient (n<20) / preliminary (20–49) / developing (50–99) / useful (n≥100). `status: ready` (READY_MIN_N=5) no significa estadísticamente útil.
- UI Expectativa: «muestra insuficiente (n=…)» antes de E±R si insufficient. Sigue `≠ permiso`. Parsers `asMfeMae` / `asExpectancy` fail-soft.
- Advisory ≠ permiso. **No** mezclar proxy y bars en agregados futuros. Sin journal histórica.

### Ciclo C3 — ActionQueue

- `buildActionQueue(board)` devuelve la cola completa ordenada (prioridad D2 + `actionability` del plan vivo; dedup por símbolo post-sort).
- Hoy (`mapDecisionBoardToHoyQueue`, default 8) es un **slice** de esa cola, no una agregación que corta a 8 antes de ordenar. C1 intacto: sin TradePlan vivo → WATCH (nunca BUY/ARMED inventados). Sin HTTP ActionQueue.

### Ciclo C2 — Alembic única autoridad

- Públicos `pnpm db:push` / `db:migrate` / `db:migrate:deploy` fail-closed (`Prisma schema is not authoritative. Use Alembic.`).
- Bootstrap (`setup` / `db-ensure` / `db-check`) aplica schema vía `ensure_migrated`. Prisma queda seed + `db:generate`. ADR-025 enmendado.

### Docs

- ADR-032 Operational Core (v1.9 contrato, **docs-only**, no implementado): TradePlan / PositionState / ExecutionPlan. Thin congelados. NO TRADE first-class.

### Ciclo C1 — Hoy honesty + HELP (v1.8.1 P0)

- Hoy: F3/sesión **sin** TradePlan vivo → `WATCH` (nunca BUY/ARMED heurístico). BLOCKED/WATCH de proyección → `whyNot: legacy_projection` (no `fit` ficticio).
- Ayuda: `HELP_CONTENT_AS_OF = 2026-08-25` — AUTO BETA-D (`ACTIVAR AUTO` + `PAPER_D_EXECUTE` opt-in), Decision Spine, TradePlan, Hoy proyección.
- Roadmap consolidación: [`roadmap-v181-operational-consolidation-2026-08-25.md`](./docs/engineering/roadmap-v181-operational-consolidation-2026-08-25.md). **No** módulos thin nuevos.

## [1.8.0-beta] — 2026-08-25

Post-`v1.7.0-beta` spine growth + integrity + Camino D thaw parcial. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.0-beta` → `8c8b789`**. Partida: **`v1.7.0-beta` → `e3b943a`**. Spine battery **`pnpm test:decision-spine` = 159**.

### Decision Spine — TradePlan / mesa / journal

- TradePlan v0 + Ciclos **4.0–4.9** (stop ATR/swing, EntrySetup, ARMED, Wyckoff formal→effort, Board echo).
- Ciclos **5.0–5.3** thin: Thesis Health · Protect/T1 · Exit Radar · MFE/MAE (advisory; ≠ permiso).
- Ciclo **6** Attribution journal thin · Ciclo **7** Spine honesty.
- Ciclos **8.0–8.2** thin: Expectancy · Trail · Bracket (advisory; sin OCO/broker). **Línea crecimiento thin CERRADA.**

### Integridad execute / honesty

- **I1** ExecuteTrade converge (`check_opening` en buy HTTP).
- **I2** Actionability / Indice Operativo server.
- **I3** Shadow honesty — HTTP `paper_auto` exige `PAPER_D_EXECUTE`.
- **RX1** exits `full_auto` honesty — mismo env gate antes del Router. **No** auto-exit producto.

### Thaw Camino D (ADR-023)

- Medición estricta P1–P5 **FAIL** · perfil **BETA-D Accepted** (P1'–P5' + W2–W4).
- UI Libro AUTO on · execute **opt-in** `PAPER_D_EXECUTE=1` (default repo off).
- **A3-wire** (`d704263`): frase exacta `ACTIVAR AUTO` obligatoria antes de `mode:auto`; disarm al salir. Arm ≠ execute.
- Deuda estricto tracking: runbook + `scripts/thaw_estricto_snapshot.mjs` (W2–W4 vigentes).

### Ops / docs

- `TRUSTED_PROXIES` runbook exact-string · valor prod **OWNER**.
- Pack auditoría: [`audit-pack-estado-global-2026-08-25-v180.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v180.md).

## [1.7.0-beta] — 2026-08-24

Ciclo post-`v1.6.0-beta` (Decision Spine + mesa U0–U6 + gates DS-05/DS-03 + ops + copy Research→Radar). Producto sigue **BETA**. Tag anotado **`v1.7.0-beta`** (pendiente de crear por coordinador sobre commit de stamp). Partida: **`c3964fc`**. Tags `v1.6.0-beta` / `v1.5.0-beta` / `v1.3.0` intactos.

### Track B — split backtests + nav Señales (heredado post-R-13)

- **F4′–F6′** (`240c846`): copy nav **Señales** (`/screeners`); tests href B0; herencia R-13 Track B desbloqueado.
- **B1–B12**: extracción incremental de `backtests-page.tsx` (~4698→321 LOC shell) — constantes/tipos, queries, mutations, derivados, URL sync, navegación, Lista AUTO, play cycle, Lab handlers, tabs run/jobs, `useBacktestPageModel`. Sin cambio de comportamiento; smoke manual backtests sigue recomendado.

### Fase 0 Decision Spine (código + docs)

- **F0.5b** (`3670a09`): PortfolioFit v1 — concentración cesta activo+sector, VETO fail-closed; `MaxSectorExposure` cableada.
- **F0.6b + F0.6-UI** (`8df8a65`, `672e88f`): Decision Board v1 backend + UI solo lectura (`/decision-board`).
- **D1/D2/D3**: risk cesta SEMI=AUTO (`7530556`); DecisionPackage contrato en confirm SEMI (`f7b1f6c`); Lab/Radar **fuera** del spine (`ea0c93f`, ADR-019).
- **Confirm SEMI deuda** (`2281903`): `wait` sin sesión ya no ejecuta sell default; side de `exit_hint`/`reduce` desde package.
- **Prove Spine** (`5e81350`): S0–S3, tests `pnpm test:decision-spine`, golden scenario.
- **H5** (`f56af2f`): perfil inversor SEMI → `check_opening` (mismo SoT AUTO).

### UX mesa U0–U6

- **U0–U4** (`6f26f9d`): tips Ayuda, presets S/R, Confirm drawer, chips Fit.
- **U5** (`04e441e`): proyección orden F3 en chart (post-SEMI preview).
- **U6** (`9e9a346`): preview ticket en Confirm/drawer — notional, comisión, margen (UI-only; sin bypass execute).

### Spine residual — gates en `check_opening`

- **DS-05** (`15e86a4`): Data Freshness Gate fail-closed (umbral 5×24h; SEMI ohlcv + AUTO `signal.timestamp`; exits fuera).
- **DS-03** (`41adb8e`): Account Mandate Gate fail-closed (tenure BD `mandate_tenures`; mismatch estrategia AUTO; exits fuera). Batería `pnpm test:decision-spine` **53**.

### Ops (ejecutable + propietario)

- **Ops residual** (`3c53f4e`…`7363ec6`): saneo símbolos `/` en import índices; fix 404 recurrente `BP.L`; re-sync `idx-ftse100` verificado; backup corrupt drop.
- **Ops propietario** (`5100d23`): secret scanning + push protection enabled vía API; runbook `TRUSTED_PROXIES` prod (valor real sigue en propietario).
- **Higiene dev** (`ea9a985`, dato local `bolsa_v1`): script `cleanup_dev_test_residues.py`; 3 cuentas huérfanas R8C eliminadas; `verify_ledger_balance_chain.py` **EXIT 0**.

### Research→Radar copy (UI)

- CTAs y cross-links **Asesor** (`/research`) vs **Señales** (`/screeners`); helpers `asesorHistoryHref`; sin fusión de páginas ni rutas API. Hereda F4′–F6′. Batería: `daily-nav.test.ts` 8/8.

## [1.6.0-beta] — 2026-08-22

Consolidación BETA post-R-12 (ciclo R-13). Producto sigue **BETA**. Tag anotado **`v1.6.0-beta` → `c3964fc`**. Tags `v1.5.0-beta` / `v1.3.0` intactos. Plan: `docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md`.

### R-13 consolidación (docs + E8 micro)

- Cierre de R-12 como ciclo de reparación. Firma de partida R-13: `origin/main` **`5edbcb5`** (histórica) → **`c3964fc`** (A0–A3). README alineado a **v1.6.0-beta**. Track B producto (god-page / Research→Radar) **bloqueado**.
- A2: tests de contrato/ausencia en `chart-new-tab-setup.test.ts`; **purge** de `normalizeChartNewTabSeed` (0 callers). `extractChartNewTabSeed` / `applyChartNewTabSeed` intactos. Pending-delete alto **sin purge**.

### Auth D4 / JWT (incluido en release; commits post-`v1.5.0-beta`, ya en `main`)

- **R12-ACCOUNTS** (`3c958f1`) paquete `bolsa_application/accounts/`
- **R12-AUTH F1–F3** stamp owner + 404 cuenta ajena + cash/trade scoped
- **F4** ADR-027 Opción C **Aceptado** · **F5–F7a** tabla `users` + JWT + list/get scoped · **F8–F8e** perfiles, trackers, policies, events, workspaces, list-for-list
- **F9** FE login campo `login` opcional · **F10** `session_version` + `/auth/refresh` + rate-limit user
- **F7b** script + apply **local** (103→0 NULL; no prod) · **JWT-only** (`tokens.py` eliminado; SHA-256/HMAC → 401)
- **F7c** match estricto `user_id == principal` · `scan.completed` `ownerUserId` · cron stamp `tracker.user_id`
- Pending-delete E8 tests (`851b545`) · purge V2 métricas T+0 19/19 (**E8 N, sin purge**)

## [1.5.0-beta] — 2026-08-22

R-12 Track C (mesa SEMI frontend) + copy E8 residual + leftover CORE-R + tres gates de contrato/ejecución/workers. Producto sigue **BETA**. Tag anotado **`v1.5.0-beta` → `5e52bd6`**. Tag `v1.3.0` → `b778292` intacto. Plan: `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md`.

### Track C + higiene copy

- Track C **C1** (`5bc51ff`): ruta `/confirm`, nav Confirmar con badge de cola, `openHelpAiPlatform({ panel: "supervised-f3" })` navega SPA (no Ayuda)
- Track C **C2** (`01af9ff`): nav diaria Trading · Señales · Confirmar vs Laboratorio / Asesor; hub Señales; copy Universo en vigilancia
- Track C **C3** (`97e20ab`): AUTO de cuenta «No disponible (BETA)»; copy de mesa sin `PAPER_D_EXECUTE`; execute sigue congelado
- Track C **C4** (`154fcd1`): nav **Libro** (Operaciones + Historial); cabeceras «Libro · …»; sin fusionar páginas
- Track C **C5** (`0eb8976`): HELP + Ayuda sync Confirm `/confirm` · Señales/Libro · AUTO BETA · frase SEMI
- Copy E8 residual (`ce601c9`) + leftover CORE-R (`8dd3caf`): CTAs de firma → `/confirm` dejan de decir Ayuda; atajos list-hub `/screeners` = Señales (Laboratorio); leftover CORE-R Proponer F3 ya en Confirmar

### Gates cerrados

- **R12-409 B1** (`eb24608`): declarar HTTP 409 en OpenAPI para conflictos de `idempotency_key` en deposit/withdraw/trade (`{detail: str}`); regen acotada `openapi.json` + `schema.d.ts`; runtime handler sin cambio
- **EXEC-B-CONC** (`ca60d0a`): `ExecuteTrade` deriva `balance_after` trade/fee desde cash post-lock (`result.summary.portfolio.cash`); elimina lectura pre-lock `get_summary`; chaos refuerza invariante B estricta bajo concurrencia
- **R12-SCHED / R-8C.2** (`5e52bd6`): scheduler = crons only; poll no-ARQ → `bolsa-queue-poll-worker`; ARQ → `bolsa-arq-worker` (queue_poll no-op); `run-dev.mjs` spawnea el proceso correcto según `SCAN_QUEUE_BACKEND`

### Contexto R-12 previo (Track A+B)

- Firma de estado: **GitHub `origin/main`**; implementación Track A+B `48cc255`; partida R-12 `f7a86cc`; premisas esenciales del ciclo R-12
- Alineación documental: README `v1.3.0 BETA`; tag `v1.3.0` → **`b778292`**
- Tests/scripts de verificación residuales (DEFAULT_PORTFOLIO, invariantes C–E, retry HTTP)
- Inventario `pending-delete` (sin purge) + higiene E8 + estudio UX comparativo (Track B **aprobado**, mesa 5 puertas)

## [1.3.0] — 2026-08-21

Endurecimiento del núcleo financiero y del gate CI apuntado por la **auditoría externa sobre v1.2.1** (R-11: C1–C5, C6, D1, D2 — todas cerradas) + deuda de datos/código residual cerrada tras el cierre de R-11. Documenta la política de cargo de custodia (C6) y deja `verify_ledger_balance_chain.py` en **EXIT 0 global**. Tag: `v1.3.0` sobre **`b778292`** (cierre documental; padre `deafa27` = fix test + verify EXIT 0). DEMO / paper; sin broker live.

### Post-R-11 (deuda §3 del traspaso, cierre de release)

- **Test** (`deafa27`) `test_execute_trade_con_fees_reconcilia` corregido: `ExecuteTrade.execute(...)` pide `idempotency_key` (R-10 F1 / R-11 C2); se añade `f"trade-{uuid4().hex[:8]}"` (deuda ajena a R-11, no regresión de gate). Batería coordinador: `test_m2` 7 passed 1 xfailed
- **Dato dev** (fuera de repo) cuenta de simulación huérfana `acc_broken_72ab7c2aa881` ("R8C broken", única de 111 que fallaba la cadena `balance_after` por +0.01 float legacy) **eliminada por path canónico** `close_account`→`delete_simulated_account` (coherente con R-10 F3-sim; **D6 prohíbe backfill** por eso no se reescribió `balance_after`) → `verify_ledger_balance_chain.py` **EXIT 0**

### R-11 — Endurecimiento post-v1.2.1 (C1–C6 + D1 + D2 cerradas a `main`)

- **C1** (`c3327c1`) Custodia **multi-periodo** (R-10.6): tabla `custody_obligations` PK `id` autoincremento + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migración Alembic `006_custody_obligations_period` (encadena sobre `005`); `upsert` reparado para **no sobrescribir** + `get_pending_by_account`/`get_by_account_period`; `ApplyCustodyFees`/`RunCustodyJob` liquidan primero el PENDING más antiguo antes del periodo nuevo
- **C2** (`17a1107`) **Idempotency_key end-to-end** (R-10.7): DTOs `DepositCashDto`/`WithdrawCashDto`/`TradeRequestDto` con `str_strip_whitespace=True`, `min_length=16`, `max_length=128`; repo `execute_trade` con `idempotency_key: str` obligatoria + rechazo de `""`/whitespace; guard en `ConfirmRecommendationIntent` (uuid4 fallback)
- **C3** (`cda26e9`) **Precisión Decimal end-to-end** (R-10.8): en `ExecuteTrade.execute` `notional`/`cash_before`/`amount`/`trade_balance`/`fee_balance` en `Decimal`, `float` solo en el borde al invocar repo/ledger; invariante secuencial exacta
- **C4** (`157bb45`) `contract:check` **EXIT 0** (R-10.9, Opción A): regen acotada de `apps/web/api/openapi.json` — `idempotencyKey` con `minLength/maxLength` + `TaxProfileDto` con `minimum:0.0`; `schema.d.ts` sin cambio; el 409 sigue solo en runtime (handler global), no en OpenAPI (decisión Opción A)
- **C5** (`6762614`) **`mypy` == 0 en gate CI** (R-10.9): añadida `packages/py/application/src` al step Mypy de `.github/workflows/python-ci.yml`; limpiados **105 errores en 33 ficheros** de la capa application; semántica mínima en `ledger_repository` (`limit: int|None=50`), `market_indices`, `fetch_core_r_pnl_extra_rows` (guard numérico) y `scans.py` (fix de `TypeError` latente: `expected_last_daily_bar()` sin el `exchange` obligatorio; ahora por instrumento)
- **C6** (docs, 2026-08-21) Política de cargo de custodia **`custody_charge_source = DEFAULT_PORTFOLIO`** documentada en ADR 026: la custodia es obligación de cuenta (importe sobre **equity agregado**) pero se cobra **exclusivamente desde la cartera seleccionada/default** (`scope.portfolio`, fallback `is_default`); sin transferencia implícita entre carteras — **solo documenta la regla, sin cambio de comportamiento**
- **Batería global R-11** (verificada por el coordinador): mypy gate `344 files` EXIT 0 · mypy application `95 files` EXIT 0 · ruff 0 · pytest application+market `388` · pytest api-python offline `84`
- **D2** (`db95709`, con C6) **Cierre documental**: docstrings aditivos en `ApplyCustodyFees.execute`/`ExecuteTrade.execute` (accounts.py, 14 ins, 0 lógica) · estado documental en PROJECT_STATE/backlog/index/plan/ADR 026/CHANGELOG
- **D1** (`870fb21`) **Limpieza transversal E8**: `custody_obligation_repository.get_by_account` + `get_by_account_period` (0 callers producción; el segundo nunca se cableó a `ApplyCustodyFees`/`RunCustodyJob`) quitados del repo y de fakes de test · se mantienen `get_pending_by_account`/`upsert` · **sin tocar ítems RIESGO ALTO** · batería D1: ruff 0 · mypy repo gate 0 · pytest custodia 7 · pytest application 279

## [1.2.1] — 2026-08-21

Correcciones de la **auditoría externa post‑v1.2.0** (R-10, F1–F5). Refuerza el núcleo financiero detectado en la pasada: `balance_after` secuencial, custodia con obligación pendiente y fuera del GET, DTOs estrictos, idempotencia exacta y `idempotency_key` obligatoria. DEMO / paper; sin broker live.

### R-10 — Correcciones de la auditoría externa (cerrada, F1–F5)

- **F1** `idempotency_key` **obligatoria** en deposit/withdraw/trade (422 si falta) + contrato/regen OpenAPI y ajuste de consumidores web
- **F2a** `TaxProfileDto` estricto (Pydantic fail-fast 422): `ge=0`, `allow_inf_nan=False`, `fiscal_year_start_month ∈ [1,12]`
- **F2b** Comparación idempotente **exacta normalizada a `Numeric(18,6)`** (eliminada la tolerancia de `0.01`)
- **F3** `balance_after` de trade+fee **secuencial por fila** (cash FINAL ya no en ambas), sin backfill (forward-only)
- **F4a** Custodia **Opción B con obligación pendiente** (tabla `custody_obligation`, `PENDING`/`APPLIED`, ADR 026, migración `005`): si `cash < fee` no descuenta ni marca DONE — registra `PENDING` y cobra el total cuando haya saldo
- **F4b** Custodia **fuera del GET** → job periódico `RunCustodyJob` (scheduler/worker); `GetAccountSummary`/`GetTaxReport` quedan **100% de solo lectura** (desfase de saldo pre‑custodia aceptado mientras corre el job). **Reabre `M-4/T-M4`** (job de custodia dedicado)
- **F5** Cierre: docs de estado (backlog, PROJECT_STATE, engineering-index, plan-r10) + CHANGELOG `[1.2.1]` + limpieza E8 inventariada

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · **R-8C.2 scheduler-vs-worker** · gobernanza IA
- **`M-4/T-M4` REACTIVADO y CERRADO por R-10 F4b** (`e12a125`) — la custodia ya es un job dedicado, no muta en GET

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.2.0] — 2026-08-20

Refactorización y corrección R-7 / R-8 / R-9 completadas (hardening financiero + limpieza + contrato). DEMO / paper; sin broker live.

### R-9 — Núcleo financiero determinista (cerrada, F1–F8)

- **F1** Idempotencia deposit/withdraw aislada por cuenta + `type` (align lookup ↔ UNIQUE por-cuenta)
- **F2** 409 `IDEMPOTENCY_KEY_REUSED` ante `idempotency_key` reutilizada con payload distinto (sin migración)
- **F3** Carrera de custodia idempotente → nunca 500 en contienda (UNIQUE + savepoint + detección de violación)
- **F4** DTOs financieros estrictos (Pydantic fail-fast 422): `ge/gt` + `allow_inf_nan=False` en `CommissionProfileDto` / `CreateInvestmentAccountDto`
- **F5** Sesión con **epoch UTC** (`time.time()`) en vez de `time.monotonic()` (portable multi-host)
- **F6** `balance_after` documentado como **postcondición de app** (no constraint DB) + corrección de docs
- **F7** Suite de **concurrencia/invariantes** en PG real (`test_concurrency_scenarios.py`) + verifiers `scripts/verify/`
- **F8** Limpieza transversal E8: código/aliases muertos en Python + web + shared (pending-delete riesgo alto intacto)
- **F9 (V2)** — arquitectura Python + puente `legacy_portfolio_id`: **DIFERIDA** (requiere ADR + decisión explícita)

### R-7 — Deuda de dinero real (cerrada)

- Doble cargo de custodia en GET concurrentes · deposit/withdraw idempotentes · claim AUTO no quemado
- Ledger con UNIQUE `(account_id, reference_type, reference_id, type)` · reconciliación cash↔ledger · cost-basis FIFO/avg con fee · margen real · max drawdown high-water-mark · `transfer_cash` muerto eliminado · trade+fee idempotente en AUTO execute/confirm · guard FIFO qty==0 + observabilidad PnL CORE-R · `total_unrealized_gain` fail-closed

### R-8 — Prevención de riesgo + contrato (cerrada; incluida en v1.1.0)

- Sesión HttpOnly firmada + logout · rate-limit login/status · invariante `balance_after` por grupo atómico · limpieza transversal baja (R-8D) · fidelidad wire DTOs shared (R-8B.3) · CONTRACT-STALE resuelto (`openapi.json`+`schema.d.ts` regenerados)

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · R-8C.2 scheduler-vs-worker · M-4/T-M4 (job dedicado custodia) · gobernanza IA

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.1.0] — 2026-08-20

Integridad R-7/R-8 y fidelidad de contrato. DEMO / paper; sin broker live.

### Seguridad / sesión (R-8B)

- Cookie de sesión **HttpOnly firmada** + logout + endpoint `authenticated`
- Rate-limit en login/status (R-8B.1)
- Sesión vulnerable a reutilización multi-host corregida (preludio de epoch en R-9.5)

### Robustez financiera (R-7)

- `A-1/A-3` custodia: mutex `claim_custody_charge` + release · `A-2` deposit/withdraw idempotentes por `idempotency_key`
- `L-M3/M-5` ledger UNIQUE por-cuenta+type · `M-1` fallback mark-to-cost · `M-2` `sum_cash_amounts` rest con ledger · `M-3` cost-basis con fee · `M-6` margen real · `M-4/T-M5` fees de custodia fuera de `fees_paid_total` · `M-7` dedup verificación por UNIQUE · `B-1` max drawdown high-water-mark · `B-3` `transfer_cash` eliminado · `B-4` trade+fee idempotente AUTO/confirm · `B-5` guard FIFO qty==0 + obs. PnL CORE-R · `B-2` `total_unrealized_gain` fail-closed
- Invariante `balance_after` por grupo atómico (R-8C) · bootstrap advisory-lock · fidelidad wire DTOs (R-8B.3, fases A–D) · CONTRACT-STALE resuelto

## [Unreleased] — stage 2026-08-06

### Listas / Visualizados

- **Visualizados** = espejo de pestañas abiertas (separado de **Estudio** API)
- Quitar selección cierra tabs (sin resucitar por autosave) · **Por IO** ordena por Índice Operativo
- Columnas opcionales IO/TA/FA/★/Postura · sort por columna (tabs siguen el orden)
- Foco buscar/pestaña: lista **Cartera → Estudio → resto** + scroll bajo cabecera sticky
- Docs: `visualizados-list-ux-2026-08-06.md` · handoff `session-handoff-2026-08-06-visualizados-list-ux.md`

### Arranque (perf)

- Windows: liberar puertos con `netstat` (sin PowerShell Get-NetTCPConnection)
- `GET /api/lists/memberships` batch · sync catálogo con TTL 60s en `GET /lists`
- Monitor / CORE-R: batch `instrument-strategy-tops/query` (menos N+1 al pintar Trading)
- CORE-R shell: primer tick + hydrate diferidos (~1.5–4 s / idle) tras el paint

### Estudio / Operativa (ADR-024 + UI procesos)

- Universo **Estudio** API · Supervisión ON · cadencias Vigilia / Frescura / Redescubrimiento
- UI: subtítulo procesos bajo el nombre · botones **Actualizar** / **Redescubrir** (barra inferior) · chips cadencia V·F·R en banner · sellos locales
- Manual/SEMI/AUTO en barra de estado (`OPERATIVA: …`) → Cuentas · Config (fuera del panel por valor)
- Docs: `docs/engineering/estudio-process-status-ui-2026-08-06.md` · handoff `session-handoff-2026-08-06-estudio-process-ui.md` · HELP sync
- GitHub: [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) · PR stage [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)

## [1.0.0] — 2026-08-01

Primera release empaquetada (**BETA1 → GitHub V1**). DEMO / paper; sin broker live.

### Producto

- Embudo Backtesting: Coach ★ local · Lab AT · Lista AUTO (frescura v1.3) · Finalistas
- **CORE-P** perfil ↔ Coach/Lab (gate, techo DD, soft-bias espacio, E2E smoke/ASGI)
- **CORE-B** v0.2 memoria Lab (meseta → espacio · `resolveDefaultLabFamily`)
- **CORE-R** v1.8 reevaluación (Monitor, cola, narración; cron local)
- **DÍA D** v0.11 simulación as-of + Evidence (fullBleed no se persiste)
- Análisis del valor / FA·FIE · Tarjeta CAPM footnote · Composite liquidez v1.1
- Trading supervisado F3 (Decision Engine); paper auto dry-run (execute off-by-default)
- Ayuda / trackers sincronizados (`HELP_CONTENT_AS_OF` 2026-08-01)

### Calidad

- `pnpm test:coach` · `test:coach:smoke` · `test:coach:api`
- `pnpm test:operativa` · `test:operativa:smoke`
- `pnpm test:fa`

### Congelado (no en V1)

- Belief UI · Lab Discovery P3–P9 · `PAPER_D_EXECUTE` · CORE-R multi-dispositivo · broker live

### Notas

- Stack: React/Vite + FastAPI + PostgreSQL
- Requiere Node ≥20, pnpm ≥10, Python ≥3.11, Docker Desktop
