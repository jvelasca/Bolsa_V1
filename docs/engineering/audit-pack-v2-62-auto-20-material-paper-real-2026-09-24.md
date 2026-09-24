# Audit-pack — `v2.62-beta` (`AUTO-20` · material PAPER real + cierre de O1/O2)

**Versión:** `1.87.0-beta` · **Rótulo:** `AUTO-20` / `V2.62` · **Fecha:** 2026-09-24 · **Base de
auditoría:** `f55e6921` (cierre de `v2.61-beta`).

**Plan:** [plan-v2-62-auto-20-material-paper-real-2026-09-24.md](./plan-v2-62-auto-20-material-paper-real-2026-09-24.md) ·
**Origen:** [auditoría de `v2.61-beta`](./auditoria-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md).

## §1 — Qué se construyó (afirmación → código → test)

| # | Afirmación | Código | Test que la sostiene |
|---|---|---|---|
| 1 | Una versión **sin ningún R medible** se declara, no desaparece (**O1**) | `auto_adaptive_calibration.py` → `notes.extend(f"unmeasured_r:{version}" …)` | `test_a_strategy_without_any_measurable_r_is_declared_not_silently_dropped` |
| 2 | Una versión **parcialmente** medida no se marca como hueco | idem | `test_a_partially_measured_strategy_is_not_flagged_as_unmeasured` |
| 3 | Las filas **sin versión** se declaran | idem (`unversioned_cycles`) | `test_cycles_without_a_version_are_declared` |
| 4 | El WFE usa **solo** pliegues emparejados (**O2**) | `_aggregate` → `mean_paired_oos / mean_paired_is` | `test_walk_forward_efficiency_is_computed_on_paired_folds_only` |
| 5 | Sin pliegue emparejado, el WFE es `None` (no un 0) | idem | `test_the_walk_forward_efficiency_is_none_without_a_paired_fold` |
| 6 | Los conteos publicados no se contradicen | idem (`foldCount`/`isFoldCount`/`oosFoldCount`/`pairedFoldCount`) | `test_the_report_payload_is_json_shaped` |
| 7 | El material del instrumento **lleva el riesgo** | `auto_self_evaluation_feed.py` → `adaptive_instrument_cycles` | `test_instrument_cycles_is_the_public_seam_that_carries_the_risk_basis` |
| 8 | La lectura cambió ⇒ **sube el sello** | `CALIBRATION_METHOD = "walk_forward_calibration_v2"` | `test_no_cycles_…` (`payload["method"] == CALIBRATION_METHOD`) |
| 9 | El exportador **no miente sin PG** | `paper_cycles_export.py` → `return 2` si no puede leer | sonda manual (exit 2 verificado) |

Cada afirmación tiene su **mutación** (§4) que la mata.

## §2 — Superficie medida (compuertas)

| Compuerta | Comando | Resultado |
|---|---|---|
| Lint | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Capas | `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| Tipos | `uv run mypy … --follow-imports=silent` | **499 ficheros, 0 errores** |
| Puros | `uv run pytest packages/py/analytics/tests packages/py/application/tests -q` | **3133 passed** |
| Mutaciones (nuevas) | `v2_44_mutation_audit.py M165 M166 M167 M168` | **4/4** muerden |
| Mutaciones (matriz) | `v2_44_mutation_audit.py` | **168/168**, `0` sin fragmento, restauración byte a byte |
| Sonda adversaria | propiedades del split + oráculos de cobertura/signo | **sin hallazgos** |

## §3 — Superficie de cambio

`11 ficheros` modificados (**+275 / −8**) más **6 ficheros nuevos** (sin contar este pack):

* `auto_adaptive_calibration.py` (+45/−8 en la fase) — O1 y O2, sello `…_v2`.
* `auto_self_evaluation_feed.py` (+21) — `adaptive_instrument_cycles` (aditivo).
* `paper_cycles_export.py` (**nuevo**) — exportador I/O.
* `test_auto_adaptive_calibration.py` (+74), `test_auto_self_evaluation_feed.py` (+28).
* `v2_44_mutation_audit.py` (+40) — M165–M168 y su documentación.
* `CHANGELOG.md` (+58), `PROJECT_STATE.md`, `engineering-index`, `package.json`
  (`1.86.0-beta`→`1.87.0-beta`), los dos workflows (comentario de CI).

## §4 — Mutaciones de la fase

| Id | Qué rompe | Rojo en |
|---|---|---|
| **M165** | El hueco de O1 vuelve a silenciarse | `test_a_strategy_without_any_measurable_r_is_declared…` |
| **M166** | El WFE vuelve a mezclar medias de pliegues distintos | `test_walk_forward_efficiency_is_computed_on_paired_folds_only` |
| **M167** | Los pliegues emparejados se cuentan como todos | los dos tests de O2 |
| **M168** | El instrumento vuelve a leer ciclos sin denominador | `test_instrument_cycles_is_the_public_seam…` |

## §5 — Freeze respetado

* `ADAPTIVE_POLICY_VERSION = "auto18-v1"` y `DATA_GATE_POLICY_VERSION = "auto15-v1"` **intactos**.
* `auto_adaptive.py`, `auto_adaptive_data_gate.py`, `auto_simulation_worker.py`,
  `auto_adaptive_journal.py`, `v2_43_governor_evidence.py` y `governor.json` **byte a byte iguales**.
* **`auto_adaptive_replay.py` NO se toca**: el contrato `statistical_oos_v1` de `AUTO-19A` queda
  igual (decisión declarada: O1 se cierra en la calibración, no en el replay).
* **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.

## §6 — Límites declarados (lo que este pack NO prueba)

1. **El camino durable del exportador no está ejercitado end-to-end.** Está cableado sobre costuras
   ya selladas (`cycles_from_fills`, `cycle_risk_from_reservations`, régimen `AUTO-10`,
   `adaptive_instrument_cycles`) y pasa `ruff`/`mypy`/sonda de bloqueo, pero **no hay fixture PG que
   siembre fills + reservas reales** para él. **Es la deuda nº 1 de la fase.**
2. **No demuestra edge**: el fixture del instrumento es **sintético**. La calibración publicada mide
   el instrumento, no la estrategia. Ejecutarla sobre una cuenta real es un paso **operativo**.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** siguen fuera de alcance.
