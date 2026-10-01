# Plan de trabajo `W4` — Proveedor de precio REAL (`v2.88.17-beta`)

> **Clase: PLAN** (no sello; **SIN bump, SIN tag, CERO `src`, CERO tests, CERO umbrales de producto**).
> **AsOf:** 2026-10-01. **Origen:** `W4` del [plan `W1`…`W6`](./plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md),
> **re-ordenado a primera palanca** por la decisión del propietario de 2026-10-01
> ([`evidence/v2.88.16.3/README.md`](./evidence/v2.88.16.3/README.md) §7, opción 2).
> **Base:** `v2.88.16.3-beta` (`fa0d69b0`).

---

## 0. Por qué `W4` va primero (y no es «el siguiente»)

`W3.3` **midió** el instrumento del que dependía toda lectura de mérito: el replay OOS es un
**sorteo del venue** y la banda de `K = 12` sorteos va de **`R −37,72` a **`+0,82`**, con
`σ(R) = 10,14` y la banda **cruzando el cero** ⇒ **`point_citable = False`**. El simulador sortea
rechazos, timeouts y parciales **sobre un `base_mid` constante de `100.0`**: sin precio real, el
book es casi todo ruido y cualquier incremento posterior no se puede distinguir del dado.

⇒ **`W4` es la precondición de cualquier lectura de mérito**, y su **criterio de éxito deja de ser
«el PAPER mide algo real»** para pasar a ser **«la banda se estrecha»** (§7).

---

## 1. Punto de partida (verificado en el código, no recordado)

| Qué | Dónde | Estado |
| --- | --- | --- |
| Contrato del precio | `PriceScript = Callable[[str, int], float]` (`auto_simulation_worker.py:309`) | ya existe, **ya recibe el tick de BARRA** (`W3`) |
| Default de producción | `flat_price_script` → **`100.0`** (`:330`), `price_script: PriceScript = flat_price_script` (`:629`) | **precio plano** |
| *Mid* del fill | `base_mid=self._price_script(symbol, bar_tick_now) or 100.0` (`:1404`) | **`100.0` silencioso** |
| Composición real | `AutoSimRuntime.__init__` (`:5956`) **no acepta** `price_script` ⇒ construye el worker (`:5996`) sin él | **el `100.0` es lo que corre en producción** |
| Dato real disponible | `SqlAlchemyOhlcvRepository(session)` + `make_closed_bar_loader(..., as_of, limit=120)` en régimen (`:5679-5683`) y ATR (`:5711-5715`) | **la fuente ya está inyectada**, con la frontera `<= B-1` de `W3` |

**Lectura:** `W4` no necesita inventar un proveedor. Necesita **leer el precio de la misma fuente y
la misma frontera**, y **dejar de fabricar un precio cuando no lo hay**.

---

## 2. Dos hallazgos que `W4` tiene que arreglar (invisibles con el precio plano)

**(P1-A) `:1996` — el `or 0` llega a la GEOMETRÍA de la señal.**
`price = Decimal(str(self._price_script(symbol, self._minute) or 0))` alimenta
`signal_identity_for_bar` y el plan (entrada/stop/R). Con `100.0` nunca se dispara; con precio real,
un símbolo sin barra en la ventana daría **precio `0`** ⇒ **stop a `0` y R sin sentido**. Es la
**misma clase** de bug latente que `W3` desactivó en el fill (un camino que «funcionaba» sólo porque
el otro extremo era constante).

**(P1-B) `:1580` — `or 0` + `if price > 0`: no revienta, OMITE EN SILENCIO.**
La equity no realizada **excluye** las posiciones sin precio. Con `100.0` es inocuo; con precio real,
**el DD se calcula sobre una equity que ignora posiciones abiertas** — una mentira silenciosa en el
camino de riesgo.

**(P1-C) Seis lecturas, tres formas, y sólo una usa el tick de barra.**

| Sitio | Forma | Ticks |
| --- | --- | --- |
| `:1404` (*mid* del fill) | `... or 100.0` | **`bar_tick_now`** ✅ |
| `:1580`, `:1860`, `:1996`, `:4836` | `Decimal(str(... or 0))` | `self._minute` ❌ |
| `:4075` | `self._price_script(row.instrument_id, self._minute)` (sin fallback) | `self._minute` ❌ |

Hoy son inocuas **porque el script es constante**; con precio real, **el *mark* y el *fill* leerían
precios de instantes distintos** (y por tanto distintos símbolos «sin precio»). `W4` las unifica.

**PERO la unificación NO es `Δ = 0`** (hallazgo 2026-10-01, ver §2.b): hay tests y scripts
herméticos cuyo `price_script` **sí** depende del argumento `tick`
(`_rising_price` = `100 + (minute % 40) * 0.05`; scripts que **cuentan llamadas**). Cambiar
`self._minute` por el tick de barra les cambia el resultado. La unificación es, por tanto,
un cambio de comportamiento **deliberado y medido**, no un efecto colateral gratis.

#### 2.b El paso 2 se parte en dos mitades (una es `Δ = 0`, la otra no)

| Mitad | Contenido | `Δ` |
| --- | --- | --- |
| **2a** | el worker adopta el seam `price_source` (default = envolver el `price_script` actual, que **ignora el tick**), refresco async por tick, y **muerte de los fallbacks silenciosos** (`or 100.0`, `or 0`) sustituidos por fail-closed **declarado** | **`Δ = 0` exacto**: con la envoltura constante ningún precio es `None`, así que el fail-closed no se dispara y los sitios de lectura conservan su tick actual | 
| **2b** | **unificar** las 6 lecturas al tick de barra (el contrato de `:304`) | **`Δ ≠ 0`**: mueve `_rising_price` y los scripts que cuentan llamadas ⇒ exige re-medir y actualizar esos tests, y **re-evaluar el golden** |

`2a` cierra el objetivo literal de `W4` («nunca un `100.0`/`0` silencioso») **sin mover un
byte**; `2b` cierra la **incoherencia temporal** que dejó el `W3` a medias. Se hacen por
separado para que cada una tenga su propia auditoría.

---

## 3. Diseño DECIDIDO (propietario, 2026-10-01)

### 3.1 Frontera temporal del precio: **MIXTA**

| Uso | Frontera | Razón |
| --- | --- | --- |
| **DECISIÓN** (señal, régimen, ATR, geometría) | **`close` de la última barra CERRADA (`<= B-1`)** | Es la frontera que `W3` instaló (`last_closed_bar_day`), **estrictamente sin lookahead**, y comparte cargador con régimen y ATR ⇒ **una sola foto por tick**. |
| **EJECUCIÓN y MARCA** (*mid* del fill, marks de equity y de protección) | **`open` / último precio de la barra CORRIENTE** | Es el precio del instante que `W3` declaró como ancla de ejecución (`OPEN(D+1)`) y **es conocido**: no es lookahead. Mantiene al fill anclado al tick de barra (idempotencia intra-barra intacta). |

**Regla de coherencia (test):** el *mid* del fill de un tick y la marca del mismo tick leen la
**misma** frontera de ejecución; la decisión de ese tick lee `<= B-1`. Nunca al revés.

#### 3.1.b Hallazgo de la exploración (2026-10-01): la ejecución necesita **dos ventanas**

El cargador que ya usan régimen y ATR (`make_closed_bar_loader`) acota a **`<= B-1`** y
**excluye** la barra corriente por diseño (es la guardia de `W3`). De esa ventana se obtiene
el `close(B-1)` de la **decisión** ✅, pero **no** el `open(B)` de la **ejecución**: la barra
`B` está fuera por construcción.

⇒ La fuente real necesita **una lectura con `as_of = día(B)`** (ventana `<= B`) y partirla:

| Uso | De la ventana `<= B` | Nunca |
| --- | --- | --- |
| DECISIÓN | `close` de la última barra con **día `< B`** | el `close`/`high`/`low` de `B` |
| EJECUCIÓN/MARCA | **`open` de la barra con día `== B`** | su `close`/`high`/`low` |

Sigue siendo **una sola lectura por tick** (una query), pero **no** la misma `as_of` que
régimen y ATR: la foto del precio es `<= B` y la del dato de decisión es `<= B-1`.

**Consecuencia operativa que hay que decidir ANTES de cablear (bloqueante):** con barras
`D1`, ¿de dónde sale el `open(B)`?

* **En replay/OOS** (histórico): la barra `B` **existe** en `ohlcv` ⇒ se lee su `open`. ✅
* **En vivo/PAPER**: la barra `D1` de **hoy** puede **no estar persistida** todavía ⇒ **no hay
  precio de ejecución** ⇒ por la regla fail-closed (§3.2) **ningún** símbolo ejecuta y el
  turno sale **`BLOCKED`**: el motor se **congela**, no falla. Es la regla funcionando, pero
  es una **consecuencia operativa de primer orden** que no se puede descubrir *después*.

Opciones para el `open(B)` en vivo (decisión del propietario, §10):
**(a)** sólo de la barra `ohlcv` de `B` (replay ✅ / vivo `BLOCKED` hasta que se persista);
**(b)** del último precio observado vivo (*feed*/`liquidity_source`) — precio real de mercado,
pero obliga a declarar su frontera temporal y su determinismo;
**(c)** aproximarlo con el `close(B-1)` de forma **explícita y declarada** (no silenciosa),
anotando que reintroduce el ancla de decisión como ancla de ejecución.

#### 3.1.c `refresh` debe ser asíncrono

El dato sale de PG por sesión/tick, igual que régimen y ATR ⇒ `PriceSource.refresh` es
**`async`** (el worker ya espera la foto de las otras fuentes en el mismo punto). El paso 1
(commit `10447d51`) lo dejó **síncrono**: se corrige al cablear, antes de sellar.

### 3.2 Fail-closed: **POR SÍMBOLO**

* Símbolo sin precio ⇒ **no se puede ejecutar** (`HOLD`), **declarado y contado** en el informe del
  turno y en el journal. El turno **sigue**.
* **Ningún** símbolo con precio ⇒ el turno se declara **`BLOCKED`**.
* **Nunca** `100.0` ni `0` silenciosos: no hay valor por defecto. Un precio ausente es un estado
  **nombrado**, no un número.

---

## 4. Alcance previsto

| Fichero | Cambio |
| --- | --- |
| `apps/api-python/src/bolsa_api/background/auto_price_provider.py` (**nuevo**) | `PriceSource` (protocolo que puede decir «no hay precio»: `float \| None`) + `OhlcvPriceSource` (real, `close(B-1)` para decisión / `open(corriente)` para ejecución, misma sesión y frontera que régimen/ATR) + `ConstantPriceSource` (envuelve el `PriceScript` inyectable para que **replay y tests sigan byte a byte**) |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | seam `price_source` (opcional; con `None` se envuelve el `price_script` actual ⇒ **`Δ = 0` para replay/tests**); muerte de `or 100.0` / `or 0`; unificación de las 6 lecturas al tick de barra; estado `HOLD`/`BLOCKED` declarado y contado |
| `AutoSimRuntime` (`:5956`) | compone el `OhlcvPriceSource` real por tick (misma sesión que régimen/ATR) |
| Tests | nuevo `test_auto_v2_real_price_source.py` (puro) + `test_auto_v2_real_price_pg.py` (PG real): sin barra ⇒ HOLD declarado; ningún símbolo ⇒ `BLOCKED`; **un precio `0`/`100.0` nunca aparece**; coherencia de fronteras (§3.1); el plan/stop no puede construirse sobre un precio ausente |
| Mutaciones | ver §5 |

---

## 5. Mutaciones previstas (mínimo 4; deben **morder**)

| Id | Defecto | Qué debe cazar |
| --- | --- | --- |
| `M283` | caer a **constante** (`100.0`) cuando no hay precio | el fail-closed (§3.2) |
| `M284` | precio **no determinista** (`now()`/último precio vivo) | el contrato determinista del `PriceScript` |
| `M285` | volver al **`or 0`** en la geometría de la señal | `P1-A` (§2) |
| `M286` | **lookahead**: la decisión lee `close` de la barra **en curso** | la frontera `B-1` de la decisión (§3.1) |
| `M287` | sin barra `B`, la ejecución cae a la barra **`B-1`** (precio rancio) | el fail-closed «sin `open(B)` ⇒ HOLD» (§3.1.b, §10.2) |

---

## 6. Golden

Todo precio sale de `100.0` ⇒ **los resultados cambian en todo** el golden y las suites de evidencia.
Se aplica la **misma política que `W3`**: el día se **re-mide y se re-elige por medición, no por
conveniencia**, con un script de delta reproducible (`v2_88_17_golden_day_delta.py`, exit `2` si el
delta no se reproduce) ⇒ **el sello no se firma si el delta no se reproduce**.

---

## 7. Criterio de ÉXITO de `W4` (declarado antes de medir)

> **`W4` sirve si y sólo si la banda del instrumento OOS SE ESTRECHA.**

Se mide **con la sonda de `W3.3`**, sin cambios en ella:

```
uv run --no-sync python apps/api-python/scripts/v2_88_16_3_oos_seed_robustness.py \
    --draws 12 --observe --out-dir operability_runs/w4-band
```

y se compara contra la banda sellada en `W3.3`:

| Métrica | `W3.3` (línea base, `100.0` plano) | `W4` | Criterio |
| --- | --- | --- | --- |
| `σ(R)` | **10,1381** | ? | **debe bajar** |
| IC 95 % de la media de R | **±5,7362** | ? | **debe bajar** |
| banda de R | `[−37,72, +0,82]` | ? | **no debe cruzar el cero** para poder citar un punto |
| banda de ciclos | `[43, 107]` | ? | **debe estrecharse** |

**Si la banda NO se estrecha, se declara así y `W4` no ha servido para lo ordenado** — no se
re-etiqueta como éxito. Es el compromiso de honestidad de todo el tramo `W3.x`.

> **Nota de instrumento:** la sonda de `W3.3` desplaza el ancla del `seed` del **venue**. Si con
> precio real el venue deja de ser la fuente dominante de varianza, la sonda sigue siendo válida
> (mide lo mismo) pero **su banda incluirá ahora la varianza del dato**, no sólo la del book. Se
> declarará explícitamente si eso pasa.

---

## 8. Deuda que este plan NO cierra

`P3-2`/`P3-3` (ventana PAPER real; `W4` la **habilita**), `OBS-19` (causa estructural de las listas
manuales), `OBS-16`, `OBS-15`, `OBS-22`, `OBS-14.b`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`,
`OBS-5`. `OBS-21`/`OBS-23` siguen **CERRADAS**. Nuevas de `W3.3`: la banda **no se asserta en CI** y
`K = 12` es un **presupuesto de tiempo**, no una elección estadística.

---

## 9. Secuencia de ejecución propuesta

1. **Proveedor puro** (`ConstantPriceSource` + `PriceSource`) con sus tests puros ⇒ **`Δ = 0`**
   verificable (replay y suites existentes **byte a byte iguales**).
   **HECHO** (`10447d51`): 12 tests puros; `Δ = 0` **estructural** (sólo su test importa el módulo).
2. **Paso 2a — HECHO**: el worker adopta el seam (`price_source`, default `None` ⇒ lee
   `price_script` **en vivo**, así que el `Δ = 0` incluye a los tests que mutan
   `worker._price_script`), **mueren los fallbacks silenciosos** (`or 100.0` en el *mid* del
   fill; `or 0` en los cuatro sitios de marca/señal/turno) y cada ausencia se **declara y
   cuenta** (`price_missing_counts`) con la señal anclada en `mid` (§3.1) y el *fill* en
   `execution`. Evidencia: 17 tests nuevos, `463 passed / 1 failed` en la suite `auto`
   (el fallo es el pre-existente de PostgreSQL, verificado contra el árbol prístino),
   `mypy` y `ruff` limpios, y —**la prueba fuerte**— el artefacto del sello **reproducido
   byte a byte** (§11).
   **RESUELTO en el paso 3–4**: el contrato de refresco se alineó a **async sin argumentos**
   (igual que régimen/ATR) y el precio se refresca en el MISMO punto por tick.
3. **Paso 2b (pendiente)**: unificar las 6 lecturas al tick de barra (§2.b) — **`Δ ≠ 0`**.
4. **`OhlcvPriceSource` real + composición — HECHO y TRAS INTERRUPTOR** (§12): el proveedor
   real (dos ventanas §3.1.b, `solo_ohlcv` §10.1), cableado de `refresh` y fail-closed
   end-to-end. Componer sin más **rompía ~8 tests `_pg` y el golden day** (que no siembran
   barras y vivían del `100.0`), así que la composición queda **inerte** tras
   `AUTO_ENGINE_SIM_REAL_PRICE` (default OFF). Evidencia: 23 tests puros verdes y la suite
   `auto` de vuelta al baseline `1 failed / 469 passed` (sólo el pre-existente de PG).
5. **Mutaciones `M283`–`M287`** (deben morder).
6. **Golden**: delta reproducible + re-elección del día por medición.
7. **Criterio de §7**: re-correr la banda de `W3.3` con precio real y **publicar el estrechamiento**
   (o la ausencia de él).
8. Sello `v2.88.17-beta` (`2.11.17-beta`) con su cita POST-TAG.

---

## 10. Decisiones del propietario

1. **Origen del `open(B)` en vivo/PAPER** (§3.1.b): **DECIDIDO (2026-10-01) = opción (a)**,
   sólo la barra `ohlcv` de `B`. En replay/OOS se lee su `open`; en vivo/PAPER, mientras la
   barra del día no esté persistida **no hay precio de ejecución** ⇒ `HOLD` por símbolo y
   turno `BLOCKED`, declarado. Se descartan (b) (precio vivo no determinista) y (c)
   (`close(B-1)` como ejecución, que reintroduciría el ancla de decisión).

2. **Fuente sin barra `B`**: confirmado por (a) — «no hay `open(B)`» ⇒ **`HOLD` por símbolo y
   turno `BLOCKED`**, y **nunca** caer a la barra `B-1` (mutación `M287`).

> La exploración de 2026-10-01 (**§3.1.b**) es un hallazgo **contra el plan original**, que
> asumía «una sola foto por tick»: la frontera de ejecución **no** es la de régimen/ATR.

---

## 11. Evidencia del `Δ = 0` del paso 2a (2026-10-01): artefacto **byte a byte**

El paso 2a se cierra **contra el artefacto sellado**, no contra la suite:

```
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
    --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py \
    --json --watch "$WATCH" --out artifacts/replay-fresh-w4.json
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py assert-artifact \
    --file artifacts/replay-fresh-w4.json
```

`VEREDICTO  REPRODUCIDO (render del sello, byte a byte)`: **3 445 622 B** y
`24066225…9F54F0` (CRLF) / `1E3ADAC2…9A37E7` (LF) — los tres idénticos al sello.

### 11.a La atribución se hizo por **experimento**, no por argumento

Con el worker **revertido a `d41a654b`** (pre-2a) el artefacto sale **byte a byte idéntico** al
del worker de `W4` (`8EE343F5…`): el cambio del paso 2a es **neutro** sobre el replay. Dos
corridas del mismo árbol también coinciden ⇒ el replay es determinista en esta máquina.

### 11.b Hallazgo operativo: el sello sólo reproduce contra una base **FRESCA**

La primera corrida dio `NO reproducido` (**3 540 095 B**): era la base de **desarrollo**
(`bolsa_v1`), donde cada símbolo del watch tiene **1286** barras —**una de más** que las 1285
del fixture congelado— por el dato real que ya vivía allí. La entrada no era la congelada y el
censo del artefacto cambió.

⇒ **`replay-repro` reproducido en local EXIGE base fresca** (`bolsa_v1_replay_w321` en `W3.2`;
`bolsa_v1_replay_w4` aquí). El job del CI no lo sufre porque arranca un servicio PostgreSQL
vacío, pero **correrlo a mano contra `bolsa_v1` da un rojo FALSO** cuya causa es la BD, no el
motor. Queda declarado para no volver a perseguirlo.

---

## 12. Rollout del precio REAL: costura INERTE tras declaración (2026-10-01)

Componer el `OhlcvPriceSource` en `AutoSimRuntime` **sin más** destapa una dependencia oculta
y deja el árbol en rojo: **~8 tests `_pg` + el golden day no siembran barras** y vivían del
`100.0` silencioso. Con `W4`, «sin precio ⇒ no se ejecuta» ⇒ dejan de abrir.

Evidencia medida con `pytest -k auto` (misma BD):

| Árbol | fallos |
| --- | --- |
| composición **sin** interruptor | **11** (≈8 nuevos) |
| composición revertida (`git stash`), misma BD | **3** (2 del sembrado, transitorios) |
| composición **con** interruptor (default OFF) | **1** (el pre-existente de PG) |

El golden day lo dijo con la traza del propio motor:

```
WARNI auto_sim v2 precio AUSENTE symbol=inst-gd2-0-0000000001: no se ejecuta/marca (HOLD fail-closed; jamás 100.0/0 silencioso)
assert 0 >= 3
```

⇒ **DECISIÓN del propietario (2026-10-01): opción (a), costura INERTE.** La composición queda
tras `AUTO_ENGINE_SIM_REAL_PRICE` (**default OFF**): el runtime conserva el `price_script`
hermético y **`main` sigue verde** (sólo el fallo pre-existente de PG). Activar el precio real
es un **acto explícito** — el patrón «costura inerte» que ya usó `V2.88.14/W1` — y es lo que
ejercita el criterio de éxito de §7.

### 12.a Trabajo que este interruptor ORDENA (no deuda nueva, trabajo declarado)

Con el flag OFF, el motor sigue usando `100.0` en producción: **`W4` no produce todavía su
efecto**. Para retirarlo hacen falta, en este orden:

1. **Sembrar barras `D1`** en los ~8 tests `_pg` y en el golden day, para que ejerciten el
   camino **REAL** (hoy dependen de un precio que no existe) — es el arreglo **correcto**, no
   un parche: un test que conduce el runtime real **debe** aportar su dato de precio.
2. **Re-elegir el golden day por medición** (§6), no por conveniencia.
3. **Encender el flag** en el camino de producción/medición y **correr §7**.

Declarado: mientras el flag esté OFF, el `Δ = 0` sigue siendo exacto (replay y suite intactos);
encenderlo **no** promete `Δ = 0` y obliga a re-medir el golden.

### 12.b Fronteras y contrato del proveedor real (implementado)

* `OhlcvPriceSource.refresh` es **async sin argumentos** (mismo contrato que régimen y ATR): el
  worker lo espera en `_v2_refresh_regime`, en el MISMO punto por tick, pero con **su propia
  ventana** (`<= B`, para sacar el `open(B)`), no la de régimen/ATR (`<= B-1`).
* `mid` = `close` de la última barra con día `< B`; `execution` = `open` de la barra con día
  `== B`. **Nunca** se lee `close`/`high`/`low` de `B` para la decisión (lookahead).
* Sin barra `B` ⇒ `execution` `None` ⇒ `HOLD` declarado (`M287` caza la caída a `B-1`).
* Sin `as_of` resoluble ⇒ ventana vacía ⇒ ningún precio (fail-closed), sin leer nada.
