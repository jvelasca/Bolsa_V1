# Plan de fase — `V2.44` / `AUTO-4` · Portfolio Optimizer (`1.69.0-beta`)

**Fecha:** 2026-09-20 · **Punto de partida:** tag `v2.43.3-beta` → `52b97126` (AUTO-3 reliability
closure cerrada) · **Migración:** ninguna prevista (el optimizador es puro + journal aditivo).
**Roadmap:** §6 de [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).

> **Aviso de numeración (declarado):** el plan de `v2.43.2` reutilizó la etiqueta «v2.44» para Exit
> Governance. Esta fase es la **`V2.44` del roadmap**: `AUTO-4 — Portfolio Optimizer` / `1.69.0-beta`.
> Es el aviso que el relevo de `v2.43.2` §7 pidió explícitamente.

---

## 0. Decisiones del owner (fijadas 2026-09-20)

| Decisión | Elección                                                                                                |
| -------- | ------------------------------------------------------------------------------------------------------- |
| Alcance  | **Fase completa**: optimizador de conjuntos **+** modelo de valor esperado económico.                   |
| Entrada  | **Flag OFF por defecto** (`AUTO_ENGINE_SIM_V2_OPTIMIZER=0`): con OFF el camino V2 es **byte-idéntico**. |
| Búsqueda | **Enumeración exacta acotada** de subconjuntos, determinista y con desempate declarado.                 |

## 1. Invariante que instala

> **El ranking deja de ser la decisión: la cartera elige el conjunto que maximiza valor esperado
> sujeto a riesgo.**

Hoy `plan_v2_tick` hace `rank_opportunities → select_top_opportunities(top_n)` y luego decide
**una a una** (`decide_portfolio`), reservando secuencialmente contra la foto de trabajo
(`auto_v2_entry.py:757-886`). El ranking **es** la respuesta: la primera del TOP entra, la segunda
solo si la primera dejó hueco, etc. AUTO-4 invierte eso: el `TOP_N` pasa a ser el **tamaño del
conjunto candidato** y la **combinación** se elige antes de decidir, contra las restricciones de
cartera (capital, sector, correlación, liquidez, capacidad, drawdown).

## 2. Qué NO cambia (freeze)

- `AUTO_ENGINE_SIM_V2=0` sigue siendo `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` (default): **byte-identidad** con `v2.43.3` — el optimizador no se
  construye, no se journaliza ninguna clave nueva y el orden de evaluación es el del ranking.
- `AUTO_ENGINE_SIM_V2_GOVERNOR=0` sin parada dura: intacto.
- Tabla/umbrales del gobernador (`operational_governor.py`): **no se tocan**. El kill switch y el
  gobernador **mandan sobre el optimizador** (no al revés).
- `v2_43_governor_evidence.py`: byte a byte igual, `"bump"` en `1.68.0-beta`.
- `v0` del clasificador de régimen: inmutable.
- Sin migración.

## 3. Piezas nuevas

### 3.1 `expected_value.py` (puro, `packages/py/analytics/.../cognitive/`)

Valor esperado **económico** por oportunidad, con la misma disciplina de medición que el resto del
repo (fail-closed, nunca `0.0` por un dato ininterpretable):

- `ExpectedValue`: `p_win`, `avg_win_r`, `avg_loss_r`, `expected_r`, `risk_amount` (el `1R` en
  dinero), `expected_currency`, `cost_currency`, `net_expected_currency`, `measurement`
  (`COMPLETE`/`PARTIAL`/`UNKNOWN`), `notes`.
- `build_expected_value(...)`: función pura sobre geometría (`entry`, `stop`, `target`, `qty`) +
  probabilidades/medias declaradas + `TradingCostModel`.
- **Degradación honesta:** `p_win` fuera de `(0, 1)` ⇒ `UNKNOWN` (no `0.5` inventado); sin coste
  medido ⇒ `cost_currency = None` y la medición **no** es `COMPLETE`; sin `avg_loss_r` ⇒ `UNKNOWN`
  (no se puede calcular `Expected R`). `expected_r = p·avg_win_r + (1−p)·avg_loss_r` con
  `avg_loss_r <= 0`.

### 3.2 `portfolio_optimizer.py` (puro, `packages/py/analytics/.../cognitive/`)

- `OptimizerCandidate`: `instrument_id`, `sector`, `expected_value` (de 3.1), `risk_amount`,
  `notional`, `liquidity_notional`, `correlation_with_portfolio`.
- `OptimizerConstraints`: `available_cash`, `max_positions`, `max_sector_pct`, `max_correlation`,
  `min_liquidity_notional`, `max_drawdown_used_pct`, `max_combinations` (tope de combinatoria).
- `optimize_portfolio(candidates, constraints, *) -> OptimizerDecision`:
  - **Enumeración exacta** de todos los subconjuntos de tamaño `1..max_positions` del conjunto
    candidato; se descartan los **infeasibles** (capital, sector, correlación, liquidez, drawdown).
  - Objetivo: **maximizar** `Σ net_expected_currency` (valor esperado de la cartera) sujeto a
    **minimizar** el riesgo (`Σ risk_amount`) — desempate declarado y determinista: mayor EV neto →
    menor riesgo → `tuple(sorted(instrument_ids))` lexicográfica (reproducible).
  - `OptimizerDecision`: `selected` (tupla ordenada), `objective`, `expected_value_total`,
    `risk_total`, `combinations_evaluated`, `candidates_considered`, `rejections`
    (`instrument_id → reason`: `optimizer_not_selected`), `measurement`, `notes`.
  - **Tope de combinatoria fail-closed:** si `2^n` supera `max_combinations`, el optimizador
    **no optimiza** y devuelve `measurement=UNKNOWN` con
    `optimizer_enumeration_cap_exceeded`, y el llamante **cae al camino del ranking** (no se
    inventa un resultado ni se degrada a greedy en silencio).
  - `max_combinations` por defecto `4096` (`2^12`): con `TOP_N=5` (default) el espacio es `2^5=32`,
    así que el tope no ata en el caso nominal.

### 3.3 Cableado en `plan_v2_tick` (flag OFF)

- `V2Tunables.optimizer_enabled: bool = False` + `optimizer_max_combinations: int = 4096` +
  `optimizer_max_positions: int | None = None` (default ⇒ `top_n`), leídos de env en
  `tunables_from_env` (`AUTO_ENGINE_SIM_V2_OPTIMIZER`, `AUTO_ENGINE_SIM_V2_OPT_MAX_COMBINATIONS`,
  `AUTO_ENGINE_SIM_V2_OPT_MAX_POSITIONS`).
- Con el flag **ON**: tras el rankeo y el `select_top_opportunities` (ese es el **conjunto
  candidato**), se llama al optimizador y el `ordered` de evaluación pasa a ser la **combinación
  elegida**, en su orden determinista. Las candidatas del TOP que la combinación **no** elige se
  journalizan con `optimizer_not_selected` (nunca `edge_below_threshold`, que sería falso) y su
  score real.
- Con el flag **OFF**: `ordered` es el de siempre, no se llama al optimizador, `V2TickPlan.optimizer`
  queda `None` y **no se emite ninguna clave nueva** en el journal.
- Todo el resto del camino (decisión por candidata, `_working_snapshot`, reservas, gobernador,
  kill switch, degradación a `RESERVATION_FAILED`) queda **intacto**: el optimizador solo cambia
  **qué** candidatas se evalúan y **en qué orden**.

### 3.4 Reason codes (aditivos, `auto_reason_codes.py`)

- `OPTIMIZER_NOT_SELECTED = "optimizer_not_selected"` — factible sola, pero fuera de la mejor
  combinación (el motivo honesto de su no-trade).
- `OPTIMIZER_ENUMERATION_CAP_EXCEEDED = "optimizer_enumeration_cap_exceeded"` — el espacio de
  búsqueda supera el tope declarado ⇒ **no se optimiza** (fail-closed) y se declara.

## 4. Gate (lo que mide el roadmap §6)

1. **No elige tres correlacionados** cuando existe una combinación de **igual** valor esperado y
   **menor** riesgo ⇒ el optimizador debe elegir la de menor riesgo (test puro determinista con
   cartera sintética).
2. **Invariante de capital:** `Σ notional <= available_cash` para **toda** combinación elegida.
3. **Determinismo:** mismo conjunto de entrada ⇒ misma combinación y mismo orden (dos llamadas).
4. **Tope fail-closed:** con el espacio por encima de `max_combinations`, `measurement=UNKNOWN` y el
   motivo declarado, y el tick cae al camino del ranking.
5. **Integración (flag OFF byte-idéntico):** el mismo tick con OPTIMIZER=0 y =1 no comparte journal
   cuando cambia la selección, y con OFF el journal no gana claves.
6. **Golden day con el optimizador ON ≠ selección por ranking**, con la diferencia **explicada en el
   journal** (criterio de salida del roadmap).
7. **El gobernador y el kill switch mandan:** un `HALTED`/`EXIT_ONLY` veta aunque el optimizador
   proponga el conjunto.

## 5. Criterios de salida

- `ruff` limpio con la invocación de la casa (`--config pyproject.toml`) · `mypy` 0 issues ·
  `lint-imports` `4 kept / 0 broken`.
- Bloques offline con los targets **extraídos del YAML** verdes, con el delta exacto de tests
  nuevos en **ambos** bloques (que lo nuevo **sí** corre en CI).
- Los tests nuevos entran por las listas existentes de CI o se añaden **explícitos** a los dos jobs.
- Matriz de mutaciones **medida** (no declarada) sobre el invariante nuevo.
- Pack + arranque del auditor, `CHANGELOG`, `PROJECT_STATE`, índice y bump a `1.69.0-beta`.

## 6. Límites previstos (declarar, no maquillar)

- El EV necesita `p_win`/`avg_win_r`/`avg_loss_r`: **hoy no hay productor real** de esos números en
  el camino del tick (el `expectancy` existente es advisory thin sobre muestras). Fase 1: el seam se
  alimenta de lo que exista y **degrada a `PARTIAL`/`UNKNOWN`**; el productor real es de `AUTO-7`.
- La restricción de **correlación** usa lo que hoy aporta el `TradeContext`/snapshot
  (`correlation_with_portfolio`); una matriz de correlación por pares es de `AUTO-4`/`AUTO-8` según
  el roadmap (§11).
- El objetivo es **EV neto con desempate por riesgo**, no una frontera eficiente completa: el
  «MIN Portfolio Risk» del roadmap se implementa como **desempate y como restricciones duras**, no
  como optimización multi-objetivo con pesos continuos. Declararlo.
- Umbrales (`max_combinations`, `max_positions`) **declarados y no calibrados**.

---

## 7. Estado de ejecución (2026-09-20) — lo implementado, con sus desviaciones

Cerrado en el mismo día. **Sin migración** (el optimizador es puro + journal aditivo) y **sin tocar
el gobernador**.

| Pieza del plan                       | Estado                       | Fichero                                                                                                                                                                                                  |
| ------------------------------------ | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §3.1 valor esperado puro             | hecho                        | `packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py`                                                                                                                                  |
| §3.2 optimizador puro                | hecho                        | `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py`                                                                                                                             |
| §3.3 cableado (flag OFF por defecto) | hecho                        | `packages/py/application/src/bolsa_application/auto_v2_entry.py`                                                                                                                                         |
| §3.4 reason codes                    | hecho (**ampliado**, ver D2) | `packages/py/application/src/bolsa_application/auto_reason_codes.py`                                                                                                                                     |
| §4 gate (7 puntos)                   | hecho (ver D5)               | `packages/py/analytics/tests/test_{expected_value,portfolio_optimizer}.py`, `packages/py/application/tests/test_auto_v4_optimizer_wiring.py`, `apps/api-python/tests/test_auto_v2_worker_integration.py` |
| §5 matriz de mutaciones medida       | hecho                        | `apps/api-python/scripts/v2_44_mutation_audit.py`                                                                                                                                                        |

### 7.1 Desviaciones declaradas (el plan decía otra cosa)

- **D1 — la foto del candidato sale del PROPIO motor.** El plan no decía de dónde salían `notional`/
  `risk_amount`. Se obtienen de una **sonda** `decide_portfolio(...)` contra la foto **inicial** del
  tick, con la **misma** caída de ATR (`atr_pct_fallback`) que usará la decisión real y leyendo `quantity`/`stopDistance`/`positionValue`/`riskAmount` de su `allocation`. No hay una segunda
  fórmula de stop ni una segunda de sizing: si el motor no dimensiona la candidata, la candidata no es
  medible económicamente y el optimizador la declara (`optimizer_expected_value_unmeasured`).
- **D2 — los reason codes del optimizador son más de dos.** El plan §3.4 preveía
  `optimizer_not_selected` y `optimizer_enumeration_cap_exceeded`. La implementación **declara la causa
  concreta** en vez de un genérico: `optimizer_capital_exceeded`, `optimizer_sector_exceeded`,
  `optimizer_sector_unmeasured`, `optimizer_correlation_unknown`, `optimizer_correlation_exceeded`,
  `optimizer_liquidity_unknown`, `optimizer_liquidity_below_minimum`, `optimizer_notional_unmeasured`,
  `optimizer_risk_unmeasured`, `optimizer_expected_value_unmeasured`,
  `optimizer_drawdown_blocks_new_risk`. `optimizer_not_selected` queda como el motivo **de la que cabía
  y no entró**. Todos se re-exportan en `OPTIMIZER_REASONS` (el journal tiene una sola casa).
- **D3 — `max_drawdown_used_pct` no existe como restricción numérica.** El plan §3.2 lo listaba; el
  veto de drawdown se pasa como **permiso de cartera** `new_risk_allowed` (que es como lo aplica el
  gobernador: política de drawdown ⇒ estado), y su negativa es una decisión **COMPLETA** de no operar
  (`optimizer_drawdown_blocks_new_risk`, `notes=("new_risk_not_allowed",)`), no un `UNKNOWN`.
- **D4 — el gobernador entra como parada DURA, no como tabla completa.** La restricción de conjunto
  recibe `new_risk_allowed = not halted` (el kill switch, que es del tick); los vetos por candidata del
  gobernador (`EXIT_ONLY`, listón de edge escalado, bandas de volatilidad/liquidez de la candidata)
  siguen aplicándose **íntegros y sin cambios** en el bucle de decisión de abajo. El optimizador **no**
  los sustituye: solo decide **qué** candidatas se evalúan y **en qué orden**.
- **D5 — el punto 6 del gate (Golden Day) se midió en dos capas** en vez de con un día dorado
  multi-fase: (a) en el tick (aplicación) con el nº1 del ranking **excluido por falta de economía** y
  el nº2 operado, con su motivo real en el journal; (b) en el **worker real**
  (`test_v2_optimizer_on_without_an_economic_producer_is_fail_closed`), que prueba que el flag ON está
  cableado de punta a punta y que, **sin productor de economía**, el tick no abre y lo declara. Un
  día dorado completo con ON no puede diferir hoy del ranking por una razón de fondo, no de test: ver
  §7.2.
- **D6 — campos nuevos en `V2Signal`.** El plan no lo decía explícitamente: `target_price`, `p_win`,
  `avg_win_r`, `avg_loss_r` son **aditivos y opcionales** en `V2Signal`. Sin ellos la oportunidad no es
  comparable y se declara; nunca se puntúa `0`.

### 7.2 Límite confirmado al medir (era §6, ahora medido)

El worker **no** construye hoy señales con economía (`_v2_signals` no pasa `p_win`/medias): con el flag
ON, **todas** las candidatas son `optimizer_expected_value_unmeasured` y el conjunto vacío gana. Es
fail-closed declarado y está **fijado en test**; el productor real es de `AUTO-7`. El flag sigue
**OFF por defecto**, así que el camino de producción no cambia.

### 7.3 Verificación medida

```text
ruff check packages/py apps/api-python --config pyproject.toml     → All checks passed
mypy <5 paquetes + apps/api-python/src> --follow-imports=silent    → Success: 489 ficheros, 0 issues
lint-imports --config packages/py/.importlinter                    → 4 kept, 0 broken (607 ficheros)
las 33 suites nuevas (EV 12 + optimizador 12 + cableado 8 + worker 1) → 33 passed
offline_ci_run_yaml.py ... release-tag-ci.yml python (baseline)    → 2053 passed, 0 skipped (exit 0)
CI real · quality (run 35510546044) → 2075 passed, 0 skipped (v2.43.3: 2042 ⇒ +33)
CI real · python del tag (run 35510840734) → 2086 passed, 0 skipped (v2.43.3: 2053 ⇒ +33)
v2_44_mutation_audit.py                                            → 7/7 muerden, huella intacta
```

Los bloques completos de `v2.44` **no se midieron en local**: sin PostgreSQL alcanzable el `conftest` paga
un _timeout_ por test y el bloque se vuelve inviable (ver la **corrección de procedencia** del pack §5). El
`+33` de cada workflow lo certifica **CI real**; los `v2.43.3` son los conteos de CI de esa versión.

`lint-imports`: `analytics y market no se importan entre sí` + `Domain no importa infra/analytics/
application` siguen **KEPT** con los dos módulos nuevos (que solo importan analytics).
