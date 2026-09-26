# Traspaso de relevo — post `v2.70-beta` (`AUTO-23`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.70-beta` (`1.95.0-beta`) · **Base:** `v2.69-beta`
> **Para:** el auditor externo y el siguiente agente.

## 1. Qué se ha hecho

Fase de **preparación y blindaje** (no de decisión), en tres frentes:

1. **UI — procedencia y realidad de ejecución imposibles de confundir** (punto 22 de la auditoría de
   `v2.69`):
   - `auto-evidence-report.ts`: `classifyExecutionReality` + `execution` en `EvidenceView` +
     `source.subtitle` ("DATOS REALES DE LA CUENTA PAPER · DINERO VIRTUAL · NO ES DINERO REAL").
   - `auto-evidence-section.tsx`: bloque **`EXECUTION REALITY`** (`VIRTUAL — NO REAL MONEY`,
     `ops-auto-evidence-execution-reality`) + **`SOURCE`** reforzado.
   - Reglas duras: `null` ⇒ `NO MEDIDO`; un origen `desconocido` **nunca** se degrada a `paper_real`.
2. **Harness de validación** (nuevo, puro + CLI):
   - `bolsa_analytics/cognitive/auto_evidence_validation.py` — `EVIDENCE_VALIDATION_SCHEMA =
     "auto23_evidence_validation_v1"`; barrido `P(R>0)` vs N, estabilidad de régimen, diagnósticos de
     correlación `P3-2`. **Consume** la única matemática (`build_evidence_run_bundle`,
     `build_adaptive_uncertainty`, `build_strategy_correlation_report`); **no** reimplementa nada.
   - `apps/api-python/scripts/auto_evidence_validate.py` — bundle inmutable en
     `evidence_validations/<UTC>-<huella8>/`, `exit 2` **BLOQUEADO** sin escribir nada.
3. **Runbook** `protocolo-primer-run-paper-real-v2.70-2026-09-25.md` (1 estrategia ≥32 ciclos → 2ª
   estrategia → sweep/régimen), con la **regla dura** de no bajar umbrales.

## 2. Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| Frontend `vitest` | **1339 passed** (232 ficheros, sin flag de timeout) |
| `typecheck` / `build` / `contract:check` | OK |
| `lint` | **0 errores** (23 warnings preexistentes) |
| Python `application` + `analytics` | **3203 passed / 5 skipped** |
| CLI `test_auto_v70_auto23_evidence_validation.py` | **6 passed** (sonda PG opt-in deselected) |
| `ruff` / `import-linter` / `mypy` | **All checks passed** / **4 kept, 0 broken** / **0 issues (501 files)** |
| Matriz de mutaciones | **192/192**, byte a byte |

## 3. Qué NO se ha tocado

- **Freeze**: `auto18-v1` / `auto15-v1`, umbrales de rotación, `portfolio_optimizer.py`,
  `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
  `auto_adaptive_journal.py`.
- **Aritmética de evidencia**: `build_calibration_report`, `build_strategy_correlation_report`,
  `build_current_regime_evidence`, `build_evidence_run_bundle` — **consumidos**, no modificados.
- **Sin migración**: Alembic head `046_fill_reference_mid`.
- **El reparto no se mueve**: `ALLOCATION = none`.

## 4. Deuda y límite

- **Bloqueante central: material.** El RUN y el harness están listos, pero **no hay material PAPER
  real**. La corrida real es **paso operativo del propietario**.
- **P3-2 / P3-3 abiertas** (necesitan el primer dataset real); el harness ya publica los diagnósticos.
- **Fuera de alcance por decisión**: allocation dinámica, `current-regime gating` operativo, LIVE, SHORT.

## 5. Siguiente paso

1. Ejecutar el runbook sobre material real (1 estrategia → `auto_evidence_run.py` → 2ª estrategia →
   `auto_evidence_validate.py`).
2. Cerrar P3-2/P3-3 con los diagnósticos.
3. Sólo después, plantear si la evidencia **mueve** algo (fase de producto con contrato propio).
