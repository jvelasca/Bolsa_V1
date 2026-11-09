# `stopFiredNotFilled` — auditoría de los 27 ciclos del ledger `v2_93`

**Fecha:** 2026-11-09
**Objeto:** los ciclos con la marca `stopFiredNotFilled` del ledger
[`v2_93_2026-11-09.cycles.json`](../../operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json)
(192 ciclos, 182 emparejados con la fidelidad).
**Herramienta:** [`scripts/stop_fired_not_filled_audit.py`](../../scripts/stop_fired_not_filled_audit.py)
(`--selftest`, solo lectura). Salida completa en
`operability_runs/dia-d-auto/stop_fired_not_filled_audit.json` (gitignored).
**Estado:** el árbol medido **no se toca**. `pnpm window:freeze` → `freeze OK (c6cef5c9)` y
`git status --porcelain -- apps packages` vacío antes y después.

---

## 1. La pregunta

La auditoría externa pidió investigar la causa de los 26 ciclos con "stop disparado y no
ejecutado" (−0,05 R/ciclo). El informe de la ventana (§1.3) apuntó a un posible artefacto:
**93 filas con `mark = 0.0`** en 66 de los 192 ciclos, que `finite_number` acepta como número
y `mark <= stop` cuenta como toque.

La pregunta era binaria: ¿la marca `stopFiredNotFilled` la pone una **barra ausente** o una
**ejecución fallida**? Se responde ciclo a ciclo, sin re-ejecutar el harness, porque la
secuencia (`mark`/`currentStop`/`filledQty`/`orderCreated`/`survived`/`decisionReasons`) viaja
en **192/192** ciclos del ledger.

## 2. Reparto de los 27 ciclos marcados

La marca del ledger se **reproduce literalmente** en 192/192 ciclos (0 discrepancias) con su
regla: un tick con el stop disparado, `filledQty` nulo o `0` y `survived=True`. Después se
separa la causa:

| Cubo | n | Lectura |
| --- | ---: | --- |
| `fill_posterior` | **24** | El stop disparó en una barra REAL, no llenó ese tick y **ejecutó después**. Mediana de retraso: **1 tick** (18 de 24 al tick siguiente; 1 caso a 26 ticks). |
| `orden_creada_sin_fill` | **3** | Orden creada y **nunca** llenada al stop; la posición salió por `thesis_exit`. |
| `stop_evaluado_sin_orden` | 0 | Ningún ciclo con toque real y orden no creada. |
| `no_medible` | 0 | Ningún `orderCreated` nulo en los disparos. |
| `artefacto_puro` | **0** | Ningún ciclo marcado SOLO por barras ausentes. |
| `artefacto_metrico` | **0** | Ningún ciclo cuyo disparo ocurriera solo en un `mark = 0.0`. |

**Conclusión del reparto:** el `mark = 0.0` **no crea ninguna de las 27 marcas**. Todas nacen
de un toque con precio real. La hipótesis del artefacto queda refutada para la marca; no para
la métrica (§4).

Los tres `orden_creada_sin_fill` son la pérdida operativa real:

| Ciclo | Entrada | Toques reales | Salida | `realizedR` |
| --- | --- | --- | --- | ---: |
| `ABT` | 2024-07-26 | 2024-07-29 | `thesis_exit` 2024-07-30 | −0,590 |
| `PFE` | 2026-04-09 | 2026-05-04 | `thesis_exit` 2026-05-05 | −0,683 |
| `DIS` | 2026-06-04 | 2026-07-01 y 2026-07-02 | `thesis_exit` 2026-07-06 | −0,532 |

En los tres la posición quedó **sin protección** hasta la salida por tesis. Es el riesgo que
bloquea el dinero real; los otros 24 son el mismo mecanismo con una noche de exposición.

Y hay que decirlo entero: en los tres el precio **recuperó** y la salida por tesis fue mejor
que el stop (`realizedR − currentStopAtExitR` = +0,410, +0,317 y +0,468 R). No es edge: es
suerte de una muestra de tres. Por eso su peso en el sesgo es 0,0004 R/ciclo — y por eso un
solo hueco adverso los convertiría en el peor grupo de la tabla.

## 3. De dónde sale el −0,05 R/ciclo

Cruce con [`fidelidad_calibrado.csv`](../../operability_runs/dia-d-auto/fidelidad_calibrado.csv)
(26 de los 27 ciclos tienen pareja; el 27 es un duplicado de `AI.PA@2022-10-25`). El
denominador es el mismo 182, así que es comparable con lo publicado:

| Subconjunto | n | Σ (sim − real) | media | R/ciclo |
| --- | ---: | ---: | ---: | ---: |
| Todos los marcados (publicado) | 26 | **+8,9623 R** | +0,3447 R | **+0,0492** |
| `fill_posterior` | 23 | **+8,8851 R** | +0,3863 R | **+0,0488** |
| `orden_creada_sin_fill` | 3 | +0,0772 R | +0,0257 R | +0,0004 |

**El 99,1 % de la componente es la ejecución TARDE, no la ausencia de ejecución.** Los tres
ciclos sin ejecución aportan 0,0004 R/ciclo: casi no mueven la aguja porque salieron por
tesis a un R parecido al que el simulador les atribuía.

Contra el stop vigente, la pérdida extra por ciclo afectado tiene mediana **−0,488 R** y media
**−0,459 R** (`realizedR − currentStopAtExitR`, rango −1,642 a +1,418). Es el precio de una
noche de exposición, no de un stop que no existe.

**Corrección a la descomposición de la auditoría externa:** el componente de ejecución no es
"26 ciclos con stop disparado y no ejecutado" sino "24 ciclos con el stop ejecutado un tick
tarde". La recomendación no cambia —stop en firme en el bróker por posición—, pero el
mecanismo sí: lo que se corrige es el **retraso**, no una orden perdida.

## 4. El `mark = 0.0` sí contamina la métrica de toques

Separado de la marca, el defecto es real y está medido sobre los 192 ciclos:

| Medida | Valor |
| --- | ---: |
| Filas con `mark` ausente (`<= 0`) | **93** |
| Ciclos afectados | **66 / 192 (34,4 %)** |
| Ciclos con `stopTouchDays` inflado | **66** |
| `stopTouchDays` publicado | **579** |
| `stopTouchDays` con toques reales | **486** |
| Inflación | **+19,1 %** |

Afecta a `stopTouchDays`, `firstTouchDay`, `daysToFirstTouch` y `maeR`; **no** a
`stopFiredNotFilled` ni al R. Un ejemplo: `cyc-096f8782c440` (JPM, 2022-02-18) tiene un
"toque" el 2022-02-21 con `mark = 0.0`, `decisionReasons = []` y `orderCreated = false` — no
disparó nada. El disparo real es el 2022-02-24.

La corrección sigue siendo la misma y sigue pendiente: **una barra ausente debe ser `None`,
nunca `0.0`**, antes de `finite_number` y de la comparación con el stop.

## 5. Qué cambia y qué no

**Cambia:**

1. La causa del −0,05 R/ciclo queda nombrada: **retraso de un tick en la ejecución del stop**
   (99 % del peso), no stop ausente. Mediana de lag 1 tick; 18 de 24 al día siguiente.
2. El `mark = 0.0` **no** explica ninguna de las 27 marcas; infla la métrica de toques un
   19 % y hay que corregirlo igual.
3. El riesgo operativo duro son **3 ciclos** (`ABT`, `PFE`, `DIS`), no 26.

**No cambia:**

- La recomendación: stop en firme en el bróker, invariante `protective_order_present`
  por tick, veto de aperturas sin protección y reconciliación de órdenes vivas.
- La cifra de la descomposición: +0,0492 R/ciclo sobre 182.
- El bloqueo de dinero real: los 24 ciclos siguen teniendo una noche de hueco y los 3
  ninguna protección.

## 6. Reproducir

```powershell
.venv\Scripts\python.exe scripts/stop_fired_not_filled_audit.py --selftest
.venv\Scripts\python.exe scripts/stop_fired_not_filled_audit.py
```

El script reutiliza `export_auto_entries.load_ledger/select_entries/load_symbol_map` para que
la clave `(yahoo_symbol, entryDay)` sea la misma que produjo
[`entradas_auto.csv`](../../entradas_auto.csv). Sin base de datos imprime el `instruments.id`
y avisa; el reparto por cubos no depende del ticker.

## 7. Journal por ciclo (el artefacto que faltaba)

El reparto por cubos no permitía analizar los pares uno a uno. La misma herramienta emite ahora,
**sin re-ejecutar el harness**, un journal que une las tres piezas:

| Fuente | Qué aporta |
| --- | --- |
| `v2_93_2026-11-09.cycles.json` | `sequence` completo día a día (`mark`, `currentStop`, `orderCreated`, `filledQty`, `survived`, `decisionReasons`, `decisionLabel`, `dayFills`, `dayOrders`, `maeR`, `mfeR`) |
| `stop_fired_not_filled_audit.json` | `bucket`, `firstFireDay`, `stopFillAfterFireDay`, `lagTicksToStopFill`, `touchDays`, `firedDays`, `artifactDays`, `realizedR`, `currentStopAtExitR`, `excessLossR`, `unprotectedUntilThesis` |
| `fidelidad_calibrado.csv` | `simR`, `realR`, `reason`, `realExitReason`, `frictionR`, `riskPctSim`, `realRiskPct` y `pairStatus` (`paired`/`unmatched`) |

Artefactos (gitignored):

- `operability_runs/dia-d-auto/stop_fired_not_filled_journal_2026-11-09.json` — `schema:
  stop-fired-not-filled-journal-v1`, 27 ciclos marcados, **26 emparejados**, 1 sin pareja.
- `operability_runs/dia-d-auto/stop_fired_not_filled_journal_2026-11-09.csv` — una fila por ciclo
  marcado, con `sequenceJson` compacto para abrirlo en hoja de cálculo.

Verificación de la salida: 27 entradas con secuencia no vacía (2 a 58 ticks), 24
`fill_posterior` + 3 `orden_creada_sin_fill`, los tres sin protección (`ABT` 2024-07-26, `PFE`
2026-04-09, `DIS` 2026-06-04) y el único `unmatched` es `cyc-469e97bb6fc3:AI.PA@2022-10-25`, el
duplicado ya declarado en §3. La suma `sim − real` sigue siendo **+8,9623 R** sobre 182 pares
(**+0,0492 R/ciclo**).

## 8. Lectura del journal (2026-11-09, 15:40)

Estadística de solo lectura sobre el propio journal (`operability_runs/dia-d-auto/_journal_stats.py`).

### 8.1 El retraso no es de un tick en todos los casos

| Ticks entre el disparo y el fill | Ciclos |
| --- | ---: |
| 1 | **18** |
| 2 | 1 |
| 3 | 3 |
| 5 | 1 |
| 26 | 1 |

El 75 % es una sola marca y el 91,7 % son ≤3. Pero hay un ciclo de **26 ticks** (`AI.PA`
2022-10-25, el duplicado) y otro de 5 (`AI.PA` 2023-03-02).

### 8.2 El coste NO crece con el retraso

`excessLossR = realizedR − currentStopAtExitR` (negativo = se salió **peor** que el nivel del stop):

| Ticks | n | Σ exceso | Media |
| --- | ---: | ---: | ---: |
| 1 | 18 | **−11,6115 R** | −0,6451 R |
| 2 | 1 | −1,4115 R | −1,4115 R |
| 3 | 3 | **+0,7118 R** | +0,2373 R |
| 5 | 1 | −0,8431 R | −0,8431 R |
| **26** | 1 | **−0,4424 R** | −0,4424 R |
| sin fill | 3 | +1,1941 R | +0,3980 R |

Un ciclo con 26 ticks de retraso costó **menos** que la media de los de un tick, y los tres de
tres ticks salieron **mejor** que su stop. El determinante no es la espera: es la distancia entre
el nivel del stop y la marca a la que se ejecuta. La formulación "ejecución un tick tarde" describe
bien el caso modal, pero **no** es el mecanismo del coste.

### 8.3 El coste es de cola, no sistemático

22 ciclos salieron peor que su stop (−15,0203 R) y 5 mejor (+2,6179 R); suma −12,4024 R sobre
|coste| 17,6381 R. El top-5 concentra el **40,5 %** del valor absoluto: `AMZN` 2026-04-09
(−1,64 R), `NOKIA.HE` 2025-03-10 (−1,43 R), `JPM` 2022-08-29 (+1,42 R), `NOKIA.HE` 2024-06-18
(−1,41 R) y `OR.PA` 2022-04-26 (−1,25 R). Con 26 pares en cuatro años, cualquier media es
sensible a tres o cuatro nombres; `TXN` (6), `ABT` (4) y `NOKIA.HE` (4) aportan más de la mitad
de la muestra.

### 8.4 Los tres sin protección salieron mejor que el stop que les faltaba

`ABT` −0,590 R, `PFE` −0,683 R y `DIS` −0,532 R, con el stop en **−1,000 R** en los tres: la
salida por tesis fue más barata que un stop en firme. No es un argumento a favor de operar sin
protección (n = 3 y el riesgo es el hueco, no la media), pero sí impide presentarlos como pérdida
realizada.

### 8.5 Verificación independiente del sesgo

Suma `sim − real` sobre los **182** pares de `fidelidad_calibrado.csv`: **+23,9153 R**
(+0,1314 R/ciclo). Los 26 marcados aportan **+8,9623 R (37,5 %)** y los otros 156 pares
+14,9530 R. Confirma el "37,4 %" de [respuesta-auditoria-externa-2026-11-09.md](./respuesta-auditoria-externa-2026-11-09.md)
§1; el "+0,0492 R/ciclo" es la contribución **de estos 26 sobre el denominador de 182**, no el
sesgo total.

### 8.6 Lo que el journal NO permite afirmar

Cuánto del exceso es **hueco inevitable** (el precio abrió por debajo del stop) y cuánto es
**modelo** (el motor rellena a la marca del día siguiente en vez de al nivel del stop). Un sondeo
con `ohlcv_bars` y la regla "open/high/low frente al stop" sólo resuelve **2 de 24** casos: la
`currentStopAtExitR` del audit es el stop **al salir del ciclo**, no el del tick del fill, así que
derivar el riesgo por acción de ahí no es fiable. Separarlo exige el detalle de fills parciales y
la barra intradía, y eso no está en este journal. Se declara como límite, no se estima.
