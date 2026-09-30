# `FLAKE-1` — CAUSA RAÍZ: el `RETRY` intermitente de `lifecycle-pg` NO era el motor, ni el entorno, ni la clave de idempotencia: **era el FIXTURE** (2026-09-30)

**Estado del hallazgo: 🟢 CERRADA** (causa raíz medida, reproducida contra PG real y sellada con un gate que la fuerza).
Hallazgo original: [`deuda-p3` §`FLAKE-1`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
Origen de la traza: `Release tag CI` run **`36681305812`** (ref `v2.88.8-beta`) —
[`evidencia-ci-tag-v2.88.8-2026-09-30.txt`](./evidencia-ci-tag-v2.88.8-2026-09-30.txt).
Instrumento que lo cazó: sello [`evidence/v2.88.8/README.md`](./evidence/v2.88.8/README.md).

---

## 1. Qué se creía y qué es

| Hipótesis | Veredicto | Cómo se refuta/confirma |
|---|---|---|
| **(a)** Orden/visibilidad entre las patas del MISMO ciclo | **REFUTADA** | Ambas patas corren **secuencialmente** en la misma sesión (`for side in ("buy", "sell")`), con `await` |
| **(b)** Desajuste cuenta/cartera entre patas | **REFUTADA** | Las dos resuelven el **mismo** `scope` (misma cuenta → misma cartera legacy; `portfolio_id` ninguno) |
| Colapso de clave de idempotencia (`v2.40.3`/`F1`) | **REFUTADA** | La excepción es del **repo de cartera**, no un `IdempotencyKeyReused` |
| Variable de ENTORNO (runner 2 vCPU vs local) | **REFUTADA** | La causa es una **función pura** del `instrument_id` que el test sortea; no depende de CPU, ni de paralelismo, ni de red |
| **(c)** El FIXTURE construye un ida-y-vuelta que no es net-zero | **CONFIRMADA** | Medida determinista + contraste rojo→verde contra PG real (§3 y §4) |

**La frase que resume el hallazgo:** el motor hizo lo correcto — **rechazó una venta que no cabía en la cartera (`fail-closed`)**. Lo que estaba mal era el **plan del test**: pedía vender más acciones de las que su propia pata de compra había dejado.

---

## 2. Mecanismo exacto (función pura, sin PG)

En `packages/py/application/src/bolsa_application/simulated_broker.py`, el corte de las parciales **no** depende de la orden, sino de la **pata**:

* `draw_queue_noise(seed, side, instrument_id)` → terminal noisy (`reject`/`timeout`/…) ⇒ `fills=()`.
* `mid_cut = sim_rand(seed, side, instrument_id, "partialcut", i)` → si `< 0,07`, la orden **se corta** en esa parcial.

Con `quantity=60` y `fill_chunks=3` los pesos son `[0,5 · 0,47 · 0,44]` y el último chunk consume el resto, así que cada pata sólo puede acabar en:

* **1 chunk** ⇒ liquidó **30** (cortada tras la primera parcial), o
* **3 chunks** ⇒ liquidó **60**, y de ahí `30 · 14,1 · 15,9`.

Como `side` entra en el hash, **con el MISMO seed las dos patas pueden acabar distintas**. El caso real del CI (`instrument_id = inst-fin-59e064e70b`, el primer seed válido era `2`):

```
BUY   30                      (cortada tras su 1er chunk)  -> deja 30 en cartera
SELL  30 + 14,1 + 15,9 = 60    (llena los tres)             -> pide 60
```

* `sell#1` = 30 ⇒ cartera 30 → 0 (la posición se **borra** al llegar a cero).
* `sell#2` = 14,1 ⇒ `held = 0.0` ⇒ **`ValueError`** ⇒ `RETRY`.
* `sell#3` = 15,9 ⇒ `held = 0.0` ⇒ **`ValueError`** ⇒ `RETRY`.

Eso **predice exactamente** las dos tranchas del CI (`#2` y `#3`), y predice que `#1` sí pasa. Es lo observado.

El selector clásico del test (`_seed_with_fills`) exigía **«algún fill en cada pata»** — y eso lo cumplían las dos. Nunca exigió que **la venta cupiera en la cartera**.

---

## 3. Medida (determinista, 20 000 sorteos)

El `instrument_id` es `uuid4().hex[:10]` ⇒ la tasa de rojo es una **lotería medible**:

| Fixture | Rojos / 20 000 | Tasa | Patrón de tranchas fallidas |
|---|---|---|---|
| **Viejo** (venta a la cantidad nominal en ambas patas) | **1336** | **6,68 %** | **100 % `(2,3)`** |
| **Arreglado** (venta dimensionada a lo liquidado por la compra) | **0** | **0 %** | — |

Dos consecuencias:

1. **El `instrument_id` del rojo del CI reproduce el fallo al 100 %** (`inst-fin-59e064e70b` ⇒ `buy=[30]`, `sell=[30 · 14,1 · 15,9]`, fallos `(2,3)`), y el patrón de tranchas es **idéntico** al del runner. Mecanismo cerrado, no correlación.
2. **No hay ninguna regresión**: el arreglo no introduce rojos nuevos (`only-new = 0`) y cura todos los del fixture viejo.

### Nota de honestidad (declarada, no escondida)

La tasa medida (**6,68 %** por corrida) explica el rojo de `36681305812`, pero **no** explica del todo la racha histórica de **3 rojos en 4 corridas** (~0,1 % de probabilidad si fueran independientes a esa tasa). Las dos posibilidades son: (i) mala suerte, o (ii) que alguna de las corridas anteriores tuviera un aporte adicional **que nunca se pudo ver**, precisamente porque el `RETRY` era **mudo** hasta `v2.88.8`. La instrumentación ya no permite ese agujero: cualquier repetición futura **llega con traza**. Se declara la discrepancia en vez de reclamar un cierre perfecto. Con el arreglo, **la clase entera desaparece** (0/20 000), así que la pregunta deja de tener efecto práctico.

---

## 4. Verificación contra PG real: contraste ROJO → VERDE (mismo `instrument_id`)

No bastaba el modelo puro: se ejecutó el **camino completo** (`submit_simulated_order` +
`build_simulated_execute_trade_applier` + `ExecuteTrade` + `portfolio_repository`) contra PostgreSQL real,
**fijando el `instrument_id` del CI** y variando **sólo** la cantidad de la venta:

| Cantidad de la venta | Resultado | Detalle |
|---|---|---|
| **60** (fixture viejo) | **ROJO** — `1 failed` | `buy#1 = APPLIED`; `sell#2 = RETRY`, `sell#3 = RETRY`; `ValueError: No tienes suficientes acciones. En cartera: 0.0` con la traza **línea por línea igual** a la del CI (`simulated_finance.py:260` → `accounts/trade.py:131` → `portfolio_repository.py:383`) |
| **30** (arreglo) | **VERDE** — `1 passed` | los **4** fills `APPLIED` (1 compra + 3 ventas), el ida-y-vuelta cierra a cero |

Misma máquina, misma base, mismo código: **lo único que cambia es el plan del fixture**. Ese es el cierre.

---

## 5. El sello: tres gates herméticos que FUERZAN el fallo

Añadidos en `packages/py/application/tests/test_simulated_finance.py` (fichero **ya cableado a CI** desde `OBS-19` en `v2.88.8`), **sin PG**:

1. `test_flake1_partial_cut_is_asymmetric_across_sides` — fija la **raíz**: con el mismo seed, `buy` se corta (`30`) y `sell` no (`30+14,1+15,9`), usando el **`instrument_id` real del rojo**.
2. `test_flake1_oversell_plan_is_rejected_by_the_pure_domain_mirror` — el plan del fixture viejo lo **rechaza el propio espejo del dominio** (`sim_roundtrip_accounting` → `ValueError: sell exceeds the held position`). Era una lectura disponible todo el tiempo: *vender más de lo que dejó la compra es oversell, y el dominio ya lo sabía*.
3. `test_flake1_sizing_the_sell_to_the_realized_buy_never_oversells` — fija el **arreglo** sobre una rejilla fija de `instrument_id` y, además, exige que la rejilla **alcance al fallo** (con el dimensionado viejo sí sobrevende): un gate que no cubre el fallo que arregla no sella nada.

Y el arreglo del fixture PG (`apps/api-python/tests/test_simulated_finance_pg.py`): `_seed_with_fills` → **`_roundtrip_plan`**, que devuelve `(seed, cantidad_comprada, cantidad_a_vender)` con la venta **dimensionada a lo que la compra liquida**, más el invariante del propio fixture (`sum(sell) <= realized`). La cantidad viaja también al resolver del applier, que **rehace el schedule** para recuperar el precio/cantidad de cada fill.

---

## 6. Observación derivada: `RETRY` para un rechazo PERMANENTE (`OBS-21`)

La traza deja al descubierto algo que el `RETRY` mudo tapaba: **`retryable_on_ineffective=True` marca como
reintentable un rechazo determinista**. `No tienes suficientes acciones` no se arregla reintentando: es una
condición **permanente** del estado de la cartera. Un motor real que reintente ese fill lo hará para siempre
sobre un hecho que no cambia (mientras que un `RETRY` por `deadlock`/`timeout` sí debe reintentarse).
**No se toca en este cambio** (alcance: la causa del rojo de CI); queda registrada como `OBS-21` en la deuda.

---

## 7. Qué NO se ha tocado

* **Motor**: `auto_simulation_worker.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py` — sin cambios. Ni `simulated_broker`/`simulated_settlement`/`simulated_finance` de `src`.
* **Semántica `fail-closed`**: intacta. El rechazo de `portfolio_repository` **sigue siendo el comportamiento correcto** y no se relaja.
* **Umbrales** de `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B: sin cambios. Sin backdating. Sin migración (Alembic head sigue en `046_fill_reference_mid`).
* **Alcance del cambio**: **sólo tests** (2 ficheros) + documentación.
