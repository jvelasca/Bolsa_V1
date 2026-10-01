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

---

## 3. Diseño DECIDIDO (propietario, 2026-10-01)

### 3.1 Frontera temporal del precio: **MIXTA**

| Uso | Frontera | Razón |
| --- | --- | --- |
| **DECISIÓN** (señal, régimen, ATR, geometría) | **`close` de la última barra CERRADA (`<= B-1`)** | Es la frontera que `W3` instaló (`last_closed_bar_day`), **estrictamente sin lookahead**, y comparte cargador con régimen y ATR ⇒ **una sola foto por tick**. |
| **EJECUCIÓN y MARCA** (*mid* del fill, marks de equity y de protección) | **`open` / último precio de la barra CORRIENTE** | Es el precio del instante que `W3` declaró como ancla de ejecución (`OPEN(D+1)`) y **es conocido**: no es lookahead. Mantiene al fill anclado al tick de barra (idempotencia intra-barra intacta). |

**Regla de coherencia (test):** el *mid* del fill de un tick y la marca del mismo tick leen la
**misma** frontera de ejecución; la decisión de ese tick lee `<= B-1`. Nunca al revés.

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
2. **`OhlcvPriceSource` real** + composición en `AutoSimRuntime` + fail-closed **por símbolo**.
3. **Muerte de los `or 100.0` / `or 0`** y unificación de las 6 lecturas al tick de barra (tests de
   `P1-A`/`P1-B`/`P1-C`, con test que **falla** si un precio `0`/`100.0` vuelve a aparecer).
4. **Mutaciones `M283`–`M286`** (4/4 deben morder).
5. **Golden**: delta reproducible + re-elección del día por medición.
6. **Criterio de §7**: re-correr la banda de `W3.3` con precio real y **publicar el estrechamiento**
   (o la ausencia de él).
7. Sello `v2.88.17-beta` (`2.11.17-beta`) con su cita POST-TAG.
