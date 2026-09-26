# Arranque del auditor — `v2.72-beta` · cierre de `P3-4`

> **AsOf:** 2026-09-26 · **Tag a auditar:** `v2.72-beta` (`1.97.0-beta`) · **Base:** `v2.71-beta`
> **Commit sellado:** `0f8cc888` (feat `02bd2066` + docs encima) · **Tag anotado** objeto `82b231d3`
> · **Publicado** en `origin/main`
> **`Release tag CI`:** run `36241408164` **GREEN en la primera pasada** (8m07s, `intento=1`, **10 jobs**
> + `certify`; `playwright (integrated E2E, opt-in)` skipped por diseño). Sobre el mismo commit y tag:
> `Python CI` `36241408161`, `Frontend CI` `36241408114`, `Optimize lab` `36241408122` y
> `Fase 2 scientific` `36241408179`, todos **success** (`intento=1`).
> **Naturaleza:** **corrección del instrumento** (un nivel publicado), no estadística nueva.
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca** (`auto18-v1` / `auto15-v1`).
> **Origen:** `P3-4`, la **única** observación de la auditoría externa de `v2.71-beta`.

## Qué se pide verificar

Auditar el código **sellado**, no la narración. Tesis a comprobar (idealmente reproduciendo el rojo del
invariante y restaurando byte a byte):

### El cierre de `P3-4`

1. **El `level` publicado es el clampeado.** `build_current_regime_evidence` publica
   `min(max(level, 0.5), 0.99)`, **no** el crudo. Reconstruye el defecto original
   (`resolved_level = level`) y comprueba que la lectura publica `0.0` mientras el bootstrap mide con
   `0.5`. **M198 debe morder.**
2. **No hay segunda aritmética.** Con `level=0.0`, la celda publicada (`evidence_for(v)`) es
   **idéntica** a la que produce `level=0.5` explícito; y con `level=5.0`, idéntica a `level=0.99`.
3. **El hueco declarado también se clampa.** Con **cero** ciclos, la lectura vacía publica
   `level == ADAPTIVE_INTERVAL_LEVEL_MIN` (no el crudo) y `notes == ("no_cycles",)`.
4. **El sello sube a `current_regime_evidence_v3`.** Comprueba que **ningún** consumidor del repo
   afirma el literal `current_regime_evidence_v2` (grep del árbol) y que el test fija el **literal**
   nuevo (no solo la constante).
5. **Con el `level` default (`0.90`) el payload no cambia.** El clamp es idempotente dentro del rango:
   el `byStrategy`, la `P(R>0)` por ciclos, la `P(edge>0)`, los `notes` y el régimen seleccionado son
   los de `v2.71`.

### Freeze / integridad

6. **El freeze está intacto**: diff **vacío** en `portfolio_optimizer.py`,
   `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
   `auto_adaptive_journal.py`, `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y `DATA_GATE_POLICY_VERSION`
   (`auto15-v1`).
7. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
8. **La lectura no reparte**: la evidencia del régimen no toca sizing, plan, reserva ni rotación; no
   se toca `evidence_runs`/`evidence_validations` ni el runbook.
9. **Matriz de mutaciones completa** (**198/198**) con restauración **byte a byte** y `git status`
   idéntico; sin fragmentos ausentes. Evidencia cruda persistida:
   `evidencia-matriz-mutaciones-v2.72-198-2026-09-26.txt`.

### El RUN PAPER (verificar la DECLARACIÓN, no una corrida)

10. **El RUN se declaró BLOQUEADO, no se fingió.** Comprueba que `evidence_runs/` **no** existe en el
    repo y que el material del entorno auditado no sostiene la corrida. Si tienes PostgreSQL con
    material real, **re-ejecuta** el runbook: un RUN con `exit 2` es el resultado correcto sin
    material; un bundle con umbrales rebajados sería el hallazgo.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
uv run pytest packages/py/analytics/tests/test_auto_adaptive_regime_evidence.py -q
uv run pytest packages/py/analytics -q
uv run pytest apps/api-python/tests/test_auto_v60_auto19_uncertainty_seam.py apps/api-python/tests/test_auto_v64_auto20c_artifact.py apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M198
```

## Reglas de la casa a recordar

- El nivel que se publica es el que se **usó** (clampeado). Vale para el informe de replay **y** para
  la lectura del régimen.
- Un nombre, un funcional: `P(R>0)` es **ciclos**; `P(edge>0)` es **medias**. No se intercambian.
- Lo que no se midió se **declara** (`None` + `cellsUnmeasured`); nunca evidencia negativa ni un `0`.
- Un contrato que no puede fallar **no es un contrato**: el invariante viaja con su mutación
  (**M198**) y la prueba de que **muerde**.
- **La corrida se ejecuta completa o se declara BLOQUEADA**; sin material **no** se baja ningún umbral.
- No se toca el freeze ni el reparto. **Sin migración.**
