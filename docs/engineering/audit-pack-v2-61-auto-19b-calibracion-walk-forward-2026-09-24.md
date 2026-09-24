# AUDIT-PACK — `v2.61-beta` (`AUTO-19B`, calibración del intervalo + walk-forward) · 2026-09-24

**Bump:** `1.85.0-beta` → **`1.86.0-beta`**. **Migración: NO** (Alembic head sigue en
`046_fill_reference_mid`). **El reparto NO se mueve: `ADAPTIVE_POLICY_VERSION` sigue `auto18-v1`** y
`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`. Fase **solo medición**: el instrumento es puro y
read-only.

**Fase anterior:** `AUTO-19A` / `V2.60` (`1.85.0-beta`, tag `v2.60-beta`, PR
[#69](https://github.com/jvelasca/Bolsa_V1/pull/69)). **Documentos de esta fase:**
[plan](./plan-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[arranque auditor](./arranque-auditor-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[relevo](./traspaso-relevo-post-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[agente siguiente](./arranque-agente-post-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md).

---

## §1 — Qué se construyó (afirmación → código → test)

| # | Afirmación | Código | Test | Mutación |
|---|---|---|---|---|
| 1 | El walk-forward usa ventanas **crecientes** y contiguas | `split_walk_forward_folds` | `test_the_walk_forward_windows_grow_and_never_overlap` | **M159**, **M164** |
| 2 | El split es **cronológico**, no por orden de llegada | `order_cycles_by_instant` + `build_calibration_report` | `test_the_split_is_chronological_not_by_arrival` | — |
| 3 | **Sin muestra no hay veredicto** (seis preguntas) | `_calibration_questions`, `_inconclusive` | `test_no_cycles_returns_six_declared_inconclusive_questions` | **M162** |
| 4 | La cobertura se **mide** contra el nivel declarado | `_question_interval_coverage` | `test_interval_coverage_is_measured_against_the_declared_level` / `..._refutes_a_too_narrow_interval` | **M161** |
| 5 | **Sin intervalo** no hay cobertura (ni cubierta ni descubierta) | `_question_interval_coverage` (filtro) | `test_without_an_interval_there_is_nothing_to_cover` | **M160** |
| 6 | El signo del EDGE se calibra con muestra mínima | `_question_edge_sign` | `test_edge_sign_calibration_measures_accuracy_against_the_floor`, `test_medium_and_unknown_edges_do_not_claim_a_sign` | **M162** |
| 7 | La banda de medición ordena la estabilidad OOS | `_question_confidence_band` | `test_confidence_calibration_compares_oos_dispersion`, `test_a_single_oos_cycle_is_not_stable_material_for_the_band` | — |
| 8 | Las tres preguntas de `AUTO-19A` se **reutilizan** (un solo productor) | `_as_calibration` + `_question_shrinkage` / `_question_effective_n` / `_question_coverage` | `test_the_replay_questions_are_reused_under_calibration_keys` | (cubiertas por `M155/M156/M157`) |
| 9 | La acotación de pliegues impide llamar walk-forward a un split | `resolve_calibration_folds` | `test_the_folds_are_clamped_to_the_declared_range` | **M163** |
| 10 | Los pliegues escasos se **declaran** | `build_calibration_report` (`skipped_strategy` / `insufficient_folds`) | `test_a_strategy_without_enough_material_is_skipped_and_named`, `test_material_for_fewer_folds_than_requested_is_declared` | — |
| 11 | La lectura es **aditiva**: `AUTO-19A` no cambia | `measure_is_oos_row` extraído; split conservado | `test_the_auto19a_replay_fixture_is_unchanged` | — |
| 12 | La lectura es **determinista y orden-invariante** | ordenación por instante + bootstrap con semilla | `test_the_report_is_deterministic_and_order_invariant` | — |
| 13 | El payload tiene forma estable | `CalibrationReport.as_dict` | `test_the_report_payload_is_json_shaped` | — |

## §2 — Superficie medida (local)

Comandos de compuerta (los del YAML):

| Compuerta | Comando | Resultado |
|---|---|---|
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Import Linter | `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (624 ficheros, 3355 dependencias) |
| Mypy | `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 499 source files** |

Tests (en esta máquina, `uv run --no-sync python -m pytest`, porque `uv run pytest` lo bloquea la
directiva de Control de aplicaciones):

| Suite | Resultado |
|---|---|
| `packages/py/analytics/tests` + `test_auto_v60_auto19_uncertainty_seam.py` | **1190 passed** |
| `packages/py/application/tests` | **1941 passed** |
| `test_auto_adaptive_calibration.py` (nueva) | **19 passed** |

Sonda de mutaciones (restauración byte a byte, huella `git status` de los ficheros mutados):

| Corrida | Resultado |
|---|---|
| `... v2_44_mutation_audit.py M159 M160 M161 M162 M163 M164` | **6/6** muerden; árbol intacto |
| `... v2_44_mutation_audit.py` (matriz completa) | **164/164** muerden; `0` fragmentos ausentes; `intacto: la sonda no altero el arbol` |

Invariante de byte-identidad: `python scripts/research/auto_replay_battery.py` (sin
`--walk-forward`) emite **el mismo JSON** que `build_replay_report` sobre el fixture de `AUTO-19A`
(comparado byte a byte en la verificación de la fase).

## §3 — Superficie del cambio

| Fichero | Δ |
|---|---|
| `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` | **nuevo** (632 líneas) |
| `packages/py/analytics/tests/test_auto_adaptive_calibration.py` | **nuevo** (431 líneas) |
| `packages/py/analytics/tests/fixtures/auto_calibration_cycles.json` | **nuevo** (126 ciclos, 1643 líneas) |
| `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_replay.py` | `+28` (extracción aditiva de `measure_is_oos_row`) |
| `scripts/research/auto_replay_battery.py` | `--walk-forward` / `--folds` |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `+69` (`M159…M164` + bloque de cabecera) |
| `.github/workflows/python-ci.yml`, `.github/workflows/release-tag-ci.yml` | registro documentado del puro |
| `package.json` | `1.85.0-beta` → `1.86.0-beta` |
| `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index-2026-08-03.md` | entrada `1.86.0-beta` |

Confirmado **sin cambios** (byte a byte, no aparecen en el diff de fase):
`auto_adaptive.py`, `auto_self_evaluation_feed.py`, `auto_simulation_worker.py`,
`auto_adaptive_journal.py`, `v2_43_governor_evidence.py`, `auto_adaptive_confidence.py`,
`auto_adaptive_uncertainty.py`, el gobernador y la tabla estado→efecto.

## §4 — Freeze respetado

- **Sin migración.** `_ALEMBIC_HEAD` = `046_fill_reference_mid`.
- **Sello del reparto intacto:** `ADAPTIVE_POLICY_VERSION = "auto18-v1"`, `DATA_GATE_POLICY_VERSION =
  "auto15-v1"`.
- **Sin UI, sin SHORT, sin backfill.** `*.md` sin `prettier`; `governor.json` sin trackear.
- El journal durable (`auto_adaptive_journal.py`) queda **byte a byte** igual.

## §5 — Límites declarados (lo que este pack NO afirma)

- La calibración publicada es la del **material que se le dé**. El fixture por defecto es **sintético
  y declarado**: mide el **instrumento**, no la estrategia real.
- **`P(R > 0)` no existe** en esta fase; la correlación entre estrategias y el current-regime gating
  tampoco.
- El walk-forward es **expanding** con segmentos de igual tamaño (patrón de `optimize`); otra
  partición puede dar otro número.
- **CI remoto del tag:** las cifras de este pack son la medición **local** de la fase. El resultado de
  `Python CI` / `Release tag CI` del tag `v2.61-beta` se registra en el commit de cierre del sello.
