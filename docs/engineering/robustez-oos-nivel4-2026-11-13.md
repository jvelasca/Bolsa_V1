# Robustez OOS del motor AUTO con datos reales — 2026-11-13

**Nivel 4 del plan de sellado.** Medición de robustez *out-of-sample* con el motor **congelado**, stores en
memoria (**cero escrituras** en PostgreSQL) y los umbrales **pre-registrados** del repositorio. Ni se ajusta
ningún umbral ni se rellena ningún hueco con `0`.

**Veredicto de este nivel: `NOT_MEASURED`.** El replay OOS no produjo **ningún ciclo cerrado**, así que no hay
R realizado, ni acierto de signo, ni distribución que declarar. Todo hueco se publica como `n/d`.

> **Corrección de causa (2026-11-13, mismo día).** La primera versión de este documento atribuía la ausencia
> de operaciones al motor («un motor que casi nunca entra»). El diagnóstico posterior
> ([`diagnostico-gobernador-oos-2026-11-13.md`](diagnostico-gobernador-oos-2026-11-13.md)) demuestra que la
> causa es un **defecto de cableado del propio replay**: no se inyecta `exit_order_store`, la primera salida
> protectora no se puede persistir y engancha el latch de parada dura con `SYSTEM_ERROR` el 2022-02-03, que
> **nunca se libera**. El veredicto `NOT_MEASURED` sigue siendo correcto, pero por una razón más grave: el
> artefacto **no mide al motor**, mide la parada dura. Los apartados §3 y §7 quedan corregidos abajo.

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

## 3 · Lectura honesta (corregida)

- El motor pasó **1.239 días rejugados** haciendo **una** entrada y **ningún** cierre. No hay ida y vuelta, así
  que la pregunta «¿el motor gana dinero fuera de muestra?» **no queda contestada**: queda declarada como no
  medida.
- ~~El patrón que sí se ve es el **gobierno**~~ **Corregido:** lo que se veía no era gobierno. De las 3.650
  ocurrencias de `governor_halted`, **3.650 son artefacto** (cero son parada legítima por drawdown). El motivo
  real es el latch de parada dura enganchado por un fallo de cableado:
  - `v2_86_replay_oos_viability.py` no inyecta `exit_order_store`; el replay siguiente
    (`v2_87_replay_oos_durable_cycle.py:402`) **sí** lo hace.
  - Sin store, `_v2_save_exit_order` devuelve `False` (`auto_worker_state.py:845-849`) y la política B degrada a
    `engage_kill_switch_durable("SYSTEM_ERROR")` (`auto_worker_execution.py:810-823`).
  - El latch sólo se libera con una reconciliación explícita que el replay nunca invoca
    (`auto_worker_safety.py:539-542`), así que queda enganchado desde el 2022-02-03 hasta el final.
  - Con `halted=True` la tabla del gobernador se evalúa igualmente (`auto_v2_entry.py:1651`) y `HALTED` tiene
    precedencia absoluta sobre el resto de ejes (`operational_governor.py:323-324`).
  - Prueba negativa: `governor_exit_only` aparece **0 veces**. Si el gobernador estuviera frenando por no tener
    la cuenta medida, el código habría sido `governor_exit_only`, no `governor_halted`.
- Contraste que fija la causa: en los **mismos 40 ticks**, inyectando sólo
  `exit_order_store=InMemoryExitOrderStore()`, el latch no se engancha, el gobernador **no se consulta** (0
  llamadas) y el motor pasa de 1 orden / 4 fills / 0 cierres a **14 órdenes / 49 fills / 5 cierres**
  (`meanR = -1.2756`, `positiveShare = 0.2`).
- Y lo que el gobernador **sí** haría si se le diera insumo: con `AUTO_ENGINE_SIM_V2_GOVERNOR=1` y el store,
  los estados son `ENTRY_RESTRICTED`/`ENTRY_REDUCED` con eje `market` y `drawdown_pct = 0.0`; **cero** `HALTED`.
  Es decir, ni siquiera con el gobernador encendido habría producido el cuadro del artefacto.
- **Lo que sigue siendo del motor y no del artefacto:** `regime_invalid` 2.544 (gate direccional por símbolo en
  una ventana mayoritariamente bajista) y `top_n_excluded` 4.957 (`AUTO_ENGINE_SIM_V2_TOP_N=5`). Y con el
  cableado corregido el resultado sigue siendo malo en la ventana corta (`meanR ≈ -1.2`, `positiveShare`
  0.0-0.2): eso es una señal sobre ventana/estrategia, no sobre el gobernador.
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
misma cuenta y el rango 2022–2026 con `--draws 3`. **No se publica resultado: no terminó dentro de la ventana
de ejecución** (más de 17 minutos sin artefacto) y se detuvo dejando constancia.

Detalle que importa y se declara: esa sonda **muta el motor en el árbol de trabajo** (desplaza
`fill_seed(bar_tick_now + k, symbol)` en `auto_simulation_worker.py`) y lo restaura tras cada sorteo. Al
detenerla, el fichero se restauró a mano y se verificó que volvió a `fill_seed(bar_tick_now, symbol)` con el
árbol limpio. No es una herramienta que deba correr sobre un árbol con trabajo sin commitear.

Sin ciclos cerrados en el punto, una banda de `expectancyR` sólo puede reproducir el mismo «no medido» con más
coste. El intento y su alcance se declaran aquí para que consten; no se presenta como medición.

## 6 · Invariantes respetados

- Motor congelado, stores en memoria, cero escrituras.
- Sin ajuste de umbrales, sin forzar régimen, sin backdating.
- `activationAllowed` sigue `false`.
- Este documento **no** acredita rentabilidad ni aptitud operativa: acredita que el OOS, hoy, **no está medido**.

## 7 · Qué haría falta para medirlo

1. ~~Un replay OOS en el que el motor **cierre** al menos un número declarado de ciclos (hoy: 0).~~
   **Paso cero, corregido:** reparar el instrumento. Inyectar `exit_order_store≈InMemoryExitOrderStore()` en
   `v2_86`, publicar el estado del latch por tick (`killState {engaged, reason, day}`) y **fallar la corrida**
   si el latch se engancha y no se libera. Sin eso, cualquier número que salga del replay mide la parada dura.
   Condición observable: el artefacto debe declarar `0 governor_halted` **o** justificar cada uno con un
   `drawdown_band` medido. Mientras `governor_halted` conviva con `drawdown_band = UNKNOWN`, el replay está
   roto.
2. Un replay OOS en el que el motor **cierre** al menos un número declarado de ciclos (hoy: 0).
3. Ventana y watch declarados de antemano, con barras `1d` completas para todos los símbolos del watch.
4. Coste y liquidez medidos, no tomados de un seam declarado (`edge = 0.9`, `liquidez = 1e6`).
5. Repetición con banda (K sorteos) **después** de que el punto tenga muestra.

Trazabilidad completa del defecto y su reproducción:
[`diagnostico-gobernador-oos-2026-11-13.md`](diagnostico-gobernador-oos-2026-11-13.md).
