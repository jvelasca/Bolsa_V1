# Traspaso de relevo — post `v2.71-beta` (`AUTO-19A`+`AUTO-19B`)

> **AsOf:** 2026-09-26 · **Tag vigente:** `v2.71-beta` (`1.96.0-beta`) · **Base:** `v2.70-beta`
> **Para:** el auditor externo y el siguiente agente.

## 1. Qué se ha hecho

Fase de **corrección del instrumento** (no de estadística nueva), en cuatro frentes:

1. **Separar las dos probabilidades** que el nombre `P(R>0)` mezclaba:
   - `edgePositiveProbability` = `P(edge>0)` = fracción de **medias bootstrap** `> 0`.
   - `cyclePositiveShare` = `P(R>0)` = fracción de **ciclos medidos** con `R>0` (estricto).
   - Sellos: `bootstrap_episodes_v3`, `walk_forward_calibration_v4`, `current_regime_evidence_v2`,
     `auto23_evidence_validation_v2`, `auto23_sample_size_sweep_v2`, `auto23_regime_stability_v2`,
     método `chronological_prefix_sweep_v2`.
2. **Calibración homogénea**: `_question_probability_positive` compara `P(ciclo>0)` IS vs frecuencia
   positiva OOS; **ignora** `P(edge>0)`.
3. **Cierre de P3 de `AUTO-19A`/`AUTO-19B`**:
   - H2: cobertura **no medida** (`None`) sale de la comparación y se declara en `cellsUnmeasured`.
   - H3: `build_replay_report` publica el nivel **clampeado** (el que usó el bootstrap).
   - H4: la celda de replay usa **`dominantRegimeCoverage`** (fin de la colisión con el `float`
     `regimeCoverage` de `StrategyConfidence`).
4. **Mutaciones** `M182`–`M184`/`M187` actualizadas y **`M193`–`M197`** nuevas; matriz **197** (192 + 5 nuevas; el plan citaba `198` por un desliz aritmético).

## 2. Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| Frontend `vitest` | **ver §Compuertas del `CHANGELOG`** |
| `typecheck` / `build` / `contract:check` | **ver §Compuertas del `CHANGELOG`** |
| `lint` | **ver §Compuertas del `CHANGELOG`** |
| Python `packages/py/analytics` | **1262 passed** |
| Python `packages/py/application` | **1945 passed** (5 errores de fixture PG por DSN fast-fail, ajenos) |
| Suites `api-python` afectadas | `test_auto_v60_...`, `test_auto_v64_...`, `test_auto_v70_...` verdes |
| `ruff` / `import-linter` / `mypy` | **ver §Compuertas del `CHANGELOG`** |
| Matriz de mutaciones | **197/197**, byte a byte |

## 3. Estado del sello

- **Tag:** `v2.71-beta` (`1.96.0-beta`) — paquete de fase.
- **Evidencia de la matriz:** `evidencia-matriz-mutaciones-v2.71-197-2026-09-26.txt` — `197/197`
  medidas, `197/197` rojas, restauración **byte a byte**, árbol intacto.
- **Base del diff:** `v2.70-beta`.
- **`v2.70-beta` permanece intacta** (tag inmutable).

## 4. Qué NO se ha tocado

- **Freeze**: `auto18-v1` / `auto15-v1`, umbrales de rotación, `portfolio_optimizer.py`,
  `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
  `auto_adaptive_journal.py`.
- **La aritmética**: bootstrap, WFE, correlación, régimen y banda de edge **congelados**; solo cambió
  **la lectura** de una probabilidad.
- **`evidence_runs`/`evidence_validations`** y el **runbook** del primer RUN.
- **Sin migración**: Alembic head `046_fill_reference_mid`.
- **El reparto no se mueve**: `ALLOCATION = none`.

## 5. Deuda y límite

- **Bloqueante central: material.** El RUN y el harness están listos, pero **no hay material PAPER
  real**. La corrida real es **paso operativo del propietario** y el **hito siguiente**.
- **P3-2 / P3-3 abiertas** (necesitan el primer dataset real); H1/H2/H3/H4 **cerradas** en `v2.71`.
- **Fuera de alcance por decisión**: allocation dinámica, `current-regime gating` operativo, LIVE, SHORT.

## 6. Siguiente paso

1. **PRIMER RUN PAPER REAL** (paso del propietario, ver
   [`protocolo-primer-run-paper-real-v2.70-2026-09-25.md`](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md)):
   `auto_evidence_run.py` con **≥32 ciclos medibles** de una estrategia, añadir la 2ª y validar
   `correlation(A,B)`, sweep `P(R>0)` vs N y estabilidad de régimen. **No se bajan** umbrales.
2. Cerrar **P3-2** y **P3-3** con el primer dataset real.
