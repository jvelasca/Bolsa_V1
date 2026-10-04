# Evidencia `v2.88.47-beta` — `AUTO · DÍA-D-3f`: **desambiguación `THESIS_EXIT` vs `STOP`** (por qué RUTA se invalidó la tesis), sin tocar motor

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.47-beta` · **Package:** `2.11.47-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.97 DIA-D AUTO THESIS EXIT` · **Δ motor = 0**.

**Schemas:** `dia-d-thesis-exit-v3` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`), `dia-d-multi-cycle-ledger-v5` (aditivo sobre `-v4`) y `dia-d-thesis-stop-sequences-v1` (`KIND = "DIA_D_AUTO_THESIS_STOP_SEQUENCES"`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.46`](../v2.88.46/README.md) (la condición: el nivel congelado ES el stop inicial) → [`v2.88.45`](../v2.88.45/README.md) (dónde viven los `38` `THESIS_EXIT`) → [`v2.88.44`](../v2.88.44/README.md) (de dónde nace la pérdida).

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-band/draw-00…draw-11/multi-cycles.json` — `12` ledgers `dia-d-multi-cycle-ledger-v5` (con la secuencia día a día por ciclo).
- `operability_runs/dia-d-auto/multi-band-detail-2021_2026.json` — el plegado `v2_94` con `--cycle-detail` (`45 205 B`).
- `operability_runs/dia-d-auto/thesis-exit-2021_2026.json` — el artefacto `dia-d-thesis-exit-v3` (`139 979 B`).
- `operability_runs/dia-d-auto/thesis-stop-sequences-2022_2025.json` — el volcado `--sequences` (`130 014 B`).

---

## 0. Qué añade este sello (y qué NO)

`v2.88.46` cerró *qué condición* disparó el `THESIS_EXIT` (el nivel congelado **ES** el stop inicial, `levelEqualsInitialStop 38/38`), pero dejó una pregunta falsable **sin responder**: si el nivel es el stop, **¿por qué el MISMO nivel produce `THESIS_EXIT` en unos ciclos y `STOP_EJECUTADO` en otros?** Este sello reconstruye la **secuencia temporal real** de los `38` ciclos y clasifica la **RUTA** de la invalidación —`ruta_mark` vs `ruta_mae` sobre el **MAE PERSISTIDO** (`mfeMae.maeR`)— sin inventarla, desde la costura inerte ya sellada (`v2_87.capture_cycle_detail`).

**NO** toca el motor, los umbrales, `TOP_N` ni la allocation. **NO** introduce contrafactuales. **NO** reconcilia la duplicidad semántica que sí **mide** (`structuralStopCandidate`): se declara, no se arregla.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1` contra el `current_stop` del día. Por eso el campo "existía orden STOP" **no aplica** a este motor y no se emite.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **La capa v5 es ADITIVA:** los `38` ciclos `THESIS_EXIT` y su `expectancyR` bruta `-0.7087` son idénticos a `v2.88.45`/`v2.88.46`. | Que el global difiera del sello anterior. | `global.realizedRGross.expectancyR.mean = -0.7087` (`total -2.3462`), `cycles = 38`, `coverage.cyclesTotal = 38`, `hitRate = 0.0833`. |
| **2** | **El nivel de invalidación SIGUE siendo el stop inicial** (`levelEqualsInitialStop 38/38`), y la ruta se mide sobre el **MAE persistido**. | Que `levelEqualsInitialStop` no sea `38/38`. | `global.invalidation.levelEqualsInitialStop = {count: 38, measured: 38, share: 1.0}`; `invalidationLevelR = -1.0000`. |
| **3** | **Ruta dominante = MAE PERSISTIDO:** el `mfeMae.maeR` capturado cruzó el nivel en los `38` ciclos (`persistedMaeR` mediana `-1.1847 ≤ -1.0`). | Que el MAE persistido NO cruce el nivel en la mayoría. | `global.disambiguation.persistedMaeR = {mean: -1.2282, median: -1.1847, measured: 38}`; `firstTouchMeasured = 38`. |
| **4** | **`ruta_mark` (mark cruza el nivel y el MAE NO) ≈ 0**, porque la monotonía del ratchet lo prohíbe. | Que aparezca `ruta_mark` con frecuencia. | `route = {ruta_ambas: 34, ruta_mae: 4}`; `ruta_mark = 0`, `sin_geometria = 0`. |
| **5** | **El MAE persistido cruza el nivel en `38/38` frente al `35/38` del MAE D1 reconstruido**: la diferencia (`3`) es el artefacto de reconstrucción declarado. | Que `maeReachedLevel` (D1) y la ruta persistida coincidan. | `routeByMaeReached = {ruta_ambas: {reached: 33, notReached: 1}, ruta_mae: {reached: 2, notReached: 2}}` ⇒ D1 alcanzó `35/38`; persistido `38/38`. |
| **6** | **`structuralStopCandidate` DEBÍA ser `False`** en un `THESIS_EXIT` (la precedencia del `STRUCTURAL_STOP` lo impediría). | Que sea `True`. | **FALSADA:** `structuralStopCandidate = {count: 38, measured: 38, share: 1.0}` — en **todos** los `THESIS_EXIT` algún mark del día tocó el stop vigente; y en **`31/38`** el toque del nivel (`markFirstTouchDay`) es en un día **ESTRICTAMENTE ANTERIOR** al cierre (sólo `1/38` el mismo día, `4/38` sin toque por mark). **Es el hallazgo del sello** (duplicidad semántica declarada, §2.5). |
| **7** | **El stop casi nunca se apretó por encima del nivel:** la mayoría son `sin_cambio`. | Que `sin_cambio` no sea mayoritario. | `byStopPath = {sin_cambio: 31, breakeven: 6, ratchet: 1}`; `stopChanged = 7/38`, `breakevenReached = 6/38`, `stopAboveLevel = 6/38`. |
| **8** | **El primer toque del nivel por el MAE persistido ocurre, en su mayoría, el mismo día del cierre** (el MAE adverse se materializa y la posición cierra). | Que `daysToFirstTouch` sea grande en la mayoría. | `touchBeforeExit = 13/38` (`0.3421`); `firstTouchEqExit = 25/38`; `daysToFirstTouch` media `5.63` / mediana `0.0` (en el sub-cubo `breakeven` la mediana sube a `19.5`: recuperación larga). |
| **9** | **Un hueco es `None`, nunca `0`:** sin la secuencia capturada la capa v5 queda `sin_geometria` y los booleanos `None`. | Que aparezca un `0.0` donde falta el dato. | Regla dura del código + test `test_ledger_v5_without_sequence_declares_the_gap_never_zero`; `--sequences` declara `seqNone = 0` (ningún ciclo sin secuencia en esta corrida). |
| **10** | **Determinismo:** dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**; `v2_97 --sequences` ídem. | Que dos corridas difieran. | `sha256 thesis-exit-v3 = EC4D4CC92513028F60889ED33F14C496CF6A2DF9F3DFD76BD98AD546A5A9A014` (`139 979 B`); `sha256 sequences = DF369FC524F068BF2DA375F17896ABAFD6A50FC55D419DDC1D8DDFD956CDE71C` (`130 014 B`). |
| **11** | **`Δ motor = 0`:** ningún fichero de motor cambia; la costura `capture_cycle_detail` sigue **inerte por defecto**. | Que el árbol del motor cambie o que la costura altere el replay con `capture_cycle_detail=False`. | `git status` del motor vacío; la costura sólo añade **LECTURA** del estado ya producido y va tras `if capture_cycle_detail:`; `v2_95`/`v2_96` siguen leyendo `realizedR/year/regime`. |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` observaciones `THESIS_EXIT` (pooled sobre sorteos) · **`32` identidades de ciclo únicas** (símbolo+entrada+salida) · `38` con fricción `COMPLETE` · `detailCaptured = true` · `11/12` sorteos con celda · **una** estrategia (`v283-window-a`) y **una** dirección (`long`) · `9` símbolos distintos.

### 2.1 Global (idéntico a `v2.88.45`/`v2.88.46`: la capa v5 es aditiva)

| Métrica | Valor |
| --- | --- |
| R bruto total (por sorteo, media) | `-2.3462` |
| Expectancy bruta (entre sorteos) | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| HitRate | `0.0833` |
| R neto total (por sorteo, media) | `-2.5012` |
| Expectancy neta | `-0.7525` |
| Concentración | `9` símbolos · top símbolo `26,3 %` · top semana `2025-W12` `21,1 %` |

### 2.2 Desambiguación `THESIS_EXIT` vs `STOP` (nuevo, capa v5)

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `route` | `{ruta_ambas: 34, ruta_mae: 4}` | el mark **y** el MAE persistido cruzan el nivel (`ambas`) o sólo el MAE (`mae`); **`ruta_mark = 0`** |
| `routeByMaeReached` | `ambas {reached 33, notReached 1}` · `mae {reached 2, notReached 2}` | el MAE **D1 reconstruido** alcanzó el nivel en `35/38`; el **persistido** en `38/38` |
| `persistedMaeR` media / mediana | `-1.2282` / `-1.1847` | el peor adverso **persistido** vive por debajo de `-1R` (el nivel) en la mayoría |
| `minMarkR` media / mediana | `-1.1823` / `-1.1530` | el mark del día también baja del nivel en la mayoría (⇒ `ruta_ambas`) |
| `persistedMaeAtExitR` media / mediana | `-1.1367` / `-1.1616` | el MAE al cierre sigue por debajo del nivel |
| `touchBeforeExit` | `13/38` (`0.3421`) | en `13` ciclos el primer toque del MAE es **anterior** al cierre declarado |
| `daysToFirstTouch` media / mediana | `5.63` / `0.0` | la mitad de los ciclos materializa el toque **el día del cierre** |
| `structuralStopCandidate` | **`38/38` (`share 1.0`)** | **TODOS** los `THESIS_EXIT` tienen un mark que tocó el stop vigente ⇒ **duplicidad semántica declarada** |
| `stopChanged` | `7/38` (`0.1842`) | el stop se movió (ratchet/break-even) en una minoría |
| `breakevenReached` | `6/38` (`0.1579`) | el stop llegó al menos a la entrada real |
| `stopAboveLevel` | `6/38` (`0.1579`) | el stop vigente quedó **por encima** del nivel congelado en 6 ciclos |

### 2.3 Ejes `byRoute` y `byStopPath` (nuevos)

| Eje | Cubo | Sorteos | Ciclos | Expectancy bruta | Ruta / stop |
| --- | --- | --- | --- | --- | --- |
| `route` | `ruta_ambas` | `11/12` | `34` | `-0.8311` | `stopChanged 3/34`; `structuralStopCandidate 34/34` |
| `route` | `ruta_mae` | `2/12` | `4` | `+0.0282` | `stopChanged 4/4`; `touchBeforeExit 2/4`; `daysToFirstTouch` mediana `18` |
| `stopPath` | `sin_cambio` | `11/12` | `31` | `-0.9073` | `route = ambas 31/31`; `stopAboveLevel 0` |
| `stopPath` | `breakeven` | `4/12` | `6` | `+0.1160` | `route = ambas 3 + mae 3`; `touchBeforeExit 5/6`; `daysToFirstTouch` mediana `19.5` |
| `stopPath` | `ratchet` | `1/12` | `1` | `-0.9348` | `route = mae`; `stopAboveLevel 1/1` |

Todos los cubos siguen `fragile` (`few_cycles_per_draw`; `ratchet` y `ruta_mae` además `insufficient_draws`). **Ninguna celda se cita como fuerte.**

### 2.4 Volcado de secuencias (`--sequences`, `dia-d-thesis-stop-sequences-v1`)

| Campo | Valor |
| --- | --- |
| `draws` / `thesisExitObservations` / `uniqueCycleIdentities` | `12` / `38` / `32` |
| `cyclesPerDraw` | `{0:4, 1:3, 2:4, 3:4, 4:1, 5:3, 6:4, 7:3, 8:4, 9:0, 10:5, 11:3}` (suma `38`) |
| `sequence` ausente | `0` (todos los ciclos traen su secuencia) |

Cada registro trae la secuencia `{day, mark, currentStop, maeR, mfeR}` más la desambiguación por ciclo (`thesisExitRoute`, `levelR`, `markAtExitR`, `minMarkR`, `persistedMaeR`, `persistedMaeAtExitR`, `firstTouchDay`, `markFirstTouchDay`, `daysToFirstTouch`, `touchBeforeExit`, `stopChanged`, `breakevenReached`, `stopAboveLevel`, `structuralStopCandidate`).

### 2.5 Lectura honesta

- **La ruta de la invalidación NO es el mark, sino el MAE persistido.** `ruta_mark` = `0`: en ningún ciclo el mark cruzó el nivel sin que también lo cruzara el MAE persistido. La clasificación se reparte entre `ruta_ambas` (`34`) y `ruta_mae` (`4`). El **MAE persistido** cruza el nivel en `38/38` frente al `35/38` del **MAE D1 reconstruido** que usaba `v2.88.46` (`routeByMaeReached`): los `3` de diferencia son el **artefacto de reconstrucción** ya declarado en el sello anterior.
- **HALLAZGO — la predicción `structuralStopCandidate = False` se FALSÓ.** El sello esperaba que ningún mark tocara el stop vigente en un `THESIS_EXIT` (la precedencia del `STRUCTURAL_STOP` sobre `THESIS_INVALIDATION` debería impedirlo). Se midió **`38/38` `True`**: en **todos** los `THESIS_EXIT` algún mark del día tocó el stop vigente, pese a que el motor cerró con el motivo de invalidación de tesis. Más fuerte aún: **en `31/38` el mark alcanzó el nivel del stop en un día ESTRICTAMENTE ANTERIOR al cierre** (`markFirstTouchDay < exitDay`; `1/38` el mismo día; `4/38` sin toque por mark, todos `ruta_mae` con el stop ratcheado por encima del nivel), y **`30/31` de los `sin_cambio`** están en ese caso. La predicción **falló**, y el fallo es el resultado: **la duplicidad semántica entre "nivel de invalidación" y "stop inicial" es TOTAL**, y la posición **sobrevivió** a un toque previo del stop para cerrar después por invalidación de tesis. Se **DECLARA**, no se reconcilia aquí.
- **El stop no se apretó por encima del nivel en la mayoría.** `byStopPath` = `{sin_cambio: 31, breakeven: 6, ratchet: 1}`: en `31/38` el stop vigente al cierre seguía **en el nivel** (`stopAboveLevel = 0` en ese cubo). El ratchet sólo aparece en `7` ciclos y se concentra en `ruta_mae` (`4/4`) y `breakeven` (`6/6`).
- **El toque adverso (MAE persistido) es, en su mayoría, del propio día del cierre; el toque del STOP por el MARK es, en su mayoría, ANTERIOR.** `25/38` ciclos con `daysToFirstTouch = 0` (el `maeR` persiste el `mark` del cierre); sólo `13/38` (`touchBeforeExit`) traen un toque **anterior** al cierre por esa vía. En cambio, `markFirstTouchDay < exitDay` en **`31/38`**: el mark del día alcanzó el nivel/stop **antes** del cierre. Ambas series son observables distintos (el `maeR` de un día `D` se registra en la captura de `D+1`, de ahí el desfase de un día): el STOP fue tocado por el mark sobre todo **antes** del cierre, mientras el MAE persistido se materializa el día del cierre. En el sub-cubo `breakeven`, la mediana de días hasta el primer toque sube a `19.5`: recuperación larga tras el break-even.
- **El mismo nivel, distinta ejecución.** La evidencia separa lo que `v2.88.46` no podía: el nivel **ES** el stop (`levelEqualsInitialStop 38/38`) **y** el nivel **fue tocado** en `38/38` (`structuralStopCandidate 38/38`). La diferencia entre `THESIS_EXIT` y `STOP_EJECUTADO` **no vive en el nivel** (es el mismo) sino en la **ruta de evaluación / ejecución**. El cierre por tesis es estructural y **coexiste** con el stop tocado.

### 2.6 Límite del hallazgo 2.5 (declarado, NO cerrado)

La secuencia `D1` captura el **estado al inicio del tick** (`mark` = apertura del día, `currentStop` = stop tras el ratchet previo). Con esas dos series, `structuralStopCandidate = True` dice que **algún mark del día alcanzó el stop**, pero **no** distingue *"el stop se evaluó y no ejecutó"* de *"el stop no se evaluó ese tick"*: el motor ejecuta el stop **dentro del tick** (decider `D1`), y una orden de stop disparada puede **no materializarse** aguas abajo (veto/ausencia de fill) sin que la costura `D1` lo vea. Reconciliar esa cadena exigiría leer el journal **intra-tick** por evento (`managementRows` viaja ya en `cycleDetail`, pero sin `cycle_id` propio ⇒ no se une a un ciclo sin una clave fiable; **deuda declarada**). El hallazgo es **"nivel tocado, no ejecutado"** medido desde `D1`; **la causa exacta de la no-ejecución NO se afirma aquí.**

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` DÍA-D (`test_dia_d_*.py` + `test_dia_d_bump_guard.py`) | **155 passed** (`v2.88.46` selló `144`) |
| `test_dia_d_multi_sampling.py` (capa v5) | **26 passed** (ruta mae/mark/ambas, `touchBeforeExit`, `structuralStopCandidate`, ratchet/break-even, hueco sin secuencia, v5) |
| `test_dia_d_thesis_exit.py` (bloque `disambiguation` + ejes) | **21 passed** (plegado de ruta, cruce `route × maeReached`, ejes `byRoute`/`byStopPath`, hueco declarado, determinismo) |
| `test_dia_d_bump_guard.py` | **1 passed** (`meta.bump` alineado a `2.11.47-beta` en `v2_89…v2_97`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros, `3 609` dependencias) |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| `contract:check` (`@bolsa/web`) | OK (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| Determinismo `v2_97` / `v2_97 --sequences` | byte a byte idéntico (`sha256 EC4D4CC9…` / `DF369FC5…`) |
| `Δ motor = 0` | `git status` sin ficheros de motor; la costura sólo **lee** estado ya producido y su `default` sigue `False` |
| `replay-repro` | **NO re-ejecutado localmente** (requiere re-sembrar la BD desde el fixture congelado; no se hizo para no tocar el entorno). **Certificado en CI:** `Release tag CI` run [`37215515993`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37215515993) `attempt 2` `REPRODUCIDO` `1E3ADAC2…` (`3 340 728 B` LF), **idéntico** a `v2.88.46.1` ⇒ el artefacto congelado no se movió. El cambio del seam es **inerte por defecto** (`if capture_cycle_detail:`). |

---

## 4. Límites declarados (NO se cierran aquí)

- **`structuralStopCandidate 38/38` se DECLARA y NO se reconcilia:** la causa exacta de que el stop tocado no se ejecute no se afirma (§2.6); `managementRows` se captura pero no se une a un `cycle_id` sin clave fiable (deuda).
- **El nivel congelado SIGUE siendo hoy el stop inicial** (deuda de `v2.88.45`/`v2.88.46`): la capa v5 **confirma** la duplicidad pero no introduce un nivel de tesis distinto.
- **La capa v5 es OPT-IN:** exige la costura `--cycle-detail` con la secuencia; sin ella `thesisExitRoute = sin_geometria` y los booleanos `None` (nunca `0`).
- **`firstTouchDay`/`markFirstTouchDay` son fechas de OBSERVACIÓN `D1`:** no son el instante intrabar del toque; el `mark` es la **apertura** del día.
- **`AUTO` no deja orden STOP en reposo:** el stop lo ejecuta el decider `D1`; "existía orden STOP" **no aplica**.
- **Unidad = ciclo por sorteo:** `38` observaciones pooled vs `32` identidades únicas; no se suman como operaciones financieras independientes.
- **`n` pequeño:** `38` observaciones en `11/12` sorteos ⇒ **todos** los cubos `fragile`; ninguna celda se cita como fuerte.
- **`stopBasisMismatchR` sigue `P3`** (`4/38`, media `0.1699`): discrepancia medida, no reconciliada (arreglarla tocaría el replay).
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle v5 (secuencia día a día por ciclo).
#    OJO: borrar antes los draw-XX/multi-cycles.json v4 (o correr sin --reuse):
#    v2_94._DETAIL_LEDGER_SCHEMA exige v5 y si no, re-corre; un ledger v4 con el
#    MISMO string no debe reutilizarse con la semántica anterior.
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/multi-band-detail-2021_2026.json

# 2) Plegar los 38 THESIS_EXIT al artefacto v3 (bloque disambiguation + ejes byRoute/byStopPath)
#    y volcar la secuencia por ciclo (--sequences → thesis-stop-sequences-YYYY_YYYY.json)
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/thesis-exit-2021_2026.json \
  --sequences

# 3) Dos corridas deben dar el mismo sha256 (determinismo):
#    EC4D4CC9… (thesis-exit-v3) / DF369FC5… (sequences)
```

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.47/README.md`.
- **Modificados:** `v2_87_replay_oos_durable_cycle.py` (costura inerte: `cycleDetail.cycleTimeline` + `cycleDetail.managementRows`), `dia_d_multi_sampling.py` (ledger `-v5`: `thesisExitRoute`/`levelR`/`markAtExitR`/`minMarkR`/`persistedMaeR`/`persistedMaeAtExitR`/`firstTouchDay`/`markFirstTouchDay`/`daysToFirstTouch`/`touchBeforeExit`/`stopChanged`/`breakevenReached`/`stopAboveLevel`/`structuralStopCandidate`/`sequence`), `dia_d_thesis_exit.py` (`dia-d-thesis-exit-v3`: bloque `global.disambiguation` + ejes `byRoute`/`byStopPath` + límites), `v2_93_dia_d_multi.py` (acumula `cycleTimeline`), `v2_94_dia_d_multi_band.py` (`_DETAIL_LEDGER_SCHEMA` exige v5), `v2_97_dia_d_thesis_exit.py` (`--sequences`/`--sequences-out` + impresión), `v2_89`…`v2_97` (`meta.bump`), `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `package.json` (`2.11.47-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado (la costura `capture_cycle_detail` sólo lee estado ya producido y su default sigue `False`).
- **Tag:** `v2.88.47-beta` → objeto `a5f32537`, commit `3353d6f9`.
- **Commits:** funcional `8ca0d5d4` → re-anclaje del freeze `87c7089e` → docs `3353d6f9`.
- **`Release tag CI` run [`37215515993`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37215515993) VERDE** (`attempt 2`; `attempt 1` cayó por un **test FLAKE** de `apps/web` ajeno al sello — `dia-d-auto-feedback-panel.test.tsx`, carrera en un `expect(spy).toHaveBeenCalledWith(...)`, reproducido en verde 4/4 corridas locales de la suite web): `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4511 passed / 45 skipped` (**+8** sobre `v2.88.46.1`); `replay-repro` `REPRODUCIDO` `1E3ADAC2…` = **idéntico** a `v2.88.46.1` ⇒ **`Δ motor = 0` confirmado por CI**. **GitHub Release** publicado.
