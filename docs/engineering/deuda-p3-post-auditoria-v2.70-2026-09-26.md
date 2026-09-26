# Deuda P3 post-auditoría `v2.70` (y cierre en `v2.71`) — 2026-09-26

> **AsOf:** 2026-09-26 · **Origen:** auditoría profunda de `auto_adaptive_uncertainty.py` y
> `auto_adaptive_replay.py` (AUDITORIA 2 sobre `AUTO-23`).
> **Naturaleza:** hallazgos **P2/P3** sobre **la lectura** de la incertidumbre; ninguno publica un
> número falso nuevo, pero H1 **sí** mezcla dos funcionales en el mismo nombre.
> **Estado:** **H1 y H2/H3/H4 cerrados en `v2.71`**; **P3-4** (hallazgo de la auditoría de `v2.71`,
> preexistente y read-only) **abierta**; P3-2 y P3-3 siguen **abiertas** (requieren el primer dataset
> PAPER real). **El bloqueante central es MATERIAL, no código.**

## H1 — `P(R>0)` mezclaba dos funcionales (P2/P3) — 🟢 CERRADO en `v2.71`

**Observación.** En `auto_adaptive_uncertainty.py`, `probability_positive` era la fracción de
**medias bootstrap** `> 0` (≈ `P(edge>0)`). En `auto_adaptive_replay.py`, `oos_positive_share` era la
fracción de **ciclos** `> 0` (≈ `P(R>0)`). `_question_probability_positive`
(`auto_adaptive_calibration.py`) las comparaba **como si fueran lo mismo**: la "calibración" medía una
diferencia de **definición**, no de acierto.

**Cierre.** Se publican **ambas** con nombres distintos:

- `P(ciclo>0)` = `cyclePositiveShare` = fracción de ciclos medidos con `R>0` (estricto).
- `P(edge>0)` = `edgePositiveProbability` = fracción de medias bootstrap `> 0`.
- La calibración compara `P(ciclo>0)` **IS** vs frecuencia positiva **OOS** (magnitudes homogéneas).
- Sellos nuevos: `bootstrap_episodes_v3`, `walk_forward_calibration_v4`, `current_regime_evidence_v2`,
  `auto23_evidence_validation_v2`, `auto23_sample_size_sweep_v2`, `auto23_regime_stability_v2`.

**Criterio de reversión.** Si un consumidor necesitara `P(edge>0)` para calibrar, tendría que
justificar por qué mide la misma magnitud que el OOS (no lo es).

## H2 — La ausencia de medición contaba como no cubierta (P3) — 🟢 CERRADO en `v2.71`

**Observación.** `_question_coverage` metía `dominant_regime_coverage is None` (no medido) en el grupo
"no cubierta", convirtiendo **ausencia de evidencia** en **evidencia negativa**.

**Cierre.** Esas celdas salen de la comparación y se declaran en **`cellsUnmeasured`**; `sample` y
veredicto solo miran bandas **medidas**. Protegido por **M195**.

## H3 — `build_replay_report` publicaba un nivel sin clampar (P3) — 🟢 CERRADO en `v2.71`

**Observación.** El informe publicaba `interval_level` **crudo** (p. ej. `0.0`) aunque el bootstrap usó
el nivel **clampeado** `0.5`; su hermano `CalibrationReport` sí publicaba el clampeado.

**Cierre.** `build_replay_report` calcula `resolved_level = min(max(level, MIN), MAX)` y publica **ese**
nivel. Protegido por **M196**.

## H4 — Colisión de la clave `regimeCoverage` (P3) — 🟢 CERRADO en `v2.71`

**Observación.** `regimeCoverage` era un **`float`** en `StrategyConfidence.as_dict()` y una **banda**
(`"HIGH"`/`None`) en `ReplayCell.as_dict()`: mismo nombre, dos formas.

**Cierre.** La celda de replay usa **`dominantRegimeCoverage`**. Protegido por **M197** y por el
contrato `test_the_regime_coverage_key_is_a_float_in_confidence_and_a_band_in_replay`.

## P3-1 — Flake ajeno del test runner (`core-r-scheduler.test.ts`)

**Estado: 🟢 CERRADA en `v2.69`.** Presupuesto **por fichero**
(`vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 })`); la suite completa queda verde **sin**
flag global.

## P3-2 — Validación empírica de la correlación por cubos temporales

**Estado: 🔴 ABIERTA** (requiere el primer dataset PAPER real). La herramienta está lista en
`auto_evidence_validate.py` (`sharedSingleCycleShare`, ciclos/cubos activos por estrategia). Criterio
de cierre: comparar la correlación por cubos contra un oráculo por pares de ciclos emparejados y
declarar, **antes** de tocar la métrica, si la frecuencia/exposición sesga el número.

## P3-3 — `P(R>0)` frente al tamaño muestral

**Estado: 🔴 ABIERTA** (requiere el primer dataset PAPER real). Regla que se mantiene: `P(R>0)` es
**evidencia descriptiva**; nunca se traduce en `confidence` ni en sizing. El barrido publica
`P(R>0)`, `P(R>0)` OOS, WFE y `effective_n` sobre el prefijo cronológico para `N ∈ {16,32,64,128}`.
**Nota `v2.71`:** el barrido ya publica la `P(R>0)` por **ciclos** (antes publicaba una mezcla por la
ambigüedad de H1).

## P3-4 — `build_current_regime_evidence` publica el `level` sin clampar (P3) — 🔴 ABIERTA

**Origen:** auditoría externa de `v2.71-beta` (2026-09-26). **Preexistente** (idéntico en `v2.70-beta`;
el diff `v2.70 → v2.71` **no** lo toca) y **ajena a las 15 tesis** de la fase.

**Observación.** `build_current_regime_evidence`
(`auto_adaptive_regime_evidence.py:177`) hace `resolved_level = level` **sin clampar** y lo emite en
`CurrentRegimeEvidence.level`, mientras el bootstrap aguas abajo (`build_adaptive_uncertainty`) **sí**
clampa (`MIN_INTERVAL_LEVEL`/`MAX_INTERVAL_LEVEL`). Medido con sonda: `level=0.0` se **publica** `0.0`
pero la incertidumbre **usa** `interval.level=0.5`. Es la **misma clase** que **H3**, que la fase cerró
**solo** en `build_replay_report`.

**Impacto.** **P3**: evidencia **read-only** (`AUTO-21`/`AUTO-23` no mueven reparto, sizing, plan ni
reserva); solo observable con un `level` **no default**.

**Criterio de cierre.** Clampar `resolved_level` en `build_current_regime_evidence` y publicar el nivel
**efectivo**, subir el sello `current_regime_evidence_v2` → **`v3`**, y añadir la mutación + test
correspondientes. **No se aborda en `v2.71`** (fase cerrada y elevada).

## Bloqueante central — material PAPER real

**No es deuda P3: es el límite declarado.** `v2.71` **corrige el instrumento**; el **primer RUN
PAPER real** es el **paso operativo del propietario** y el **hito siguiente**. **No se bajan**
`min cycles` / `min R` / `folds` para forzarlo. No se toca `evidence_runs`/`evidence_validations` ni
el runbook.

## Fuera de alcance de esta deuda

- **Allocation dinámica** y **LIVE AUTO**: `❌`, no abordados.
- **Current-regime gating operativo**: fase posterior declarada.
