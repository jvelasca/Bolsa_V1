# Plan — `v2.88.111-beta` / **`§8` — Validación OOS financiera por `(estrategia × instrumento)`**: métricas de dinero con costes, sensibilidad y banda

> **Estado:** **PROPUESTO** (2026-10-11) — pendiente de ratificación del propietario en la **decisión de alcance D-§8** (§5).
> **Base funcional:** `v2.88.110-beta` (tag anotado `v2.88.110-beta`, objeto `b08bbff2` → commit `d868ea40`). HEAD del árbol al redactar: `29579803`.
> **Naturaleza prevista:** `Δ motor` **aditivo** (módulo puro nuevo + ampliación **opt-in** del CLI OOS) · **`Δ decisión = 0`** · **SIN migración** (head `052_top3_opportunities`) · **contrato sin cambio** salvo el fichero de evidencia **opt-in**.
> **Origen:** hueco **`§8` (Validación OOS por valor, P3)** de la [auditoría profundizada](./auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md) §8/§9. Depende de `§6` (bucle con motor real, **cerrada** en `v2.88.109`) y sucede a `§7` (**cerrada** en `v2.88.110`).

---

## 0. Objetivo y criterio de aceptación (falsable)

**Hueco (textual de la auditoría §8):** «ocupar el puesto #1 de Finalistas **no** demuestra rentabilidad; la propia evidencia lo declara.»

Cerrar `§8` exige un **reporte financiero fuera de muestra**, agregado por **`(estrategia, instrumento)`**, con:

- retorno **neto** (con costes) y bruto,
- **drawdown** máximo,
- **ratio de Sharpe** *cuando proceda* (guarda de muestra/varianza),
- **tasa de acierto**,
- **profit factor**,
- **número de operaciones**,
- **sensibilidad a costes/deslizamiento**,
- selección y parámetros **fijados sin consultar** el periodo de prueba,
- resultados **reproducibles**, y un dato no medido ⇒ **«Sin dato todavía»**, **nunca `0`**.

**Criterio de aceptación falsable.**
1. Para cada grupo `(strategy_version, symbol)` con `≥ min_trades` round-trips cerrados, el reporte **afirma** `netReturnPct`, `maxDrawdownPct`, `hitRate`, `profitFactor`, `trades` y, si procede, `sharpe`; con `< min_trades` **todos** los ratios son `None` y el grupo aparece en `unmeasured` (no se rellena con `0`).
2. `netReturnPct ≤ grossReturnPct` siempre (los costes **restan**; con costes `0` son iguales).
3. La sensibilidad a costes es **monótona**: al subir el multiplicador de `bps`, `netReturnPct` **no** sube.
4. El reporte declara `pointCitable: false` mientras la banda de `K` sorteos cruce el cero ([`v2.88.16.3`](./evidence/v2.88.16.3/README.md)): **nunca** se cita un punto como propiedad del motor.
5. **Reproducibilidad:** el artefacto por defecto (JSON) del CLI OOS queda **byte a byte** igual (el sello congelado de `replay-repro` **no cambia**); el reporte financiero se emite en un fichero **separado** y **opt-in**.

---

## 1. Precedente y reutilización (no duplicar)

- **Métricas FIFO de dinero ya probadas:** [`strategy_observed_metrics.py`](../../packages/py/application/src/bolsa_application/strategy_observed_metrics.py) — `compute_observed_metrics(side, qty, price)` ya da `return_pct`, `max_drawdown_pct`, `win_rate`, `profit_factor` con guarda `min_trades` y contrato «sin pérdidas ⇒ `profit_factor = None`, nunca `∞`».
- **Modelo de coste:** [`cost_model_v2.py`](../../packages/py/analytics/src/bolsa_analytics/cost_model_v2.py) — `commission_bps`, `slippage_bps_base`, `spread_bps`; `resolve_bar_costs_v2`. Reutilizable como **overlay** de coste.
- **Motor de métricas all-in-one (LAB):** [`backtest.py:171`](../../packages/py/analytics/src/bolsa_analytics/backtest.py) `compute_is_metrics(...)` ya calcula `totalReturnPct/maxDrawdownPct/sharpeRatio/winRate/profitFactor/tradeCount` con costes. **No se duplica**: el nuevo reporte es del **replay AUTO OOS** (R-only hoy), no del motor LAB.
- **Holdout / sin *peek*:** [`holdout.py`](../../packages/py/analytics/src/bolsa_analytics/optimize/holdout.py) (`split_holdout_bars`, `MIN_IS_BARS`/`MIN_OOS_BARS`), [`optimize.py:538`](../../packages/py/application/src/bolsa_application/optimize.py) `_eval_oos_for_grid` (params **congelados** en IS, warm-up IS, arranque plano en OOS) y [`closed_bars.py`](../../packages/py/application/src/bolsa_application/closed_bars.py) (frontera `B-1`). El replay OOS ya es *no-lookahead* por el `ReplayCursor`.
- **Estadística:** [`psr_dsr.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/psr_dsr.py) (`observed_sharpe`) y [`stats_suite.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/stats_suite.py) (`walk_forward_efficiency`).
- **Evidencia previa que se debe respetar:** el replay OOS declara **hoy** que **no** mide edge ni rentabilidad ([`replay-oos-ciclo-durable-v2.87`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md)) y la banda `K=12` **cruza el cero** ⇒ `point_citable = false` ([`v2.88.16.3`](./evidence/v2.88.16.3/README.md)).

---

## 2. Hallazgos del reconocimiento (qué existe, qué falta)

| Pieza | Estado hoy | Falta para `§8` |
| --- | --- | --- |
| Scorer OOS (`replay_oos.ScoreReport`) | R-multiples, coste-ciego, `byVersion/byDay/byYear`, huecos declarados | dinero, costes, DD, Sharpe, PF, dimensión `(estrategia × instrumento)` |
| `strategy_observed_metrics` | FIFO neto/DD/win/PF + guarda | overlay de **costes**, sensibilidad, agrupación `× symbol`, Sharpe |
| LAB `compute_is_metrics` | neto/DD/Sharpe/win/PF **con costes** por backtest | es el motor **LAB**, no el replay AUTO; sin sensibilidad |
| Persistencia | `research_trials.blocks.oosMetrics`, `backtest_runs`, `strategy_shadow_validations` | no hay reporte OOS **por `(strategy_definition_id/preset, instrument_id)`** con costes+sensibilidad |
| Banda | `v2.88.16.3` mide banda `K=12` y declara `point_citable=false` | citarla en el reporte en vez de un punto |

**Conclusión:** el material existe pero **disperso**. `§8` es, en lo esencial, un **reporte puro y reproducible** que reúne (a) dinero FIFO, (b) overlay de coste, (c) guardas de muestra, (d) la banda declarada — **sin tocar el artefacto congelado**.

---

## 3. Restricción DURA — el sello `replay-repro` NO se puede mover

`replay-repro` regenera `replay-oos-durable-v2.88.7.json` desde el fixture y **asserta su `SHA-256` byte a byte** ([`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml)). Por tanto:

- **Prohibido** añadir/renombrar cualquier clave del JSON por defecto de `v2_87_replay_oos_durable_cycle.py` (rompería el sello).
- El reporte financiero viaja en un **fichero aparte**, activado por un flag **opt-in** (`--finance-report PATH`), **apagado por defecto**.
- Las dataclasses congeladas (`RoundTrip.to_dict`, `ScoreReport.to_dict`) **no** se tocan.

---

## 4. Diseño por fases

### Fase `§8-a` — Módulo PURO de reporte financiero OOS (núcleo)

Nuevo módulo [`packages/py/application/src/bolsa_application/oos_finance.py`](../../packages/py/application/src/bolsa_application/oos_finance.py), **puro y determinista** (sin DB, red ni reloj):

- **Entrada:** filles OOS con `(symbol, strategy_version, side, quantity, price, direction)` + un **overlay de coste** (`commission_bps`, `slippage_bps`) + `min_trades` + `stress_multiplier`.
- **Agrupación:** por `(strategy_version, symbol)`; se reconstruyen round-trips **FIFO** por grupo (reutilizando la contabilidad de `strategy_observed_metrics`), **con dirección** (los cortos ya existen en el dominio: [`directional_geometry.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/directional_geometry.py)).
- **Métricas por grupo:** `trades`, `grossReturnPct`, `netReturnPct`, `maxDrawdownPct`, `hitRate`, `profitFactor` (`None` si no hay pérdidas), `sharpe` (`None` salvo `n ≥ min_trades` y `vol > 0`), `commissionPaid`, `slippagePaid`, `netReturnPctAtStress`.
- **Contrato de honestidad:** `< min_trades` ⇒ ratios `None` + grupo en `unmeasured`; nunca `0`.
- **Banda:** `pointCitable: false` + razón citada, mientras no se cite la banda `K`.
- **Reproducible:** orden de grupos estable (clave ordenada), redondeos fijados, sin dependencia de `hash`.

**Pruebas** ([`test_oos_finance.py`](../../packages/py/application/tests/test_oos_finance.py)): neto ≤ bruto; monótona con el estrés; `None` bajo `min_trades`; PF `None` sin pérdidas (nunca `∞`); Sharpe `None` con varianza nula; agrupación correcta por `(versión, símbolo)`; determinismo (dos corridas ⇒ `to_dict()` idéntico).

### Fase `§8-b` — Ampliación **OPT-IN** del CLI OOS (evidencia reproducible, sello intacto)

En [`v2_87_replay_oos_durable_cycle.py`](../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py):

- Nuevo flag `--finance-report PATH` (**apagado por defecto**): reúne los `ReplayFill` ya materializados, invoca `oos_finance.build_report(...)` y escribe el JSON **en `PATH`**, **sin** tocar el payload por defecto.
- **Guarda anti-regresión:** un test que ejecuta el **renderer por defecto** y verifica que el `dict` emitido es **idéntico** al de antes (claves y orden), de modo que el `SHA-256` del sello no puede moverse por accidente.
- Pruebas de renderer en [`test_replay_oos_cli_renderers.py`](../../apps/api-python/tests/test_replay_oos_cli_renderers.py) (patrón ya existente: carga por `spec_from_file_location`).

### Fase `§8-c` — Banda `K` y cita (diferida o incluida según D-§8)

- Reutilizar el arnés de [`v2_88_16_3_oos_seed_robustness.py`](../../apps/api-python/scripts/v2_88_16_3_oos_seed_robustness.py) para emitir el reporte financiero como **banda** (`min/median/max` por métrica) y fijar `pointCitable` según si la banda cruza el cero.
- Si se difiere, la evidencia `§8-a/b` **declara** la cita pendiente (no fabrica un punto).

---

## 5. Decisión de alcance `D-§8` (la del propietario)

La auditoría ordena `§8` **después** de los `P2` (DÍA-D enlazado al ciclo + auditoría por valor). Hay tres alcances defendibles para **este** sello:

- **D-§8.A (recomendado) — `§8-a` + `§8-b`:** módulo puro + ampliación opt-in del CLI + evidencia financiera de **un** watch, citada como **banda declarada** (sin afirmar un punto). Cierra el núcleo financiero sin mover el sello ni la decisión.
- **D-§8.B — solo `§8-a`:** únicamente el módulo puro y sus pruebas (sin CLI); más pequeño, pero el reporte aún sin caller de producción.
- **D-§8.C — `§8-a` + `§8-b` + `§8-c`:** añade la banda `K` medida y la cita. Mayor coste (re-ejecuta el replay `K` veces y **no** es reproducible sin PG), pero cierra la cita completa.

**Recomendación:** `D-§8.A` — cierra el núcleo (§8-a) con caller real (§8-b) y **declara** la banda (§8-c) como pendiente explícita, sin fabricar un punto. La banda medida (`§8-c`) merece su propio sello reproducible.

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Mover el sello congelado `replay-repro` | Reporte en fichero **aparte**; test que compara el dict por defecto |
| Doble contabilización de costes (los filles SIM ya llevan fricción del venue) | El overlay se declara **modelado** y **explícito**; la fricción **medida** (si hay `reference_mid`) se reporta **aparte** y **no** se suma dos veces |
| Sobreafirmar con muestra anécdota | Guarda `min_trades` + `pointCitable: false` |
| `inf`/división por cero rompen JSON | `None` explícito (precedente `strategy_observed_metrics`) |
| Sesgo de selección | Parámetros congelados en IS (reutiliza `_eval_oos_for_grid`); el reporte **no** re-optimiza |
