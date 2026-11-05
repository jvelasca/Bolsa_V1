# Auditoría: cómo AUTO determina el precio de compra y venta dentro del rango diario

**Fecha:** 2026-11-05 · **Alcance:** SIM/PAPER (AUTO OFF, PAPER `INCONCLUSIVE`). Auditoría **por lectura**; no se ejecutó
el motor con datos reales ni se midió ningún P&L.

## 1. Conclusión principal

**No existe un «punto óptimo» de compra/venta dentro del rango diario.** El motor no lo calcula ni lo estima:
no hay ninguna feature de posición en el rango (CLV, IBS, percentil del día, distancia a máximo/mínimo), ni órdenes
límite, ni zona de entrada. Lo que hay es una **regla fija** de precios:

| Evento | Precio usado | Fuente |
| --- | --- | --- |
| Decisión (señal, geometría, sizing) | `close(B-1)` (última barra cerrada) | `OhlcvPriceSource.mid` |
| Entrada (fill) | `open(B)` ± fricción simulada | `OhlcvPriceSource.execution` → `simulated_fill_schedule` |
| Stop / objetivo (salida) | nivel del stop/objetivo, o `open(B)` si el hueco es peor | `protective_fill_price` |
| Salida por otro motivo (T-stop, régimen, manual…) | `open(B)` ± fricción | `_v2_price_exec` |

Es decir: se compra a la **apertura** del día siguiente a la señal y se vende en un nivel **derivado del ATR**
(stop = entrada − 1,5·ATR; T1 = +1R; T2 = +2R) o a la apertura. El «punto» es el `open`, no un óptimo.
`close(B)` nunca se lee (correcto: sería lookahead).

## 2. Cadena verificada

1. **Señal:** sobre la barra cerrada anterior (`signal_feature_context`, `rules_engine`); sin lookahead.
2. **Geometría:** `entry = signal.price = close(B-1)`; `atr` real de la señal o, si falta, `price × 2 %`
   (`auto_v2_entry.py:1597`, `atr_pct_fallback`). Stop = `entry − atr_multiplier(1,5) × atr`; T1/T2 = `entry + 1R / 2R`
   (`target1_r`, `target2_r`).
3. **Sizing:** `qty = riesgo / |entry − stop|` con `entry = close(B-1)` (`risk_allocator`), con coste (comisión 10 bps,
   spread 2 bps, slippage 5 bps) **dentro del presupuesto**.
4. **Fill de entrada:** `open(B)` como `base_mid` + slippage/spread del simulador (`simulated_broker.py:156`).
5. **Posición:** `build_position_state_from_fill` conserva el stop y T1/T2 **del plan** (calculados sobre `close(B-1)`);
   solo recalcula `initial_risk = |fill − stop|`.
6. **Gestión intradía:** con `low/high` de la barra, `exit_plan._collect_reasons` detecta toques; si stop y objetivo
   caen en la misma barra gana el stop (conservador). El fill se declara en el nivel (`protective_fill_price`).

## 3. Hallazgos

### R1 — Hueco decisión→ejecución sin guarda ni re-dimensionado · 🟠 Alta · Por lectura
- **Dónde:** `auto_v2_entry.py:1645` (entrada = `close(B-1)`), `position_state.py:584-692`.
- **Fallo:** el sizing y la geometría se calculan sobre `close(B-1)`, pero se ejecuta a `open(B)`. Ante un hueco
  alcista, la distancia real al stop es mayor que la presupuestada: el riesgo efectivo por operación **supera**
  `max_risk_per_trade_pct`, y T1/T2 quedan más cerca (en R reales) de lo previsto. Ante un hueco bajista hacia el stop,
  el riesgo real es menor pero el stop puede quedar a una fracción de ATR. Solo la ruta con propuesta del parte
  contrasta `execution_price` (D-1); las señales normales no.
- **Debería ser:** un veto `entry_gap_exceeds_tolerance` si `|open − close(B-1)| > k·ATR`, y recalcular
  `qty`, `T1`, `T2` sobre el precio de ejecución (o fijar el stop en R sobre el fill). Medir el hueco en el journal.

### R2 — La fricción aplicada no coincide con la modelada · 🟡 Media · Por lectura
- **Dónde:** `simulated_broker.py:164-165` (`adverse_slippage_bps=4`, `spread_bps=6`, fijos) frente a
  `auto_v2_entry.py:362-377` (comisión 10, spread 2, slippage 5, configurables por env).
- **Fallo:** el sizing descuenta un coste y el fill aplica otro. Cambiar `AUTO_ENGINE_SIM_V2_*_BPS` mueve el
  presupuesto pero no el precio de fill. Además el slippage crece con el ordinal del parcial (`4·i`), sin relación
  con liquidez ni con el rango del día.
- **Debería ser:** una única fuente de costes que alimente a ambos, y slippage función de volatilidad/liquidez.

### R3 — El precio de fill no se acota al rango real de la barra · 🟡 Media · Por lectura
- **Dónde:** `simulated_broker.py:252-258`, `exit_plan.py:303-343`.
- **Fallo:** `open ± fricción` y `nivel de stop − fricción` pueden quedar **fuera** de `[low, high]` del día
  (p. ej. vender por debajo del mínimo). Es conservador, pero un precio imposible contamina la medición de fricción
  (`applied_cost`) y el P&L comparado con un backtest.
- **Debería ser:** clamp declarado a `[low, high]` de la barra, y registrar cuando el clamp actúa.

### R4 — Los objetivos se llenan al nivel exacto si el `high` lo toca · 🟡 Media · Por lectura
- **Dónde:** `exit_plan.py` (`_target_touched` con `high`), `protective_fill_price`.
- **Fallo:** un toque de 1 tick en T1/T2 se liquida al nivel completo (fill de límite sin cola, sin volumen en ese
  nivel). El propio docstring declara que no es realista. Sesga a favor los P&L de T1/T2 frente al stop.
- **Debería ser:** exigir penetración mínima (`high ≥ target + ε·ATR`) o aplicar la fricción de salida al nivel.

### R5 — ATR sintético permitido por defecto · 🟡 Media · Por lectura
- **Dónde:** `auto_v2_entry.py:214-224`, `1127`, `1597` (`atr_required=False`).
- **Fallo:** sin ATR real, stop y tamaño derivan de `2 %` del precio: la distancia de stop no refleja la
  volatilidad del instrumento. Está declarado en el journal (`ATR_GEOMETRY`), pero no veta.
- **Debería ser:** activar `AUTO_ENGINE_SIM_V2_ATR_REQUIRED` una vez medida la fracción de señales con ATR real.

### R6 — Sin evidencia de que el punto de entrada sea mejor que alternativas · 🟡 Media · Por diseño
- **Fallo:** al no existir optimización de entrada, no hay prueba de que `open(B)` (frente a un límite en
  retroceso, a `close(B-1)` o a una media del día) rinda mejor. El Strategy Lab simula `signal[i-1] → open[i]`
  (`rules_grid.py:91-96`), por lo que es coherente con AUTO, pero **no compara** ejecuciones.
- **Debería ser:** si se quiere un «punto óptimo», es un **experimento medible**, no una constante: comparar en OOS
  `open(B)` vs. límite a `close(B-1) − k·ATR` (con tasa de no-fill medida) vs. VWAP del día, con los mismos costes.
  Con barras D1 no se puede reconstruir el orden intrabar: cualquier «óptimo diario» calculado a posteriori
  (mínimo/máximo del día) es **lookahead** y no debe usarse como referencia de ejecución.

## 4. Lo que está bien

- Sin lookahead: decisión sobre `close(B-1)`, ejecución sobre `open(B)`, `close(B)` no se lee (`_finite_field`).
- Sin precio no hay operación (fail-closed, W4/P9); jamás se cae a la barra `B-1` como precio de ejecución.
- Stop y objetivo en la misma barra: gana el stop.
- Hueco adverso al stop: se llena al `open`, no al nivel (`min/max` en `protective_fill_price`).
- El P&L, el fill y el estado usan **un único** precio declarado (P-2).

## 5. Limitaciones

Auditoría por lectura. No se midió la distribución real de huecos, la fracción de señales con ATR real ni el efecto de
R1–R4 sobre el P&L. Cerrar estos hallazgos **no aporta evidencia operativa**: AUTO sigue OFF y la rentabilidad no está
demostrada.
