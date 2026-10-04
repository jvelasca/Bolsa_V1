# Evidencia `v2.88.48-beta` — `AUTO · DÍA-D-3g`: **correlación DECISIÓN↔CICLO** (`THESIS_EXIT` vs `STOP`), Δ motor = 0

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.48-beta` · **Package:** `2.11.48-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.97 DIA-D AUTO THESIS EXIT` · **Δ motor = 0**.

**Schemas:** `dia-d-thesis-exit-v4` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`), `dia-d-multi-cycle-ledger-v6` (aditivo sobre `-v5`) y `dia-d-thesis-stop-sequences-v1` (`KIND = "DIA_D_AUTO_THESIS_STOP_SEQUENCES"`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.47`](../v2.88.47/README.md) (el nivel tocado **no** ejecutado: `structuralStopCandidate 38/38` medido desde `D1`) → [`v2.88.46`](../v2.88.46/README.md) (la condición: el nivel congelado ES el stop inicial) → [`v2.88.45`](../v2.88.45/README.md) (dónde viven los `38` `THESIS_EXIT`).

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-band/draw-00…draw-11/multi-cycles.json` — `12` ledgers `dia-d-multi-cycle-ledger-v6` (con la secuencia día a día **y** la huella de decisión intra-tick por ciclo).
- `operability_runs/dia-d-auto/multi-band-detail-2021_2026.json` — el plegado `v2_94` con `--cycle-detail` (`45 205 B`).
- `operability_runs/dia-d-auto/thesis-exit-2021_2026.json` — el artefacto `dia-d-thesis-exit-v4` (`176 912 B`).
- `operability_runs/dia-d-auto/thesis-stop-sequences-2022_2025.json` — el volcado `--sequences` (`259 280 B`).

---

## 0. Qué añade este sello (y qué NO)

`v2.88.47` midió que el stop vigente **fue tocado** en los `38/38` `THESIS_EXIT` (`structuralStopCandidate 38/38`), pero su propia secuencia `D1` se captura **antes** de `auto_turn()` y **no registra qué hizo el decider ese tick**: no podía separar *"el stop se evaluó y no ejecutó"* de *"el stop no se evaluó"*. Este sello cierra ese hueco **sin tocar el motor**: tras `auto_turn()`, el worker deja la decisión del tick en memoria keyed por símbolo (`_v2_last_exit_reasons`/`_v2_last_exit_label`) y los fills durables ya traen `cycle_id`. La **costura inerte** `v2_87.capture_cycle_detail` **lee** ese estado ya producido y lo escribe **en el mismo fotograma del día** (no un segundo fotograma), y anota cada fila `managementRows` con el `cycleId` del ciclo abierto de su instrumento (`(instrument_id, day)`). El ledger `-v6` publica por ciclo la **huella de decisión** y una **ruta** cerrada:

> `decisionRoute` ∈ {`materializado`, `stop_evaluado_sin_materializar`, `stop_no_evaluado`, `sin_toque`, `sin_traza`}.

**NO** toca el motor, los umbrales, `TOP_N` ni la allocation. **NO** introduce contrafactuales. **NO** separa el caso A del C (ver §4: `dayOrders`/`dayFills` son señal de **DÍA**, no por ciclo).

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. La huella se **LEE** del estado ya producido por el worker tras `auto_turn`; **no** re-ejecuta la decisión ni la altera (`Δ motor = 0`).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **La capa v6 es ADITIVA:** los `38` ciclos y su `expectancyR` bruta `-0.7087` son idénticos a `v2.88.45`/`v2.88.46`/`v2.88.47`. | Que el global difiera del sello anterior. | `global.realizedRGross.expectancyR.mean = -0.7087` (`total -2.3462`), `cycles = 38`, `coverage.cyclesTotal = 38`, `hitRate = 0.0833`. |
| **2** | **La huella de decisión se LEE del estado ya producido** tras `auto_turn`; no re-ejecuta la decisión ni la altera. | Que el replay con `capture_cycle_detail=False` difiera del artefacto congelado. | `replay-repro` local **byte a byte idéntico** al sello (`24066225…` CRLF / `1E3ADAC2…` LF, `3 445 622 B`) en **dos** corridas (§3). |
| **3** | **El decider SÍ corrió en todos los toques:** `deciderRanOnTouch` y `stopEvaluatedOnTouch` = `38/38`. | Que algún toque no deje ni motivos ni etiqueta. | `global.decisionCorrelation.stopEvaluatedOnTouch = {count: 38, measured: 38, share: 1.0}`; `deciderRanOnTouch = {count: 38, measured: 38, share: 1.0}`. |
| **4** | **La pregunta A/B/C CIERRA: `stop_no_evaluado = 0`.** En los `38` `THESIS_EXIT` el stop **fue evaluado** en el toque; la división es *materializado* vs *evaluado sin materializar*, **nunca** "no evaluado". | Que aparezca cualquier ciclo en `stop_no_evaluado`. | `route = {materializado: 19, stop_evaluado_sin_materializar: 19}` ⇒ los otros tres cubos (`stop_no_evaluado`, `sin_toque`, `sin_traza`) valen **`0`**. |
| **5** | **El reparto es `19 / 19`:** el stop disparó y **materializó** fill en `19` ciclos; disparó **sin** fill en los otros `19`. | Que el reparto sea desigual en exceso o que un cubo quede vacío. | `routeByStructuralStopCandidate = {materializado: {candidate 19, notCandidate 0}, stop_evaluado_sin_materializar: {candidate 19, notCandidate 0}}` ⇒ **`candidate 38/38`** (reproduce el hallazgo de `v2.88.47`). |
| **6** | **`stopFiredNotFilled = 22/38`:** el stop disparó sin materializar en **todos** los `stop_evaluado_sin_materializar` (`19`) **más** `3` ciclos que sí materializaron en otro tick. | Que el conteo no cuadre con `19 + 3`. | `stopFiredNotFilled = {count: 22, measured: 38, share: 0.5789}`; en el eje: `materializado → 3/19`, `stop_evaluado_sin_materializar → 19/19`. |
| **7** | **D47-01 DECLARADO, no capturado:** la secuencia empieza en el **primer tick `D1` completo post-entrada**; el día de entrada **no** tiene fotograma. | Que `timelineStartsAt` no sea `first_full_tick_after_entry`. | `global.decisionCorrelation.timelineStartsAt = "first_full_tick_after_entry"` (viaja al artefacto, al volcado y a los `limits`). |
| **8** | **Un hueco es `None`, nunca `0`:** sin la secuencia capturada, `decisionRoute = sin_traza` y los booleanos `None`. | Que aparezca un `0.0`/`0` donde falta el dato. | Regla dura del código + tests `test_ledger_v6_*`; `--sequences` declara `seqNone = 0` (ningún ciclo sin secuencia en esta corrida). |
| **9** | **Determinismo:** dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**; `v2_97 --sequences` ídem. | Que dos corridas difieran. | `sha256 thesis-exit-v4 = A4CECDAAB50C4110C3E8A4C27C596E007F18194D1D89D3E0DBCBD14616B26C62` (`176 912 B`); `sha256 sequences = 742ADBEDA62D9592FB95D1D3AE04CACDE9B0D3780377BFA350A887E87D1380EC` (`259 280 B`). |
| **10** | **`Δ motor = 0` DEMOSTRADO LOCALMENTE:** ningún fichero de motor cambia y el artefacto congelado **se reproduce byte a byte** contra el fixture sellado. | Que el árbol del motor cambie o que el replay con `capture_cycle_detail=False` difiera del sello. | `git status` sin ficheros de motor; `replay-repro` **`REPRODUCIDO`** `24066225…` (render) / `1E3ADAC2…` (contenido LF) — **idéntico** al sello de `v2.88.46.1`/`v2.88.47` (§3). |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` observaciones `THESIS_EXIT` (pooled sobre sorteos) · **`32` identidades de ciclo únicas** (símbolo+entrada+salida) · `38` con fricción `COMPLETE` · `detailCaptured = true` · **una** estrategia (`v283-window-a`) y **una** dirección (`long`) · `9` símbolos distintos.

### 2.1 Global (idéntico a `v2.88.45`…`v2.88.47`: la capa v6 es aditiva)

| Métrica | Valor |
| --- | --- |
| R bruto total (por sorteo, media) | `-2.3462` |
| Expectancy bruta (entre sorteos) | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| HitRate | `0.0833` |
| R neto total (por sorteo, media) | `-2.5012` |
| Expectancy neta | `-0.7525` |
| `levelEqualsInitialStop` | **`38/38`** (`share 1.0`) |
| `disambiguation.route` (capa v5) | `{ruta_ambas: 34, ruta_mae: 4}` (`ruta_mark = 0`) |
| Concentración | `9` símbolos · top símbolo `26,3 %` · top semana `2025-W12` `21,1 %` |

### 2.2 Correlación DECISIÓN↔CICLO (nuevo, capa v6)

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `route` | `{materializado: 19, stop_evaluado_sin_materializar: 19}` | **mitad y mitad**: el stop disparó **y** materializó fill en `19`; disparó **sin** fill en `19`. `stop_no_evaluado`/`sin_toque`/`sin_traza` = **`0`** |
| `routeByStructuralStopCandidate` | `materializado {candidate 19}` · `stop_evaluado… {candidate 19}` | **`candidate 38/38`**: reproduce el hallazgo de `v2.88.47` (el nivel **fue tocado** en todos) |
| `stopEvaluatedOnTouch` | **`38/38` (`share 1.0`)** | en **todos** los toques, `STRUCTURAL_STOP` aparece en los motivos del tick ⇒ **`stop_no_evaluado = 0`** |
| `deciderRanOnTouch` | **`38/38` (`share 1.0`)** | el decider dejó huella (motivos o etiqueta) en todos los toques |
| `stopFiredNotFilled` | `22/38` (`0.5789`) | el stop disparó sin materializar: los `19` `stop_evaluado_sin_materializar` **+** `3` `materializado` con un toque que no llenó |
| `stopTouchDays` media / mediana | `2.0789` / `1.0` | días con `mark ≤ currentStop` por ciclo |
| `timelineStartsAt` | `first_full_tick_after_entry` | **D47-01** declarado en artefacto, volcado y `limits` |

### 2.3 Eje `byDecisionRoute` (nuevo)

| Cubo | Sorteos | Ciclos | Expectancy bruta | HitRate | MAE | MFE | `stopFiredNotFilled` | `touchBeforeExit` | `stopChanged`/`breakeven` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `materializado` | `10/12` | `19` | `-0.7936` | `0.1167` | `-1.3836` | `+0.9234` | `3/19` (`0.158`) | `10/19` | `7` / `6` |
| `stop_evaluado_sin_materializar` | `9/12` | `19` | `-0.6938` | `0.0000` | `-1.4222` | `+0.4111` | `19/19` (`1.0`) | `3/19` | `0` / `0` |

Ambos cubos son `fragile` (`few_cycles_per_draw`). **Ninguna celda se cita como fuerte.**

### 2.4 Volcado de secuencias (`--sequences`, `dia-d-thesis-stop-sequences-v1`)

| Campo | Valor |
| --- | --- |
| `draws` / `thesisExitObservations` / `uniqueCycleIdentities` | `12` / `38` / `32` |
| `cyclesPerDraw` | `{0:4, 1:3, 2:4, 3:4, 4:1, 5:3, 6:4, 7:3, 8:4, 9:0, 10:5, 11:3}` (suma `38`) |
| `sequence` ausente | `0` (todos los ciclos traen su secuencia) |

Cada registro trae la secuencia `{day, mark, currentStop, maeR, mfeR}` **enriquecida** con `decisionReasons`, `decisionLabel`, `survived`, `filledQty`, `dayOrders`, `dayFills`, más la desambiguación v5 (`thesisExitRoute`, `levelR`, `markAtExitR`, `minMarkR`, `persistedMaeR`, …) y la correlación v6 (`decisionRoute`, `stopEvaluatedOnTouch`, `deciderRanOnTouch`, `stopFiredNotFilled`, `timelineStartsAt`).

### 2.5 Lectura honesta

- **La pregunta A/B/C de `v2.88.47` CIERRA.** El sello anterior dejó abierto *si el stop tocado en un `THESIS_EXIT` se había evaluado o no*. La huella intra-tick lo responde: **`stopEvaluatedOnTouch 38/38`** y **`deciderRanOnTouch 38/38`** ⇒ **`stop_no_evaluado = 0`**. En los `38` `THESIS_EXIT` el stop **se evaluó siempre**; el reparto es **`materializado 19` ↔ `stop_evaluado_sin_materializar 19`**. **No** hay ningún caso de "toque sin evaluación".
- **Mitad materializa, mitad no.** `materializado 19` = el stop disparó **y** el tick produjo fill del ciclo (caso **B**). `stop_evaluado_sin_materializar 19` = el stop disparó (`STRUCTURAL_STOP` en los motivos) **pero no hubo fill** (casos **A/C agrupados**). El reparto `19/19` **no** es un artefacto de redondeo: el eje `byDecisionRoute` lo confirma con `19` ciclos en cada cubo.
- **El cubo que materializa captura más upside.** `materializado` tiene `hitRate 0.1167` y `MFE +0.9234` (algunos ciclos ganan); `stop_evaluado_sin_materializar` tiene `hitRate 0.0000` y `MFE +0.4111` (ninguno gana). La lectura: cuando el fill del stop **sí** llega, el ciclo conserva parte del recorrido favorable; cuando **no** llega, el ciclo muere por invalidación de tesis sin haber ganado. Es una **correlación medida**, no una causa.
- **El stop sin materializar tiene los toques más próximos al cierre.** En `stop_evaluado_sin_materializar`, `touchBeforeExit 3/19` (`0.158`) y `daysToFirstTouch` mediana `0.0`: el toque es, casi siempre, el **propio día del cierre**; en `materializado`, `touchBeforeExit 10/19` (`0.526`) y `stopTouchDays` medio `3.16`: el stop fue tocado en varios días antes de materializar. El `stop` **no** se movió en `stop_evaluado_sin_materializar` (`stopChanged 0`, `breakevenReached 0`), mientras que en `materializado` sí (`7` y `6`).
- **El `3` de diferencia.** `stopFiredNotFilled 22/38` frente a los `19` del cubo sin materializar: los `3` restantes son ciclos `materializado` en los que **algún** toque previo disparó el stop sin llenar, pero el ciclo **sí** materializó en otro tick. Es la misma semántica ("disparó y no llenó") aplicada **por día**, no un segundo cubo.

### 2.6 Límite del hallazgo (declarado, NO cerrado)

La ruta distingue **evaluado** de **no evaluado** y **materializado** de **no materializado**, pero **NO** separa el caso **A** (el stop se evaluó y **no** generó orden) del caso **C** (el stop generó orden y **no** se llenó aguas abajo): desde la costura inerte, ambos colapsan en `stop_evaluado_sin_materializar`. La única señal de **DÍA** disponible (`dayOrders`/`dayFills`, delta de `report.orders`/`report.fills`) **NO** es por ciclo y **no** se usa para separarlos. Separarlos exigiría un join intra-tick adicional evento por evento (**deuda declarada**). El hallazgo es **"stop evaluado, no materializado"** medido desde la huella del worker; **la causa exacta de la no-materialización NO se afirma aquí.**

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` suite DÍA-D completa (`test_dia_d_*.py` + `test_dia_d_bump_guard.py`) | **163 passed** (`v2.88.47` selló `155` ⇒ **+8**) |
| `test_dia_d_multi_sampling.py` (capa v6) | **32 passed** (`v2.88.47` `26` ⇒ **+6**; rutas A/B/C, `stopFiredNotFilled`, `timelineStartsAt` D47-01, hueco `sin_traza`, match case-insensitive de `structural_stop`, `managementRows` con `cycleId`) |
| `test_dia_d_thesis_exit.py` (bloque `decisionCorrelation` + eje `byDecisionRoute`) | **23 passed** (`v2.88.47` `21` ⇒ **+2**) |
| `test_dia_d_bump_guard.py` | **1 passed** (`meta.bump` alineado a `2.11.48-beta` en `v2_89…v2_97`) |
| `test_dia_d_loss_origin.py` | **9 passed** (espera ledger `-v6`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros, `3 609` dependencias) |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Determinismo `v2_97` / `v2_97 --sequences` | byte a byte idéntico (`sha256 A4CECDAA…` / `742ADBED…`) |
| **`Δ motor = 0` (`replay-repro` LOCAL)** | **`REPRODUCIDO`** — fixture congelado re-sembrado (`20` instrumentos, `25 700` barras) en una **BD efímera**; `assert-artifact` ⇒ `render 240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0` (`3 445 622 B` CRLF) / `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (`3 340 728 B` LF) = **idéntico al sello**; dos corridas del `v2_87` ⇒ **byte a byte idénticas** ⇒ la costura sigue **inerte por defecto**. |

---

## 4. Límites declarados (NO se cierran aquí)

- **A vs C quedan AGRUPADOS** en `stop_evaluado_sin_materializar`: `dayOrders`/`dayFills` son señal de **DÍA**, no por ciclo (deuda §2.6).
- **D47-01 SÓLO se DECLARA:** la secuencia empieza en el primer tick `D1` completo post-entrada (`timelineStartsAt = first_full_tick_after_entry`); el **día de entrada no tiene fotograma** y no se captura.
- **La capa v6 es OPT-IN:** exige la costura `--cycle-detail`; sin ella `decisionRoute = sin_traza` y los booleanos `None` (nunca `0`).
- **`decisionRoute` NO es contrafactual:** `materializado` = el stop disparó **y** el tick produjo fill; `stop_evaluado_sin_materializar` = el stop disparó **sin** fill. No se afirma qué *habría* pasado.
- **La huella de decisión se LEE, no se re-ejecuta:** `decisionReasons`/`decisionLabel`/`filledQty`/`survived` salen del estado ya producido por el worker tras `auto_turn` (`Δ motor = 0`).
- **El nivel congelado SIGUE siendo hoy el stop inicial** (deuda de `v2.88.45`/`v2.88.46`/`v2.88.47`): no se introduce un nivel de tesis distinto.
- **`stopBasisMismatchR` sigue `P3`** (discrepancia medida, no reconciliada): arreglarla tocaría el replay.
- **Unidad = ciclo por sorteo:** `38` observaciones pooled vs `32` identidades únicas; no se suman como operaciones financieras independientes. `n` pequeño ⇒ **todos** los cubos `fragile`.
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle v6 (secuencia + huella de decisión por ciclo).
#    OJO: borrar antes los draw-XX/multi-cycles.json v5 (o correr sin --reuse):
#    v2_94._DETAIL_LEDGER_SCHEMA exige v6 y si no, re-corre; un ledger v5 con el
#    MISMO string no debe reutilizarse con la semántica anterior.
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/multi-band-detail-2021_2026.json

# 2) Plegar los 38 THESIS_EXIT al artefacto v4 (bloque decisionCorrelation + eje byDecisionRoute)
#    y volcar la secuencia por ciclo (--sequences → thesis-stop-sequences-YYYY_YYYY.json)
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/thesis-exit-2021_2026.json \
  --sequences

# 3) Dos corridas deben dar el mismo sha256 (determinismo):
#    A4CECDAA… (thesis-exit-v4, 176 912 B) / 742ADBED… (sequences, 259 280 B)

# 4) Δ motor = 0 contra el fixture congelado (BD efímera; NO se toca la BD de desarrollo):
#    sembrar el fixture y regenerar el replay con la costura OFF por defecto.
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
  --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson
WATCH="$(uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  watch --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson)"
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py \
  --json --watch "$WATCH" --out artifacts/repro/replay-1.json
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  assert-artifact --file artifacts/repro/replay-1.json   # ⇒ REPRODUCIDO
```

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.48/README.md`.
- **Modificados:** `v2_87_replay_oos_durable_cycle.py` (costura inerte: `decisionReasons`/`decisionLabel`/`survived`/`filledQty`/`dayOrders`/`dayFills` en el mismo fotograma + `managementRows` con `cycleId`), `dia_d_multi_sampling.py` (ledger `-v6`: `_compact_sequence` enriquecido, `_decision_correlation_fields` con `decisionRoute`, `timelineStartsAt` D47-01), `dia_d_thesis_exit.py` (`dia-d-thesis-exit-v4`: bloque `global.decisionCorrelation` + eje `byDecisionRoute` + límites), `v2_93_dia_d_multi.py` (acumula `managementByCycle`), `v2_94_dia_d_multi_band.py` (`_DETAIL_LEDGER_SCHEMA` exige v6), `v2_97_dia_d_thesis_exit.py` (claves de secuencia + impresión `decisionCorrelation`; consola UTF-8), `v2_89`…`v2_97` (`meta.bump`), `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `test_v2_87_release_log.py`, `package.json` (`2.11.48-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado; la costura `capture_cycle_detail` sólo **lee** estado ya producido y su default sigue `False`; `replay-repro` **reproducido byte a byte** contra el fixture congelado (§3).
- **Tag:** `v2.88.48-beta` → **PENDIENTE de sellar** (el `Release tag CI` se cita al empujar el tag).
