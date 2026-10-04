# Evidencia `v2.88.49-beta` — `AUTO · DÍA-D-3h`: **separación A/C** (`stop_evaluado_sin_orden` vs `orden_creada_sin_fill`), Δ motor = 0

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.49-beta` · **Package:** `2.11.49-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.97 DIA-D AUTO THESIS EXIT` · **Δ motor = 0**.

**Schemas:** `dia-d-thesis-exit-v5` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`), `dia-d-multi-cycle-ledger-v7` (aditivo sobre `-v6`) y `dia-d-thesis-stop-sequences-v2` (`KIND = "DIA_D_AUTO_THESIS_STOP_SEQUENCES"`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.48`](../v2.88.48/README.md) (el decider **SÍ** evaluó el stop: `stopEvaluatedOnTouch 38/38`, `deciderRanOnTouch 38/38`) → [`v2.88.47`](../v2.88.47/README.md) (el nivel tocado **no** ejecutado: `structuralStopCandidate 38/38`) → [`v2.88.46`](../v2.88.46/README.md) (la condición: el nivel congelado ES el stop inicial).

**Estado del sello:** implementación **local**. El **re-pipeline con PostgreSQL** (`v2_94 --cycle-detail` → `v2_97 --sequences`) y el **`replay-repro`** quedan **PENDIENTES** de esta máquina (no hay ledgers `draw-XX/multi-cycles.json` sembrados); se declaran, no se fingen.

---

## 0. Qué añade este sello (y qué NO)

`v2.88.48` midió que en los `38` `THESIS_EXIT` el stop **fue evaluado siempre** (`stopEvaluatedOnTouch 38/38`), pero dejó los `19` ciclos `stop_evaluado_sin_materializar` agrupando dos causas con solución opuesta:

- **A** — el stop se evaluó y **no** se creó orden (veto o corte del spine). Se investigaría precedencia/veto/estado/sizing/reservation/risk.
- **C** — se creó orden y **no** hubo fill (falla ejecución/venue aguas abajo).

**El hueco no estaba en el motor, estaba en la costura.** El spine mintea un `ExitOrder` durable **por ciclo** antes de liquidar (`_v2_reserve_exit` → `self._v2_exit_orders[exit_order_id] = reserved`, con `cycle_id`). Sólo si ese INTENT existe se intenta `_settle()`; un `settlement.applied` vacío veta `FILL_NOT_MATERIALIZED` **sin** incrementar `report.orders`. Por eso `dayOrders`/`dayFills` (señal de **DÍA**) **no** separan A de C, pero **un diff de `_v2_exit_orders` antes/después de `auto_turn()` sí** (señal **por ciclo**).

> `decisionRoute` ∈ {`materializado`, `orden_creada_sin_fill` **(C)**, `stop_evaluado_sin_orden` **(A)**, `stop_evaluado_sin_materializar` **(Hueco)**, `stop_no_evaluado`, `sin_toque`, `sin_traza`}.

**NO** toca el motor, los umbrales, `TOP_N` ni la allocation. **NO** introduce contrafactuales: `orderCreated` es la **existencia** de un INTENT durable ya producido, no una re-simulación.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. `orderCreated` se **LEE** del estado ya producido por el worker tras `auto_turn` (`diff` de `_v2_exit_orders`, capturado antes de `close_tick`); **no** re-ejecuta la decisión ni la altera (`Δ motor = 0`).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia (local) |
| --- | --- | --- | --- |
| **1** | **La capa v7 es ADITIVA:** los `38` ciclos y su `expectancyR` bruta `-0.7087` siguen idénticos a `v2.88.45`…`v2.88.48` (sólo se **añade** `orderCreated` y los dos tokens). | Que el global difiera del sello anterior al re-correr el pipeline. | **PENDIENTE** de re-pipeline (declarado); el código sólo añade campos. |
| **2** | **A y C quedan SEPARADAS:** `stop_evaluado_sin_orden` (A) ⇔ todos los ticks disparados con `orderCreated is False`; `orden_creada_sin_fill` (C) ⇔ algún tick disparado con `orderCreated is True` y ningún fill. | Que la clasificación mezcle A y C. | Tests `test_ledger_v7_decision_route_order_created_without_fill_is_case_c` y `test_ledger_v6_decision_route_evaluated_without_materialization` (A). |
| **3** | **`stop_evaluado_sin_materializar` es SÓLO hueco:** aparece sólo cuando hay disparo, ningún `orderCreated is True` y algún `orderCreated is None` (no medido). | Que un caso MEDIDO caiga en el hueco. | Test `test_ledger_v7_decision_route_unmeasured_order_is_a_declared_hueco`. |
| **4** | **La huella se LEE, no se re-ejecuta:** `orderCreated` sale del `diff` de `_v2_exit_orders` antes/después de `auto_turn`, **antes** de `close_tick` (que poda los INTENT cerrados). | Que el replay con `capture_cycle_detail=False` difiera del sello. | `git status` sin ficheros de motor; costura inerte por defecto (un `if`). |
| **5** | **Un hueco es `None`, nunca `0`:** sin `orderCreated` medido, el fotograma lo deja `None` y la ruta cae en el hueco declarado. | Que aparezca un `False`/`0` donde falta el dato. | `_compact_sequence` + `_decision_correlation_fields` + tests. |
| **6** | **`decisionRoute` sigue siendo una tupla CERRADA** (ahora de `7` valores) y el eje `byDecisionRoute` viaja ordenado. | Que aparezca un token fuera de la tupla. | `DECISION_ROUTES` + test `test_decision_correlation_route_splits_the_a_and_c_cases`. |
| **7** | **D47-01 se mantiene DECLARADO** (`timelineStartsAt = first_full_tick_after_entry`). | Que cambie la frontera. | Test `test_ledger_v6_decision_route_sin_toque_and_sin_traza_are_distinct` + límites. |
| **8** | **`Δ motor = 0`:** ningún fichero de motor cambia; la costura sólo LEE estado ya producido y su default sigue `capture_cycle_detail=False`. | Que cambie el árbol del motor o que `replay-repro` difiera. | `git status` sin ficheros de motor; `replay-repro` **PENDIENTE** de esta máquina (declarado). |

---

## 2. Medición real

**PENDIENTE.** Requiere re-correr `v2_94 --reuse --cycles --cycle-detail` con el esquema v7 (que **rechaza** los `multi-cycles.json` v6 por el bump de `_DETAIL_LEDGER_SCHEMA`) y plegar con `v2_97 --sequences`. Esta máquina **no** tiene los `draw-XX/multi-cycles.json` sembrados (`operability_runs/` vacío). No se publica un reparto A/C sin la medición; el número se sella al re-correr el pipeline.

### 2.1 Verificación de la plomería (sintética, `K = 1`)

Con un ledger `draw-00/multi-cycles.json` sintético (un `THESIS_EXIT` con `sequence=[{…, "orderCreated": true, "filledQty": 0}]`), el CLI `v2_97 --sequences` reproduce la ruta **C**:

- `CORRELACIÓN DECISIÓN↔CICLO (capa v7: A/C separadas)` → `ruta de decisión {'orden_creada_sin_fill': 1}`.
- `secuencias` → `schemaVersion = "dia-d-thesis-stop-sequences-v2"`, con `sequence[0].orderCreated = true` y `decisionRoute = "orden_creada_sin_fill"`.

No es evidencia de mercado: es la prueba de que la plomería v7 sella A/C y las secuencias v2 conservan `orderCreated`.

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` suite DÍA-D + guards (`test_dia_d_auto`/`auto_feedback`/`attribution`/`longitudinal`/`multi`/`multi_uncertainty`/`loss_origin`/`multi_sampling`/`thesis_exit` + `bump_guard` + `v2_87_release_log`) | **`172 passed`** |
| `test_dia_d_multi_sampling.py` (capa v7) | **`34 passed`** (`v2.88.48` `32` ⇒ **+2**; caso A, caso C, hueco mixto) |
| `test_dia_d_thesis_exit.py` (bloque `decisionCorrelation` + eje `byDecisionRoute`) | **`24 passed`** (`v2.88.48` `23` ⇒ **+1**; A/C separadas) |
| `test_dia_d_loss_origin.py` | **`9 passed`** (espera ledger `-v7`) |
| `test_dia_d_bump_guard.py` | **`1 passed`** (`meta.bump` alineado a `2.11.49-beta` en `v2_89`…`v2_97`) |
| `test_v2_87_release_log.py` (helper `_minted_exit_cycles`) | **`9 passed`** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros, `3 609` dependencias) |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Determinismo `v2_97` / `v2_97 --sequences` | **PENDIENTE** de re-pipeline (declarado). |
| **`Δ motor = 0` (`replay-repro` LOCAL)** | **PENDIENTE** de esta máquina (declarado). La costura sigue **OFF** por defecto y `git status` **no** toca motor. |
| **`Δ motor = 0` (CI por tag)** | **PENDIENTE** (sin tag/CI aún). |

---

## 4. Límites declarados (NO se cierran aquí)

- **La causa exacta NO se afirma:** A y C se **separan** (existía o no el INTENT de salida), pero **no** se nombra el veto concreto de A ni la causa del no-fill de C.
- **`orderCreated` mide la EXISTENCIA del INTENT durable del tick**, no su desenlace: un ciclo con `orderCreated=True` sin fill es C (el motor hizo lo correcto y falló aguas abajo).
- **Si `structural_stop` viaja como motivo SECUNDARIO** junto a otro exit, la atribución hereda la semántica `stop_fired` de `v2.88.48` y se declara.
- **`dayOrders`/`dayFills` siguen siendo señal de DÍA** y **no** votan en la ruta: la señal por ciclo es `orderCreated`.
- **La capa v7 es OPT-IN:** exige la costura `--cycle-detail`; sin ella `decisionRoute = sin_traza` y los booleanos `None` (nunca `0`).
- **D47-01 SÓLO se DECLARA:** la secuencia empieza en el primer tick `D1` completo post-entrada; el **día de entrada no tiene fotograma**.
- **El nivel congelado SIGUE siendo hoy el stop inicial** (deuda de `v2.88.45`…`v2.88.48`): no se introduce un nivel de tesis distinto.
- **`stopBasisMismatchR` sigue `P3`** (discrepancia medida, no reconciliada): arreglarla tocaría el replay.
- **Unidad = ciclo por sorteo:** `38` observaciones pooled vs `32` identidades únicas; no se suman como operaciones financieras independientes. `n` pequeño ⇒ **todos** los cubos `fragile`.
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle v7 (secuencia + huella de decisión + orderCreated por ciclo).
#    OJO: borrar antes los draw-XX/multi-cycles.json v6 (o correr sin --reuse):
#    v2_94._DETAIL_LEDGER_SCHEMA exige v7 y si no, re-corre.
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/multi-band-detail-2021_2026.json

# 2) Plegar los THESIS_EXIT al artefacto v5 (bloque decisionCorrelation con A/C separadas)
#    y volcar la secuencia por ciclo (--sequences → thesis-stop-sequences-YYYY_YYYY.json, v2)
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/thesis-exit-2021_2026.json \
  --sequences

# 3) Dos corridas deben dar el mismo sha256 (determinismo): PENDIENTE de registrar el hash v5/v2.

# 4) Δ motor = 0 contra el fixture congelado (BD efímera; NO se toca la BD de desarrollo).
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

- **Añadidos:** `docs/engineering/evidence/v2.88.49/README.md`.
- **Modificados:** `v2_87_replay_oos_durable_cycle.py` (capa v7: helper `_minted_exit_cycles`, `diff` de `_v2_exit_orders` antes/después de `auto_turn` y, antes de `close_tick`, `orderCreated` por fotograma), `dia_d_multi_sampling.py` (ledger `-v7`: `orderCreated` en la secuencia compacta, tokens `orden_creada_sin_fill`/`stop_evaluado_sin_orden`, clasificación A/C + hueco), `dia_d_thesis_exit.py` (`dia-d-thesis-exit-v5`: `_decision_correlation_fold` con la tupla ampliada, límites y `recompileNote`), `v2_97_dia_d_thesis_exit.py` (secuencias v2 + impresión capa v7), `v2_94_dia_d_multi_band.py` (`_DETAIL_LEDGER_SCHEMA` exige v7), `v2_89`…`v2_97` (`meta.bump`), `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `test_v2_87_release_log.py`, `package.json` (`2.11.49-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado; la costura `capture_cycle_detail` sólo **lee** estado ya producido y su default sigue `False`; `replay-repro` **PENDIENTE** de esta máquina (declarado).
- **Tag:** **PENDIENTE** (`v2.88.49-beta` por sellar cuando el re-pipeline + `replay-repro` se ejecuten).
