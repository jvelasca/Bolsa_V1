# Diagnóstico — 2026-10-21: por qué la ventana PAPER sigue sin ciclos medibles

**Estado:** documento de diagnóstico. **No aplica cambios**: el árbol (`apps/`, `packages/`) está
congelado por el pin de la ventana mientras el día `20261021` está en vuelo. Todo lo que sigue es
**medido** sobre el run forzado de `2.11.159-beta`; lo que no se pudo medir se declara como tal.

- Motor: `auto-window-1484e253` · cuenta `1484e253d2d54645945a6b1d7` · venue `paper`
- Pin: `apps f37b6da0…` / `packages b33bf1e0…` (`freeze OK`, commit `fd8049c6`)
- Config del día: `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`, preflight con
  **37/80** símbolos operables (eje `BEAR_TREND`, gate por símbolo) y **80/80** barras
- Snapshot de las cifras: **2026-10-21 18:04 UTC** (el run sigue; los conteos crecen)

---

## 0. Resumen: cinco huecos, ninguno es el que creíamos

| # | Hueco | Severidad | Evidencia medida |
|---|---|---|---|
| A | El ranking es degenerado: **40 de 41** candidatas puntúan **0.0** exacto | Alta (selección arbitraria) | `opportunityScore` = `0.0` ×3232 / `0.37` ×119; 1 instrumento ≠ 0 |
| B | La adopción reconstruye el stop **sin validar la geometría** (12.9144 sobre entrada 10.3335) | **Crítica** (liquida en el primer tick) | log `adopted position without surviving plan … stop=12.9144…` + 4 ventas 17:46:06 |
| C | La evidencia de la adopción **no es durable** | Alta (no auditable) | 238 filas de posición hoy, **0** del símbolo adoptado |
| D | La adopción **pierde la atribución** (versión y ciclo) | **Crítica** (0 ciclos) | 4 fills de venta con `ver=None cycle=None` |
| E | Proyecciones **duplicadas** de motores efímeros | Media (coste ambiguo) | `3204115d` ×2 con 1933.3953 cada una |

---

## 1. Lo que sí quedó cerrado (y su evidencia)

El sello `2.11.159-beta` arregló dos costuras de cableado y **se ve en los números del día**:

| | `2.11.158-beta` (19:19) | `2.11.159-beta` (18:04 UTC) |
|---|---|---|
| entradas vetadas por `regime_invalid` | 275/280 (~98 %) | **399 / 3351** (11,9 %) |
| propuestas aprobadas | 0 | **1** |
| fills aplicados | 0 | **8** |
| posición adoptada | `avg_price=NULL` | `entry` reconstruido del libro + plan durable |

El `regime_invalid` residual **no es un fallo**: de los 80 símbolos, 43 están en `trend_down` y el
gate es `per_symbol`, así que vetar LONG ahí es la política. Antes vetaba el **100 %** porque el mapa
llegaba vacío (instancia recompuesta por tick + cortocircuito por barra).

---

## 2. Hueco A — el ranking es degenerado: 40 de 41 candidatas puntúan 0.0

**Medido** (filas `auto_entry_decision` de hoy, agrupadas por instrumento):

```
filas=3351   instrumentos=41   barras=['2026-10-21T00:00:00+00:00', 'None']
opportunityScore: {'0.0': 3232, '0.37': 119}
reasonCodes:      {'top_n_excluded': 2931, 'regime_invalid': 399,
                   'liquidity_unknown': 18, 'risk_measurement_unknown': 2, 'approved': 1}
instrumentos con score != 0.0: 1 -> 08598cdfbe004fbcaa59d5e2f
instrumentos con score == 0.0: 40
```

**Por qué 0.37 y no otra cosa.** Los pesos del ranker son `edge 0.30`, `liquidity 0.10`
(`OPPORTUNITY_WEIGHTS`). `0.37 = 0.30·0.9 + 0.10·1.0`: el edge sembrado por el preflight (`0.9`)
más la liquidez topada a `1.0`. Para las otras 40 candidatas **no hay edge** y la liquidez suma `0`,
así que el combinado es **exactamente cero** — no un cero pequeño, un cero estructural.

**Consecuencia.** Con `top_n = 5` el TOP queda formado por **1 candidata real y 4 ceros** elegidos por
desempate. `top_n_excluded` (2931) deja de distinguir "no compitió" de "no medía nada": el motivo es
cierto pero vacío de contenido. Esto **no impide operar** (hoy hubo 1 aprobación y 8 fills), pero la
selección no es económica: es alfabética.

**Observación abierta (no medida).** Solo **41** instrumentos generaron decisión de entrada de los
80 del watch. Conteo por tick (≈34 candidatas/tick: `top_n_excluded` 2896 y `regime_invalid` 395,
que son señales BUY) y el `HOLD` de la estrategia para el resto explica la diferencia, pero **es una
hipótesis, no una medición**: nadie ha registrado cuántas propuestas son `HOLD` en este run. Queda
como pregunta para el siguiente.

**Medido y descartado como causa (tick 1).** El primer tick del día emitió **80 avisos
`precio AUSENTE`** —uno por símbolo, exactamente 80 ocurrencias y todas contiguas, memoizadas una
sola vez— porque el loader todavía no había servido precios; a partir del tick 2 el progreso marca
`prices=80/80` en todos los ticks. Es un arranque en frío declarado, no una fuga de precio.

**Arreglo propuesto (sin aplicar).**
1. Leer el edge por `(instrumento, versión)` o declararlo ausente **por símbolo**; hoy el único con
   edge es el que sembró el preflight.
2. Una candidata **sin ningún componente medido** no debe entrar al ranking como un `0.0`
   comparable: debe declararse `opportunity_unscored` y quedar fuera del TOP (fail-closed honesto,
   mismo criterio que ya usa el optimizador con `optimizer_expected_value_unmeasured`).
3. Test: 41 candidatas con 1 sola medida ⇒ el TOP no se rellena con ceros.

---

## 3. Hueco B — la adopción reconstruye el stop sin validar la geometría (crítico)

**Medido** en el log del run, al adoptar `3204115d34544d00b2dd40b3c`:

```
WARNI auto_sim v2 adopted position without surviving plan symbol=3204115d… stop=12.91446496797647335
WARNI auto_sim v2 adoption degraded symbol=3204115d… source=reconstructed reason=no_durable_plan stop=12.9144…
```

y **4 ventas 0,04 s después** (`17:46:06.591 … 17:46:06.603`) que cierran 1933,3953 títulos a ~10,42.

El coste canónico de esa posición, desde los fills aplicados del `2026-10-20`, es **10,3335**
(966,69765 @10,3277 + 454,347895 @10,3318 + 225,433892 @10,3373 + 286,915863 @10,3389).

⇒ El stop reconstruido (**12,9144**) está **25 % POR ENCIMA** de la entrada en una posición **larga**:
es un stop que se dispara en el primer tick, por construcción. La liquidación inmediata no fue una
decisión de mercado: fue geometría inválida.

**Lo que no se puede afirmar.** La aritmética del código es `stop = entry − 1,5·ATR` con
`ATR ≥ 0`, y con `entry = 10,3335` eso da **10,02** (fallback 2 %) o `10,3335 − 1,5·ATR` (real):
**ninguna** de las dos produce 12,91. El valor exacto de `entry`/`ATR` usado en esa adopción **no es
reconstruible a posteriori** — y esa imposibilidad es, en sí, el Hueco C.

**Arreglo propuesto (sin aplicar).**
1. Validar la geometría reconstruida con holgura explícita (`0 < stop ≤ entry·(1 − min_gap)`) y,
   si no se cumple, declarar `PROTECTION_MISSING` **sin stop** en vez de un número que dispara.
   El guard actual (`stop <= 0 or stop >= entry`) existe pero **no se activó**, así que además hay
   que instrumentar qué valores entraron.
2. Construir la geometría sobre el **coste canónico** del libro, no sobre un espejo por motor.
3. Test: adopción con stop invertido ⇒ `PROTECTION_MISSING`, cero ventas en el tick de adopción.

---

## 4. Hueco C — la evidencia de la adopción no es durable

`_journal_position_event` (`auto_simulation_worker.py:5967`) hace solo:

- `self._v2_journal.append(entry)` (memoria del proceso),
- `self._emit(...)` (fila del día en memoria).

No hay writer al spine. Compárese con `_v2_journal_protection`, `_v2_journal_entry_decisions` o
`build_cycle_regime_sink`, que **sí** escriben en `decision_journal_entries`.

**Medido:** hoy hay **238** filas de posición en `decision_journal_entries` y **0** mencionan el
símbolo adoptado. Tras el run, `forward-market-20261021.json` solo conservará el **agregado**
(`journalReasons`): se sabrá que hubo `PROTECTION_MISSING`, no con qué entrada, stop, ATR ni fuente.

**Arreglo propuesto (sin aplicar).** Sink durable para `RECONCILIATION_REQUIRED` /
`PROTECTION_MISSING` / `ATR_GEOMETRY` (patrón de `build_cycle_regime_sink`) con
`entry`, `stop`, `atr`, `atrSource` y `reason`. Es el prerrequisito para poder depurar el Hueco B.

---

## 5. Hueco D — la adopción pierde la atribución: por eso hay 0 ciclos (crítico)

**Medido.** Los fills de compra del `2026-10-20` **sí** declaran versión; los de venta de hoy no:

```
2026-10-20 buy  966.697650 @ 10.3277 ver=v283-window-a cycle=None
2026-10-21 sell 966.697650 @ 10.4236 ver=None          cycle=None
```

`paper_material_readiness` casa ciclos por identidad; sin versión ni ciclo el cierre **no es un
ciclo medible**, y el gate `4 días / 2 episodios / 32 ciclos` no puede avanzar. Causa: la adopción
restaura `_position_version` desde la proyección (`None` en un motor nuevo) y el plan reconstruido
nace sin `cycleId`; los fills históricos, además, tienen `cycle_id = NULL`.

**Arreglo propuesto (dos partes, la segunda es decisión de diseño).**
1. Derivar la **versión** del último BUY aplicado del libro canónico (`AppliedFillFact.strategy_version_id`).
   Es un dato que existe y hoy se ignora.
2. Decidir si se acuña un `cycleId` **de adopción** determinista. Un ciclo acuñado no es un ciclo
   nacido de una entrada planificada: si se adopta, debe declararse como tal (`cycleOrigin=adopted`)
   o el conteo de ciclos mediría algo distinto de lo que dice medir.

---

## 6. Hueco E — proyecciones duplicadas de motores efímeros

**Medido.** El mismo símbolo con la **misma** cantidad bajo dos motores huérfanos, mientras el
canónico tiene una sola posición:

```
3204115d… engine=auto-v76-61bd1569 qty=1933.395300 entry=10.32  ver=v283-window-a
3204115d… engine=auto-v76-3ad9a1c8 qty=1933.395300 entry=None   ver=None
08598cdf… engine=auto-window-1484e253 qty=2170.458900 entry=9.152 ver=v283-window-a
```

**Riesgo declarado.** La cura de `entry_price` sellada en `.159` escribe el coste medio **de la
cuenta** sobre una fila **por motor**. Es correcto mientras el canónico tenga una sola posición viva
por símbolo (el caso de hoy); si algún día dos motores sostienen posiciones legítimas distintas, ese
coste sería ambiguo. En el siguiente sello: **no curar** cuando el símbolo tenga más de una fila viva.

---

## 7. Lo que NO es la causa (para que nadie lo persiga)

- **El régimen**: cerrado y medido (399/3351, todos `trend_down` legítimos).
- **El ATR ausente**: cerrado (`loaded()`), el ATR real llega y se declara su fuente.
- **El score 0.0**: degrada la selección (Hueco A) pero **no bloquea** — hoy aprobó 1 y hubo 8 fills.
- **La liquidez** (18 `liquidity_unknown`) y **la medición de riesgo** (2): residuales.
- **El gate**: no hay nada que "desbloquear"; el gate lee material y hoy no hay ciclos que leer.

## 8. Por qué el día 20261021 no puede aportar ciclos MEDIBLES

La única posición viva (`08598cdf`, ciclo `cyc-9b1599c7c635`) tiene plan durable con
`entrada 9.152`, `stop 8.9421`, objetivos `pending` y `holdingDeadlineAt = 2026-12-05`. El precio del
día es siempre la **apertura de la barra B** (`AUTO_ENGINE_SIM_REAL_PRICE=1`), idéntica en los 400
ticks. Con el stop un 2,3 % por debajo y el plazo en diciembre, **ningún tick adicional puede
cerrarla**: el día no puede aportar ciclos **medibles** y el gate seguirá sin avanzar.

> **Corregido tras el cierre (2026-10-22 17:54).** La predicción de "0 ciclos cerrados" era
> **falsa**: el run cerró **4 round-trips** (`sample.closedCycles = 4`, `durableFills = 20`,
> `turnTotals.closed = 1`, 12 fills en el día). La parte que sí se cumplió es la que importa para
> el gate: **0 medibles**. Medido en `forward.json` del run:
> `measurableCycles = 0`, `maxMeasurableCyclesPerVersion = 0`, blockers
> `no measurable risk` / `no exit orders` / `insufficient measurable cycles per strategy`.
> Los 4 ciclos aparecen además **sin fecha** en la ventana (`window.json → undatedCycles = 4`,
> `cyclesRead = 4`, `gate.cycles = 0`): el cierre existe pero no se puede atribuir a un día de
> calendario, así que el gate no lo cuenta. Es un hueco **nuevo** (ver §12) y no estaba en A–E.
>
> El veredicto del día fue el correcto y no un fallo duro: `status = MEDIDO` con
> `steps.forward = {exit: 2, declared: true, hard: false}` y `sample.verdict = BLOCKED`;
> `reason` vacío, sin `HARD_ERROR`. El freeze del artefacto es `apps f37b6da0` /
> `packages b33bf1e0`, idéntico al pin.

## 9. Orden de arreglo propuesto (ninguno aplicado)

| Orden | Hueco | Por qué primero |
|---|---|---|
| 1 | C (durabilidad de la adopción) | sin evidencia no se puede verificar B |
| 2 | B (geometría validada) | hoy destruye la posición en el primer tick |
| 3 | D (atribución versión → ciclo) | sin esto ningún cierre cuenta |
| 4 | A (ranking con ceros) | la selección pasa a ser económica |
| 5 | E (duplicados por motor) | corrección de coste, no de operación |

Cada uno con su test de regresión antes de tocar el siguiente, y **todos** requieren re-sellar
(`bump` + `window-pin --write`) y una nueva medición: no se backfillea nada de lo ya corrido.

## 10. Reproducción

```python
# distribución de scores del día (read-only)
select payload->>'instrumentId' inst, payload->>'opportunityScore' score
  from decision_journal_entries
 where event_type = 'auto_entry_decision' and created_at >= <inicio_del_dia>;
# ⇒ 1 instrumento con 0.37, 40 con 0.0

# coste canónico del símbolo adoptado
select created_at, side, quantity, price, strategy_version_id, cycle_id
  from sim_fill_finance_context
 where instrument_id = '3204115d34544d00b2dd40b3c' order by created_at;
# ⇒ compras 2026-10-20 @ ~10.33 (ver=v283-window-a) y ventas 2026-10-21 @ ~10.42 (ver=None)

# proyecciones vivas (motores huérfanos incluidos)
select symbol, engine_id, quantity, entry_price, strategy_version_id from sim_auto_positions;
```

## 11. Límites declarados

- Las cifras son un **snapshot** de las 18:04 UTC del 2026-10-21; los conteos del run siguieron
  creciendo hasta el cierre del 2026-10-22 a las 17:54.
- El valor exacto de `entry`/`ATR` en la adopción es **desconocido** y así se declara (Hueco C).
- AUTO sigue **OFF**; la ventana sigue **`INCONCLUSIVE`**; la rentabilidad **no** está certificada.

## 12. Hueco F — nuevos: ciclos cerrados SIN día y sin denominador de riesgo

**Medido al cerrar el día** (`operability_runs/window-runs/20261021/forward.json`,
`window.json`, `audit.json`; capturado 2026-10-22T15:54Z):

```
sample.closedCycles              4      (durableFills 20, turnTotals.closed 1)
sample.measurableCycles          0      maxMeasurableCyclesPerVersion 0
blockers                         no measurable risk · no exit orders ·
                                 insufficient measurable cycles per strategy
window.header.cyclesRead         4      undatedCycles 4
window.header.reservationsRead   1      regimeConfirmed 1
gate.cycles                      0      gate.days 4/4 · episodes 0/2
```

Dos huecos distintos que **no** son A–E:

**F-1 · el ciclo cerrado no lleva día.** El gate cuenta `days` por cubos de calendario y `cycles`
por ciclos **atribuidos a un día**. Con `undatedCycles = 4`, cuatro round-trips reales no entran en
el numerador: el gate lee `0/32` aunque hubo cierres. Sin resolverlo, ningún día aportará ciclos por
más que el motor opere.

**F-2 · el cierre no arrastra denominador de riesgo.** `no measurable risk`: el ciclo cerrado no
conserva `riskAmount`/`reserved_risk` positivo, así que su R no es reconstruible. Con
`reservationsRead = 1` sobre 4 ciclos, la reserva del ciclo no está enlazada al cierre. `no exit
orders` es la misma carencia por la vía de la orden de salida.

Ambos son de **atribución/registro**, no de decisión: el motor operó, cerró y no fabricó nada. Se
declaran aquí para que no se confundan con un fallo del sello A–E, y su arreglo requiere su propio
ciclo (test de regresión + re-sello + nueva medición).
