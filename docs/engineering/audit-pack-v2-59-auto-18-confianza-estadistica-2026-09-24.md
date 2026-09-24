# Audit-pack `AUTO-18` Confianza estadística — `1.84.0-beta` (2026-09-24)

**Fase:** `V2.59` · **Rótulo:** `AUTO-18` · **Bump:** `1.83.0-beta` → **`1.84.0-beta`** · **Tag:**
`v2.59-beta` (cifras de CI en §11, añadidas en el commit de docs **posterior** al sello) · **Fase
anterior:** `V2.58` / `AUTO-17` (tag `v2.58-beta` → `72f6084a`, `Release tag CI` `35976693458`
**GREEN a la primera**, `1.83.0-beta`, PR de auditoría
[#67](https://github.com/jvelasca/Bolsa_V1/pull/67)).

**NO hay migración:** Alembic head sigue en **`046_fill_reference_mid`**. `costModelVersion` entra como
clave **aditiva** en el JSON de `TradingCost.to_dict()` (ya persistido en reservas) y la confianza viaja en
`healthByStrategy`/`evidence_for` con campos nuevos que son `null` por defecto. Sin SHORT, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la proyección por
lista blanca `riskMultipliers` + `evidenceAxis` de `auto_adaptive_journal.py` queda **byte a byte igual**).
El gobernador y su evidencia quedan **intactos**. Adaptive **sigue siendo recomendador read-only**.

**Ruta con el flag OFF:** el camino Adaptive **no se recorre** (ni lectura ni plan), así que el plan, el
journal y la API quedan **byte a byte iguales** a `v2.58`.

---

## 0. Resumen: qué instala esta pasada

`AUTO-12` publicaba una confianza estadística, pero su `effective_n` era **la muestra bruta** (ciclos con R
medido) y el reparto encogía el peso con esa `n`. Con eso, **100 ciclos dentro de una sola fase de mercado
pesan como 100 observaciones independientes**, que es precisamente lo que no son. Y el metro con el que se
midió el neto **no viajaba**: dos versiones con modelos de coste distintos podían competir en el eje del R
neto como si fueran comparables.

Esta pasada instala cuatro cosas, sin migración y sin I/O nuevo:

1. **`effective_N` estadístico por episodios.** `effective_n = min(measured_n, episodes)`, donde
   `episodes` son las **rachas de régimen** de los ciclos medidos ordenados. Se publica el descuento
   declarado (`episode_discount`), de modo que una muestra que se encoge por falta de independencia **no
   parece** un dato perdido.
2. **Cobertura por régimen** como **eje propio** (`HIGH`/`MEDIUM`/`LOW`/`UNCOVERED` por celda, desde la
   muestra efectiva) y **calibración descriptiva** (`ConfidenceCalibration`: banda → `n`/`mean_r`/`win_rate`
   /rango prometido/fiabilidad observada), read-only: **no** mueven banda ni reparto.
3. **`shrunk_expectancy_r`** publicada en cada fila/celda y **shrinkage del reparto con la `n` nueva**; el
   factor aplicado se publica por versión (`shrinkFactor`).
4. **El metro del coste viaja** (`costModelVersion` aditivo) y un cambio de metro **separa series** y
   **bloquea** `decay`/eje (`COST_MODEL_TRANSITION`), en la misma línea que `AUTO-17` hizo con la base.

Superficie tocada: `auto_adaptive_confidence.py`, `auto_self_evaluation.py`, `auto_adaptive.py`,
`portfolio_reservation.py`, la sonda de mutaciones, los dos arneses de seam de AUTO-13/AUTO-14, los dos de
AUTO-12/AUTO-16 (solo el sello) y **un** fichero de test nuevo (`test_auto_v59_auto18_confidence_seam.py`,
en `apps/api-python/tests`, que entra por pase de directorio). **Sin listas nuevas en los workflows** (el
único fichero nuevo está en un directorio con pase de directorio).

---

## 1. El invariante: **nadie pesa más de lo que su población independiente sostiene**

> La evidencia de una versión no es su número de ciclos: es su número de **observaciones independientes**.
> Un régimen que dura 100 ciclos es **una** fase; medirla como 100 hace que una racha mueva el presupuesto
> de estrategias que sí demostraron. Y el número solo es comparable si comparte **metro** (`net_r_basis`,
> `cost_model_version`).

De ahí las seis reglas duras, todas con test y con mutación que las mata:

- **La independencia acota la muestra.** `effective_n = min(measured_n, episodes)`; los ciclos `UNKNOWN`
  forman/extienden su **propia** racha (declarado, nunca fusionados con un régimen real).
- **La cobertura es un eje propio.** Una celda `coverage=HIGH` puede tener `decay=SEVERE`: independencia y
  deterioro son **dos** cosas.
- **La calibración no decide.** Publica la fiabilidad observada por banda; no cambia banda ni reparto.
- **La expectancy se encoge con la `n` nueva.** `shrunk_expectancy_r` en cada fila/celda; el reparto usa
  `effective_n`, no `measured_n` (`shrinkFactor` publicado).
- **Dos metros ⇒ dos series.** Un cambio de `costModelVersion` **separa** series; `COST_MODEL_TRANSITION`
  bloquea `decay` y el eje del R neto. Población homogénea = `(basis, cost_model_version)`.
- **`DATA_DEGRADED` no es `UNKNOWN`.** Un neto **sin** base declarada baja la banda y añade nota
  (`ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED`); **no** hay neto es el `UNKNOWN` **inocuo** que no bloquea.

**La compatibilidad es parte del invariante:** sin `confidence` el plan es **byte a byte**; los campos
nuevos tienen defecto seguro (`measured_n = effective_n` histórico, `cost_model_version=None`,
`episodes=0`). El código viejo que no los declara conserva el comportamiento histórico.

---

## 2. Sin migración: qué se declara y qué **no**

| Punto | `ruta:línea` |
| --- | --- |
| Alembic head (sin cambio) | `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py:38` |
| Guardia de head del repo (`_ALEMBIC_HEAD`) | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Firma del modelo de coste (recomputable) | `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reservation.py:205` |

- **El metro no se persiste como columna**: entra **aditivo** en el JSON de `TradingCost.to_dict()` (ya
  persistido en reservas) y se **recomputa** de `commissionPresetId + bps`. Sin migración.
- **Sin backfill:** las filas históricas quedan `None`/`undeclared` **declarado** (nunca afirmado).
- **La guardia `_ALEMBIC_HEAD` NO cambió** (`046_fill_reference_mid`): al no haber migración, no hay riesgo
  del rojo que obligó a re-sellar `v2.56`.

---

## 3. La muestra estadística y su cobertura

| Punto | `ruta:línea` |
| --- | --- |
| `_episodes` (rachas de régimen por versión, sobre los medidos ordenados) | `auto_adaptive_confidence.py:391` |
| `_coverage_band` (eje de cobertura, desde la muestra efectiva) | `auto_adaptive_confidence.py:416` |
| `_shrunk` (expectancy encogida `expectancy·n/(n+k)`) | `auto_adaptive_confidence.py:434` |
| `_band` (banda **bajada** si `DATA_DEGRADED`) | `auto_adaptive_confidence.py:464` / `:494` |
| `_regime_calibration` (tabla descriptiva por banda) | `auto_adaptive_confidence.py:1026` |
| `RegimeConfidence` (`measured_n`/`episodes`/`coverage`/`shrunk_expectancy_r`) | `auto_adaptive_confidence.py:634` |
| `StrategyConfidence` | `auto_adaptive_confidence.py:700` |
| `ConfidenceCalibration` | `auto_adaptive_confidence.py:767` |
| `AdaptiveConfidence` (con `calibration`) | `auto_adaptive_confidence.py:813` |
| Descuento declarado | `auto_adaptive_confidence.py:267` |

**Decisiones finas, medidas.**

- **`effective_n ≤ measured_n` es estructural** (`min`). No hay camino en el que la independencia
  *infle* la muestra.
- **`UNKNOWN` es una racha propia.** Un ciclo sin régimen legible **no** se fusiona con un régimen real: la
  racha se corta al cambiar de valor, y `UNKNOWN` es un valor más.
- **Sin fechas legibles no hay rachas que contar**: la cobertura/calibración se declaran, no se inventan.

---

## 4. El metro del coste y el reparto

| Punto | `ruta:línea` |
| --- | --- |
| `NetRBasis` (enum cerrado) | `auto_self_evaluation.py:131` |
| `NetRBasisSeries` | `auto_self_evaluation.py:746` |
| `_net_r_series` (agrupa por `(basis, model)`) | `auto_self_evaluation.py:1233` |
| `_cost_model_key` / `_cost_model_of` | `auto_self_evaluation.py:1270` / `:1275` |
| `_basis_of` / `_pooled_net_expectancy` | `auto_self_evaluation.py:1289` / `:1331` |
| `affirms_declared_net_r_basis` + guarda en `_strategy_row` | `auto_self_evaluation.py:1307` / `:1424` |
| `BasisTransition` (enum cerrado) | `auto_adaptive_confidence.py:210` |
| `_basis_transition` (con `DATA_DEGRADED`) | `auto_adaptive_confidence.py:514` / `:555` |
| `_decay` gated por transición | `auto_adaptive_confidence.py:577` |
| `cost_model_signature` / `TradingCost.cost_model_version` | `portfolio_reservation.py:205` / `:263` |
| `_net_basis_comparable` (población homogénea) | `auto_adaptive.py:1030` |
| `_confidence_factor` (usa `effective_n`) | `auto_adaptive.py:1188` |
| `shrink_factors` publicado | `auto_adaptive.py:615` / `:1308` |
| `evidence_for` (los seis campos) | `auto_adaptive.py:830` |
| Sello del reparto | `auto_adaptive.py:198` |

- **El sello sube a `auto18-v1`**: aquí **sí** cambia la **regla** del reparto (la `n` del encogimiento),
  a diferencia de `AUTO-17`, donde cambiaba la condición del eje. `DATA_GATE_POLICY_VERSION` sigue
  `auto15-v1`.
- **`MIXED` vs `TRANSITION`:** `MIXED` es heterogeneidad **interna** (dos bases conviviendo en la MISMA
  ventana); `TRANSITION` es un cambio **temporal** de base entre ventanas. Son **dos ejes distintos** y
  ambos se declaran.
- **`DATA_DEGRADED`** es el estado de «hay un neto y **no** declara su base»: **baja la banda**. El `UNKNOWN`
  («no hay neto») **no** bloquea: es el hueco benigno.

---

## 5. La costura (con CONTROL)

- **Costura hermética** (`test_auto_v59_auto18_confidence_seam.py`, por el camino **real** del worker): la
  evidencia publicada lleva los seis campos `measuredN`/`episodes`/`effectiveN`/`coverage`/
  `shrunkExpectancyR`/`shrinkFactor`, y el factor **es** el de la `n` **estadística** (`1/(1+prior)`), no
  el de la bruta.
- **Controles puros:** la muestra efectiva **nunca** supera la medida; `UNKNOWN` no se fusiona; la
  calibración omite bandas sin celdas; `shrunk_expectancy_r` declara ausencia en vez de `0`.
- **Control negativo del reparto:** sin `confidence` el plan es **byte a byte**; con `confidence`, el
  `multiplier` se queda en `(0,1]` y la suma de pesos se preserva.

---

## 6. Matriz de mutaciones `M139…M148`

| # | Mutación | Invariante que ataca | Detectada (tests en rojo) |
| --- | --- | --- | --- |
| `M139` | la muestra efectiva es la **bruta** y las rachas no acotan | independencia ignorada | `test_effective_n_counts_regime_episodes_not_cycles`, `test_consecutive_cycles_of_one_regime_are_a_single_episode`, `test_the_sample_that_sustains_the_number_is_the_measured_one`, `test_an_unknown_decay_caps_the_confidence_instead_of_premising_it`, `test_the_coverage_is_its_own_axis_and_does_not_move_the_band`, `test_the_payload_is_json_shaped_and_carries_the_gaps` |
| `M140` | toda celda con muestra se declara cubierta al máximo | cobertura colapsada | `test_effective_n_counts_regime_episodes_not_cycles`, `test_the_coverage_bands_follow_the_effective_sample`, `test_the_coverage_is_its_own_axis_and_does_not_move_the_band`, `test_the_payload_is_json_shaped_and_carries_the_gaps` |
| `M141` | se publican bandas sin celdas que las respalden | calibración inventada | `test_the_calibration_omits_bands_without_cells` |
| `M142` | la expectancy publicada es la **bruta**, sin muestra | expectancy sin encoger | `test_the_shrunk_expectancy_is_published_and_only_shrinks`, `test_the_shrunk_helper_declares_absence_instead_of_zero` |
| `M143` | el reparto encoge por la muestra **bruta** | `measuredN` en vez de `effectiveN` | `test_the_shrinkage_reads_the_statistical_n_not_the_measured_n`, `test_the_shrinkage_uses_the_confidence_of_the_CELL_not_the_strategy` |
| `M144` | el modelo de coste no publica su versión y nadie la propaga | `cost_model_version` perdida | `test_the_cost_model_version_travels_from_the_model_to_the_cycle_row` |
| `M145` | dos metros dentro de una base se agrupan como una sola serie | series que funden modelos | `test_two_cost_models_in_the_same_basis_are_two_series_not_one_average`, `test_one_cost_model_keeps_the_pooled_number_and_one_series` |
| `M146` | el detector nunca ve cambiar el instrumento | transición de metro no declarada | `test_the_cost_model_transition_is_its_own_state` |
| `M147` | el deterioro se mide aunque el metro cambie entre ventanas | `decay` cross-modelo | `test_the_cost_model_transition_alone_blocks_the_decay` |
| `M148` | el reparto cambia de regla y el sello se queda en `auto17` | sello sin moverse | `test_the_policy_version_seals_the_auto18_evidence_contract`, `test_the_operational_states_travel_in_their_own_field_without_mixing_axes` |

**Esperada / detectada / corregida / residual (punto #27 del auditor):**

| Etiqueta | Esperada | Detectada | Corregida | Residual |
| --- | --- | --- | --- | --- |
| `M139…M148` | 10 | **10** (0 en `NADA`) | la producción es correcta (la mutación se restaura byte a byte) | **0** |
| `M60`/`M125`/`M128`/`M131`/`M134` (realineadas) | 5 | **5** | ancla nueva, invariante intacto | **0** |

La corrida **completa** `M1…M148` está en §7. **Cinco realineos declarados** (`M60`, `M125`, `M128`,
`M131`, `M134`) porque su ancla cambió con esta fase: una sonda desalineada **afirma** cobertura que no
tiene, así que se realinea, no se borra. `M131` en particular dejó de morder porque `AUTO-18` añadió una
**segunda** guarda a `_pooled_net_expectancy` (dos metros dentro de la misma base), de modo que la guarda
de `MIXED` ya no era la única que frenaba el promedio: la mutación pasa a desactivar **las dos** guardas y
vuelve a morder (3 tests: `test_a_mixed_basis_is_declared_and_never_silently_averaged`,
`test_a_historical_transition_is_declared_by_regime_without_splitting_the_cell`,
`test_two_cost_models_in_the_same_basis_are_two_series_not_one_average`).

---

## 7. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas con el comando de CI** (no rutas sueltas):
  - `ruff check packages/py apps/api-python --config pyproject.toml` ⇒ **`All checks passed!`**
  - `mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`
    ⇒ **`Success: no issues found in 499 source files`** (`0` errores; el contador **no** sube porque la
    fase no añade módulos nuevos).
  - `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
- **Tramo de la fase: `311 passed`, `0` rojos** (once suites):

  | Fichero | Fase | `HEAD` |
  | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive_confidence.py` | **45** | 25 |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | **99** | 95 |
  | `packages/py/analytics/tests/test_auto_self_evaluation.py` | **52** | 47 |
  | `packages/py/application/tests/test_cycle_risk.py` | **34** | 33 |
  | `packages/py/application/tests/test_auto_self_evaluation_feed.py` | **29** | 29 (sin cambios) |
  | `apps/api-python/tests/test_auto_v59_auto18_confidence_seam.py` | **3** | — (nuevo) |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | **9** | 9 |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | **14** | 14 |
  | `apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py` | **10** | 10 |
  | `apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py` | **6** | 6 |
  | `apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py` | **10** | 10 |

  **33 tests nuevos** (20 + 4 + 5 + 1 + 3).
- **Dos ficheros de arnés** (`test_auto_v54_auto13_data_gate_wiring_seam.py` y
  `test_auto_v55_auto14_regime_cell_allocation_seam.py`) se realinearon para **sembrar régimen** en el
  `_worker`, porque el `effective_N` estadístico necesita rachas que contar: sin régimen, 180 ciclos son
  **una** racha y el test de la celda fina no podía medir lo que dice medir.
- **Delta simétrico FICHERO A FICHERO contra `HEAD`** (nunca restando totales). Se corrió **la versión de
  `HEAD` de cada fichero de test modificado** (copiada como fichero sonda **no rastreado**, sin tocar el
  árbol) contra el árbol de la fase; los rojos que salen son los **declarados de antemano**, y **solo
  ésos**: **10** rojos.

  | Fichero | `HEAD` vs fase | Rojos | Causa declarada |
  | --- | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | `2 failed, 93 passed` (`71252` B → `77029` B) | **2** | el **sello** (`auto17-v1` → `auto18-v1`) |
  | `packages/py/analytics/tests/test_auto_adaptive_confidence.py` | `4 failed, 21 passed` (`21099` B → `41880` B) | **4** | la `effective_n` pasa a **estadística** (3) y `DATA_DEGRADED` baja la banda (1) |
  | `packages/py/analytics/tests/test_auto_self_evaluation.py` | `47 passed` (`38553` B → `44555` B) | **0** | — (campos/metro **aditivos**) |
  | `packages/py/application/tests/test_cycle_risk.py` | `33 passed` (`24103` B → `26081` B) | **0** | — (campo nuevo aditivo) |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | `1 failed, 8 passed` (`11314` B → `11562` B) | **1** | el **sello** |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | `1 failed, 13 passed` (`15482` B, **idéntico**) | **1** | el marco de la evidencia gana el eje de confianza |
  | `apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py` | `1 failed, 9 passed` (`15686` B → `17259` B) | **1** | el **sello** en el camino de la confianza |
  | `apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py` | `1 failed, 5 passed` (`15950` B → `16189` B) | **1** | la celda se mide con la `effective_n` **estadística** |
  | Controles **sin cambios** `test_auto_self_evaluation_feed.py` / `test_auto_v57_auto16_applied_cost_seam.py` | `29` / `10` passed | **0** | — |

  **No hay rojo residual ni rojo corregido dentro de la fase:** los 10 rojos son **esperados** (el sello y
  el cambio de comportamiento del encogimiento/cobertura) y **no** se «arreglan» en el código de producción
  porque son exactamente lo que la fase promete. **Un** rojo no-determinista
  (`test_a_version_that_leaves_its_pause_is_dated_in_the_same_tick`) se observó **una vez** al correr la
  sonda de relevo en aislamiento y **no** se reproduce (es dependiente de orden/fecha, ajeno a esta fase):
  la medición de referencia lo da en **verde**.
- **Matriz de mutaciones COMPLETA** (`M1…M148`): **`148/148` muerden**, **`0`** etiquetas en `NADA`,
  **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`). **Cinco realineos declarados** (`M60`, `M125`, `M128`,
  `M131`, `M134`; ver §6).
- **Gobernador y contrato durable intactos** (medido): `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`
  y `git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py` ⇒ **vacíos**.
- **Batería COMPLETA pre-tag, con la selección EXACTA del CI** (`uv run --no-sync python -m pytest` sobre
  la lista literal de `python-ci.yml`, incluyendo `apps/api-python/tests` con sus `--ignore`): **`2728
  passed`**, `0` rojos, **`94.07 s`** (`4` warnings de `jwt`/HMAC ajenos a la fase; los mismos `4` que
  `HEAD`). Esto cierra la deuda de «no se pudo medir la batería completa aquí» para la cara **sin PG**:
  lo que queda fuera es **solo** lo que necesita PostgreSQL real (`apps/api-python/tests/integration`,
  las suites PG `--ignore`adas y `chaos/live_a7`), que corre en los jobs dedicados del tag y de la CI
  per-commit (§11).
- **Lo que no se pudo medir aquí:** los runs de CI y la batería **completa con PG real** del tag (las
  suites PG necesitan PostgreSQL y, en el job `python` del tag, van en jobs dedicados). **Ese límite lo
  cierra la CI del tag** (§11).

---

## 8. Límites declarados (no silenciosos)

- **La calibración es descriptiva.** Publica `n`/`mean_r`/`win_rate`/rango prometido por banda; **no**
  mueve banda ni reparto.
- **El `effective_N` por episodios es una cota conservadora declarada**, no una varianza muestral: cuenta
  fases, no observaciones independientes demostradas.
- **`cost_model_version` no se reconstruye hacia atrás.** El histórico queda `None`/`undeclared`
  **declarado** (nunca un metro inventado).
- **No hay migración ni backfill.** El metro se recomputa; la base del neto (AUTO-17) sigue sin persistirse.
- **El flag Adaptive sigue OFF**: sin él no hay plan, ni lectura, ni encogimiento.

---

## 9. Freeze respetado

No se toca el sello de `V2.53`…`V2.58` (`auto13-v1`…`auto17-v1`), `auto_adaptive_journal.py` (**byte a
byte igual**), el contrato de `decision_journal_entries`, `v2_43_governor_evidence.py` (**diff vacío**),
`yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación ni la tabla estado→efecto
(`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`). **Sin UI**, sin SHORT, sin backfill; `*.md` **sin
`prettier`**; `governor.json` sigue **sin trackear**.

---

## 10. Sellado

El paquete de cierre (este pack, el [plan](./plan-v2-59-auto-18-confianza-estadistica-2026-09-24.md), el
[relevo](./traspaso-relevo-post-v2.59-auto-18-confianza-estadistica-2026-09-24.md), el
[arranque del auditor](./arranque-auditor-v2.59-auto-18-confianza-estadistica-2026-09-24.md), `CHANGELOG.md`,
`PROJECT_STATE.md`, el índice y el bump `1.84.0-beta`) viaja **dentro** del tag. **Excepción declarada:**
esta §11 con los runs de CI **medidos** se añade en el commit de docs **posterior** al sello (mismo patrón
que `AUTO-13`…`AUTO-17`): el run del tag no existe hasta que el tag se empuja, así que la tabla se
**mide** en lugar de predecirse.

**Superficie de auditoría (post-sello, declarada):** el PR de auditoría se abre **después** del sello para
que el auditor externo revise el delta con comentarios en línea. Su diff medido es el de la fase y **no** es
vehículo de merge: `main` ya la recibió en **fast-forward**.

---

## 11. CI del sello `v2.59-beta` (medida, no predicha)

**Se mide, no se predice:** el run del tag no existe hasta que el tag se empuja, así que estas cifras se
añaden en el **commit de docs posterior al sello** (mismo patrón que `AUTO-13`…`AUTO-17`), citando cada una
el run que la produjo.

### 11.1 El CI del tag: la head no se movió (sin migración)

**Contraste:** `AUTO-17` no migró y el sello salió verde a la primera; `AUTO-18` tampoco migra, así que la
guardia `_ALEMBIC_HEAD` sigue en `046_fill_reference_mid` y no hay ese rojo posible.

### 11.2 Cifras medidas del sello

| Corte | Run | Resultado |
| --- | --- | --- |
| `Release tag CI` (`97763093`) | [`35991289733`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35991289733) | **GREEN**: `10 success` + `1 skipped` (`playwright (integrated E2E, opt-in)`), `certify` en `success` (**tras el re-run declarado de §11.6**) |
| job `python` del tag | run anterior | ruff `All checks passed!` · mypy `Success: no issues found in 499 source files` · pytest **`2701 passed / 35 skipped`** (**+33** passed, **0** skips nuevos sobre `v2.58`) |
| `Python CI` per-commit del tag | [`35991289795`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35991289795) | **`5/5` jobs `success`** (`quality`, `auto-v2-durable-pg`, `grammar-discovery-pg`, `paper-forward-pg`, `lifecycle-pg`); job `quality` **`2690 passed / 38 skipped`** |
| `Python CI` per-commit de `main` | [`35991292329`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35991292329) | **`5/5` jobs `success`**; job `quality` **`2690 passed / 38 skipped`** (mismo corte que el tag) |
| `check-runs` del commit sellado `97763093` | API de checks | `total_count = 45` ⇒ **`44` success** + **`1` skipped** |
| `status` (Commit Status **legacy**) de `97763093` | `/commits/{sha}/status` | **`pending`** con **`0` statuses** *a la vez* que los `45` check-runs están `completed` ⇒ **cruce de API reproducido en vivo** (no es un hallazgo; §8 del arranque) |
| PR de auditoría [#68](https://github.com/jvelasca/Bolsa_V1/pull/68) | checks del PR | **`29` checks `SUCCESS`** + `1` `SKIPPED` (el playwright opt-in), `certify` incluido |

**+33 tests** sobre `v2.58` en los dos cortes (job `python` del tag `2668` → `2701`; job `quality` `2657` →
`2690`), que es **exactamente** la cuenta del tramo de la fase (§7): **0** skips nuevos.


### 11.3 El límite declarado del §7, cerrado por la CI del tag

El §7 declaró que los runs de CI y la batería **completa con PG real** no se pueden medir en esta máquina.
**El tag las cierra**: la CI del tag corre los jobs PG que la batería offline **no** puede correr.

### 11.4 La ruta sin migración: qué NO se movió (medido)

- `_ALEMBIC_HEAD` (`test_discovery_evidence_snapshot_pg.py:43`) = **`046_fill_reference_mid`** (idéntico).
- `git diff` del gobernador (`v2_43_governor_evidence.py`) y del contrato durable
  (`auto_adaptive_journal.py`) ⇒ **vacíos**.
- `DATA_GATE_POLICY_VERSION` = **`auto15-v1`** (intacto).

### 11.5 La superficie de auditoría post-sello

El PR de auditoría [#68](https://github.com/jvelasca/Bolsa_V1/pull/68) se abrió **después** del sello;
su diff es **exactamente** el delta de la fase — `audit-base-v2.58-beta` @ **`75913f0c`** (el **último**
commit de `v2.58`, docs incluidas: el mismo patrón que `audit-base-v2.57-beta` @ `7b664fb6`) → head
`2cc323fb` —, **22 ficheros, `+3173/−171`**, y **no** es vehículo de merge (`main` ya recibió la fase en
**fast-forward**).

### 11.6 El único rojo del tag: un flake **ajeno a la fase**, cerrado por re-run declarado

El **primer** intento del `Release tag CI` (`35991289733`) trajo **un** rojo en el job
`lifecycle-pg (Alembic + auth + golden restart)`:

- `apps/api-python/tests/test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once`
  ⇒ `AssertionError: RETRY` (la fila de `execution_events` quedó `RETRY` en vez de `APPLIED`),
  **`1 failed, 160 passed`**.

**Por qué no es de `AUTO-18`** (declarado, medido, no supuesto):

1. **El camino no toca la fase.** `test_simulated_finance_pg.py` conduce por
   `bolsa_application.simulated_finance` / `simulated_settlement` / `execution_event`, y **ninguno** importa
   `auto_adaptive.py`, `auto_adaptive_confidence.py`, `auto_self_evaluation.py` ni `portfolio_reservation.py`
   (los cuatro ficheros que la fase toca): el síntoma es un **estado de lease/reintento** de
   `execution_events`, no un número de confianza, reparto, base o modelo de coste.
2. **El gemelo per-commit pasó.** En el `Python CI` del **mismo** commit (`35991289795`) los `5/5` jobs
   —incluido `lifecycle-pg`— salieron `success`.
3. **Se reproduce como flake, no como regresión.** El **re-run de los jobs fallidos** (`gh run rerun
   --failed`) dejó el `Release tag CI` **`success`** con los `10` jobs en verde y `certify` en `success`;
   un rojo determinista de la fase **no** se apaga con un re-run.

Queda **declarado** aquí (no escondido): el flake es de **temporización de lease** en la ruta de finanzas
simuladas, **preexistente** y **fuera del alcance** de `AUTO-18`. La **corrida de cierre** del tag es la
**verde**; los `45` check-runs y las cifras de §11.2 son de esa corrida.
