# Arranque del auditor — `v2.73-beta` · `AUTO-MATERIAL-1`: PAPER MATERIAL READINESS

> **AsOf:** 2026-09-26 · **Tag a auditar:** `v2.73-beta` (`1.98.0-beta`) · **Base:** `v2.72-beta`
> **Commit sellado:** `a9166655` (feat `d614e16f` + docs encima) · **Tag anotado** objeto `fd891fcd`
> · **Publicado** en `origin/main`
> **`Release tag CI`:** run `36244779500` **GREEN en la primera pasada** (8m52s, **10 jobs** +
> `certify`; `playwright (integrated E2E, opt-in)` skipped por diseño). Sobre el mismo commit y tag:
> `Python CI` `36244779488`, `Frontend CI` `36244779559`, `Optimize lab` `36244779562` y
> `Fase 2 scientific` `36244779467`, todos **success**. En `main`, sobre el mismo commit:
> `Python CI` `36244778024`, `Frontend CI` `36244778014`, `Gitleaks` `36244778017`,
> `Optimize lab` `36244778000` y `Fase 2 scientific` `36244778040`, **success**.
> **Naturaleza:** **diagnóstico read-only** del material PAPER (un gate + sondas de linaje), no
> estadística nueva y **no** reparación del productor. **SIN migración** (head `046_fill_reference_mid`).
> **El freeze no se toca** (`auto18-v1` / `auto15-v1`).

## Qué se pide verificar

Auditar el código **sellado**, no la narración. La tesis central es que el gate **mide y declara** sin
reparar, y que **no** puede dar luz verde sin material medible.

### El gate mide el MISMO material y no repara nada

1. **Una sola aritmética.** `build_paper_material_readiness` cuenta ciclos cerrados y R medible
   reutilizando `adaptive_instrument_cycles` (= `cycles_from_fills` + `cycle_risk_from_reservations`
   + fricción aplicada). Comprueba que **no** hay un segundo FIFO ni una segunda aritmética de R en el
   módulo nuevo (grep del árbol).
2. **No repara material.** El módulo **no** infiere `cycle_id`, **no** construye
   `PortfolioReservation`, **no** sustituye el denominador por capital/equity/nominal y **no** convierte
   N fills en N operaciones. Debe quedar **demostrado por el código**, no por la prosa: busca en
   `paper_material_readiness.py` cualquier construcción de reserva o de identidad de ciclo.
3. **Sin denominador no hay R.** Con cierres pero **sin** reservas, el gate declara `0` ciclos con R
   medible y `BLOCKED` (motivo `insufficient measurable cycles per strategy`). Una reserva de **venta**
   (`reserved_risk = 0`) **no** es denominador.

### Fail-closed: `READY` exige mínimo medible

4. **`M199` muerde.** Con la guarda mutada a un umbral laxo, el gate devolvería `READY` sin mínimo;
   reproduce el rojo (`pytest packages/py/application/tests/test_paper_material_readiness.py`) y
   **restaura byte a byte**.
5. **El mínimo es declarado y no rebajable.** `≥32` ciclos medibles por estrategia (operativo del
   [protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md), `folds=3`,
   `min_is=8`, `min_oos=4`), parametrizable por `--min-cycles`. Comprueba que **ningún** camino lo baja
   para forzar una corrida.
6. **Lo no medido se declara.** El linaje de exit orders sin lectura es `None` (**no medido**), nunca un
   `0` de relleno; y una lectura de reservas posiblemente truncada se declara
   (`reservationsReadComplete`).

### El CLI y el contrato de superficie

7. **Códigos de salida.** `0` READY · `2` BLOCKED · `1` uso incorrecto; guarda de venue
   `BROKER_VENUE=paper` (una venue distinta ⇒ `2`), y `--json` con el sello
   `paper_material_readiness_v1`.
8. **Es un pre-flight separado.** El gate **no** modifica el `exit 2` de `paper_cycles_export.py` ni
   de `auto_evidence_run.py`, y **no** escribe en `evidence_runs/` / `evidence_validations/` /
   `governor.json` (comprueba que `evidence_runs/` **no** existe tras correrlo).
9. **No hay UI** en esta fase: el JSON queda listo para una pantalla futura, pero `apps/web` no cambia.

### El material real: verificar la MEDICIÓN, no una corrida

10. **El diagnóstico reproduce los hechos de `v2.72`.** Con PostgreSQL y material real, re-ejecuta:
    ```bash
    $env:BROKER_VENUE="paper"
    uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \
        --account-id <cuenta> --strategy-version <v> --json
    ```
    La cuenta del RUN (`181e7e07d27d4cdebc342ff83`) declara **4** fills / **0** `cycle_id` / **0**
    reservas / **0** exit orders y sale `2` con los cinco motivos; la tabla completa, **761** fills
    (**751 `buy` / 10 `sell`**), **0** `cycle_id`, **53** versiones, **0** reservas. El gate **solo
    mide**: si un auditor "arreglara" material para que salga `READY`, ese sería el hallazgo.

### Freeze / integridad

11. **El freeze está intacto**: diff **vacío** en `portfolio_optimizer.py`,
    `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
    `auto_adaptive_journal.py`, `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y `DATA_GATE_POLICY_VERSION`
    (`auto15-v1`).
12. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
13. **Matriz de mutaciones completa** (**199/199**) con restauración **byte a byte** y `git status`
    idéntico; sin fragmentos ausentes. Evidencia cruda persistida:
    `evidencia-matriz-mutaciones-v2.73-199-2026-09-26.txt`.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
uv run pytest packages/py/application/tests/test_paper_material_readiness.py -q
uv run pytest apps/api-python/tests/test_auto_v73_material_readiness_seam.py -q
uv run pytest packages/py/analytics packages/py/application -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M199
```

## Notas para el auditor

- El **diff `v2.73-beta` → `main`** puede contener **solo docs** (la cita del CI y este arranque). El
  código auditado es el del **tag**; si el diff no fuera docs-only, sería un hallazgo.
- La corrida offline completa de `apps/api-python` incluye **3 tests DB-gated** ajenos a esta fase
  (`test_tax_report_after_round_trip_trade`, `test_auto_v70_auto23_evidence_validation.py::…real_postgres…`,
  `test_workspaces_crud`): dependen de PostgreSQL con datos y **no** forman parte de la compuerta.

## Reglas de la casa a recordar

- El material se **mide y se declara**; el gate **no repara** (ni `cycle_id` ni `reserved_risk`).
- `READY` **exige** ciclos cerrados con denominador positivo por encima del mínimo. Sin material, el
  veredicto correcto es **BLOCKED**.
- Lo que no se midió se **declara** (`None`); nunca un `0` de relleno.
- Un contrato que no puede fallar **no es un contrato**: el invariante viaja con su mutación
  (**M199**) y la prueba de que **muerde**.
- **La corrida se ejecuta completa o se declara BLOQUEADA**; sin material **no** se baja ningún umbral.
- No se toca el freeze ni el reparto. **Sin migración.**
