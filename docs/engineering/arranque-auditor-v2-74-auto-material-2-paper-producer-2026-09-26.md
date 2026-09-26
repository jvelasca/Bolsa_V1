# Arranque del auditor — `v2.74-beta` · `AUTO-MATERIAL-2`: PAPER PRODUCER

> **AsOf:** 2026-09-26 · **Tag a auditar:** `v2.74-beta` (`1.99.0-beta`) · **Base:** `v2.73-beta`
> **Naturaleza:** **activación y control del productor** AUTO 2.0 (material PAPER nuevo con estructura) +
> veredicto de **dos niveles**. **No** estadística nueva, **no** `AUTO-22`, **no** backfill del histórico.
> **SIN migración** (head `046_fill_reference_mid`). **`auto18-v1` / `auto15-v1` intactos**;
> `auto_simulation_worker.py` **intacto**.

## Qué se pide verificar

Auditar el código **sellado**, no la narración. La tesis central es que el camino V2 **acuña estructura**
sin tocar el material legacy, que el gate **distingue "bien formado" de "suficiente"**, y que el
**denominador de R sobrevive al cierre**.

### El productor V2 acuña estructura (no la repara)

1. **Costura real (hermética).** `test_v2_producer_leaves_structure_that_the_gate_declares_producer_ready`
   conduce `worker.auto_turn()` con stores in-memory y V2 ON: el fill hereda `cycle_id`, la reserva es
   durable y el exit deja INTENT con `cycle_id`. El veredicto es `PRODUCER_READY` (y **no**
   `EVIDENCE_READY`: la muestra es corta).
2. **El camino LEGACY no deja estructura.** `test_legacy_path_leaves_no_structure_and_stays_blocked`:
   V2 OFF ⇒ `fillsWithCycle == 0`, `reservations == 0`, `exitOrdersWithCycle == 0` ⇒ el gate lo DECLARA
   (`BLOCKED`), no lo "arregla".
3. **Inmutabilidad legacy.** `test_v2_producer_never_backfills_the_frozen_legacy_material` siembra un fill
   legacy (`cycle_id=None`), corre el productor V2 sobre el mismo libro y comprueba que la fila histórica
   **no** se toca y que el material NUEVO sí nace con linaje. **Ningún `UPDATE` de backfill.**

### El denominador de R sobrevive al cierre

4. **La liberación conserva el riesgo comprometido.** `reservation_store.py::_committed_risk` guarda
   `reserved_risk × quantity / remaining_qty` en la **fila durable** de la reserva liberada, mientras el
   **objeto devuelto** y el **libro vivo** siguen escalando a `0`/escalado. Verifica que
   `test_portfolio_reservation.py` cubre liberación total y escalera parcial, y que
   `test_a_released_entry_reservation_still_supplies_the_denominator` pasa de `measurableCycles == 0` a
   `> 0`.
5. **Sin riesgo no hay denominador inventado.** `test_a_released_entry_without_a_preserved_risk_stays_unmeasured`
   y `test_a_sell_reservation_does_not_become_the_denominator`: la ausencia se declara, no se rellena.

### Doble nivel fail-closed

6. **`PRODUCER_READY` exige estructura.** `producer_blockers` nombran cada eslabón (`no cycle lineage`,
   `no reservations`, `no closed cycles`, `no measurable risk`, `no exit orders`,
   `producer path not exercised`). **M200** muerde: con los `producer_blockers` ignorados, el gate daría
   `PRODUCER_READY` a un material mal formado; reproduce el rojo y **restaura byte a byte**.
7. **`EVIDENCE_READY` exige mínimo.** `EVIDENCE_READY ⇒ PRODUCER_READY`; bajo mínimo el veredicto es
   `PRODUCER_READY` con `insufficient measurable cycles per strategy`. **M199** muerde. El mínimo `≥32` es
   declarado y **no rebajable**.
8. **Lo no medido se declara.** `lineage.cycle.exitOrders` sin lectura es `None`, **nunca** un `0` de
   relleno; una lectura de reservas posiblemente truncada se declara (`reservationsReadComplete`).

### El CLI y el contrato de superficie

9. **Niveles y códigos.** `--level producer` distingue "bien formado" de "suficiente"; `0` = nivel pedido
   alcanzado, `2` = BLOCKED, `1` = uso incorrecto; guarda de venue `BROKER_VENUE=paper`; `--json` con el
   sello `paper_material_readiness_v2` y los dos niveles (`producerReady` / `evidenceReady`).
10. **Tres poblaciones.** `DATABASE TOTAL` (tabla entera), `INSTRUMENT UNIVERSE` (cuenta, todas las
    versiones) y `AUTO MATERIAL` (versiones pedidas). La población total es **informativa** y no cambia el
    veredicto (lo fija un test).
11. **Es un pre-flight separado.** El gate **no** modifica el `exit 2` de `paper_cycles_export.py` ni de
    `auto_evidence_run.py`, y **no** escribe en `evidence_runs/` / `evidence_validations/` /
    `governor.json`.

### El material real: verificar la MEDICIÓN, no una corrida

12. **El harness reproduce el A/B.** Con PostgreSQL y material real, re-ejecuta:
    ```bash
    uv run --no-sync python apps/api-python/scripts/v2_74_paper_producer_evidence.py --json \
        --out docs/engineering/evidencia-material-producer-v2.74-2026-09-26.txt
    ```
    El arm LEGACY reproduce el material de `v2.72` (sin linaje, sin reservas, sin R); el arm V2 declara
    `PRODUCER_READY`. Si un auditor "arreglara" material para forzar `EVIDENCE_READY`, ese sería el
    hallazgo.
13. **El gate no repara.** `paper_material_readiness.py` **no** infiere `cycle_id`, **no** construye
    reservas, **no** sustituye el denominador por capital/equity/nominal y **no** convierte N fills en N
    operaciones. Debe quedar **demostrado por el código**.

### Freeze / integridad

14. **El freeze está intacto**: diff **vacío** en `portfolio_optimizer.py`, `portfolio_reservation.py`,
    `auto_adaptive.py`, **`auto_simulation_worker.py`**, `auto_adaptive_journal.py`, `ADAPTIVE_POLICY_VERSION`
    (`auto18-v1`) y `DATA_GATE_POLICY_VERSION` (`auto15-v1`). La única reparación es en
    `reservation_store.py` (**store**, no congelado) y está declarada.
15. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
16. **Matriz de mutaciones completa** (**200/200**) con restauración **byte a byte** y `git status`
    idéntico; sin fragmentos ausentes. Evidencia cruda persistida:
    `evidencia-matriz-mutaciones-v2.74-200-2026-09-26.txt`.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
uv run pytest packages/py/application/tests/test_paper_material_readiness.py -q
uv run pytest packages/py/application/tests/test_portfolio_reservation.py -q
uv run pytest apps/api-python/tests/test_auto_v74_producer_seam.py -q
uv run pytest packages/py/analytics packages/py/application -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M199 M200
```

## Notas para el auditor

- El **diff `v2.74-beta` → `main`** puede contener **solo docs** (la cita del CI y este arranque). El
  código auditado es el del **tag**; si el diff no fuera docs-only, sería un hallazgo.
- La corrida offline completa de `apps/api-python` incluye **3 tests DB-gated** ajenos a esta fase
  (`test_tax_report_after_round_trip_trade`, `test_auto_v70_auto23_evidence_validation.py::…real_postgres…`,
  `test_workspaces_crud`): dependen de PostgreSQL con datos y **no** forman parte de la compuerta.

## Reglas de la casa a recordar

- El productor **acuna** material nuevo; **jamás** reescribe el histórico (sin backfill de `cycle_id`).
- `PRODUCER_READY` = "bien formado"; `EVIDENCE_READY` = "bien formado **y** suficiente". No se confunden.
- Lo que no se midió se **declara** (`None`); nunca un `0` de relleno.
- Un contrato que no puede fallar **no es un contrato**: el invariante viaja con su mutación (**M199**,
  **M200**) y la prueba de que **muerde**.
- **La corrida se ejecuta completa o se declara BLOQUEADA**; sin muestra **no** se baja ningún umbral.
- No se toca el freeze ni el reparto. **Sin migración.**
