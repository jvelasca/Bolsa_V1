# Audit-pack — `v2.66-beta` (`AUTO-20E`) · hardening de procedencia del AUTO EVIDENCE REPORT

> **AsOf:** 2026-09-25 · **Versión:** `1.91.0-beta` · **Base auditada (diff):** `v2.65-beta` (`a077c1c6`)
> **Alcance:** las 3 P3 de la auditoría de `v2.65-beta`. Fase de endurecimiento; sin producto nuevo.
> **SIN migración.** **El freeze no se toca.**

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | El contrato de claves **lee Python de verdad** (no un literal espejo) | `auto-evidence-report.test.ts` → `pythonCalibrationKeys()` | `matches the calibration keys the Python instrument actually emits` |
| 2 | Ese contrato **puede fallar**: renombrar una clave en Python lo pone rojo | `auto_adaptive_calibration.py:116-121` | prueba manual reproducida por el auditor (es **vitest**; **no** la cubre la matriz pytest) |
| 3 | La compuerta **corre** ante un cambio solo de Python | `.github/workflows/frontend-ci.yml` (`paths`) | revisión del `on:` |
| 4 | El render no se desalinea del instrumento | `auto_evidence_report.py` `_CALIBRATION_ROWS` | `test_the_render_rows_use_the_canonical_calibration_keys` |
| 5 | Una procedencia **contradictoria** no se resuelve a `PAPER REAL` | `auto-evidence-report.ts` `classifyEvidenceSource` | `a contradictory materialOrigin is declared…` |
| 6 | La contradicción **avisa** | `auto-evidence-report.ts` `integrityWarnings` | mismo test (assert en `incoherente`) |
| 7 | **Ausente ≠ vacío** en el perímetro (TS) | `auto-evidence-report.ts` `listLabel` | `distinguishes an absent perimeter list from an empty one` |
| 8 | **Ausente ≠ vacío** en el perímetro (Python) | `auto_evidence_report.py` `_version_list` | `test_the_render_distinguishes_an_absent_perimeter_list_from_an_empty_one` |
| 9 | El render de artefactos reales **no cambia** | listas siempre presentes en la cadena real | lectura del exportador + render |
| 10 | El freeze sigue intacto y no hay migración | `git diff` del freeze; Alembic head | verificación git + `046_*` |

## 2. Qué cambia (y qué no)

**Cambia.**
- El test de contrato del frontend: de **TS-vs-TS** a **TS-vs-Python**.
- `frontend-ci.yml`: `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` entra
  en los `paths` de `push` y `pull_request`.
- `classifyEvidenceSource` / `integrityWarnings`: incoherencia raíz↔material ⇒ `PROCEDENCIA DESCONOCIDA` + aviso.
- Perímetro: `NO MEDIDO` (ausente) vs `(ninguna)` (vacío), en TS y en Python.
- Matriz de mutaciones: **M179**, **M180**.

**NO cambia.**
- El esquema del artefacto (`auto20c_evidence_artifact_v1`), el render para artefactos reales, el invariante
  PAPER=virtual, el reparto (`auto18-v1`/`auto15-v1`), el freeze y la migración.

## 3. Compuertas a re-ejecutar

| Compuerta | Comando | Esperado |
|---|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` | **1323 passed** (232 ficheros) |
| Frontend typecheck | `pnpm --filter @bolsa/web typecheck` | OK |
| Frontend lint | `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| Frontend build | `pnpm --filter @bolsa/web build` | OK |
| Contrato OpenAPI | `pnpm --filter @bolsa/web contract:check` | OK |
| Python analytics | `uv run pytest packages/py/analytics -q` | **1208 passed** |
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | OK |
| Import-linter | `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones nuevas | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py M179 M180` | ambas **muerden** |
| Matriz completa | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py` | **180/180**, 0 sin fragmento |

## 4. Evidencia de que el contrato es real (y no decorativo)

Se rompió a propósito `CALIBRATION_QUESTION_INTERVAL_COVERAGE = "interval_coverage"` → `"interval_coverage_BROKEN_FOR_PROOF"`
en `auto_adaptive_calibration.py` y se corrió el test del frontend:

```
× schema contract > matches the calibration keys the Python instrument actually emits
Tests  1 failed | 21 passed (22)
```

Restaurado el fichero (diff **vacío**), el test vuelve a verde.

> **Corrección (`v2.67`, P3-1 de la auditoría de `v2.66`).** Este contrato es **vitest**: **no** lo cubre la
> matriz de mutaciones (pytest). La mutación **M180** formaliza **otra** propiedad —el atado
> `_CALIBRATION_ROWS`↔`_CALIBRATION_QUESTIONS` **dentro del render Python**—, no el contrato TS-vs-Python.
> La frase original («la matriz lo formaliza como M180») era una **sobre-afirmación**.

## 5. Límite declarado (no es fallo de la fase)

- La **corrida PAPER real** no se ejecuta aquí; el bloqueo por material del PostgreSQL local
  (`sim_fill_finance_context` con `cycle_id` NULL en todos los fills) sigue siendo **paso operativo del
  propietario**. Esta fase no lo toca.
- **P3-2** es **TS puro**: la matriz de mutaciones (que corre pytest) **no** puede morderlo; su cobertura es
  **vitest**. Se declara para que el auditor no lo cuente como hueco de la matriz.
