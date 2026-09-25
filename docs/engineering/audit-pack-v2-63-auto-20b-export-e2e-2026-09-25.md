# Audit-pack — `v2.63-beta` (`AUTO-20B` · Export E2E + oráculo same-material)

**Versión:** `1.88.0-beta` · **Rótulo:** `AUTO-20B` / `V2.63` · **Fecha:** 2026-09-25 · **Base de
auditoría:** cierre de `v2.62-beta`.

**Plan:** [plan-v2-63-auto-20b-export-e2e-2026-09-25.md](./plan-v2-63-auto-20b-export-e2e-2026-09-25.md) ·
**Origen:** [auditoría de `v2.62-beta`](./auditoria-v2-62-auto-20-material-paper-real-2026-09-24.md)
(deuda nº 1) · **Pack previo:** [audit-pack v2.62](./audit-pack-v2-62-auto-20-material-paper-real-2026-09-24.md).

## §1 — Qué se construyó (afirmación → código → test)

| # | Afirmación | Código | Test que la sostiene |
|---|---|---|---|
| 1 | La lectura paginada **recupera todo** (no trunca) | `paper_cycles_export.py` → `_read_all_reservations` | `test_pagination_reads_the_whole_universe_across_pages` |
| 2 | Una página llena **sin progreso** ⇒ `saturado=True` | idem | `test_a_page_that_never_advances_is_declared_as_saturated` |
| 3 | Un total múltiplo exacto de la página **termina completo** | idem | `test_an_exact_multiple_page_size_still_terminates_complete` |
| 4 | Sin completitud, el exportador **no publica JSON** (`exit 2`) | `main` → `MaterialIncompleteError` → `return 2` | `test_the_exporter_blocks_with_exit_two_when_completeness_cannot_be_proven` (PG) |
| 5 | `offset` **no** repite ni salta filas (orden total) | `reservation_store.py` (InMemory + Postgres) | `test_a_cycle_query_can_be_paginated_without_gaps_or_repeats` |
| 6 | El worker de `AUTO-9` sigue **byte-idéntico** (no pasa `offset`) | idem (parámetro keyword-only opcional) | las suites de la costura `AUTO-9` sin cambio |
| 7 | El manifest cuenta **el MISMO** material que el instrumento | `auto_material_manifest.py` (application) | `test_the_manifest_counts_the_same_material_the_instrument_carries` |
| 8 | Las particiones por versión **no se contaminan** | idem (`perVersion`) | `test_the_manifest_partitions_by_version_without_contaminating` |
| 9 | El hueco de identidad se declara | idem (`cyclesWithoutIdentity`) | `test_the_manifest_declares_the_identity_gap` |
| 10 | La huella es **orden-invariante** y estable | `auto_material_manifest.py` (analytics) | `test_the_fingerprint_is_stable_and_order_independent` |
| 11 | La huella normaliza números por **valor** (no por serialización) | idem (`_NUMERIC_KEYS`) | `test_the_fingerprint_normalizes_the_number_not_its_serialization` |
| 12 | Los identificadores **no** se normalizan | idem | `test_the_fingerprint_does_not_touch_identifiers_that_look_numeric` |
| 13 | Un cambio de universo cambia la huella | idem | `test_changing_the_universe_changes_the_fingerprint` |
| 14 | **Sin reloj**: el instante de exportación no entra a la huella | idem (el timestamp vive en el manifest, no en el hash) | `test_the_fingerprint_does_not_depend_on_a_clock` |
| 15 | El manifest es la huella del material **del instrumento** | application llama al puro de analytics | `test_the_manifest_fingerprint_is_the_instrument_material_fingerprint` |
| 16 | Sin manifest, el informe es **byte-idéntico** al auditado | `auto_adaptive_calibration.py` → `as_dict()` | `test_the_report_without_material_is_byte_identical_to_the_audited_one` |
| 17 | Con manifest, **ninguna medición cambia** y el sello no se mueve | idem | `test_the_material_manifest_is_published_verbatim_and_does_not_change_the_reading` |
| 18 | El battery **propaga** el manifest (nota y huella por stderr) | `auto_replay_battery.py` → `material=manifest` | `test_the_battery_propagates_the_exported_manifest_to_the_calibration_report` |
| 19 | **E2E con PG real**: fills + reservas + régimen → JSON → calibración, cardinalidad contra oráculo | fixture + exportador real (`main`, sin mocks) | `test_the_export_is_certified_end_to_end_against_real_postgres` |
| 20 | **Same-material**: AUTO-7 y AUTO-20 miden el MISMO universo (cruzando el JSON) | `adaptive_instrument_cycles` vs `build_auto_self_evaluation` | `test_the_report_and_the_instrument_measure_the_same_material` |
| 21 | O1/O2 siguen vigentes sobre el material real (`unmeasured_r:C`, sin `unmeasured_r:A`, `unversioned_cycles`, WFE emparejado, aislamiento por versión) | `auto_adaptive_calibration.py` | mismo test (PG), asertos (5) |

Cada afirmación tiene su **mutación** (§4) que la mata.

## §2 — Superficie medida (compuertas)

| Compuerta | Comando | Resultado |
|---|---|---|
| Lint | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| Capas | `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (626 ficheros) |
| Tipos | `uv run mypy … --follow-imports=silent` | **500 ficheros, 0 errores** |
| Puros | `uv run pytest packages/py/analytics/tests packages/py/application/tests -q` | **3147 passed** |
| E2E PG | `AUTO20B_EXPORT_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py -q -rs` | **3 passed** (sin skips) |
| Mutaciones (nuevas) | `v2_44_mutation_audit.py M169 M170 M171 M172 M173 M174` | **6/6** muerden |
| Mutaciones (matriz) | `v2_44_mutation_audit.py` | **174/174**, `0` en `NADA`, `0` sin fragmento, restauración byte a byte |
| Línea base | la del propio runner (sin mutación) | **`ninguno`** en cada selección de tests del tramo (el rojo de M169–M174 es de la mutación, no del árbol) |

## §3 — Superficie de cambio

`10 ficheros` **de código/CI** modificados (**+404 / −23**) más **6 ficheros nuevos** (sin contar este pack) y **4 de documentación/sello** (CHANGELOG, PROJECT_STATE, índice, `package.json`):

* `paper_cycles_export.py` (+135/−…) — paginación completa, `MaterialIncompleteError` → `exit 2` y `material_manifest`.
* `reservation_store.py` (+25) — `offset` keyword-only en el `Protocol` y en los dos stores (aditivo).
* `auto_adaptive_calibration.py` (+20/−…) — bloque `material` **opcional** en `CalibrationReport`/`build_calibration_report`.
* `auto_replay_battery.py` (+34) — `_load` devuelve el manifest; se propaga y se imprime por stderr.
* `v2_44_mutation_audit.py` (+66) — M169–M174 y sus constantes.
* `auto_material_manifest.py` (**nuevo**, analytics, 164 líneas) — huella pura.
* `auto_material_manifest.py` (**nuevo**, application, 161 líneas) — manifest de conteos.
* `test_auto_v63_auto20b_export_e2e_pg.py` (**nuevo**, 492) y `test_auto_v63_auto20b_export_completeness.py` (**nuevo**, 175).
* `test_auto_material_manifest.py` (**nuevo**, `packages/py/analytics/tests/`, 107) y `test_auto_v63_auto20b_material_manifest.py` (**nuevo**, `packages/py/application/tests/`, 196).
* `test_auto_adaptive_calibration.py` (+34), `test_auto_v47_cycle_trace.py` (+47), `test_portfolio_reservation_pg.py` (+20).
* `.github/workflows/python-ci.yml` (+24) y `release-tag-ci.yml` (+22) — el E2E `_pg.py` se ignora offline, los puros entran por pase de directorio, y el E2E se certifica en el job PG con `AUTO20B_EXPORT_PG_REQUIRED=1`.
* `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, `package.json` (`1.87.0-beta`→`1.88.0-beta`).

## §4 — Mutaciones de la fase

| Id | Qué rompe | Rojo en |
|---|---|---|
| **M169** | La paginación se desactiva (una sola página) | `test_pagination_reads_the_whole_universe_across_pages` + `test_an_exact_multiple_page_size_still_terminates_complete` + `test_a_page_that_never_advances_is_declared_as_saturated` |
| **M170** | El `offset` se ignora: la lectura paginada repite la primera página | `test_a_cycle_query_can_be_paginated_without_gaps_or_repeats` |
| **M171** | `cyclesWithoutRisk` se falsea (todo se declara con denominador) | `test_the_manifest_counts_the_same_material_the_instrument_carries` |
| **M172** | La huella deja de ver `strategyVersion`/`regime` | `test_changing_the_universe_changes_the_fingerprint` + `test_the_fingerprint_does_not_touch_identifiers_that_look_numeric` |
| **M173** | El informe publica `material` aunque no se aporte (rompe el byte-idéntico) | `test_the_report_without_material_is_byte_identical_to_the_audited_one` + `test_the_material_manifest_is_published_verbatim_and_does_not_change_the_reading` + `test_the_report_payload_is_json_shaped` |
| **M174** | El battery deja de propagar el manifest | `test_the_battery_propagates_the_exported_manifest_to_the_calibration_report` |

## §5 — Freeze respetado

* `ADAPTIVE_POLICY_VERSION = "auto18-v1"` y `DATA_GATE_POLICY_VERSION = "auto15-v1"` **intactos**
  (verificado por lectura directa).
* `git diff` **vacío** para `auto_adaptive.py`, `auto_adaptive_data_gate.py`,
  `auto_simulation_worker.py`, `auto_adaptive_journal.py`, `v2_43_governor_evidence.py`,
  `governor.json` y `auto_adaptive_replay.py`.
* **`auto_adaptive_replay.py` NO se toca**: el contrato `statistical_oos_v1` de `AUTO-19A` queda igual.
* **Sin migración**: Alembic head sigue en `046_fill_reference_mid` (el `offset` es solo código).
* El `offset` es **aditivo**: el worker llama a `list_by_cycle_ids` sin `offset` (su lectura no cambia).

## §6 — Límites declarados (lo que este pack NO prueba)

1. **El walk-forward real sigue sin ejecutarse.** Los umbrales por defecto (`folds=3`, `min_is=8`,
   `min_oos=4`) exigen **≥32 ciclos medidos por estrategia**: el fixture del E2E es **sintético y
   declarado** y mide la **cadena de material**, no el edge. Correr el instrumento sobre una cuenta
   PAPER real es un paso **operativo del propietario** (`paper_cycles_export.py` →
   `auto_replay_battery.py --walk-forward`).
2. **La huella no es prueba de procedencia criptográfica**: certifica la **igualdad de universo** entre
   dos corridas (misma huella ⇒ mismo material), no que el material venga de una fuente concreta.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** siguen fuera de alcance
   (AUTO-21).
4. **El E2E cubre el camino del exportador con `strategy_version_id` no nulo**: los fills con versión
   `NULL` **no** los lee el exportador *por diseño* (declarado en el plan y en el docstring del script).
