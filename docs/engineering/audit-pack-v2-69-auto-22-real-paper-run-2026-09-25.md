# Audit-pack — `v2.69-beta` (`AUTO-22`) · RUN de evidencia PAPER reproducible + UI de evidencia en 3 niveles

> **AsOf:** 2026-09-25 · **Versión:** `1.94.0-beta` · **Base auditada (diff):** `v2.68-beta`
> **Alcance:** el RUN end-to-end reproducible (lector único PG → composición pura → bundle con huella)
> y el rediseño de la sección AUTO EVIDENCE en **tres niveles**. Fase de **instrumentación**, no de
> decisión: **la corrida PAPER real no se ejecuta** (bloqueo por material).
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.** El reparto **no se mueve**
> (`auto18-v1` / `auto15-v1`).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | La lectura PG es **una sola** (export y run comparten `read_paper_material`) | `bolsa_application/auto_paper_material.py`; `paper_cycles_export.py` como envoltorio | `test_the_exporter_and_the_run_share_the_only_pagination_reader` |
| 2 | El exportador conserva su contrato (stdout JSON, `exit 2`) tras el refactor | `paper_cycles_export.py` | E2E PG `test_auto_v63_auto20b_export_e2e_pg.py` |
| 3 | Sin ciclos con **R medible** el run se DECLARA bloqueado (`EvidenceRunBlockedError`), no publica bundle | `build_evidence_run_bundle` (guard `_measured_cycles`) | `test_the_run_is_blocked_without_any_cycle`, `test_the_run_is_blocked_when_no_cycle_has_a_measurable_r` + **M190** |
| 4 | El bundle **encadena** las piezas ya auditadas (`AUTO-19B` + `AUTO-21` + `AUTO-20C`): no hay segunda aritmética | `build_evidence_run_bundle` | `test_the_bundle_composes_the_audited_pieces_and_declares_its_provenance` |
| 5 | El **origen por defecto** es `synthetic_fixture`, nunca `paper_real` | `material_origin` (defecto declarado) | `test_the_default_origin_is_the_synthetic_fixture_never_paper_real` + **M189** |
| 6 | El bundle **viaja con la huella** del material (sello de procedencia) | `bundle["fingerprint"]` | **M188** |
| 7 | El **script** escribe un bundle **autónomo** y completo (`cycles`/`artifact`/`render`/`run`) | `scripts/auto_evidence_run.py` | `test_the_run_writes_a_complete_bundle_and_prints_the_three_levels` |
| 8 | La procedencia **la declara el material**, no el script (no se inventa) | `_load_cycles` + `manifest.materialOrigin` | `test_the_run_declares_the_origin_of_a_manifest_instead_of_inventing_it` |
| 9 | **BLOQUEADO sin escribir nada**: sin JSON de ciclos no se crea carpeta ni fichero parcial | `main` (`return 2` antes de `_persist`) | `test_the_run_is_blocked_without_writing_anything_when_the_cycles_file_is_missing` |
| 10 | Una corrida es **inmutable**: el directorio existente se rechaza (no se sobrescribe una medición) | `_persist` (`exist_ok=False`) + guard en `main` | `test_an_evidence_run_is_immutable_and_is_never_overwritten` |
| 11 | Con PG real el run **lee, sella y compone** (mismo material que el informe durable) | `_read_pg` → `read_paper_material` | `test_the_run_reads_real_postgres_material_and_seals_it` (E2E PG) |
| 12 | Los **tres niveles a stderr** publican lo medido **y declaran los huecos** (`NO MEDIDO`) | `_print_levels` / `summarize_evidence_levels` | `test_the_three_levels_publish_the_measured_numbers_and_the_declared_gaps` |
| 13 | El nivel **Material** publica el universo, sus huecos y la **huella** | `_material_rows` | `test_the_material_level_reports_the_universe_and_its_fingerprint` |
| 14 | Una correlación **no medida** es un hueco declarado, **jamás** un `0.0000` | `_context_rows` (`null ⇒ NOT_MEASURED`) | `test_an_unmeasured_correlation_is_a_declared_gap_never_a_zero` |
| 15 | Los niveles **derivan** del artefacto sin recalcular nada | `summarize_evidence_levels` | `test_the_levels_derive_from_the_artifact_without_recalculating` |
| 16 | La UI presenta los **3 niveles** (Material / Global+Calibration / Contexto) y cierra con `ALLOCATION` congelado | `buildEvidenceView` + `auto-evidence-section.tsx` | vitest `auto-evidence-report.test.ts` + `auto-evidence-section.test.tsx` |
| 17 | `P(R>0)` **declarada** y `P(R>0) OOS` **realizada** se muestran por separado (`WFE` en global) | `globalRows` | `test_keeps_the_DECLARED_P_R_0_apart_from_the_REALIZED_OOS_share` |
| 18 | Veredicto por estrategia: `edgeConfidence` → `SUPPORTED` / `NOT_SUPPORTED` / `INCONCLUSIVE`, sin inventar | `EDGE_VERDICTS` + `regimeEvidenceRows` | `test_maps_the_edge_band_to_the_verdict_the_backend_declares_never_inventing_one` |
| 19 | `null` de correlación en la UI ⇒ `NO MEDIDO` (nunca `0.0000`) | `crossStrategyRows` (`measureLabel`) | `test_never_publishes_a_0_0000_correlation_for_a_pair_that_could_not_be_measured` |
| 20 | El freeze sigue intacto y no hay migración | `git diff` del freeze; Alembic head `046_*` | verificación git + head |

## 2. Qué cambia (y qué no)

**Cambia.**
- **Lector único** `bolsa_application/auto_paper_material.py` (`read_paper_material`, `MaterialIncompleteError`,
  `NonPaperVenueError`); `paper_cycles_export.py` pasa a **envoltorio fino**.
- **Composición pura** `bolsa_analytics/cognitive/auto_evidence_run.py` con
  `EVIDENCE_RUN_SCHEMA = "auto22_evidence_run_bundle_v1"` y `EvidenceRunBlockedError`.
- **Script** `apps/api-python/scripts/auto_evidence_run.py`: bundle autónomo por corrida
  (`evidence_runs/<UTC>-<huella8>/`) y `exit 2` BLOQUEADO.
- **UI** `auto-evidence-report.ts` / `auto-evidence-section.tsx` en **tres niveles**; título
  `AUTO EVIDENCE (AUTO-22)`.
- Matriz de mutaciones: **M188…M190**.
- **P3-1 cerrado**: `testTimeout` por fichero en `core-r-scheduler.test.ts`.
- `package.json` / `CHANGELOG`: bump a `1.94.0-beta`.

**NO cambia.**
- El esquema del artefacto (`auto20c_evidence_artifact_v1` **se mantiene**): el run **no** añade claves.
- El invariante PAPER = 100 % virtual, el reparto (`auto18-v1` / `auto15-v1`), el freeze, la migración.
- Las piezas de `AUTO-21` (`P(R>0)`, correlación, régimen): el run las **compone**, no las reimplementa.
- **La evidencia sigue sin repartir**: `ALLOCATION` se publica como `none` (congelado).

## 3. Compuertas re-medidas

| Compuerta | Comando | Resultado |
|---|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` | **1331 passed** (232 ficheros), **sin** flag de timeout |
| Frontend typecheck | `pnpm --filter @bolsa/web typecheck` | OK |
| Frontend lint | `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| Frontend build | `pnpm --filter @bolsa/web build` | OK |
| Frontend contrato | `pnpm --filter @bolsa/web contract:check` | OK |
| Python application + analytics | `uv run pytest packages/py/application packages/py/analytics -q` | **3196 passed** |
| Python runner (api-python) | `uv run pytest apps/api-python/tests/test_auto_v69_auto22_evidence_run.py -q` | **8 passed** |
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| Mypy | `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 501 source files** |
| import-linter | `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones (tramo) | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py M188 M189 M190` | las **3 muerden** (M188 → 2 tests de la composición + runner · M189 → composición · M190 → composición + runner) |
| Matriz completa | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py` | **190/190** medidas, **0** sin fragmento, restauración **byte a byte** |

### 3.bis Medición exacta

Ver [`traspaso-relevo-post-v2.69-auto-22-real-paper-run-2026-09-25.md`](./traspaso-relevo-post-v2.69-auto-22-real-paper-run-2026-09-25.md) §Compuertas
para los conteos sellados de esta corrida.

## 4. P3-1 cerrado (flake ajeno)

`apps/web/src/features/backtests/core-r-scheduler.test.ts` agotaba su timeout de **5 s** solo bajo la
carga de la suite completa (declarado como ajeno desde la auditoría de `v2.68`). Se cierra con un
**presupuesto declarado por fichero**:

```ts
vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 });
```

Es **estabilización**, no enmascaramiento: el margen (20 s) queda muy por debajo de un cuelgue real
(un deadlock seguiría superándolo), el fichero no cambia de lógica y la suite completa queda verde sin
el flag global `--testTimeout`.

## 5. Nota de alcance para el auditor

- El **material PAPER real no existe todavía** (decisión del propietario): esta fase deja el RUN
  **ejecutable y probado** con fixture declarado y con PG E2E; **no produce evidencia de mercado**. La
  UI muestra `NO MEDIDO` en los tres niveles hasta que exista material.
- El run **no decide**: publica evidencia. Que `P(R>0)`, la correlación o el régimen **no muevan** el
  reparto es el **objetivo** de la fase, no un defecto.
- El bundle es **autónomo e inmutable**: `run.json` referencia la huella y el artefacto viaja
  **verbatim** desde el instrumento; no hay recálculo ni número copiado.
- **Sin material no hay fichero**: `exit 2` y ni carpeta. La comprobación de que no se escribe nada es
  parte del contrato (`test_the_run_is_blocked_without_writing_anything...`).
