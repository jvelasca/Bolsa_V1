# Audit-pack — `v2.74-beta` · `AUTO-MATERIAL-2`: PAPER PRODUCER

> **AsOf:** 2026-09-26 · **Versión:** `1.99.0-beta` · **Base auditada (diff):** `v2.73-beta`
> **Alcance:** (A) **activar y controlar** el productor AUTO 2.0 (`AUTO_ENGINE_SIM_V2=ON` + decider +
> watch + régimen) para que nazca material PAPER **nuevo y limpio** con ESTRUCTURA completa —`cycle_id`
> en los fills, reservas con `reserved_risk` positivo, intents de salida con `cycle_id`, ciclos cerrados
> y R medible— sobre una **cuenta PAPER nueva**; (B) introducir un **veredicto de dos niveles**
> (`PRODUCER_READY` / `EVIDENCE_READY`); (C) **no** rellenar el histórico legacy, **no** ejecutar
> `AUTO-22` y **no** tocar el reparto. La fase **para en `PRODUCER_READY` estructural**.
> **SIN migración** (head `046_fill_reference_mid`). **`auto18-v1` / `auto15-v1` no se mueven.**
> **Freeze:** `auto_simulation_worker.py` sigue **intacto**; la única reparación fue en el **store**
> (`reservation_store.py`, no congelado).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | El camino V2 deja **estructura**: fill con `cycle_id`, reserva durable, exit intent con `cycle_id` | `auto_simulation_worker.py` (`_v2_*`) conducido por el harness y por la costura | `test_v2_producer_leaves_structure_that_the_gate_declares_producer_ready` |
| 2 | El camino LEGACY (V2 OFF) **no** deja estructura (ni linaje ni reservas): el gate lo DECLARA | `build_paper_material_readiness` | `test_legacy_path_leaves_no_structure_and_stays_blocked` |
| 3 | El productor **jamás** backfillea el material congelado: un fill legacy conserva `cycle_id=None` | productor V2 (append por `execution_id`) | `test_v2_producer_never_backfills_the_frozen_legacy_material` |
| 4 | El **denominador de R sobrevive al cierre**: la reserva liberada conserva el riesgo comprometido | `_committed_risk` en `reservation_store.py` | `test_a_released_entry_reservation_still_supplies_the_denominator` + `test_portfolio_reservation.py` |
| 5 | Sin riesgo comprometido **no** se inventa un denominador: R no medible | `_committed_risk` devuelve `None`; extracción solo de entrada positiva | `test_a_released_entry_without_a_preserved_risk_stays_unmeasured` · `test_a_sell_reservation_does_not_become_the_denominator` |
| 6 | `EVIDENCE_READY` **implica** `PRODUCER_READY`; "bien formado" ≠ "suficiente" | guarda de dos niveles | `test_below_the_minimum_is_producer_ready_but_not_evidence_ready` · `test_measured_cycles_reach_evidence_ready_and_achieved_levels` |
| 7 | El gate **no** declara `PRODUCER_READY` sin estructura (falla `no exit orders`, etc.) | `producer_blockers` | `test_a_complete_structure_without_exit_orders_is_blocked_when_measured` + **M200** |
| 8 | El gate **no** baja el mínimo para forzar `EVIDENCE_READY` | guarda `min_cycles_per_strategy` | `test_thresholds_are_declared_and_never_lowered_by_the_gate` + **M199** |
| 9 | Lo **no medido** se declara (`None`), nunca un cero de relleno | `lineage.cycle.exitOrders*` | `test_exit_order_lineage_is_declared_and_never_invented` |
| 10 | La población TOTAL (tabla entera) es informativa y **no** cambia el veredicto | `database_totals` | `test_database_totals_are_declared_and_never_change_the_verdict` |
| 11 | El CLI distingue `--level producer` de `--level evidence` y sella el JSON | `scripts/paper_material_readiness.py` | `test_producer_level_is_reached_without_the_evidence_minimum` · `test_the_json_payload_carries_the_two_levels_and_the_seal` |
| 12 | El productor real deja estructura medible en PostgreSQL (cuenta nueva) | conducción real contra `bolsa-postgres` | evidencia cruda (§5) |
| 13 | El legacy, el reparto y la migración siguen intactos | `git diff` del freeze + Alembic head | verificación git + head |

## 2. Qué cambia (y qué no)

**Cambia.**

- `packages/py/application/src/bolsa_application/paper_material_readiness.py`: **veredicto de dos
  niveles** (`PRODUCER_READY` / `EVIDENCE_READY`, más `BLOCKED`), `producer_blockers`, `producer_ready`,
  `evidence_ready`, `achieved(level)`, `facts["databaseTotals"]` y sello `paper_material_readiness_v2`.
  `BLOCKER_NO_MEASURABLE_RISK` y `BLOCKER_NO_EXIT_ORDERS` nuevos.
- `packages/py/application/src/bolsa_application/reservation_store.py`: `_committed_risk` — la fila
  durable de una reserva liberada conserva el riesgo COMPROMETIDO en el alta (el denominador de R que
  `cycle_risk_from_reservations` lee **después** del cierre). El objeto devuelto y el libro vivo **no**
  cambian (siguen escalando a `0`/escalado).
- `apps/api-python/scripts/paper_material_readiness.py`: `--level {producer,evidence}` (default
  `evidence`) y las **tres poblaciones** (`DATABASE TOTAL` / `INSTRUMENT UNIVERSE` / `AUTO MATERIAL`).
- `apps/api-python/scripts/v2_74_paper_producer_evidence.py` (**nuevo**): ejercicio controlado del
  productor con **A/B estructural LEGACY vs V2** y `--json` / `--out`.
- Tests: `packages/py/application/tests/test_paper_material_readiness.py` (ampliado),
  `packages/py/application/tests/test_portfolio_reservation.py` (denominador en el cierre),
  `apps/api-python/tests/test_auto_v74_producer_seam.py` (**nuevo**).
- `apps/api-python/scripts/v2_44_mutation_audit.py`: **`M200`** nueva (matriz **200/200**); `M199`
  actualizada al fragmento `evidence_gap`.
- `.github/workflows/python-ci.yml` y `.github/workflows/release-tag-ci.yml`: registran
  `test_paper_material_readiness.py` en la compuerta `quality` (antes no corría en CI).
- bump `1.98.0-beta` → **`1.99.0-beta`**.

**No cambia.**

- **El worker congelado** `auto_simulation_worker.py`: intacto (la reparación fue en el **store**).
- **El histórico legacy**: sin backfill; la cuenta histórica conserva `cycle_id=NULL`.
- **El productor de estadística**: no se corre `AUTO-22`; no se toca el `exit 2` de
  `paper_cycles_export.py` / `auto_evidence_run.py`.
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`; `portfolio_optimizer.py`,
  `portfolio_reservation.py`, `auto_adaptive.py`, `auto_adaptive_journal.py` intactos. **Sin migración**
  (`046_fill_reference_mid`).
- **`evidence_runs`/`evidence_validations`** y `governor.json`: intactos.
- **La UI**: no cambia en esta fase.

## 3. Mutación nueva

| Etiqueta | Invariante | Rojo en |
|---|---|---|
| **M200** | El gate **no** puede declarar `PRODUCER_READY` ignorando sus `producer_blockers` (sin linaje, sin reservas, sin cierres, sin salidas o sin denominador) | `test_legacy_path_leaves_no_structure_and_stays_blocked`, `test_a_complete_structure_without_exit_orders_is_blocked_when_measured`, `test_a_released_entry_without_a_preserved_risk_stays_unmeasured`, `test_a_sell_reservation_does_not_become_the_denominator`, `test_legacy_material_is_blocked_and_declares_every_missing_link`, `test_the_payload_declares_its_seal_and_the_declared_minimum` |

**Nota de conteo:** la matriz pasa de `199` a **`200`** (`M1`–`M200` contiguos; el script la autoreporta
con `len(MUTATIONS)`). `M199` se ajustó al fragmento refactorizado (`evidence_gap = ...`).

## 4. Compuertas medidas

| Compuerta | Comando | Resultado |
|---|---|---|
| `ruff` | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `import-linter` | `uv run --no-sync lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `mypy` | `uv run --no-sync mypy <5 paths> --follow-imports=silent` | **Success: 0 issues in 502 source files** |
| `analytics` + `application` | `uv run --no-sync pytest packages/py/analytics packages/py/application -q` | **3230 passed** (181 s; incluye los 13 puros del gate) |
| costura `api-python` | `uv run --no-sync pytest apps/api-python/tests/test_auto_v74_producer_seam.py -q` | **5 passed** (hermético) |
| Matriz de mutaciones | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` | **200/200**, restauración **byte a byte**, árbol intacto |
| `evidence_runs/` | `Test-Path evidence_runs` | **NO existe** (el gate es read-only) |

> **Evidencia cruda de la matriz**: `evidencia-matriz-mutaciones-v2.74-200-2026-09-26.txt`.
> **Nota de entorno:** la corrida offline completa de `apps/api-python` incluye 3 tests **DB-gated**
> (`test_tax_report_after_round_trip_trade`, `test_auto_v70_auto23_evidence_validation.py::…real_postgres…`,
> `test_workspaces_crud`) que dependen de PostgreSQL con datos; son **ajenos** a esta fase.

## 5. El productor contra el material real (resultado declarado)

Medición contra `bolsa-postgres` (`2026-09-26`). Evidencia cruda en
`evidencia-material-producer-v2.74-2026-09-26.txt`.

El harness `v2_74_paper_producer_evidence.py` conduce el camino REAL
(`AutoSimRuntime` → `worker.real_turn`) con un decider determinista y un `price_script` controlado,
sobre **dos cuentas PAPER nuevas** (una por brazo) y compara **solo estructura**:

| | LEGACY (V2 OFF) | V2 (AUTO 2.0 ON) |
|---|---|---|
| fills | 8 | **8** |
| `cycle_id` | 0 | **8** |
| closed cycles | 0 | **1** |
| reservations | 0 | **2** |
| exit orders (con `cycle_id`) | 0 | **1** |
| R measurable | 0 | **1** |
| veredicto | `BLOCKED` | **`PRODUCER_READY`** |
| blockers | `no cycle lineage` · `no reservations` · `no closed cycles` · `no measurable risk` · `no exit orders` · `producer path not exercised` · `insufficient measurable cycles per strategy` | `insufficient measurable cycles per strategy` |

Cuentas: LEGACY `ea1f0f17b8ee4365b6032cd0b` · V2 `1584664bdbcf4a8dab1c811b8` (`2026-09-26`).

**Lectura:** el arm LEGACY reproduce el material de `v2.72` (fills sin linaje, sin reservas, sin R); el
arm V2 **acuña la estructura completa**. El gate declara **`PRODUCER_READY`** (y **no** `EVIDENCE_READY`:
la muestra es corta, y se declara sin rebajar el mínimo).

**Hallazgo declarado (harness, no productor).** La primera corrida leyó `0` fills porque el decider
sintético **no atribuía** `strategy_version_id` (`DecisionPackage.source`) y el edge report estaba
sembrado bajo `"unversioned"`; el material V2 **sí** nacía con `cycle_id`, reservas y exit (verificado por
SQL directo), pero el gate —que lee por versión pedida— no podía MEDIRLO. El arreglo es **del harness**
(decider con `source="active-strategy:<v>"` y edge sembrado bajo esa versión), la MISMA vía que un decider
de producción: **el productor no se toca** y no se declara ninguna excepción de freeze. La reparación de
V2.74 es la del **denominador de R** en el **store** (`reservation_store.py`, no congelado): sin ella
`measurableR` sería `0` (la reserva liberada perdería el riesgo comprometido).

## 6. Compuertas de test (detalle)

- `packages/py/application/tests/test_paper_material_readiness.py`: **13** tests puros (dos niveles,
  exits medidos/no inventados, totales de tabla, reserva liberada con/sin denominador, sello y mínimo).
- `apps/api-python/tests/test_auto_v74_producer_seam.py`: **5** tests herméticos (V2 produce estructura
  → `PRODUCER_READY`; legacy bloqueado; sin backfill; nivel `producer` del CLI; JSON con dos niveles y
  sello).
- `packages/py/application/tests/test_portfolio_reservation.py`: incluye el caso del **denominador de R
  conservado en el cierre** (liberación total y escalera parcial).

## 7. Límite declarado

Esta fase garantiza y declara que el material está **correctamente formado**; **no** acumula `≥32`
ciclos medibles por estrategia ni corre `AUTO-22`. **`P3-2`** (correlación por cubos) y **`P3-3`**
(`P(R>0)` vs N) siguen **abiertas** hasta el primer dataset real. No hay UI en esta fase.

## 8. CI del tag `v2.74-beta` (verificado)

`main == 524538d4` == **tag anotado `v2.74-beta`** (el commit de fase; feat `ade26ada` + docs encima).

| Workflow (tag `v2.74-beta`, commit `524538d4`) | Run | Resultado |
|---|---|---|
| **Release tag CI** | `36248656947` | **GREEN en la primera pasada** (7m15s; 10 jobs en success + `certify`; `playwright (integrated E2E, opt-in)` **skipped** por diseño) |
| `Python CI` | `36248656943` | **success** (2m14s) |
| `Frontend CI` | `36248656985` | **success** (2m25s) |
| `Optimize lab` | `36248656959` | **success** (1m8s) |
| `Fase 2 scientific` | `36248657058` | **success** (1m14s) |

Sobre el mismo commit, en `main` (push `524538d4`): `Python CI` `36248618829` · `Frontend CI`
`36248618794` · `Optimize lab` `36248618844` · `Fase 2 scientific` `36248618843` · `Gitleaks`
`36248618884`, todos en **success**.
