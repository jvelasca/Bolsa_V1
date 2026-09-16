# Audit Pack — V2.40.3 / Hotfix de la clave de idempotencia financiera (colisión por recorte) + invariante del A9 sobre el ledger real (2026-09-16)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.40.3** sobre `v2.40.2-beta` — **hotfix de un bug de dinero** descubierto por el CI del
> tag anterior, más el endurecimiento del propio test que lo detectó (que hasta ahora podía
> certificar con un punto ciego).
>
> **Base auditada:** `v2.40.2-beta` (`11e2cb83`).
> **Bump:** `1.65.2-beta` → **`1.65.3-beta`**.
> **Alembic head:** `041_unique_natural_keys` (**sin migración nueva**).
> **Flags:** sin cambios (`AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**).
> **Contrato financiero:** sin cambios; el rango de las claves de idempotencia (`16..128`, sin
> whitespace, estable por `execution_id`) se mantiene y ahora se cumple **de verdad** en todo el
> rango de longitudes.
> **Sello CI:** el tag `v2.40.2-beta` **se movió** al commit del fix (`581067c4`, borrado + re-tag) para
> que el tag siga significando "commit certificado": el CI del tag antiguo (`11e2cb83`) quedó rojo
> precisamente por el bug que esta fase corrige (ver §1). **Sellado y verificado:** push a `main` en
> verde (Python CI [`35068139514`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068139514):
> `quality`, `lifecycle-pg`, `grammar-discovery-pg`, `paper-forward-pg`, `auto-v2-durable-pg`) y
> Release-tag CI del tag movido en verde (run
> [`35068488972`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068488972), `sha=581067c4`,
> `certify` ✓, incluido el job `python` con `ruff`/`imports`/`mypy`/`pytest` offline y `lifecycle-pg`
> con auth + golden restart). La evidencia de ejecución **local** está en §6 con la batería **exacta**
> del job afectado (la sonda del §6 se ejecutó antes de publicar; el sello de CI es posterior).
> **Arranque auditor:** este mismo documento (§0 resumen, §1–§4 fix, §5 mutaciones, §6 verificación,
> §7 limitaciones).

---

## 0. Resumen ejecutivo

El CI del tag `v2.40.2-beta` dejó el job `lifecycle-pg` en rojo con el invariante de equity del día
AUTO. La intuición natural —"la aritmética del ledger está mal"— era **falsa**: el ledger estaba
bien. Lo que fallaba es que **tres fills nunca llegaron a materializarse**, y ningún gate lo decía.

Causa raíz, medida: la clave de idempotencia financiera de un fill se derivaba de su
`execution_id` con un **recorte por la cola** (`slug[:120]` en SIM, `slug[:100]` en recovery LIVE).
Desde P1-03 el `venue_order_id` del AUTO va namespaced (engine + UUID de cuenta + instrumento + lado

- secuencia lógica), así que `execution_id = f"{venue_order_id}#{fill_seq}"` mide **126-128
  caracteres** y el recorte se comía justo **el `#fill_seq`**: los N fills de una misma orden
  colapsaban en **una** clave. La segunda trancha llegaba a `ExecuteTrade` con la misma clave y otro
  payload ⇒ `IdempotencyKeyReused` ⇒ `mark_retry` ⇒ fila en `RETRY` **permanente** (el reintento usa
  la misma clave, así que vuelve a chocar) ⇒ el lado que no liquidaba dejaba el libro abierto.

| Eje                             | Antes (`v2.40.2-beta`)                                                      | Ahora (`v2.40.3-beta`)                                                             |
| ------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Clave de fill (SIM)             | `f"sim-fin-{slug[:120]}"[-128:]` ⇒ 4 fills = **1** clave                    | `bounded_idempotency_key`: 4 fills = **4** claves (inyectiva)                      |
| Clave de fill (recovery LIVE)   | `f"recovery-fin-{slug[:100]}"[-128:]` ⇒ mismo colapso                       | ídem, con digest del `execution_id` completo                                       |
| Compatibilidad de claves        | —                                                                           | **exacta** por debajo del presupuesto histórico (un fill en vuelo no se re-aplica) |
| Invariante de equity del A9     | posición desde `position_states` ⇒ no realizado **siempre 0** (punto ciego) | posición desde el estado canónico `positions` + P&L cerrado desde el contexto      |
| Gate de cierre del día AUTO     | ninguno sobre el estado de los `execution_events`                           | **libro plano + cero fills sin materializar** (todos `APPLIED`, ledger cuadrado)   |
| Instrumento del test de restart | aleatorio ⇒ 12,36 % de las veces el simulador no llena nada                 | determinista entre los que **sí** llenan                                           |
| Invariante del restart          | contaba **tranchas** de fill (`execution_events`)                           | cuenta **órdenes** (`count(distinct venue_order_id)`)                              |

**Veredicto:** el camino SIM y el camino recovery vuelven a tener claves inyectivas conservando
compatibilidad byte a byte con las claves históricas, y la certificación del día AUTO ahora **nombra**
lo que antes se manifestaba como un desajuste de equity sin diagnóstico. El cambio es de **disciplina
de identidad financiera**: ni el ledger, ni el settlement, ni el `RiskGate`, ni la reconciliación
cambian de forma.

---

## 1. F1 · La clave de idempotencia dejaba de ser inyectiva (bug de dinero)

**Afirmación:** con la identidad namespaced del worker AUTO, dos fills distintos de la misma orden
generan **claves distintas** (antes generaban la misma).

**Antes** (`packages/py/application/src/bolsa_application/simulated_settlement.py` y
`recovery_apply.py`, en `11e2cb83`):

```python
slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip()).strip("-") or "unknown"
return f"sim-fin-{slug[:120]}"[-128:]        # SIM
return f"recovery-fin-{slug[:100]}"[-128:]   # recovery LIVE
```

El `[-128:]` final es **inoperante** (el total nunca superaba 128) y el `[:presupuesto]` descarta la
**cola** del `execution_id`, que es exactamente donde vive el `#fill_seq`.

**Medición reproducible** (`uv run python -`, identidad construida con los mismos datos que usa el
worker: engine `auto-a9proc-…`, cuenta UUID, instrumento; lado `buy`/`sell`):

| camino            | presupuesto | `len(execution_id)` | claves distintas / 4 fills (antes) | (ahora) |
| ----------------- | ----------: | ------------------: | ---------------------------------: | ------: |
| SIM (`sim-fin-`)  |         120 |                 126 |                              **1** |   **4** |
| recovery (`rec-`) |         100 |                 128 |                              **1** |   **4** |

Con una identidad aún más realista (engine con UUID completo) los `execution_id` miden **162-164**
caracteres y el colapso es el mismo en ambos caminos. Es decir: **no era un caso de borde**, era el
caso normal del AUTO.

**Cadena del daño (leída en el código, no inferida):**

1. La primera trancha se asienta bajo la clave `sim-fin-…` (`ExecuteTrade` idempotente).
2. La segunda trancha llega con la **misma** clave y **otro** payload ⇒ `IdempotencyKeyReused`
   (`packages/py/domain/src/bolsa_domain/errors.py`; en la app:
   `packages/py/application/src/bolsa_application/execute_gated_portfolio_trade.py`).
3. `apply_execution_financial_once` (`packages/py/application/src/bolsa_application/execution_event.py`)
   captura la excepción de `apply_finance` y llama a `store.mark_retry(error="apply_exception")` ⇒
   devuelve `retry_scheduled`.
4. El worker AUTO absorbe el fallo por símbolo
   (`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`, `auto_sim settle failed` ⇒
   "sin fill este tick") y **la fila se queda en `RETRY` para siempre**: la clave es función del
   mismo `execution_id`, así que cualquier reintento vuelve al paso 2. El libro no cierra.

**Ahora** — módulo propio `packages/py/application/src/bolsa_application/idempotency_key.py`
(`bounded_idempotency_key`), del que ambos caminos delegan:

| Rama                         | Clave resultante                                       | Propiedad                                                                                                                                                                                                                      |
| ---------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `len(slug) <= legacy_budget` | `f"{prefix}{slug}"`                                    | **byte a byte** la histórica ⇒ un fill en vuelo de un deploy anterior re-deriva LA MISMA clave ⇒ no se re-aplica dinero                                                                                                        |
| `len(slug) > legacy_budget`  | `f"{prefix}{slug[:head]}~{sha256(execution_id)[:32]}"` | 128 chars; `~` es **imposible** en un slug (`re.sub` manda todo lo que no sea `[A-Za-z0-9_]` a `-`) ⇒ largas y cortas son disjuntas; el digest del `execution_id` **completo** discrimina el `#fill_seq` que el recorte tiraba |
| slug degenerado (`unknown`)  | clave rellenada a 16 con la **misma** marca `~`        | cumple el mínimo del contrato sin poder colisionar con una clave normal                                                                                                                                                        |

**Matriz afirmación → código → test:**

| Afirmación                                                       | Código                                        | Test                                                            |
| ---------------------------------------------------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| Dos fills distintos de la misma orden ⇒ claves distintas         | `idempotency_key.bounded_idempotency_key`     | `test_fills_of_one_order_do_not_collapse[buy/sell]`             |
| El recorte histórico **sí** colapsaba (el test es una regresión) | (derivación histórica reproducida en el test) | `test_legacy_derivation_did_collapse_tails_that_share_prefix`   |
| Compatibilidad exacta por debajo del presupuesto                 | rama corta de `bounded_idempotency_key`       | `test_short_execution_ids_keep_the_exact_legacy_key`            |
| Largas y cortas estructuralmente disjuntas                       | marca `~` + digest                            | `test_long_keys_are_structurally_disjoint_from_legacy_ones`     |
| Contrato R-11 C2 (`16..128`, sin whitespace, estable)            | `IDEMPOTENCY_KEY_MIN_LEN` / `_MAX_LEN`        | `test_contract_range_whitespace_and_stability`                  |
| Inyectividad entre lados, órdenes y secuencias                   | ídem                                          | `test_keys_are_distinct_across_sides_and_orders`                |
| Caso degenerado no colisiona con una clave real                  | relleno con marca `~`                         | `test_degenerate_execution_id_does_not_collide_with_a_real_one` |
| El helper preserva la cola en **ambos** caminos                  | `bounded_idempotency_key`                     | `test_bounded_helper_keeps_the_tail_discriminator`              |

---

## 2. F2 · El invariante de equity leía una tabla que el camino AUTO SIM no escribe

**Afirmación:** el invariante de equity del test de certificación del día AUTO mide de verdad
`total_equity == initial + realized + unrealized`, incluyendo la parte **no realizada**.

**Antes** (`_assert_equity_invariant` en `11e2cb83`): reconstruía la contabilidad desde el ledger,
pero tomaba la **posición abierta** de `SqlAlchemyPositionStateRepository`
(`SqlAlchemyPositionStateRepository.list_open_for_account` → tabla `position_states`). El camino
AUTO SIM **no escribe esa tabla** (escribe `sim_auto_positions` y la canónica `positions`), así que
`remaining = 0` y, con él, `last_price = 0` y el término no realizado **siempre 0**: el invariante se
degradaba a una identidad de caja y era **ciego** a una posición a medio liquidar.

**Ahora** (`_assert_full_day_closed` mismo fichero): la identidad se reconstruye desde el **estado
canónico** (`positions`) y el P&L cerrado se deriva de `sim_fill_finance_context` (fuente
**independiente** del ledger, para que la comparación no sea circular) contra las entradas reales del
ledger.

---

## 3. F3 · Gate nuevo: libro plano y ningún fill sin materializar

**Afirmación:** el día AUTO **no** se certifica si queda un fill sin materializar o si el libro no
cierra.

Al terminar el día el test exige, conjuntamente:

1. Todos los `execution_events` de la cuenta en `APPLIED` (**cero** `RETRY`/`CAPTURED`/`APPLYING`) —
   vía `_day_progress`.
2. Todo `sim_fill_finance_context` con su transacción correspondiente en el ledger.
3. Posición final **plana** en el estado canónico y el invariante de equity del dominio sobre el
   ledger real.

Es el gate que convierte el rojo opaco del tag en un diagnóstico de una línea: _"el día AUTO deja 3
ExecutionEvents sin materializar (RETRY/CAPTURED)"_ — exactamente el síntoma medido del bug de F1
(4 tranchas de una orden, 1 asentada, 3 en `RETRY`).

---

## 4. Dos verdes falsos retirados en el mismo test

**4.1 Instrumento aleatorio ⇒ lotería determinista.** El simulador decide con un ruido determinista
por `(seed, instrument_id, lado)` si la orden topa con una "costa terminal" y **no llena nada**
(`fills=()`). Medido con la sonda (`apps/api-python/scripts/a9_noise_probe.py`, `n = 5000`):
**12,36 %** de los identificadores aleatorios no llenan (y el desglose documenta el evento:
`ok` 90,82 %; `noise_timeout` 2,24 %; `noise_reconnect` 1,94 %; `noise_duplicate` 1,78 %;
`noise_unavailable` 1,14 %; `noise_reject` 1,06 %; `noise_market_closed` 0,68 %; `noise_unknown`
0,34 %). El test de restart usaba un `instrument_id` aleatorio, así que **una de cada ocho**
ejecuciones se plantaba antes de empezar (`el proceso debe abrir (BUY durable) antes del restart`).
Ahora el identificador se elige de forma **determinista** entre los que sí llenan
(`_filling_instrument_id`), y el test del día completo usa una identidad fija.

**4.2 Se contaban tranchas, no órdenes.** El invariante del restart es "no **re-comprar**", pero el
test contaba filas de `execution_events` filtradas por lado: materializar tras el restart la trancha
que quedó **en vuelo** al matar el proceso es lo correcto, y se contaba como re-compra. Ahora cuenta
`count(distinct venue_order_id)`: una re-compra real es una `venue_order_id` **nueva**. El contador
anterior solo permanecía estable porque el bug de F1 lo congelaba (verde falso).

---

## 5. Mutaciones que deben poner la suite en rojo

| Mutación                                                      | Test que debe fallar                                                              |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Volver a `slug[:120]` en `simulated_idempotency_key`          | `test_fills_of_one_order_do_not_collapse`, `test_legacy_derivation_did_collapse…` |
| Volver a `slug[:100]` en `recovery_idempotency_key`           | `test_fills_of_one_order_do_not_collapse`, `test_short_execution_ids_…`           |
| Quitar el digest de la rama larga (recorte duro a 128)        | `test_fills_of_one_order_do_not_collapse`                                         |
| Usar un marcador que pueda existir en un slug (p.ej. `-`)     | `test_long_keys_are_structurally_disjoint_from_legacy_ones`                       |
| Quitar el relleno del mínimo de 16                            | `test_contract_range_whitespace_and_stability`, `test_degenerate_…`               |
| Volver a leer la posición del invariante en `position_states` | `test_a9_scheduler_process_full_day_pg_zero_human` (gate de libro plano)          |
| Dejar de exigir "todo `APPLIED`" al cerrar el día             | `test_a9_scheduler_process_full_day_pg_zero_human` (gate F3)                      |
| Contar filas en vez de órdenes en el restart                  | `test_a9_scheduler_process_restart_with_open_protected_position_pg`               |
| Volver a un `instrument_id` aleatorio en el restart           | `test_a9_scheduler_process_restart_with_open_protected_position_pg` (flaky)       |

---

## 6. Verificación (evidencia local)

La evidencia de ejecución de esta sección es **local** (sondas y baterías completas sobre PostgreSQL
real antes de publicar); la batería es la **exacta** del job `lifecycle-pg` (`release-tag-ci.yml`),
sobre PostgreSQL real en una **BD scratch recreada y migrada a head** y con los **mismos gates
fail-if-skipped** del job. El **sello de CI de GitHub** (posterior al commit) está en §0: push a `main`
en verde y Release-tag CI del tag movido en verde.

| Comprobación                                                                                                                      | Resultado                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `packages/py/application/tests/test_idempotency_key_budget.py`                                                                    | **10 passed** (hermético, 0,22 s)                                                                                                                                                                                                                                                                                                                                                                                  |
| A/B del bug (derivación histórica restaurada, código del fix intacto)                                                             | día AUTO rojo: **`AssertionError: el día AUTO deja 3 ExecutionEvents sin materializar (RETRY/CAPTURED)`** (1 failed en 121,26 s: los 4 fills de la orden colapsan en 1 clave ⇒ 1 asentado y 3 en `RETRY` permanente)                                                                                                                                                                                               |
| Mismo día con el fix (sin el A/B)                                                                                                 | **2 passed** en el fichero A9 (día completo 7,82 s + restart 22,67 s)                                                                                                                                                                                                                                                                                                                                              |
| Batería del job `lifecycle-pg` (BD scratch recreada + migrada a `head`, gates fail-if-skipped activos)                            | **132 passed in 106,55 s** (0 failed, 0 errors, 0 skipped)                                                                                                                                                                                                                                                                                                                                                         |
| Baterías **offline** de CI, con los comandos `pytest` **extraídos del propio YAML** (para que no se desincronicen): job `quality` | **1626 passed in 85,59 s**                                                                                                                                                                                                                                                                                                                                                                                         |
| Misma extracción para el job `python` del tag                                                                                     | **1634 passed in 58,95 s**                                                                                                                                                                                                                                                                                                                                                                                         |
| `ruff check packages/py apps/api-python --config pyproject.toml` (el comando del job `quality`)                                   | **0 hallazgos**                                                                                                                                                                                                                                                                                                                                                                                                    |
| `lint-imports --config packages/py/.importlinter`                                                                                 | **4/4 contratos KEPT**                                                                                                                                                                                                                                                                                                                                                                                             |
| `mypy packages/py/… apps/api-python/src --follow-imports=silent` (step _Mypy_ del job `quality`)                                  | **NO ejecutado en local**: la política de control de aplicaciones de Windows de la máquina de verificación bloquea el DLL `mypyc` del binario (`ImportError: DLL load failed while importing …__mypyc`). **Sí cubierto por CI**: el job `python` del tag (que corre `ruff`/`imports`/`mypy`/`pytest` offline) quedó **verde** en el run `35068488972`, y el step _Mypy_ del job `quality` en el run `35068139514`. |

Notas de reproducibilidad del §6:

- La BD scratch se recrea (`a9_scratch_db.py`) y se **pre-migra a `head`** con `ensure_migrated()` (el
  camino programático, el mismo que usan los tests y que **sí** honra `DATABASE_URL`) antes de pytest,
  igual que hace el job de CI con su step `Alembic upgrade head` (si no, los ficheros PG que asumen
  esquema ya creado fallan por fixture, no por código).
- Las dos baterías offline se lanzan **leyendo del YAML** el comando del step (con `yaml.safe_load` y
  un `shlex.split`), y no pegando la lista a mano: así lo verificado es literalmente lo que correrá CI
  (las listas de ficheros de esos jobs cambian con frecuencia y una copia local miente).
- El A/B no toca el código del repo: la derivación histórica se restaura **en runtime** mediante un
  `sitecustomize` inyectado por `PYTHONPATH`, de modo que también la ve el **subproceso** del scheduler
  (`python -m bolsa_api.workers.scheduler_worker`). El parche se borra al terminar.
- Para el CI del tag: el run del `v2.40.2-beta` (`35026285805`) registró `1 failed, 131 passed` con la
  única caída en `test_a9_scheduler_process_full_day_pg_zero_human`
  (`AssertionError: equity 89956.891432 != initial+realized+unrealized 99967.864700`) y `lifecycle-pg=failure`
  en el agregado `certify`; esta fase busca ese mismo job en verde.
- Para el CI del tag: el run del `v2.40.2-beta` (`35026285805`) registró `1 failed, 131 passed` con la
  única caída en `test_a9_scheduler_process_full_day_pg_zero_human`
  (`AssertionError: equity 89956.891432 != initial+realized+unrealized 99967.864700`) y `lifecycle-pg=failure`
  en el agregado `certify`; esta fase busca ese mismo job en verde.

---

## 7. Limitaciones declaradas

1. **El tag se mueve.** `v2.40.2-beta` se borra y se re-crea sobre el commit de este fix: el tag
   anterior (`11e2cb83`) apuntaba a un commit cuyo CI quedó rojo. Queda registrado aquí y en el
   CHANGELOG. **Consecuencia declarada:** el tag `v2.40.2-beta` apunta a un commit cuya versión es
   `1.65.3-beta` (fase V2.40.3); el nombre del tag no coincide con la versión del código que señala.
   La base auditada de esta fase sigue siendo `11e2cb83` (por SHA, ya sin tag).
2. **La rama larga de la clave introduce una marca (`~`).** No es un slug válido y por tanto ninguna
   clave nueva puede coincidir con una histórica que sí lo fuera; a cambio, los consumidores que
   validen el **alfabeto** de la clave de idempotencia (no solo longitud/whitespace) deben aceptar el
   alfabeto `[A-Za-z0-9_~]` en las claves largas. El contrato R-11 C2 vigente solo fija rango y
   ausencia de whitespace.
3. **Los `execution_events` en `RETRY` de días anteriores no se reparan solos.** El fix evita el
   fallo hacia adelante; las filas históricas en `RETRY` de una cuenta ya afectada siguen siendo
   reaplicables por el camino normal de reintento **solo** si su clave no choca (y con el fix, deja
   de chocar).
4. **La sonda de ruido es una medida, no un test.** `a9_noise_probe.py` cuantifica la lotería del
   `instrument_id`; el test usa una identidad determinista y no depende de la tasa.
5. **La certificación del día completa depende del simulador.** El test elige un instrumento que
   llena porque el ruido es determinista; si el modelo de ruido cambiara, el test fallaría de forma
   informativa (no silenciosa).
6. **Hallazgo no corregido en esta fase (deuda declarada): el CLI de Alembic ignora `DATABASE_URL`
   en modo online.** `packages/py/infrastructure/alembic/env.py::run_migrations_online` construye el
   engine desde la sección `sqlalchemy.url` de `alembic.ini` (`engine_from_config(...)`) en vez de
   usar `_resolved_url()` (que sí honra `DATABASE_URL`, pero solo se usa en modo offline). Medido al
   preparar esta verificación: `uv run alembic current` con `DATABASE_URL=postgresql://nope:nope@localhost:59999/nope_db`
   imprimió `041_unique_natural_keys (head)` — es decir, conectó a la BD del `alembic.ini`, no a la
   pedida. En CI no se nota porque el valor por defecto del `alembic.ini`
   (`bolsa:bolsa_dev@localhost:5432/bolsa_v1`) **coincide** con la BD del job; el peligro es real para
   cualquier job/entorno que apunte `DATABASE_URL` a otra base (una migración se aplicaría a la BD
   equivocada). El camino programático (`ensure_migrated`, el que usan los tests y el bootstrap de
   los workers) **sí** respeta la URL porque inyecta la conexión. Se deja fuera del hotfix por
   alcance (cambio de comportamiento del CLI) y se registra como candidato de la siguiente fase.
7. **`mypy` no se pudo ejecutar en la máquina de verificación.** La política de control de
   aplicaciones de Windows bloquea el DLL compilado (`mypyc`) del binario
   (`ImportError: DLL load failed while importing 08ae81f72d5a2b5fa9e0__mypyc`), así que el step
   _Mypy_ **no está verificado localmente**. Lo cubre el CI: el job `python` del tag
   (`ruff`/`imports`/`mypy`/`pytest` offline) quedó verde en el run `35068488972` y el step _Mypy_
   del job `quality` en el `35068139514`. El módulo nuevo (`idempotency_key.py`) tiene firmas
   anotadas y no añade dependencias. Es un límite del entorno, no del cambio.
8. **El test hermético nuevo se cablea en dos jobs de CI.** `test_idempotency_key_budget.py` no
   habría corrido en la red de CI si solo se hubiera escrito el fichero: hay que añadirlo a la lista
   explícita. Esta fase lo añade al job `quality` (`python-ci.yml`) y al job `python`
   (`release-tag-ci.yml`), porque es un test que debe correr en **cada push** (es hermético, 0,2 s)
   y que es la regresión directa del bug de dinero.
