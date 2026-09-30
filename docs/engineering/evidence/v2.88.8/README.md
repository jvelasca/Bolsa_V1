# Evidencia cruda — `FLAKE-1` instrumentado + tercera deriva de las listas offline (`OBS-19`) + primera certificación de `replay-repro` en un tag (`v2.88.8`, 2026-09-30)

Resumen **verificable** del sello. Las cifras están **transcritas** de las corridas, sin edición. Este
sello **no** produce artefacto propio: su contenido es **instrumentación de un rojo espurio**, el cableado
de un gate que **no habría corrido** y la **primera certificación a nivel de tag** del job `replay-repro`
(añadido en `v2.88.7` **después** de sellar aquel tag).

## Identidad del sello

| | |
| --- | --- |
| Fase | Cierre de `FLAKE-1` por **instrumentación** + tercer caso de `OBS-19` + certificación de `replay-repro` |
| Versión de paquete | `2.11.7-beta` → **`2.11.8-beta`** |
| Tag (lo crea el propietario) | **`v2.88.8-beta`** (anotado) |
| Base del diff | **`5cbe84b0`** (= `v2.88.7-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Contenido del sello | 1 traza (`simulated_finance.py`) + 1 gate + cableado de 2 listas de CI + docs. **MOTOR INTACTO** |

## 1. Perímetro — medido, no declarado

`git diff --stat v2.88.7-beta..HEAD` sobre el motor y el instrumento del sello:

```
packages/py/application/src/bolsa_application/auto_simulation_worker.py
packages/py/application/src/bolsa_application/replay_oos.py
apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py
  -> VACÍO (idénticos a v2.88.7-beta)
```

El **único** cambio funcional:

| Fichero | numstat | Qué es |
| --- | --- | --- |
| `packages/py/application/src/bolsa_application/simulated_finance.py` | **`+15/−0`** | la traza (`logger.exception`) que faltaba |
| `packages/py/application/tests/test_simulated_finance.py` | **`+42/−1`** | el gate nuevo (`_ExplodingExecuteTrade`) |
| `.github/workflows/python-ci.yml` | **`+7/−0`** | el fichero entra en la lista offline de `quality` |
| `.github/workflows/release-tag-ci.yml` | **`+166/−1`** | el fichero entra en la lista del job `python` del tag |

## 2. `FLAKE-1`: el rojo espurio y la medida que lo acota

**Firma (idéntica en los dos rojos).** `AssertionError: RETRY` en el assert de
`test_simulated_finance_pg.py:327` (`row.status == "APPLIED"`): un `execution_id` que el venue reportó
**lleno** seguía en **`RETRY`**, con el **dinero sin mover**.

| Corrida (`release-tag-ci` de `v2.88.7`) | `lifecycle-pg` |
| --- | --- |
| `36627838819` | 🔴 `1 failed, 164 passed in 100,07 s` |
| `36636706369` | 🔴 `1 failed, 164 passed in 100,07 s` |
| `36638231729` | 🟢 `165 passed in 82,89 s` |

⇒ **Intermitente**, no determinista. El resto del rojo era **cascada** (el step aborta y las baterías
siguientes se quedan sin log ⇒ «no dejó log de la corrida»).

**Mecanismo, por lectura de código.** El `RETRY` solo puede venir de
`apply_execution_financial_once(retryable_on_ineffective=True)` → `mark_retry(error="apply_ineffective")`
cuando el applier devuelve `False`. Y `build_simulated_execute_trade_applier._apply` devuelve `False` en
**dos** casos:

1. el resolver da `None` — **descartado**: el schedule se recomputa determinista con el **mismo**
   `venue_order_id`, así que el match por `execution_id` no puede fallar;
2. `ExecuteTrade.execute` **lanzó** y la excepción **se tragaba** (`except Exception: return False`).

⇒ El `RETRY` era un fallo de `ExecuteTrade` **sin causa visible**: el único rastro era
`error="apply_ineffective"`, **idéntico** al de un `None` del resolver.

**La sospecha previa (llenado parcial) queda REFUTADA, con medida.** El selector del test (`_seed_with_fills`,
que solo exige `fills` no vacío) **acepta** esquemas parciales: medido offline, **9 de 80** órdenes ≈ **11 %**
salen `partial`. Pero **no** es la causa:

| Experimento | Resultado |
| --- | --- |
| Corridas directas con un lado `partial` (selector permisivo) | **4 de 25** → **pasaron** |
| Corridas directas exigiendo esquema **completo** | **25 de 25** → pasaron |

**No reproducible en local: `0` rojos en `59` corridas.** <br>**⚠️ CORRECCIÓN POST-SELLO (`2026-09-30`), medida sobre los logs crudos: el `59` estaba INFLADO.** La tanda de `50` murió **entera** con `psycopg.InterfaceError: ProactorEventLoop` (`0,00–0,06 s`, sin llegar al dominio ⇒ 0 información) y las `8` del comando exacto duraron `0,1–0,6 s` con `resumen` **vacío** (la suite no se ejecutó). Válidas: **`50` corridas, `0` rojos**. El fondo del hallazgo (fixture, `6,68 %`, contraste PG) **no cambia**: §3 de [`../v2.88.9/README.md`](../v2.88.9/README.md).

| Experimento | Corridas | Rojos |
| --- | --- | --- |
| Test objetivo directo (2 políticas de selector) | 50 | **0** |
| **Comando exacto** del job `lifecycle-pg`, BD scratch **fresca** por iteración (8 × `161 passed, 4 skipped` + 1 × `165 passed, 0 skipped`) | 9 | **0** |

⇒ La variable es del **entorno** (runner de **2 vCPU** frente a local), **no** del motor.

## 3. El arreglo: hacer visible lo que se tragaba

`simulated_finance._apply` registra `logger.exception(...)` con el `execution_id` y el `instrument_id`
**antes** de devolver `False`. **El contrato NO cambia:** sigue *fail-closed* y **jamás** marca `APPLIED`
por excepción. Gate nuevo `test_applier_keeps_fail_closed_and_LOGS_the_swallowed_cause`, que afirma las
**dos** mitades (devuelve `False` **y** la traza queda en el log).

## 4. Tercera deriva de las listas offline (`OBS-19`): el gate NO habría corrido

`packages/py/application/tests/test_simulated_finance.py` — **8 tests herméticos**, `0,12 s`, existe desde
`v2.22/A9` — **no estaba en la lista de NINGÚN workflow**. Sin cablearlo, el gate nuevo **y** sus **7** tests
previos no se habrían ejecutado nunca en CI. Es el **tercer** caso de la misma clase:

| Sello | Caso | Prueba |
| --- | --- | --- |
| `v2.88.6` | `test_replay_oos_durable_cycle.py` (45 tests) en **ninguna** lista | `+45` al cablearlo |
| `v2.88.6` | deriva **estructural** entre las dos listas (`98`/`56` tests) | comparación de listas |
| **`v2.88.8`** | `test_simulated_finance.py` (8 tests) en **ninguna** lista | **`+8`** al cablearlo |

Se cablea en los **dos** jobs offline con su comentario de procedencia. **`OBS-19` sigue ABIERTA**: se
cierra el caso, **no** la causa estructural (dos listas manuales sin fuente única).

## 5. La cuenta del recuento cierra por TRES vías independientes (`+8`)

Medición local con el **comando EXACTO** extraído del workflow (`release-tag-ci.yml`, job `python`, step
`Pytest offline`; **`118`** líneas = `uv run pytest` + **`78`** rutas + **`39`** `--ignore` + `-q`), sobre
PostgreSQL real y con el entorno de shell limpio:

```
1 failed, 3148 passed in 94,20 s        (3149 recogidos, 0 skipped)
```

El **único** rojo es el **PG-local pre-existente**
(`test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`),
que el job offline del CI **skippea** (dentro de los `37`).

| Vía | Números | Δ |
| --- | --- | --- |
| (i) Local, comando EXACTO | **`3141`** (sello `v2.88.7`) → **`3149`** recogidos | **`+8`** |
| (ii) `quality` en `main` (`Python CI` **`36678944192`**, verde) | **`3093`** → **`3101 passed, 40 skipped`** | **`+8`** |
| (iii) Tamaño del fichero | **`8`** tests | **`8`** |

⇒ **Esperado del job `python` del tag: `3112 passed, 37 skipped`** (identidad *recogidos local − `37` skips*
= `3149 − 37`), **con los mismos `37` skips**.

> **Nota de honestidad sobre el entorno.** La primera medición de este sello salió
> `2 failed, 3112 passed, 26 skipped, 9 errors`: **no** era un hallazgo del repo, era **huella del repro de
> `FLAKE-1`** —`DATABASE_URL` apuntando a la base scratch `bolsa_v1_flake1` (ya borrada) y los `23` gates
> `*_PG_REQUIRED=1` del job `lifecycle-pg`—, que el fixture de esos tests lee del **entorno** con
> `load_dotenv(..., override=False)` (el entorno **gana** sobre `.env`). Limpiado el shell, la medición cuadra
> con la convención del sello anterior (`0` skips en local). Se declara porque una medición contaminada se
> parece demasiado a un hallazgo.

## 6. Cita real del CI del tag (POST-TAG, 2026-09-30)

`Release tag CI` run **[`36681305812`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36681305812)**
(`ref=v2.88.8-beta`, HEAD `21c85c0a`) → **`FAILURE`** (`attempt 1`; `07:00:49Z → 07:08:02Z`, **~7m13s**).
**11 jobs reales: 9 verdes, `lifecycle-pg` rojo, `playwright (integrated E2E, opt-in)` `skipped` por diseño
y `certify` rojo** (agrega, como debe).

| Job | Resultado |
| --- | --- |
| **`replay-repro`** | ✅ **`success`** ← **primera certificación a nivel de tag** |
| `python` | ✅ `3112 passed, 37 skipped` |
| `decision-spine` · `dr-verify` · `a7-gate` · `security` · `shared` · `frontend` · `playwright (mock)` | ✅ `success` |
| **`lifecycle-pg`** | ❌ **`failure`** — `FLAKE-1`, **ahora DIAGNOSTICADO** (ver §6.2) |
| `certify` | ❌ `failure` (agrega el rojo; **el tag queda ROJO y NO se borra: queda como rojo citado**) |

Job `python` **verbatim**: `ruff All checks passed!` · `Contracts: 4 kept, 0 broken` ·
`Success: no issues found in 508 source files` · **`3112 passed, 37 skipped, 6 warnings in 68.43s`**
⇒ **ESPERADO `3112/37` = OBSERVADO `3112/37` → COINCIDE**. La identidad `+8` de §5 queda **confirmada por
el runner**, no solo en local.

### 6.1 La certificación que el sello compraba: `replay-repro` en un tag

El job que se añadió **después** del sello `v2.88.7` corrió **por primera vez bajo un tag** y salió
**verde**: siembra la entrada congelada, regenera el artefacto con el **mismo** script del sello y asserta
SHA-256 y tamaño. Es la **primera vez** que el artefacto del replay OOS es reproducible **desde el propio
tag**, no desde un `workflow_dispatch` sobre `main`.

### 6.2 El rojo de `lifecycle-pg` es `FLAKE-1` — y la instrumentación del sello lo CAZA

El rojo **no** es una regresión del sello: es el **mismo** flake, con la **misma** firma, y la traza que
este sello añadió entrega la **causa exacta** que llevaba dos sellos sin poder nombrarse:

```
FAILED apps/api-python/tests/test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once
  1 failed, 164 passed in 95.69s (0:01:35)

AssertionError: RETRY          (assert de test_simulated_finance_pg.py:328)

Captured stderr call:
ERROR [bolsa_application.simulated_finance] apply_finance NO efectivo por excepción de ExecuteTrade
  (execution_id=sim-engine-58b3e99de0f64798b13fd4cc2-sell-instfin59e064e70b-finselle3a415b3#2,
   instrument_id=inst-fin-59e064e70b); el store lo encamina a RETRY
Traceback (most recent call last):
  File ".../packages/py/application/src/bolsa_application/simulated_finance.py", line 260, in _apply
    await executor(
  File ".../packages/py/application/src/bolsa_application/accounts/trade.py", line 131, in execute
    result = await self._portfolio_repo.execute_trade(
  File ".../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/portfolio_repository.py", line 383, in execute_trade
    raise ValueError(f"No tienes suficientes acciones. En cartera: {held}")
ValueError: No tienes suficientes acciones. En cartera: 0.0
```

**Qué dice exactamente.** La pata **SELL** del ciclo (`...-sell-instfin59e064e70b-finselle3a415b3`, tranchas
`#2` y `#3`) se aplica contra `portfolio_repository.execute_trade`, que lee la posición de
`inst-fin-59e064e70b` y encuentra **`held = 0.0`**, así que **rechaza la venta**. **No** es la clave de
idempotencia (una sospecha razonable: `v2.40.3`/F1 fue exactamente ese colapso de claves, ya corregido en
`bounded_idempotency_key`) — lo descarta la traza: la excepción es del **repositorio de cartera**, no del
`ExecuteTrade` por clave reusada.

**Lo que se sabe y lo que NO.** Se sabe: **la venta se intenta liquidar cuando la cartera real todavía no
tiene las acciones** (el motor cree estar posicionado y la cartera `positions` dice `0.0`), y las **dos**
tranchas fallan, así que es **estado**, no azar por trancha. **No** se sabe todavía **por qué**: las dos
candidatas declaradas son (a) **orden/visibilidad entre patas del mismo ciclo** (la entrada aún no
materializó cuando la salida se liquida) y (b) **desajuste de cuenta/cartera entre patas** (las dos patas
resolviendo `account_id`/cartera distintos). **`portfolio_repository` rechazar la venta es correcto y
fail-closed**: el error no está en el rechazo, está en que el motor llegue ahí. El aislamiento de la causa
es el **próximo** trabajo, y ahora es abordable porque el rojo **se reproduce en el runner bajo demanda**
(el mismo test, el mismo job) y **deja traza**.

**Valor del sello, medido:** la instrumentación convirtió un rojo **mudo** (`error="apply_ineffective"`,
indistinguible de un `None` del resolver) en una **traza con fichero, línea, excepción y `execution_id`**,
en su **primer** uso — y sin cambiar el contrato (sigue *fail-closed*).

## 7. Límites de esta evidencia

**El sello es ROJO y NO se borra: queda como rojo citado.** El rojo es `FLAKE-1` —**ajeno** al objeto del
sello y **pre-existente**—, y su **causa inmediata ya está nombrada** por la instrumentación que el sello
añade (§6.2): la pata **SELL** se liquida con la cartera a **`0.0`** y `portfolio_repository` la rechaza
(*fail-closed* y **correcto**). Lo que **NO** queda aislado es **por qué** el motor llega ahí: las dos
candidatas declaradas —**orden/visibilidad entre patas del mismo ciclo** o **desajuste de cuenta/cartera
entre patas**— exigen su propia fase de diagnóstico, ahora abordable porque el rojo **se reproduce en el
runner** (mismo test, mismo job, traza disponible). **NO** se toca el motor, ni el test del día AUTO, ni
`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/`A/B` ni ningún umbral, ni se backdatea. **`OBS-19` sigue ABIERTA.** **NO**
acredita `P3-2`/`P3-3` y **NO** cierra `OBS-15` (techo de **1000 `APPLIED`**), `OBS-16`, `OBS-13`, `OBS-11`,
`H-4`, `OBS-9`, `P3-5` ni `OBS-5`.

**Deuda declarada que este sello RE-ACARREA** (de [`../v2.88.7/README.md`](../v2.88.7/README.md) §11.1):
fijar `newline="\n"` en el escritor del replay para que el mismo contenido tenga **un** hash en cualquier
SO. **No** se hace aquí por la misma razón que allí —tocar el script del sello invalidaría la cadena «el
artefacto lo produjo **este** script»— y **exige su propia fase**: al tocarlo hay que **re-medir los cinco
digests de sección** contra el sello (`census 1237098/45e4cc80cfba6e5c`, `replay 891272/ee81e76cee0995aa`,
`score 24112/96b3d601bae8b99c`, `watch 561/40230635349bf2a0`, `totals {"fills":752,…}`) para demostrar que
el cambio es **solo de render**.

**Informes de las dos cadenas que este sello instrumenta y certifica:**
[`../v2.88.7/README.md#11`](../v2.88.7/README.md) (reproducibilidad del artefacto y hallazgo del `CRLF`) ·
[`reproducibilidad-replay-oos-v2.88.7-2026-09-29.md`](../../reproducibilidad-replay-oos-v2.88.7-2026-09-29.md) ·
[`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](../../deuda-p3-post-auditoria-v2.70-2026-09-26.md)
(`FLAKE-1` y `OBS-19`).
