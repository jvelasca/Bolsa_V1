# Evidencia cruda — `FLAKE-1` **CERRADA**: el rojo intermitente era el **FIXTURE**, no el motor (`v2.88.9`, 2026-09-30)

Resumen **verificable** del sello. Las cifras están **transcritas** de las mediciones, sin edición. Este
sello **no** produce artefacto propio: su contenido es el **cierre de hallazgo** abierto por la
instrumentación de `v2.88.8` — **sólo tests** (`+193/−34` en 2 ficheros) **más documentación**, con **cero
líneas de `src`**.

> **Base de este cierre:** el rojo **con traza** del run `36681305812` (`v2.88.8-beta`), cuyo `RETRY` dejó de
> ser mudo precisamente por el sello anterior. Sin esa traza, este aislamiento no habría sido posible:
> [`../v2.88.8/README.md#62`](../v2.88.8/README.md).

## Identidad del sello

| | |
| --- | --- |
| Fase | **Cierre de `FLAKE-1`** (causa raíz medida, reproducida contra PG y sellada con gate) |
| Versión de paquete | `2.11.8-beta` → **`2.11.9-beta`** |
| Tag (lo crea el propietario) | **`v2.88.9-beta`** (anotado) |
| Base del diff | **`21c85c0a`** (= `v2.88.8-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Contenido del sello | 2 ficheros de **test** + docs. **CERO `src`. MOTOR INTACTO** |
| Hallazgo | `FLAKE-1` → 🟢 **CERRADA**; **`OBS-21`** → 🔴 **ABIERTA** (derivada, sin arreglar) |

## 1. Perímetro — medido, no declarado

`git diff --stat v2.88.8-beta..HEAD` sobre el motor:

```
packages/py/application/src/bolsa_application/auto_simulation_worker.py
packages/py/application/src/bolsa_application/replay_oos.py
apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py
  -> VACÍO (idénticos a v2.88.8-beta)
```

`git diff --numstat v2.88.8-beta..HEAD` — **ningún fichero de `src`**:

| Fichero | numstat | Qué es |
| --- | --- | --- |
| `packages/py/application/tests/test_simulated_finance.py` | **`+118/−0`** | los **tres gates** herméticos del cierre |
| `apps/api-python/tests/test_simulated_finance_pg.py` | **`+75/−34`** | `_seed_with_fills` → **`_roundtrip_plan`** (fixture dimensionado) |
| `docs/engineering/flake-1-causa-raiz-2026-09-30.md` | `+116/−0` | informe de causa raíz |
| `CHANGELOG.md` · `PROJECT_STATE.md` · índice · `deuda-p3` · evidencia | — | documentación |

**Sin migración. Sin umbrales.** `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B y todo umbral: intactos. Sin
backdating.

## 2. El mecanismo: una función PURA del `(seed, side, instrument_id)`

En `packages/py/application/src/bolsa_application/simulated_broker.py`, el corte de las parciales **no**
depende de la orden, sino de la **pata**:

* `draw_queue_noise(seed, side, instrument_id)` → terminal noisy (`reject`/`timeout`/`closed`/`unknown`) ⇒
  `fills=()`. Si no, latencia y `ok`.
* `mid_cut = sim_rand(seed, side, instrument_id, "partialcut", i)` → si `< 0,07`, la orden **se corta** en
  esa parcial (`if not is_last: ... if mid_cut < 0.07: break`).
* Los pesos son `[max(0,5 − 0,03·i, 0,15)]` = **`[0,5 · 0,47 · 0,44]`** y **el último chunk consume el
  resto**, así que con `quantity=60` y `fill_chunks=3` cada pata sólo puede acabar en:

| Chunks | Cantidad liquidada | Desglose |
| --- | --- | --- |
| **1** | **30** | cortada tras la primera parcial |
| **3** | **60** | `30 · 14,1 · 15,9` |

**El comentario del propio código ya decía la mitad del teorema:** «la aleatoriedad del book depende SOLO del
contexto de mercado (seed/side/instrument), nunca de la identidad del order». Es decir: **`side` entra en el
hash**, y por eso **con el MISMO seed las dos patas pueden acabar distintas**.

**El caso real del CI** (`instrument_id = inst-fin-59e064e70b`; el primer seed con fills en ambas patas era
`2`):

```
BUY   30.000000                                  (cortada tras su 1er chunk)  -> deja 30 en cartera
SELL  30.000000 + 14.100000 + 15.900000 = 60.000000  (llena los tres)        -> pide 60
```

| Trancha | Cantidad | Cartera antes | Resultado |
| --- | --- | --- | --- |
| `sell#1` | 30,0 | 30,0 | ✅ vende → cartera **0** (la posición se **borra** al llegar a cero) |
| `sell#2` | 14,1 | **0,0** | ❌ `ValueError` → **`RETRY`** |
| `sell#3` | 15,9 | **0,0** | ❌ `ValueError` → **`RETRY`** |

⇒ **Predice exactamente las tranchas `#2` y `#3` del run `36681305812`**, y explica por qué `#1` sí pasaba.
**El motor hizo lo correcto:** `portfolio_repository.execute_trade` **rechazó** (`fail-closed`) una venta que
no cabía en la cartera.

**La pieza que faltaba en el selector del test.** `_seed_with_fills` exigía «algún fill en cada pata» —y eso
lo cumplían **las dos**—: **nunca** exigió que **la venta cupiera en la cartera**. El fallo estaba en el
**plan del fixture**, no en el motor.

## 3. Medida: 20 000 sorteos de `instrument_id` (determinista)

El test sortea `instrument_id = f"inst-fin-{uuid.uuid4().hex[:10]}"`, así que su desenlace es una **lotería
medible** (no una variable de entorno):

| Fixture | Rojos / 20 000 | Tasa | Patrón de tranchas fallidas |
| --- | --- | --- | --- |
| **Viejo** (venta a la cantidad nominal en **ambas** patas) | **1336** | **6,68 %** | **`(2,3)` en el 100 %** |
| **Arreglado** (venta dimensionada a lo **liquidado** por la compra) | **0** | **0 %** | — |

**Sólo se observaron dos desenlaces entre las 20 000 corridas: verde, o rojo con `#2` y `#3`.** El patrón del
modelo coincide **trancha a trancha** con el del runner. Regresiones nuevas introducidas por el arreglo:
**0**.

**Y esto cierra la frase que este hallazgo arrastró desde el principio.** El sello anterior midió **`0` rojos
en `59` corridas locales** y lo leyó como «la variable es del entorno (runner 2 vCPU vs local)». **Era
falso como explicación**; la causa es **pura** — **sin CPU, sin paralelismo y sin red**.

> **CORRECCIÓN POST-SELLO (`2026-09-30`), medida sobre los logs crudos de la terminal — no sobre lo que se
> recordaba.** El recuento **`59`** estaba **inflado**: de las tres tandas que lo componían, **dos no
> ejecutaron nada**.
>
> | Tanda | Lo que de verdad pasó | Información sobre `FLAKE-1` |
> | --- | --- | --- |
> | **`50` corridas directas** (dos políticas de selector) | **Las `50` murieron en `0,00–0,06 s` con `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`** — el bug de `win32` ya conocido del repo (`SelectorEventLoop`, PR #39) —: **nunca llegaron al dominio** | **ninguna** |
> | **`50` corridas directas** re-hechas con el *event loop* correcto | **`50 ok`, `TOTAL fallos: 0`** (`25` + `25`, una por política) | **la buena** |
> | **`8` iteraciones** del comando exacto del job `lifecycle-pg` | Cada una duró **`0,1–0,6 s`** y su `resumen` salió **VACÍO**; una corrida real de esa batería tarda **~`100 s`** ⇒ **la suite no llegó a ejecutarse** | **ninguna** |
>
> ⇒ **La evidencia local válida es `50` corridas, `0` rojos** (**no** `59`): con tasa **`6,68 %`**,
> `P(0 en 50) = (1 − 0,0668)^50 ≈ **3,2 %**`.
>
> **Y hay algo MEJOR que la suerte para explicar ese `0`, que sí está en esos logs: la asimetría que salió en
> local fue la INOFENSIVA.** Las iteraciones **`001`, `002` y `020`** de esa tanda registran
> `buy=filled(60.000000/60,chunks=3)` con `sell=partial(30.000000/60,chunks=1)` — esto es **venta cortada /
> compra completa**: vende `30` de los `60` que hay en cartera ⇒ **nunca sobrevende**. La orientación que
> hacía daño es la **contraria** —**compra cortada / venta completa**—, y **no salió en ninguna de las `50`**.
> Con esto el `0` deja de ser «mala suerte» y pasa a ser un **sesgo del sorteo observado en los propios
> logs**. (El término «`9` corridas del comando exacto» que citan los sellos `v2.88.7`/`v2.88.8` se sostiene,
> por tanto, en **una** corrida —aquella con `165 passed, 0 skipped`—, no en nueve: **aquellos ficheros no se
> reescriben**, son evidencia sellada y reescribirlos invalidaría la cadena; la corrección se declara
> **aquí**, que es su sitio.) **El fondo del hallazgo no cambia en nada:** causa raíz = fixture (§2), tasa
> `6,68 %` (§3), contraste contra PG (§4), `0/20 000` con el arreglo (§3) y tag **VERDE** (§9).

## 4. Contraste contra PG REAL — ROJO → VERDE con el MISMO `instrument_id`

El modelo puro no bastaba como cierre: se ejecutó el **camino completo**
(`submit_simulated_order` + `build_simulated_execute_trade_applier` + `ExecuteTrade` +
`portfolio_repository`) contra **PostgreSQL real**, fijando el `instrument_id` del CI y variando **sólo** la
cantidad de la venta:

| Cantidad de la venta | Resultado | Detalle verbatim |
| --- | --- | --- |
| **60** (fixture viejo) | ❌ **ROJO** — `1 failed in 1,86 s` | `buy#1 = APPLIED`; `sell#2 = RETRY`, `sell#3 = RETRY`; `ValueError: No tienes suficientes acciones. En cartera: 0.0` con la traza `simulated_finance.py:260` → `accounts/trade.py:131` → `portfolio_repository.py:383` |
| **30** (arreglo) | ✅ **VERDE** — `1 passed in 1,79 s` | los **4** fills `APPLIED` (1 compra + 3 ventas), ida-y-vuelta **cerrado a cero** |

**Misma máquina, misma base, mismo código: lo único que cambia es el plan del fixture.** Ese es el cierre.
Y la traza del rojo reproducido es **línea por línea** la del runner `36681305812`.

## 5. El sello: tres gates herméticos que **FUERZAN** el fallo

Añadidos en `packages/py/application/tests/test_simulated_finance.py` — **fichero ya cableado a CI** desde
`OBS-19` (`v2.88.8`), así que estos gates **corren en el job `python` del tag**, no en un limbo:

| Gate | Qué fija |
| --- | --- |
| `test_flake1_partial_cut_is_asymmetric_across_sides` | La **RAÍZ**: con el mismo seed, `buy` se corta (`30`) y `sell` no (`30 + 14,1 + 15,9`), con el **`instrument_id` REAL del rojo** |
| `test_flake1_oversell_plan_is_rejected_by_the_pure_domain_mirror` | El plan del fixture viejo lo **rechaza el propio espejo del dominio**: `sim_roundtrip_accounting` → `ValueError: sell exceeds the held position`. *La lectura estaba disponible todo el tiempo: vender más de lo que dejó la compra es oversell, y el dominio ya lo sabía.* |
| `test_flake1_sizing_the_sell_to_the_realized_buy_never_oversells` | El **ARREGLO**, sobre una rejilla **fija** de `instrument_id` (sin lotería), **y** que la rejilla **alcance al fallo** que arregla (con el dimensionado viejo **sí** sobrevende) |

**Y el arreglo del fixture PG**, en `apps/api-python/tests/test_simulated_finance_pg.py`:

| Antes | Después |
| --- | --- |
| `_seed_with_fills(instrument_id) -> int` — «algún fill en cada pata» | **`_roundtrip_plan(instrument_id) -> (seed, comprado, a_vender)`** — venta dimensionada a lo **liquidado** |
| `quantity=Decimal("60")` **fijo** en las dos patas (settlement y resolver) | `quantities[side]`, con la **misma** cantidad en settlement **y** resolver |
| — | invariante explícito del fixture: `sum(sell) <= realized` |

> **Detalle que importa:** el **resolver del applier rehace el schedule** para recuperar el precio/cantidad
> de cada fill, así que la cantidad **tiene que viajar** hasta él. Si no, el resolver reconstruye otro
> schedule y los parciales no son los mismos.

## 6. Verificación (los gates del CI, corridos aquí)

| Verificación | Comando | Resultado |
| --- | --- | --- |
| Lint (invocación **exacta** del CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **`All checks passed!`** |
| Tipos (**gate** del CI, 508 ficheros) | `uv run mypy packages/py/*/src apps/api-python/src --follow-imports=silent` | **`Success: no issues found in 508 source files`** |
| Tests (hermético + PG objetivo) | `pytest …/test_simulated_finance.py …/test_simulated_finance_pg.py` | **`12 passed`** (11 herméticos = 8 previos + 3 nuevos, + 1 PG) |

## 7. Derivada: `OBS-21` — `RETRY` para un rechazo **permanente** (ABIERTA, sin arreglar aquí)

No se buscaba: **la traza lo puso delante**. `apply_simulated_order_once(..., retryable_on_ineffective=True)`
marca `RETRY` cuando el applier devuelve `False`, y el applier devuelve `False` ante **cualquier** excepción
de `ExecuteTrade` —incluida `No tienes suficientes acciones`, que es una condición **PERMANENTE** del estado.

**`RETRY` significa «reintenta», y reintentar es correcto para lo transitorio** (`deadlock`, `timeout`,
conexión caída). Sobre un hecho que no cambia, un motor real reintentaría **indefinidamente** —y el `RETRY`
es justamente el estado que el reaper/recovery vuelve a barrer al arrancar.

**Por qué NO se arregla aquí.** El alcance era la causa del rojo de CI, y el arreglo exige **clasificar**
transitorio vs permanente (idealmente un **tipo de error de dominio** para «rechazo permanente») y **mutarlo**:
marcar `FAILED` a lo ancho apagaría reintentos legítimos y podría **cegar** fills que **sí** eran
transitorios. «Terminación correcta» es una propiedad del motor que conviene decidir **a propósito**, no por
omisión. Registrada en [`../../deuda-p3-post-auditoria-v2.70-2026-09-26.md`](../../deuda-p3-post-auditoria-v2.70-2026-09-26.md).

## 8. Límites de esta evidencia y honestidad declarada

**Nota de honestidad (la discrepancia que NO se esconde).** La tasa medida (**6,68 %**) explica el rojo de
`36681305812`, pero **no** explica del todo la racha de **3 rojos en 4 corridas** de `lifecycle-pg`:
si las corridas fueran independientes a esa tasa, la probabilidad sería ≈ **0,1 %**. Las dos lecturas son
**(i) mala suerte** o **(ii) que alguna de las corridas anteriores tuviera un aporte adicional que nunca se
pudo ver** — precisamente porque el `RETRY` era **mudo** hasta `v2.88.8`. Con la instrumentación ese agujero
ya no existe (cualquier repetición **llega con traza**), y con el arreglo **la clase entera desaparece**
(`0/20 000`): la pregunta deja de tener efecto práctico. **Se declara en lugar de reclamar un cierre
perfecto.**

**Lo que NO se toca:** el motor; la semántica `fail-closed` del rechazo de `portfolio_repository` (que es
**correcta** y no se relaja); el test del día AUTO; `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B y cualquier umbral;
el sello del replay OOS de `v2.88.7` (otra cadena). **Sin migración, sin backdating.**

**`OBS-19` sigue ABIERTA** (se cerró su tercer caso en `v2.88.8`, no su causa estructural).

**Deuda re-acarreada (sin cambios):** fijar `newline="\n"` en el escritor del replay OOS para que el mismo
contenido tenga **un** hash en cualquier SO — exige **re-medir los cinco digests de sección** contra el sello
(`census 1237098/45e4cc80cfba6e5c`, `replay 891272/ee81e76cee0995aa`, `score 24112/96b3d601bae8b99c`,
`watch 561/40230635349bf2a0`, `totals {"fills":752,…}`) para demostrar que el cambio es **solo de render**.

## 9. Cita real del CI del tag

`Release tag CI` del tag **`v2.88.9-beta`** → **run `36685888972`** (`ref=v2.88.9-beta`, HEAD `1e2985f5`,
`2026-09-30T07:48:56Z → 07:57:11Z`, **~8m15s**) → **`SUCCESS`**: **10 jobs reales verdes + `certify` GREEN**
(**11 verdes en total, 0 rojos**; `playwright` integrado `skipped` por diseño). **Es el primer tag VERDE
desde `v2.88.7-beta`**: el anterior (`v2.88.8-beta`) murió en `lifecycle-pg` por `FLAKE-1`.

**Lo previsto contra lo observado (identidad, no impresión):**

| Job | Previsto al sellar | Observado en el runner | Veredicto |
| --- | --- | --- | --- |
| `python` | `3115 passed, 37 skipped` | **`3115 passed, 37 skipped, 6 warnings in 45,70 s`** | **COINCIDE** |
| `lifecycle-pg` (**el que daba el rojo**) | VERDE | **`165 passed, 2 warnings in 100,62 s`** en la batería que contiene `test_simulated_finance_pg.py` (0 skips: los gates *fail-if-skipped* se cumplieron) + `45 passed` (account-isolation) + `1` golden day + `1` crash/recovery + `3` concurrent AUTO + `2` hard-kill + `2` crash injection + `1` multiprocess (`113,14 s`) | **VERDE** |
| `replay-repro` | `success` | `success` — `# sembrado 20 instrumentos, 25700 barras D1`, `watch congelado: 20 símbolos`, render **LF** `3 290 062` B / `A4DA036C…13CB`, **`VEREDICTO 2ª corrida IDÉNTICA`** + `DIGEST igual en las dos corridas`, **`VEREDICTO REPRODUCIDO`**, artefacto **ID `11083079436`** (`285 944` B) | **COINCIDE** |
| `certify` | GREEN | **GREEN** (`"status": "GREEN"`, artefacto **ID `11083039890`**, `413` B) | **COINCIDE** |

**La cuenta `+3` cierra por dos vías independientes:** en el tag, `3115 = 3112 (v2.88.8) + 3` gates (`3152`
recogidos − `37` skips); y en `main` (`Python CI` **`36685885987`**, verde), `quality` pasa de `3101` a
**`3104 passed, 40 skipped, in 125,99 s`** = **`+3`**, con `ruff All checks passed!`, `Contracts: 4 kept, 0
broken` y `Success: no issues found in 508 source files`. **Los `37`/`40` skips no se mueven.**

**El head de Alembic, confirmado en el log del propio job** (no declarado): la última línea de `Running
upgrade` es `045_adaptive_gate_state -> 046_fill_reference_mid` ⇒ **`046_fill_reference_mid`**, como exige
este sello.

**Qué prueba y qué NO prueba esta corrida.** El verde de `lifecycle-pg` es la **primera evidencia en el
runner**, pero **una sola corrida verde NO demuestra** el arreglo: su rojo era una **lotería del 6,68 %**
sobre el `instrument_id` sorteado. Lo que lo demuestra es la medida de §3 (**`0/20 000`**) y el contraste de
§4 (mismo `instrument_id`: rojo con `60`, verde con `30`). La corrida del tag aporta **encaje de cuentas y
ausencia de regresión**, no la prueba de la causa — que ya venía medida.

**Informes de las cadenas que este sello cierra y de la que lo abrió:**
[`flake-1-causa-raiz-2026-09-30.md`](../../flake-1-causa-raiz-2026-09-30.md) (informe de causa raíz) ·
[`../v2.88.8/README.md`](../v2.88.8/README.md) (el sello que la instrumentó y cuya traza lo abrió) ·
[`evidencia-ci-tag-v2.88.8-2026-09-30.txt`](../../evidencia-ci-tag-v2.88.8-2026-09-30.txt) (traza origen) ·
[`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](../../deuda-p3-post-auditoria-v2.70-2026-09-26.md)
(`FLAKE-1` cerrada y `OBS-21` abierta).
