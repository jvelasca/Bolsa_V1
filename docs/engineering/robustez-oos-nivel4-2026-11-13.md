# Robustez OOS del motor AUTO con datos reales — 2026-11-13

**Nivel 4 del plan de sellado.** Medición de robustez *out-of-sample* con el motor **congelado**, stores en
memoria (**cero escrituras** en PostgreSQL) y los umbrales **pre-registrados** del repositorio. Ni se ajusta
ningún umbral ni se rellena ningún hueco con `0`.

**Veredicto de este nivel: `NOT_MEASURED`.** El replay OOS no produjo **ningún ciclo cerrado**, así que no hay
R realizado, ni acierto de signo, ni distribución que declarar. Todo hueco se publica como `n/d`.

## 1 · Comando y modo

```text
python apps/api-python/scripts/v2_86_replay_oos_viability.py --json \
  --out operability_runs/oos/v2_86.json
```

`nature = INVESTIGACION` · `phase = V2.86 AUTO-MATERIAL-14 REPLAY OOS VIABILIDAD` · `account =
1484e253d2d54645945a6b1d7` · `venue = paper` · `watch = 20` instrumentos · `historyDays = 1303`.

El artefacto declara sus propios límites, y se reproducen aquí sin suavizarlos:

- NO sustituye la ventana PAPER: el cubo de calendario sale del reloj de pared (`sim_fill_finance_context.created_at`).
- NO cierra `P3-2`/`P3-3`: es evidencia de investigación, clase distinta.
- Aproximación D1: un día = un tick.
- `Version B = HOLD` (la ACTIVE exigiría su propia fuente de barras acotada).
- `Edge = 0.9` y `Liquidez = 1e6` son **datos declarados del seam**, no mediciones.
- Cero escrituras a PostgreSQL: stores en memoria.

## 2 · Lo que midió el replay

| Medida | Valor |
| --- | --- |
| Ventana rejugada | 2022-01-27 → 2026-11-12 |
| Ticks (un día = un tick) | 1.239 |
| Propuestas | 1.200 |
| Decisiones | 24.780 |
| Vetos | 24.779 |
| Órdenes | 1 |
| Fills | 4 |
| Días con fills | 1 (2022-01-27) |
| Régimen dominante | `BEAR_TREND` 844 / `HIGH_VOLATILITY` 392 / `SIDEWAYS` 3 |

Motivos del journal: `approved` 1 · `governor_halted` 3.650 · `regime_invalid` 2.544 ·
`top_n_excluded` 4.957.

**Puntuación OOS:** `realizedCount = 0`, `roundTrips = []`, `meanR = null`, `medianR = null`,
`positiveShare = null`, `unmeasuredCount = 0`. Queda **una posición abierta** con `unrealizedR = -4.588309`
(entrada 2022-01-27, `v283-window-a`), que no es un resultado: es una posición sin cerrar.

## 3 · Lectura honesta

- El motor pasó **1.239 días rejugados** haciendo **una** entrada y **ningún** cierre. No hay ida y vuelta, así
  que la pregunta «¿el motor gana dinero fuera de muestra?» **no queda contestada**: queda declarada como no
  medida.
- El patrón que sí se ve es el **gobierno**: de 24.780 decisiones, 24.779 fueron vetos y 3.650 de ellos
  `governor_halted`. Un motor que casi nunca entra no se puede evaluar por R realizado; se evalúa por por qué
  no entra, y eso es materia de otra evidencia (no de este doc).
- `meanR = null` **no** es «0»: es «no hay muestra». Presentarlo como 0 sería exactamente el relleno que el
  plan prohíbe.

## 4 · Contraste con los umbrales pre-registrados

Umbrales de `BASELINE_THRESHOLDS` (`baseline_arms.py`), fijados **antes** de correr y pinzados por test:

| Umbral | Valor |
| --- | --- |
| `minNetReturnPct` | 0.0 |
| `maxDrawdownPct` | 15.0 |
| `minPositiveWindowPct` | 60.0 |
| `minExcessVsBuyHoldPct` | 0.0 |
| `minRoundTripCostBps` | 22.0 |

Con `realizedCount = 0` **ninguno** de los cinco se puede evaluar: un `netReturnPct` derivado de cero cierres
no es una medición, es un artefacto aritmético. Los cinco quedan `NOT_EVALUATED` / `n/d`, y **no** se ha
tocado ninguno para que pasen.

## 5 · Variante de banda

La sonda de banda (`v2_94_dia_d_multi_band.py`, K sorteos con ancla temporal desplazada) se lanzó sobre la
misma cuenta y rango de años. **No se publica su resultado en este documento**: sin ciclos cerrados en el punto,
una banda de `expectancyR` sólo puede reproducir el mismo «no medido» con más coste. El intento y su alcance se
declaran aquí para que conste; no se presenta como medición.

## 6 · Invariantes respetados

- Motor congelado, stores en memoria, cero escrituras.
- Sin ajuste de umbrales, sin forzar régimen, sin backdating.
- `activationAllowed` sigue `false`.
- Este documento **no** acredita rentabilidad ni aptitud operativa: acredita que el OOS, hoy, **no está medido**.

## 7 · Qué haría falta para medirlo

1. Un replay OOS en el que el motor **cierre** al menos un número declarado de ciclos (hoy: 0).
2. Ventana y watch declarados de antemano, con barras `1d` completas para todos los símbolos del watch.
3. Coste y liquidez medidos, no tomados de un seam declarado (`edge = 0.9`, `liquidez = 1e6`).
4. Repetición con banda (K sorteos) **después** de que el punto tenga muestra.
