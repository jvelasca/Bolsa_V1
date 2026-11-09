# Control de entradas aleatorias frente a AUTO — el problema es la señal, y la geometría lo amplifica

**Fecha:** 2026-11-09
**Experimento:** [`scripts/random_entry_control.py`](../../scripts/random_entry_control.py)
**Ventana:** `2022-01-27` → `2026-10-26` · **coste 12,7 bps por lado** · **100 semillas** uniformes
**Universo:** los 10 símbolos con entrada real de AUTO (`--universe csv`)
**Geometría base:** `policy` — marca intradía de máximo, breakeven en T1, armado en T1, trailing `1,0 R`,
máximo 45 días de tenencia

Este es el experimento que el informe de la ventana no incluía. Responde a una sola pregunta: **las
entradas de AUTO, ¿son mejores que el azar?** La geometría de salida es la misma para las tres ramas
(`RANDOM`, `CSV`, `MOMENTUM`), así que cualquier diferencia es de **entrada**, no de salida.

---

## 1. Tabla RANDOM frente a CSV (geometría del motor, `policy`)

`RANDOM` reparte 100 entradas uniformes sobre el universo y la ventana, con las mismas reglas de
dimensionado, veto por hueco y coste. Los percentiles describen esa distribución nula.

| Métrica | p5 | p25 | **Mediana** | p75 | p95 | **CSV (AUTO)** | Percentil de CSV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Neto % | -26,651 | -12,872 | **-3,943** | 6,754 | 17,711 | **-18,644** | **12 %** |
| Expectancy R | -0,166 | -0,049 | **0,015** | 0,083 | 0,174 | **-0,056** | **23 %** |
| Net expectancy R | -0,244 | -0,126 | **-0,062** | 0,006 | 0,097 | **-0,131** | **23 %** |
| Max drawdown % | 10,331 | 14,029 | **17,999** | 23,373 | 31,126 | **24,273** | **77 %** (peor) |
| Sharpe | -0,722 | -0,296 | **-0,059** | 0,202 | 0,437 | **-0,492** | **9 %** |
| Tasa de acierto % | 43,839 | 47,296 | **49,081** | 51,339 | 54,149 | **46,154** | **20 %** |
| Payoff | 0,899 | 1,001 | **1,051** | 1,106 | 1,182 | **1,069** | **58 %** |

**Momentum en la misma geometría:** neto **+43,307 %**, expectancy **+0,102 R**, net expectancy
**+0,024 R**, `cycles 659`, `entries 668`, drawdown 23,389 %.

### Lectura

- **El neto no es una buena comparación entre ramas.** CSV ejecuta **182** ciclos y RANDOM **~204** de
  mediana con exposición media 32,2 % frente a 39 %: el neto mezcla número de ciclos, exposición y
  suerte de secuencia. **La expectancy por ciclo es la métrica limpia**, y es la que hay que citar.
- Con la geometría del motor, las entradas de AUTO se sitúan en el **percentil 12 de neto**, **23 de
  expectancy** y **23 de net expectancy**. Es decir: **entre el 77 % y el 88 % de las entradas
  aleatorias lo hacen mejor**. Un sistema con edge de entrada debería quedar por encima de la mediana.
- El **payoff** de CSV (1,069) está por encima de la mediana (1,051, percentil 58) y la **tasa de
  acierto** por debajo (46,2 %, percentil 20). Es el perfil de una entrada que acierta poco y gana
  poco cuando acierta: no es un problema de tamaño de ganadores, es de **frecuencia de acierto**.
- El **drawdown** de CSV (24,3 %) está en el percentil 77, el peor cuartil de la distribución aleatoria.
- El **Sharpe** en el percentil 9 es la peor lectura del conjunto.
- **Caveat de momentum:** su exposición media es **119,7 %**, no 32 %. Su neto de +43,3 % **no es
  comparable al de CSV**; lo comparable es la expectancy por ciclo (+0,102 R frente a -0,056 R), y ahí
  gana por 0,158 R.

### 1.1 Verificación independiente del artefacto (2026-11-09 11:30)

La tabla anterior **no se transcribe a mano**: se recalcula desde
`operability_runs/dia-d-auto/control_entradas_aleatorias.json` (75 177 bytes, `09:58:59`).
La comprobación se hizo con un lector independiente del documento (percentiles interpolados sobre las
100 ramas `random#0`…`random#99`, `mode = csv`/`momentum` aparte) y reproduce las cifras publicadas:

| Métrica | p5 | p25 | Mediana | p75 | p95 | CSV | Percentil CSV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Neto % | -26,6508 | -12,8717 | -3,9428 | 6,7541 | 17,7115 | -18,6439 | 12,0 |
| Expectancy R | -0,1661 | -0,0487 | 0,0155 | 0,0831 | 0,1740 | -0,0558 | 23,0 |
| Net expectancy R | -0,2442 | -0,1258 | -0,0619 | 0,0062 | 0,0966 | -0,1306 | 23,0 |
| Max drawdown % | 10,3305 | 14,0291 | 17,9994 | 23,3730 | 31,1264 | 24,2727 | 77,0 |
| Sharpe | -0,7218 | -0,2959 | -0,0586 | 0,2017 | 0,4365 | -0,4924 | 9,0 |
| Tasa de acierto % | 43,8386 | 47,2956 | 49,0813 | 51,3388 | 54,1493 | 46,1538 | 20,0 |
| Payoff | 0,8994 | 1,0015 | 1,0507 | 1,1063 | 1,1822 | 1,0685 | 58,0 |

Dos lecturas que la tabla principal no mostraba y que refuerzan la conclusión:

- **Exposición media:** CSV **32,2 %** frente a mediana aleatoria **39,8 %** (percentil **1**). CSV está
  **infraexpuesto** un 19 % relativo. Por eso su neto (-18,6 %) y su Sharpe (-0,49) son todavía
  **peores de lo que parecen**: con la exposición de la mediana aleatoria, el neto caería
  proporcionalmente otro ~20 %.
- **Número de ciclos:** CSV **182** frente a mediana **204** (percentil **7**). El neto no es una
  comparación limpia en ninguna dirección: menos ciclos, menos exposición y peor expectancy a la vez.

El artefacto no viaja en el ZIP (`operability_runs/` está en `.gitignore`); las cifras quedan fijadas
aquí y se regeneran con el comando de §5. La tabla de `evidence/control-entradas-aleatorias-2026-11-09/README.md`
§3.1 es la misma, sin los dos últimos puntos.

---

## 2. Señal o geometría: el mismo CSV con tres modelos de salida

Misma entrada de AUTO, misma ventana, mismo coste, misma calibración. Solo cambia cómo se sale.

| Modelo de salida | Neto CSV | Percentil neto | Expectancy CSV | Percentil exp. | Net exp. CSV | Percentil net-exp | Momento (exp.) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `policy` (motor actual) | -18,644 % | **12 %** | -0,056 R | **23 %** | -0,131 R | **23 %** | +0,102 R |
| `structural` | -15,457 % | **12 %** | -0,019 R | **26 %** | -0,093 R | **27 %** | +0,090 R |
| `time-only` | **+12,018 %** | 34 % | **+0,335 R** | **85 %** | **+0,256 R** | **85 %** | +0,408 R |

### Lectura

1. **El edge de entrada existe, pero la geometría se lo come.** Con salida solo por tiempo (45 días),
   **las mismas entradas de AUTO suben del percentil 23 al 85** de expectancy. Pasan de -0,056 R a
   **+0,335 R por ciclo**. No se ha tocado la señal: se ha dejado de interrumpirla.
2. **El culpable no es el stop, es la secuencia breakeven/T1 + trailing.** `structural` (sin breakeven
   forzado en T1) recupera solo 0,037 R; `time-only` recupera **0,391 R**. La mayor parte de la
   destrucción está en **cerrar en T1/breakeven y perseguir el precio con el trailing**, no en el stop
   inicial.
3. **En percentil de neto, `policy` y `structural` empatan en 12 %**, pero `time-only` sube al 34 % aun
   con drawdown 29,9 % (percentil 75). El neto sigue penalizando el número de ciclos y la exposición;
   la expectancy es la que cambia de régimen.
4. **AUTO no bate a momentum en ningún modo**, pero en `time-only` se acerca (0,335 R frente a 0,408 R).
   Con la geometría actual está a 0,158 R por ciclo.

**Conclusión:** el resultado no es "AUTO no tiene edge". Es "AUTO tiene edge de entrada que la
geometría de salida actual destruye". El orden de prioridad del arreglo cambia: antes que el filtro de
entrada, hay que revisar **T1/breakeven/trailing**. Aun así, el percentil 23 en una geometría que no
estorba tanto (`structural`, 26 %) confirma que **también hay un problema de señal**: ni sin el
breakeven se llega a la mediana aleatoria.

---

## 3. Caveats que invalidan el nivel absoluto (no la comparación)

| Caveat | Efecto |
| --- | --- |
| **Calibración in-sample** | La geometría se eligió por RMSE contra los mismos 182 ciclos que después se comparan (§4). El **nivel** de RANDOM queda reproducido, no predicho. La comparación **relativa** entre ramas sigue siendo válida porque comparten geometría. |
| **Momentum con exposición 119,7 %** | Su neto no es comparable al de CSV; solo su expectancy. |
| **10 ciclos reales sin pareja** | `unmatchedReal = 10`, `unmatchedSim = 0`. La fidelidad se mide sobre 182 pares, no sobre 192 ciclos. |
| **Coste 12,7 bps por lado** | Cifra de calibración, no el modelo de coste del motor (10/2/5). Afecta al nivel, no al orden. |

## 4. Fidelidad simulador/ledger (por qué el simulador es más optimista)

Del mismo artefacto, variante ganadora (`stopTrigger=close`, `watermark=high`, `breakeven=t1`, `arm=t1`,
`trailR=1,0`, `partials=t1`):

| Grupo | n | Media real | Media sim | Sesgo |
| --- | ---: | ---: | ---: | ---: |
| Todos | 182 | -0,1872 R | -0,0558 R | **+0,1314 R** |
| Ganadores reales (R>0) | 77 | +1,3450 R | +1,2851 R | -0,0599 R |
| Perdedores reales (R<=0) | 105 | -1,3109 R | -1,0392 R | **+0,2717 R** |
| Stop disparado sin fill | 26 | -0,4529 R | -0,1082 R | **+0,3447 R** |
| Sin stop disparado-sin-fill | 156 | -0,1430 R | -0,0471 R | +0,0959 R |
| Tocado y no cruzado al cierre | 16 | -1,3509 R | -1,1711 R | +0,1798 R |
| Sin toque previo declarado | 153 | +0,0117 R | +0,1424 R | +0,1307 R |
| Salida por tiempo | 2 | -0,1567 R | +0,0820 R | +0,2386 R |
| Salida por tesis | 9 | -1,0000 R | -1,0271 R | -0,0270 R |

`rmse 0,748` · `corr 0,888` · `signAgreement 0,929` · riesgo medio sim 3,419 % frente a real 3,501 %.

**El sesgo es positivo = el simulador es más optimista.** El 37 % del sesgo total
(0,0492 R de 0,1314 R por ciclo, ~8,96 R acumulados) viene de los 26 ciclos con stop disparado y no
ejecutado. Se documenta en [respuesta-auditoria-externa-2026-11-09.md](./respuesta-auditoria-externa-2026-11-09.md)
§1.

## 5. Reproducción

```powershell
# geometría del motor (policy) + calibración contra el ledger
.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --mode csv --calibrate `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias.json

# las otras dos geometrías
.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --exit-mode structural `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias_structural.json

.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --exit-mode time-only `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias_timeonly.json
```

`entradas_auto.csv` es la lista `date,yahoo_symbol` de las entradas reales de AUTO. Los tres JSON quedan
bajo `operability_runs/`, que está en `.gitignore`: **no viajan en el ZIP del tag** y se regeneran con el
comando anterior. Los parámetros y las cifras quedan fijados en este documento y en
[evidence/control-entradas-aleatorias-2026-11-09/README.md](./evidence/control-entradas-aleatorias-2026-11-09/README.md).
