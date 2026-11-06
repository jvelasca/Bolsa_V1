# Evidencia `v2.88.166-beta` — la ventana de la señal se deriva del warmup medido del preset

## 1. Qué publica este sello

Primer sello del bloque funcional posterior a `v2.88.165-beta`. Cierra **B-1** en la ruta de
producto del AUTO: hasta ahora el worker cargaba siempre `AUTO_ENGINE_SIM_SIGNAL_BARS` barras
(**120** por defecto) y, con un preset de SMA200 o un cruce 50/200, publicaba un HOLD **declarado
pero inevitable** —la ventana no alcanzaba el warmup y no había forma de que lo alcanzara—.

- **`Δ motor = 0`**: no cambia ninguna regla, indicador ni umbral de señal.
- **`Δ decisión ≠ 0` sólo** en los presets que antes no se evaluaban por ventana (ahora pueden
  emitir su señal real) y en el caso de warmup no medible (HOLD declarado, sin orden).
- **SIN contrato HTTP**: no se toca `openapi.json` ni `schema.d.ts`.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.165-beta` → `2.11.166-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard` ⇒ **2 passed**).

## 2. Los cinco frentes

| Frente | Qué estaba mal | Qué se publicó | Prueba |
| --- | --- | --- | --- |
| **B-1 · medición** | El warmup sólo se diagnosticaba *después* (`evaluability_reason`): el worker no tenía con qué dimensionar la ventana | `preset_evaluability.measured_warmup_bars`: sonda OHLCV determinista de 500 barras + `build_indicator_context` ⇒ `max(first_defined + depth)`. `0` sin series, `None` si no se puede medir (nunca aritmética de periodos). Enriquece desde `presetKey` | `test_measured_warmup_matches_the_series_threshold_for_every_preset` · `test_measured_warmup_is_evaluable_at_its_own_number` · `test_measured_warmup_is_none_when_a_spec_never_defines` · `test_measured_warmup_is_none_for_an_undeclared_spec` · `test_measured_warmup_enriches_a_definition_that_only_carries_the_preset` |
| **B-1 · ventana** | `AUTO_ENGINE_SIM_SIGNAL_BARS` era el **techo** efectivo (120) | `_signal_window`: la env es el **suelo** y `max(env, warmup)` la ventana efectiva; origen `env` / `preset_warmup`; un log de arranque con `preset`/`env`/`required`/`effective` | `test_signal_window_raises_the_env_to_the_measured_warmup` · `test_signal_window_keeps_the_env_as_floor` · `test_signal_enabled_requests_the_preset_warmup` (el loader pide **201**) |
| **B-1 · fail-closed** | Sin medición, la única alternativa era inventar un número | `warmup_unmeasurable` en `ACTIVE_HOLD_REASONS`; el decisor mide **una vez** al construirse y, si es `None`, devuelve HOLD **sin consultar el cargador** | `test_an_unmeasurable_warmup_fails_closed_and_declares_it` · `test_signal_window_never_invents_a_window_when_unmeasurable` |
| **B-1 · journal** | La ventana efectiva no era auditable | Claves **aditivas** `warmupBars` y `signalWindowSource` en `auto_entry_decision` y `auto_active_strategy_hold`; campos aditivos en `DecisionPackage`/`V2Signal`/`ActiveStrategyHold`; se omiten sin dato | `test_plan_v2_tick_seals_the_measured_warmup_and_the_window_source` · `test_the_hold_journal_declares_the_measured_warmup` |
| **scan** | El scan ya pedía 500 por defecto, pero nadie lo guardaba | El scan **no se toca**; un guardián rota si un preset entrara con warmup > defecto | `test_the_scan_default_window_covers_every_preset` |

## 3. Umbrales medidos (los 21 presets, `1`…`201`)

`golden_cross` y `death_cross` **201** · `ma_stack_bullish` y `price_above_sma200` **200** ·
`ichimoku_tk_cross` **78** · `sma_crossover` **51** · `pullback_in_uptrend` **50** · `vwap_reclaim`
**1** · el resto, según su serie. La medición **coincide con el umbral que el scan ya diagnosticaba**
(`_threshold` de `test_preset_evaluability.py`), de modo que la ventana que el worker pide y el motivo
que luego publica no pueden contradecirse.

## 4. Ficheros

| Capa | Ficheros |
| --- | --- |
| Python · analytics | `signals/preset_evaluability.py` (`PROBE_BARS`, `measured_warmup_bars`) |
| Python · aplicación | `active_strategy_signal_evaluator.py`, `auto_reason_codes.py` (`ACTIVE_WARMUP_UNMEASURABLE`), `auto_v2_entry.py`, `decision_contract.py` |
| Python · API | `auto_simulation_worker.py` (`SIGNAL_WINDOW_SOURCE_*`, `_signal_window`, `_build_signal_decider`) |
| Python · pruebas | `test_preset_evaluability.py`, `test_active_strategy_hold_reasons.py`, `test_auto_v2_entry.py`, `test_scan_preset_warmup.py`, `test_auto_sim_active_strategy_seam.py` |
| Docs | `CHANGELOG.md` (§`2.11.166-beta`), este pack |

## 5. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest` (domain + market + analytics + application + ai, hermético) | **4572 passed, 6 skipped** (4:59) |
| Suites tocadas (`test_preset_evaluability`, `test_active_strategy_hold_reasons`, `test_auto_v2_entry`, `test_scan_preset_warmup`, `test_auto_sim_active_strategy_seam`, `test_auto_simulation_worker`, `test_dia_d_bump_guard`) | **218 passed** (0:10) |
| `ruff` (CI: `packages/py apps/api-python --config pyproject.toml`) | limpio |
| `mypy` (alcance CI, `--follow-imports=silent`) | **573 ficheros, sin issues** |
| `test_dia_d_bump_guard` | **2 passed** |
| Contrato HTTP | **sin delta** (no se regenera) |
| Migración | **sin delta** (`head` `058_estudio_daily_proposals`) |

## 6. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la mueve**
  y **no demuestra rentabilidad**.
- El coste de la ventana sube para los presets que piden más de la env (barras × símbolos × turno);
  el warmup medido se calcula **una vez por decisor**, no por símbolo ni por tick.
- La medición se hace sobre una **sonda determinista**, no sobre el histórico real: mide la
  profundidad de las series, no garantiza que el histórico tenga ese número de barras (eso lo sigue
  declarando `warmup_insufficient`).
- `measured_warmup_bars` devuelve `None` si la definición referencia una spec no declarada: se
  declara `warmup_unmeasurable` en vez de inventar una ventana.
