# Evidencia `v2.88.167-beta` — un solo estado `gated` y una sola semántica de salida

## 1. Qué publica este sello

Segundo sello del bloque funcional posterior a `v2.88.165-beta`. Cierra el frente **`gated`** con
[ADR-048](../../../adr/048-estado-gated-contrato.md): la palabra `gated` respondía a **dos preguntas**
con **dos formas de dato**.

| Ruta | Pregunta | Dato con el que respondía |
| --- | --- | --- |
| Decisor ACTIVE | ¿qué tiene el **libro** ahora y qué acción cabe en la última barra? | OHLCV real de la ventana; arranca en `holds_long` (libro) |
| Ruta de política | ¿la regla de salida se cumple en la última barra? | barras **reconstruidas** `open = high = low = close`, `volume = 0` |

En presets de **volumen o rango** el VWAP desaparece (`cum_vol = 0`) y la **misma posición** podía
recibir dos respuestas según quién preguntara. El estado del libro, además, **no viajaba** en el
artefacto de decisión.

- **`Δ motor = 0`**: no cambia ninguna regla, indicador ni umbral de señal.
- **`Δ decisión ≠ 0` sólo** en (a) la ruta de política con presets de volumen/rango y (b) el caso de
  libro ilegible (HOLD declarado en vez de evaluar como si no hubiera posición).
- **SIN contrato HTTP**: no se toca `openapi.json` ni `schema.d.ts`.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.166-beta` → `2.11.167-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

## 2. Los cinco frentes

| Frente | Qué estaba mal | Qué se publicó | Prueba |
| --- | --- | --- | --- |
| **ADR-048 · fuente única** | Dos verdades posibles del mismo hecho | El estado `gated` **es** el libro real (`_open`, readoptado al arrancar); no se persiste un segundo estado | `test_the_book_is_the_source_of_the_gated_state` |
| **`gatedState`** | El libro no viajaba con la decisión | `GatedState(holdsLong, source, exitEvaluated)` con coherencia al construir; aditivo en `DecisionPackage`/`V2Signal`/`ActiveStrategyHold` y clave `gatedState` en `auto_entry_decision` y `auto_active_strategy_hold`; se **omite** sin dato | `test_the_gated_state_lands_in_the_hold_journal` · `test_the_gated_state_is_omitted_when_it_was_not_measured` · `test_the_gated_state_rejects_an_incoherent_combination` |
| **Libro ilegible** | Se evaluaba como si no hubiera posición | `gated_unavailable` en `ACTIVE_HOLD_REASONS`; HOLD con `holdsLong = null`, `source = "unavailable"`, **sin** consultar barras | `test_an_unreadable_book_fails_closed_and_declares_gated_unavailable` · `test_an_unreadable_book_never_sells_either` |
| **Readoptar antes de decidir** | El orden no estaba fijado | `_v2_tick` readopta antes de decidir; el decisor ve el libro ya readoptado en el primer tick | `test_the_decider_sees_the_readopted_book_before_deciding` |
| **Salida con OHLCV real** | La política **reconstruía** barras close-only | `evaluate_exit_last_bar_gated(..., bars=...)`; la política pasa las barras que ya carga; wrapper close-only conservado y declarado; ventana desalineada ⇒ fail-closed | `test_active_and_policy_paths_agree_on_real_ohlcv` · `test_the_real_ohlcv_path_can_emit_an_exit_the_close_only_path_cannot` · `test_the_close_only_wrapper_keeps_the_historical_signal` · `test_the_policy_route_feeds_real_ohlcv_to_the_exit_rule` |

## 3. El delta medido (no supuesto)

Con el preset `vwap_reclaim` (`precio < vwap`), 30 barras con volumen real y una última barra que cae
de `100` a `50`:

- ruta con **OHLCV real** ⇒ `SELL` (la regla dispara);
- ruta **close-only** (`volume = 0`) ⇒ `None` (el VWAP no existe).

Ese es exactamente el hueco que cierra el ADR: la ruta de producto deja de reconstruir la serie y
ambas rutas coinciden sobre el mismo dato (`test_active_and_policy_paths_agree_on_real_ohlcv`, con
control positivo de que el caso de cierre se ejerce de verdad).

## 4. Ficheros

| Capa | Ficheros |
| --- | --- |
| Python · analytics | `signals/rules_engine.py` (`evaluate_exit_last_bar_gated(*, bars=...)`) |
| Python · aplicación | `decision_contract.py` (`GatedState`, `GATED_SOURCE_*`), `auto_reason_codes.py` (`ACTIVE_GATED_UNAVAILABLE`), `active_strategy_signal_evaluator.py`, `auto_v2_entry.py`, `position_exit_evaluator.py` |
| Python · API | `auto_simulation_worker.py` (propagación de `gatedState`) |
| Python · pruebas | `test_gated_exit_parity.py`, `test_rules_engine.py`, `test_active_strategy_hold_reasons.py`, `test_position_exits_paper_auto_gate.py`, `test_auto_simulation_worker.py` |
| Docs | `docs/adr/048-estado-gated-contrato.md`, `CHANGELOG.md` (§`2.11.167-beta`), este pack |

## 5. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest` `application` (hermético, `*_db.py` excluidos: su fixture conecta a PostgreSQL real) | **2960 passed, 1 skipped** (3:25) |
| `pytest` `analytics` + `domain` + `market` | **1616 passed** (0:11) |
| Suites tocadas (`test_gated_exit_parity`, `test_active_strategy_hold_reasons`, `test_position_exits_paper_auto_gate`, `test_auto_v2_entry`, `test_scan_decider_contract`, `test_rules_engine`, `test_auto_sim_active_strategy_seam`) | **159 passed** (0:10) |
| `api-python` (ficheros afectados: worker, seam, durable cycle, regresiones, exit permission, golden day, integración, paper engine, precio real) | **161 passed** (0:12) |
| `ruff` (CI: `packages/py apps/api-python --config pyproject.toml`) | limpio |
| `mypy` (alcance CI) | **573 ficheros, sin issues** |
| `test_dia_d_bump_guard` | **2 passed** |
| Contrato HTTP | **sin delta** (no se regenera) |
| Migración | **sin delta** (`head` `058_estudio_daily_proposals`) |

## 6. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la mueve**
  y **no demuestra rentabilidad**.
- Si `readopt_positions()` no llegara a ejecutarse, `_open` estaría vacío y `holdsLong` sería `false`:
  eso **no** lo arregla este ADR — el worker declara la posición no gestionada
  (`position_unmanaged`, ADR-045/S-5) y la ventana declara sus propios límites. Es un límite conocido,
  no una segunda verdad.
- El wrapper close-only **sigue existiendo** para llamantes históricos: la paridad se exige en la ruta
  de producto, no se prohíbe el wrapper.
- `gatedState` declara el estado del libro, **no** la calidad del histórico ni la rentabilidad.
