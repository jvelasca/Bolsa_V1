# Audit-pack — `v2.71-beta` (`AUTO-19A`+`AUTO-19B`) · Corrección de `P(R>0)` y cierre de P3

> **AsOf:** 2026-09-26 · **Versión:** `1.96.0-beta` · **Base auditada (diff):** `v2.70-beta`
> **Alcance:** (A) separar `P(ciclo>0)` de `P(edge>0)` y hacer **homogénea** la pregunta de
> calibración; (B) cerrar los P3 de la auditoría de `AUTO-19A`/`AUTO-19B`. Fase de **corrección del
> instrumento**, no de estadística nueva.
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.** El reparto **no se
> mueve** (`auto18-v1` / `auto15-v1`).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | `P(edge>0)` es la fracción de **medias bootstrap** `> 0` | `ExpectancyInterval.edge_positive_probability` | `test_edge_positive_probability_is_the_share_of_positive_bootstrap_means` + **M183** |
| 2 | `P(ciclo>0)` es la fracción de **ciclos medidos** con `R>0`, distinta de `P(edge>0)` | `ExpectancyInterval.cycle_positive_share` | `test_cycle_positive_share_counts_cycles_not_bootstrap_means` + **M193** |
| 3 | Sin bootstrap, `P(edge>0)` es `None` pero `P(ciclo>0)` **existe** | `_interval_from_episodes` (rachas insuficientes) | `test_edge_positive_probability_is_none_without_a_bootstrap` |
| 4 | La calibración compara **`P(ciclo>0)` IS vs frecuencia positiva OOS** (magnitudes homogéneas) | `_question_probability_positive` | `test_probability_positive_calibration_ignores_the_edge_probability` + **M194** |
| 5 | La pregunta de calibración **ignora** `P(edge>0)` aunque esté presente | `_question_probability_positive` (filtro/errores por `is_cycle_positive_share`) | ídem |
| 6 | `regimeEvidence.probabilityPositive` = `P(ciclo>0)`; `edgePositiveProbability` viaja aparte | `auto_adaptive_regime_evidence.py` | `test_auto_adaptive_regime_evidence.py` |
| 7 | Las celdas de validación publican `probabilityPositive` = `P(ciclo>0)` + `edgePositiveProbability` | `_interval_cell` | `test_auto_evidence_validation.py` |
| 8 | Los sellos suben: `bootstrap_episodes_v3`, `walk_forward_calibration_v4`, `current_regime_evidence_v2`, `auto23_*_v2` | constantes de módulo | `test_auto_v60_auto19_uncertainty_seam.py`, `test_auto_v64_auto20c_artifact.py`, `test_auto_v70_auto23_evidence_validation.py` + **M182**/**M184** |
| 9 | La cobertura **NO MEDIDA** (`None`) sale de la comparación y se declara en `cellsUnmeasured` | `_question_coverage` | `test_a_cell_without_a_measured_regime_coverage_is_declared_not_counted_as_uncovered` + **M195** |
| 10 | El nivel de intervalo publicado es el **clampeado** (el que usó el bootstrap) | `build_replay_report` (`resolved_level`) | `test_the_interval_level_is_clamped_and_published` + **M196** |
| 11 | `ReplayCell` **no** emite `regimeCoverage`; `StrategyConfidence` sí, como `float` | `ReplayCell.as_dict` vs `StrategyConfidence.as_dict` | `test_the_regime_coverage_key_is_a_float_in_confidence_and_a_band_in_replay` + **M197** |
| 12 | La UI mantiene sus claves (`meanDeclaredProbability`, `probabilityPositiveOos`, `probabilityPositive`) | `auto-evidence-report.ts` (sin cambio funcional) | `auto-evidence-report.test.ts` |
| 13 | El reparto y el freeze siguen intactos; sin migración | `git diff` del freeze; Alembic head `046_*` | verificación git + head |

## 2. Qué cambia (y qué no)

**Cambia.**

- `.../auto_adaptive_uncertainty.py`: `edge_positive_probability` + `cycle_positive_share`; sello
  `bootstrap_episodes_v3`.
- `.../auto_adaptive_replay.py`: `isEdgePositiveProbability`/`isCyclePositiveShare`,
  `dominantRegimeCoverage`, `cellsUnmeasured` y nivel clampeado.
- `.../auto_adaptive_calibration.py`: pregunta homogénea; `walk_forward_calibration_v4`.
- `.../auto_adaptive_regime_evidence.py`: `probabilityPositive` por ciclos + `edgePositiveProbability`;
  `current_regime_evidence_v2`.
- `.../auto_evidence_validation.py`: celdas por ciclos + `edgePositiveProbability`; sellos `_v2`.
- `apps/api-python/scripts/v2_44_mutation_audit.py`: `M182`–`M187` + `M193`–`M197`.
- bump `1.95.0-beta` → `1.96.0-beta`.

**No cambia.**

- **La aritmética**: el intervalo bootstrap, el WFE, la correlación, el régimen y la banda de edge
  quedan **congelados**. Solo cambia **la lectura** de una probabilidad.
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`, umbrales de rotación, `portfolio_optimizer.py`,
  `portfolio_reservation.py` intactos. **Sin migración** (`046_fill_reference_mid`).
- **`evidence_runs`/`evidence_validations`** y el runbook del primer RUN: intactos.

## 3. Compuertas medidas

| Compuerta | Resultado |
|---|---|
| Python `packages/py/analytics` | **1262 passed** |
| Python `packages/py/application` | **1945 passed** (5 errores de fixture PG por DSN fast-fail, ajenos) |
| Suites `api-python` afectadas | `test_auto_v60_...`, `test_auto_v64_...`, `test_auto_v70_...` verdes (13 passed / 1 skipped) |
| Suites `api-python` offline (gate CI) | **479 passed, 14 skipped, 0 fallos** (26 tests `*_pg` no ejecutables sin Postgres real) |
| Frontend `vitest` / `typecheck` / `build` / `contract:check` | ver CHANGELOG |
| `ruff` / `import-linter` / `mypy` | ver CHANGELOG |
| Matriz de mutaciones | **197/197**, restauración **byte a byte**, árbol intacto |
| `Release tag CI` del tag `v2.71-beta` | run **`36236375738`** — **GREEN en la primera pasada** (8m13s, `intento=1`, 10 jobs + `certify`) |
| Mismo commit y tag | `Python CI` `36236375798` · `Frontend CI` `36236375770` · `Optimize lab` `36236375716` · `Fase 2 scientific` `36236375788` — **success** |

> **Evidencia cruda de la matriz**: `evidencia-matriz-mutaciones-v2.71-197-2026-09-26.txt`.
> Reproducible con `uv run python apps/api-python/scripts/v2_44_mutation_audit.py`.
> La medición de la fase se hizo **contra el árbol ya commiteado**: la sonda reporta
> `estado git de esos ficheros (antes): limpio` y `(despues): limpio`, es decir restauración
> byte a byte sobre un árbol **sellado**, no sobre un working tree sucio.
>
> **Nota de conteo:** el plan de fase citaba `192 → 198`; el script define exactamente `M1`–`M197`
> contiguos (192 previas + las 5 nuevas `M193`–`M197`), así que la matriz real es **197/197**. El
> script lo autoreporta (`medidas: 197/197, ninguna se quedó sin fragmento`).

## 4. Mutaciones nuevas / actualizadas

| Etiqueta | Invariante | Rojo en |
|---|---|---|
| **M182** (act.) | La lectura que separa las dos probabilidades conserva su sello `_v3` | `test_auto_v60_auto19_uncertainty_seam.py` |
| **M183** (act.) | `P(edge>0)` es la fracción de medias bootstrap positivas | `test_edge_positive_probability_is_the_share_of_positive_bootstrap_means` |
| **M184** (act.) | La calibración homogénea sella `_v4` | `test_auto_v64_auto20c_artifact.py` |
| **M187** (act.) | El régimen sin celda no publica la lectura agregada (`P(ciclo>0)`) | `test_auto_adaptive_regime_evidence.py` |
| **M193** | `P(R>0)` cuenta **ciclos** positivos, no otra cosa | `test_cycle_positive_share_counts_cycles_not_bootstrap_means` |
| **M194** | La calibración compara `P(ciclo>0)` IS vs OOS (no `P(edge>0)`) | `test_probability_positive_calibration_ignores_the_edge_probability` |
| **M195** | La cobertura `None` no entra en el grupo no cubierta | `test_a_cell_without_a_measured_regime_coverage_is_declared_not_counted_as_uncovered` |
| **M196** | El nivel publicado es el clampeado | `test_the_interval_level_is_clamped_and_published` |
| **M197** | `dominantRegimeCoverage` no colisiona con `regimeCoverage` | `test_the_regime_coverage_key_is_a_float_in_confidence_and_a_band_in_replay` |

## 5. Límite declarado

Esta fase **corrige el instrumento**; **no** produce estadística nueva ni ejecuta la corrida real. El
**primer RUN PAPER real** sigue siendo el **paso operativo del propietario** y el **hito siguiente**;
las deudas **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N) quedan **abiertas** hasta el
primer dataset real. **P3-4** (ver §6) se **registra** y no se aborda en esta fase.

## 6. Resultado de la auditoría externa (`v2.71-beta`)

**Veredicto: `APROBADA CON OBSERVACIONES` · 0 bloqueantes · 14/15 tesis PASS y la 15 PARCIAL.**

**Objeto auditado.** Tag **anotado** `v2.71-beta` = objeto `80dbed6c` → commit `a310fbc5`; `HEAD` = `2ace60fb`.
`git diff v2.71-beta..HEAD` = 7 ficheros, **todos docs** (`CHANGELOG.md`, `PROJECT_STATE.md`,
`engineering-index-2026-08-03.md` y los 4 docs de la fase), `+29/−5` ⇒ **cero código** ⇒ el código
auditado es **byte-idéntico al del tag**. Verificado de forma independiente en `main`.

| Tesis | Veredicto | Evidencia del auditor |
|---|---|---|
| 1–4 (`P(edge)>0` por medias bootstrap; `P(ciclo>0)` por ciclos; divergen; sin bootstrap `None`) | **PASS** | Sondas A/B (18 aciertos + 2 pérdidas ⇒ `cycle=0.9`, `edge=0.109`) + `M183`/`M193` |
| 5–6 (calibración homogénea; claves UI intactas) | **PASS** | `_question_probability_positive` ignora `P(edge>0)`; diff TS **solo un comentario**; `M194` (9 rojos) |
| 7–9 (H2 cobertura `None` declarada; H3 nivel clampeado; H4 sin colisión) | **PASS** | Sondas D/E/F + `M195`/`M196`/`M197` |
| 10–11 (`regimeEvidence` y validación por `P(ciclo>0)` + `edgePositiveProbability`, sellos `_v2`) | **PASS** | Sondas G/H sobre código y payload |
| 12–14 (freeze; sin migración; la evidencia no reparte ni escribe durables) | **PASS** | `git diff` vacío de los 5 congelados; head `046_fill_reference_mid`; sin refs a `evidence_*` |
| 15 (matriz 197/197 byte a byte) | **PARCIAL** | Evidencia persistida `197` entradas / `197` restauraciones; **re-ejecutó solo los 7 mandatados → 7/7 muerden y restauran, `git` limpio** (límite de mandato) |

**Compuertas re-medidas por el auditor:** `ruff` **All checks passed** · `import-linter` **4 kept / 0 broken**
(632 ficheros, 3418 deps) · `mypy` **501 ficheros, 0 issues** · `analytics` **1262 passed** · costuras
`api-python` **13 passed / 1 skipped** (skip de PG por DSN inválido, delimitado) · sonda propia de 35
oráculos **34 PASS / 1 FAIL** (el FAIL es P3-4).

**Observación única (P3-4, heredada y ajena a las 15 tesis).**
`build_current_regime_evidence` publica el `level` **sin clampar** (`auto_adaptive_regime_evidence.py:177`)
mientras el bootstrap usa el **clampeado**: sonda `G4` ⇒ `level=0.0` publicado vs `interval.level=0.5`
usado. **Preexistente** (idéntico en `v2.70-beta`), **read-only** y misma clase que **H3**, que esta fase
cerró **solo** en `build_replay_report`. Queda registrada como **P3-4** en la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) y **no** se aborda aquí.

**Límites declarados del auditor.** No re-corrió las 197 mutaciones (solo las 7 autorizadas); no corrió
`apps/api-python` completo (cuelgue de PG) ni las suites de frontend; no reproduce los runs de CI
citados (externos al repo). Cierre: `git status --porcelain` = **0** ⇒ árbol **limpio**.
