# Deuda P3 post-auditoría `v2.70` (y cierre en `v2.71`) — 2026-09-26

> **AsOf:** 2026-09-26 · **Origen:** auditoría profunda de `auto_adaptive_uncertainty.py` y
> `auto_adaptive_replay.py` (AUDITORIA 2 sobre `AUTO-23`).
> **Naturaleza:** hallazgos **P2/P3** sobre **la lectura** de la incertidumbre; ninguno publica un
> número falso nuevo, pero H1 **sí** mezcla dos funcionales en el mismo nombre.
> **Estado:** **H1 y H2/H3/H4 cerrados en `v2.71`**; **P3-4** (hallazgo de la auditoría de `v2.71`,
> preexistente y read-only) **cerrada en `v2.72`**; **P3-5** (`reserved_risk` sobrecargado: libro vivo
> vs evidencia histórica) **abierta y declarada** (2026-09-26, tras el E2E PostgreSQL de `v2.74`);
> P3-2 y P3-3 siguen **abiertas** (requieren el primer dataset PAPER real). **El bloqueante central es
> MATERIAL, no código** (y desde `v2.74` es de **muestra**, no de forma; `v2.75` cruza la **cantidad**
> —42 ciclos medibles ⇒ `EVIDENCE_READY`— pero **no** la **diversidad**: un solo bucket de calendario y
> un solo episodio de régimen). **Deuda de proceso declarada:**
> `v2.73-beta` quedó **sin auditoría externa** (ver más abajo).

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

**Actualización `v2.75` (2026-09-26):** el instrumento queda **ejercitado de punta a punta** con el
material acumulado (`activeBuckets=1`, `pairs=[]`, sin inventar celdas; `minBuckets=4` respetado), pero
**no se cierra**: la muestra del productor determinista cae en **un solo bucket** (timestamps de reloj
real del mismo día). Cerrarla exige material PAPER REAL de mercado en **≥4 cubos**.

## P3-3 — `P(R>0)` frente al tamaño muestral

**Estado: 🔴 ABIERTA** (requiere el primer dataset PAPER real). Regla que se mantiene: `P(R>0)` es
**evidencia descriptiva**; nunca se traduce en `confidence` ni en sizing. El barrido publica
`P(R>0)`, `P(R>0)` OOS, WFE y `effective_n` sobre el prefijo cronológico para `N ∈ {16,32,64,128}`.

**Actualización `v2.75` (2026-09-26):** el barrido queda **ejercitado** (`16`/`32` medidos, `64`
`insufficient_measured_cycles`), pero **no se cierra**: con `R` casi constante y **un solo episodio**
(`episodes=1`), `P(R>0)=0.0000` con `Effective-N=1` es degenerado, no un edge. Cerrarla exige material
de mercado con diversidad real (`Effective-N > 1`).
**Nota `v2.71`:** el barrido ya publica la `P(R>0)` por **ciclos** (antes publicaba una mezcla por la
ambigüedad de H1).

## P3-4 — `build_current_regime_evidence` publica el `level` sin clampar (P3) — 🟢 CERRADA en `v2.72`

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
correspondientes.

**Cierre (`v2.72`).** `resolved_level = min(max(float(level), ADAPTIVE_INTERVAL_LEVEL_MIN),
ADAPTIVE_INTERVAL_LEVEL_MAX)` **antes** de publicarlo, igual que `build_replay_report` (`H3`, `v2.71`) y
`CalibrationReport`; sello subido a **`current_regime_evidence_v3`**. Protegido por **`M198`** y por
`test_the_interval_level_is_clamped_and_published` (que además comprueba que la celda publicada es la
**misma** que con el nivel clampeado explícito: no hay segunda aritmética) y
`test_the_clamped_level_travels_even_without_cycles`. Con el `level` default (`0.90`) el payload es
**idéntico salvo el sello `method`** (`current_regime_evidence_v2` → `v3`, que sube por diseño).

**Confirmado por la auditoría externa de `v2.72-beta`** (2026-09-26): `APROBADO CON OBSERVACIONES`,
**0 bloqueantes**, 10/10 tesis PASS; `M198` muerde los dos tests del clamp y restaura **byte a byte**;
`P3-4` **CERRADA**. La única observación (H-1, LOW documental) fue precisamente el «payload
byte-idéntico» de este documento, ya corregido. **Doble pasada:** la segunda auditoría, hecha **desde un
clon fresco de GitHub** (tag `82b231d3` → `0f8cc888`), reproduce el mismo veredicto y **re-ejecuta el RUN
BLOQUEADO** contra PostgreSQL vivo con los mismos números.

**Nota INFO declarada (2026-09-26, no es deuda ni defecto).** En
`test_the_interval_level_is_clamped_and_published`, las aserciones de **identidad de celda**
(`evidence_for(v)` con `level` fuera de rango == con el nivel clampeado explícito) pasarían **también con
`M198`**, porque `build_adaptive_uncertainty` **clampa por su cuenta** aguas abajo; la **mordida** de
`M198` proviene de las aserciones del `level` **publicado**. El contrato **sí muerde** (2 rojos), pero la
propiedad «no hay segunda aritmética» la garantiza el clamp del bootstrap, **no** ese test. Se deja
anotado para no sobre-confiar en la cobertura de ese test; endurecerla requeriría un doble que **no**
clampe por su cuenta.

## P3-5 — `reserved_risk` sobrecargado: libro vivo vs evidencia histórica — 🟠 ABIERTA (2026-09-26)

**Origen.** Seguimiento del punto 12 de `v2.74`: ¿`AUTO-19` (`cycle_risk_from_reservations`) obtiene el
riesgo histórico de una evidencia **inmutable** del ciclo o del estado **mutable** del `ReservationLedger`?

**Observación.** Ninguna de las dos, exactamente. `cycle_risk_from_reservations` **no** lee el ledger vivo
(lee filas durables de `portfolio_reservations`, vivas y liberadas, y filtra `is_buy and reserved_risk > 0`),
pero **tampoco** existe una entidad `CycleEvidence`: lee la **misma** columna
`portfolio_reservations.reserved_risk`, cuya semántica depende del estado — vivo mientras `OPEN`; histórico
tras el cierre, porque `_release()` la sobrescribe con el riesgo comprometido en el alta
(`reserved_risk × quantity / remaining_qty`, `_committed_risk`). Es una **reconstrucción tardía en el
store**, no un snapshot inmutable de entrada.

**Riesgo.** Un lector que no conozca la convención puede leer "riesgo actual `0`" donde el productor quiso
decir "riesgo comprometido `X`". La reconstrucción es exacta para la liberación total intacta y para la
última liberación de una escalera (cubierto por `test_portfolio_reservation.py`), pero la garantía vive en
el store y no en el modelo.

**Criterio de cierre.** O una columna/entidad dedicada e inmutable (`reserved_risk_at_entry` / `CycleEvidence`)
o declarar la convención como contrato explícito del store. Requiere migración Alembic (hoy head
`046_fill_reference_mid`); **no** se aborda en `v2.74` (alcance acordado: solo E2E).

**Evidencia de que no bloquea `PRODUCER_READY` (2026-09-26).** El E2E PostgreSQL
`apps/api-python/tests/test_auto_v74_producer_pg_e2e.py` demuestra que la estructura del productor V2
sobrevive al COMMIT y el gate la reconstruye desde una conexión **nueva**: la fila durable de la reserva de
ENTRADA de un ciclo cerrado conserva `reserved_risk > 0` con `remaining_qty = 0`. La convención funciona;
lo que falta es modelarla explícitamente.

**Hallazgo declarado (no bloqueante).** En la misma corrida, el productor V2 deja VIVA una reserva de
SALIDA (`side='sell'`, `reserved_risk = 0`) de un intento de salida superado por otro, tras quedar la
posición plana. No puede ser denominador de R (solo una reserva de COMPRA con `reserved_risk > 0` lo es) y
no altera el veredicto, pero es una reserva viva después del cierre: queda declarada como observación del
productor, fuera del alcance de esta fase (`auto_simulation_worker.py` sigue congelado).

## Deuda de AUDITORÍA — `v2.73-beta` (`AUTO-MATERIAL-1`) sin pasada externa — 🟡 ABIERTA (de proceso)

**Estado: 🟡 ABIERTA, declarada (2026-09-26).** `v2.73-beta` (tag anotado objeto `fd891fcd` → commit
`a9166655`) quedó **sellada y con CI verde** (`Release tag CI` `36244779500`, 10 jobs + `certify`) pero
**sin auditoría externa**: la fase siguiente (`v2.74-beta`, `AUTO-MATERIAL-2`) se construyó encima y
**evolucionó su superficie** —el gate subió a **`paper_material_readiness_v2`** (dos niveles
`PRODUCER_READY`/`EVIDENCE_READY`, `--level`, tres poblaciones) y el CLI ganó la población `DATABASE
TOTAL`—, de modo que auditar `v2.73` aislado revisaría una forma **superada** del mismo gate.

**Decisión (2026-09-26).** Auditar **`v2.74-beta`** —que **incluye y supera** el gate— y dejar `v2.73`
como **deuda de auditoría declarada aquí**, no como olvido. Puntos de entrada: el
[arranque del auditor de `v2.74`](./arranque-auditor-v2-74-auto-material-2-paper-producer-2026-09-26.md)
(16 puntos) y, si se quisiera la forma v1 sellada, el
[de `v2.73`](./arranque-auditor-v2.73-auto-material-1-paper-material-readiness-2026-09-26.md) (13 puntos)
contra su tag **inmutable**.

**Criterio de cierre.** La pasada externa sobre `v2.74-beta` cubre el **linaje** del gate (el módulo
`paper_material_readiness.py` y su CLI en la forma vigente); esta deuda se cierra cuando esa pasada
declare el linaje **sostenido**. Si el auditor pide una pasada específica sobre la forma **v1** sellada
en `v2.73`, se corre contra el tag con su propio arranque (el diff `v2.73-beta → main` es **solo docs**
⇒ el código del tag es el auditado).

## Bloqueante central — material PAPER real

**No es deuda P3: es el límite declarado.** `v2.71` **corrige el instrumento**; el **primer RUN
PAPER real** es el **paso operativo del propietario** y el **hito siguiente**. **No se bajan**
`min cycles` / `min R` / `folds` para forzarlo. No se toca `evidence_runs`/`evidence_validations` ni
el runbook.

## Fuera de alcance de esta deuda

- **Allocation dinámica** y **LIVE AUTO**: `❌`, no abordados.
- **Current-regime gating operativo**: fase posterior declarada.
