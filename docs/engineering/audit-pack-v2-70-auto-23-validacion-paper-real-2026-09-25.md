# Audit-pack — `v2.70-beta` (`AUTO-23`) · Validación de evidencia PAPER real (harness) + procedencia imposible de confundir

> **AsOf:** 2026-09-25 · **Versión:** `1.95.0-beta` · **Base auditada (diff):** `v2.69-beta`
> **Alcance:** (A) procedencia y **realidad de ejecución** imposibles de confundir en la UI; (B)
> **harness de validación** reutilizable (`P(R>0)` vs N, estabilidad de régimen, diagnósticos de la
> correlación por cubos `P3-2`/`P3-3`) sobre la **misma** matemática de `AUTO-22`; (C) **runbook** del
> primer RUN real. Fase de **preparación y blindaje**, no de decisión: **la corrida PAPER real no se
> ejecuta** (bloqueo por material).
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.** El reparto **no se mueve**
> (`auto18-v1` / `auto15-v1`).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | La UI distingue **ejecución virtual** de **dinero real**: `virtual_paper_only` ⇒ `VIRTUAL — NO REAL MONEY` | `classifyExecutionReality` (`auto-evidence-report.ts`) | vitest `classifyExecutionReality > labels a paper artifact as VIRTUAL…` |
| 2 | Un artefacto con **dinero real** NO se degrada a virtual (`desconocido`, tono de peligro) | `classifyExecutionReality` (guarda `realMoneyAtRisk`) | `flags real money at risk as unknown…` + sección `flags a real-money artifact…` |
| 3 | `SOURCE` separa **dato real** de **dinero real** con subtítulo explícito | `EvidenceSourceView.subtitle` | `separates PAPER REAL data from real money…` |
| 4 | Un `executionReality` ausente es **`NO MEDIDO`** (nunca se asume virtual) | `classifyExecutionReality` (`=== null`) | `declares NOT MEASURED when executionReality is absent…` |
| 5 | El origen **nunca** se degrada `desconocido` ⇒ `paper_real` | `classifyEvidenceSource` (sin cambios de contrato) | `unknown origin never degrades to paper_real` |
| 6 | El bloque `EXECUTION REALITY` es visible y de alto contraste (`data-execution-kind`) | `auto-evidence-section.tsx` | `renders a prominent VIRTUAL execution reality…` |
| 7 | El barrido **compone** `build_evidence_run_bundle` y **copia** sus cifras (una sola aritmética) | `_sweep_row_from_bundle` | `test_the_sweep_copies_the_probability_from_the_only_arithmetic` + **M191** |
| 8 | Un `N` mayor que el material medido es **`NO MEDIDO`** (jamás fabricado / cero de relleno) | `_unmeasured_sweep_row` | `test_a_size_beyond_the_measured_material_is_not_measured_never_fabricated` + **M192** |
| 9 | El barrido **no elige** `N`: publica la serie sobre el **prefijo cronológico** y la regla de muestreo | `build_sample_size_sweep` | `test_the_sweep_declares_the_sample_and_never_selects_a_size` |
| 10 | Régimen: veredicto **global vs por régimen** con sus **divergencias** (lectura, no gate) | `build_regime_stability` | `test_regime_stability_publishes_global_and_per_regime_verdicts`, `test_regime_divergences_are_declared_as_a_reading_not_a_gate` |
| 11 | Correlación: número **y** diagnósticos `P3-2` (frecuencia/exposición) sin tocar la métrica | `build_correlation_validation` | `test_correlation_validation_publishes_every_bucket_with_its_diagnostics` |
| 12 | Correlación sin cubos compartidos: **hueco declarado**, nunca `0` | `_pair_diagnostics` + `AUTO-21` | `test_a_pair_without_shared_buckets_is_a_declared_gap_never_a_zero` |
| 13 | Origen por defecto del informe: **fixture sintético**, nunca PAPER real | `build_validation_report` (defecto declarado) | `test_the_default_origin_is_the_synthetic_fixture_never_paper_real` |
| 14 | **Fail-closed**: sin ciclos con R medible ⇒ `EvidenceValidationBlockedError` | `build_validation_report` | `test_the_validation_report_is_blocked_without_measured_cycles` |
| 15 | El CLI escribe un **bundle inmutable** (`sweep`/`regime_stability`/`correlation_validation`/`validation`) y no sobrescribe | `scripts/auto_evidence_validate.py` (`_persist`, `exist_ok=False`) | `test_the_validation_writes_a_complete_report`, `test_a_validation_is_immutable_and_is_never_overwritten` |
| 16 | El CLI **BLOQUEA sin escribir nada** (sin fichero de ciclos / sin R medible) | `main` (`return 2` antes de `_persist`) | `test_the_validation_is_blocked_without_writing_anything…`, `test_the_validation_is_blocked_when_no_cycle_has_a_measurable_r` |
| 17 | La procedencia **la declara el material**, no el script | `_load_cycles` + `manifest.materialOrigin` | `test_the_validation_declares_the_origin_of_a_manifest_instead_of_inventing_it` |
| 18 | **Un solo lector de material** (validador = aplicación) | `read_paper_material` | `test_the_validator_and_the_run_share_the_only_material_reader` |
| 19 | Con PG real, el validador **lee, sella y compone** (material real) | `_read_pg` → `read_paper_material` | `test_the_validation_reads_real_postgres_material_and_seals_it` (E2E PG, opt-in) |
| 20 | El freeze sigue intacto y no hay migración | `git diff` del freeze; Alembic head `046_*` | verificación git + head |

## 2. Qué cambia (y qué no)

**Cambia.**

- **UI** `auto-evidence-report.ts`: `classifyExecutionReality` + `execution` en `EvidenceView` +
  `source.subtitle`; `auto-evidence-section.tsx`: bloque `EXECUTION REALITY` (`ops-auto-evidence-execution-reality`)
  y `SOURCE` reforzado (subtítulo `ops-auto-evidence-source-subtitle`).
- **Harness puro** `bolsa_analytics/cognitive/auto_evidence_validation.py` (**nuevo**):
  `EVIDENCE_VALIDATION_SCHEMA = "auto23_evidence_validation_v1"`, `EvidenceValidationBlockedError`,
  `build_sample_size_sweep`, `build_regime_stability`, `build_correlation_validation`,
  `build_validation_report`.
- **CLI** `apps/api-python/scripts/auto_evidence_validate.py` (**nuevo**): bundle inmutable en
  `evidence_validations/<UTC>-<huella8>/`, `exit 2` BLOQUEADO, sin fichero parcial.
- **Runbook** `protocolo-primer-run-paper-real-v2.70-2026-09-25.md`.
- **Mutaciones** `M191` / `M192`; bump `1.94.0-beta` → `1.95.0-beta`.

**No cambia.**

- **Una sola aritmética**: bootstrap, WFE, `P(R>0)`, correlación, régimen y banda de edge **congelados**;
  el harness **consume** `build_evidence_run_bundle`, `build_adaptive_uncertainty` y
  `build_strategy_correlation_report`. **No** se modifican `build_calibration_report`,
  `build_strategy_correlation_report`, `build_current_regime_evidence` ni `build_evidence_run_bundle`.
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`, umbrales de rotación, `portfolio_optimizer.py`,
  `portfolio_reservation.py` intactos. **Sin migración** (`046_fill_reference_mid`).

## 3. Compuertas medidas

| Compuerta | Resultado |
|---|---|
| Frontend `vitest` (suite completa, sin flag de timeout) | **1339 passed** (232 ficheros) |
| `typecheck` | OK |
| `lint` | **0 errores** (23 warnings preexistentes) |
| `build` | OK |
| `contract:check` | OK |
| Python `packages/py/application` + `packages/py/analytics` | **3203 passed / 5 skipped** |
| CLI `test_auto_v70_auto23_evidence_validation.py` | **6 passed** (sonda PG **opt-in**, 1 deselected sin PG) |
| `ruff` | **All checks passed!** |
| `import-linter` | **4 kept / 0 broken** |
| `mypy` (gate del repo) | **Success: no issues found in 501 source files** |
| Matriz de mutaciones | **192/192**, sin fragmentos ausentes, restauración **byte a byte**, árbol intacto |

> **Evidencia cruda de la matriz** (`192/192` medidas, `192/192` rojas, `192/192` restauradas byte a
> byte, árbol intacto): [`evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt`](./evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt).
> Reproducible con `uv run python apps/api-python/scripts/v2_44_mutation_audit.py` (sin filtro = matriz
> completa). Incluye `M191` y `M192`.

## 4. Mutaciones nuevas

| Etiqueta | Invariante | Rojo en |
|---|---|---|
| **M191** | El barrido **compone** `P(R>0)`; recalcularla es una segunda aritmética | `test_the_sweep_copies_the_probability_from_the_only_arithmetic` |
| **M192** | Un `N` mayor que el material medido es **`NO MEDIDO`**, no una fila fabricada | `test_a_size_beyond_the_measured_material_is_not_measured_never_fabricated`, `test_the_sweep_is_blocked_without_measured_cycles` |

## 5. Puesta en seco (BLOQUEADO y procedencia)

- `--cycles <fixture>` ⇒ informe con `materialOrigin = synthetic_fixture` y `source = fixture`.
- `--cycles inexistente` ⇒ **`exit 2` BLOQUEADO** sin crear carpeta ni fichero.
- `--cycles` sin R medible ⇒ **`exit 2` BLOQUEADO** sin fichero.

## 6. Nota de reproducibilidad (sonda de referencias de documentos)

`a9_doc_refs_probe.py` marca como «referencia muerta» los **nombres de artefacto de salida** que este
pack y el runbook citan (`artifact.json`, `cycles.json`, `run.json`, `sweep.json`,
`regime_stability.json`, `correlation_validation.json`, `validation.json`). **No son ficheros del
repositorio**: los **genera** el RUN/el validador dentro de `evidence_runs/` y `evidence_validations/`
(ignorados por git, ver `.gitignore`). La sonda comprueba **existencia de rutas** y no distingue un
artefacto de salida de un fichero versionado; el **mismo** resultado se obtiene con los documentos ya
auditados de `v2.69`. Es un **falso positivo declarado**, no una referencia muerta. La sonda **no** es
un gate de CI (no la invoca ningún workflow).

## 7. Límite declarado

**El material PAPER real no existe todavía.** El harness y el runbook quedan **listos**; la
**ejecución + auditoría empírica** son el **paso operativo del propietario**. **P3-2** (validación de
la correlación por cubos) y **P3-3** (`P(R>0)` vs N) quedan **abiertas** hasta el primer dataset real.
**NO se bajan** `min cycles` / `min R` / `folds` para forzarlo.
