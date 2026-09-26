# Arranque del auditor — `v2.71-beta` (`AUTO-19A`+`AUTO-19B`)

> **AsOf:** 2026-09-26 · **Tag a auditar:** `v2.71-beta` (`1.96.0-beta`) · **Base:** `v2.70-beta`
> **Commit sellado:** `a310fbc5` (feat `0c2f5014` + docs encima) · **Publicado** en `origin/main`
> **`Release tag CI`:** run `36236375738` **GREEN en la primera pasada** (8m13s, `intento=1`, 10 jobs +
> `certify`; `playwright (integrated E2E, opt-in)` skipped). Sobre el mismo commit y tag: `Python CI`
> `36236375798`, `Frontend CI` `36236375770`, `Optimize lab` `36236375716` y `Fase 2 scientific`
> `36236375788`, todos **success**.
> **Naturaleza:** **corrección del instrumento**, no estadística nueva. **SIN migración**
> (head `046_fill_reference_mid`). **El freeze no se toca** (`auto18-v1` / `auto15-v1`).

## Qué se pide verificar

Auditar el código **sellado**, no la narración. Tesis a comprobar (idealmente reproduciendo el rojo de
cada invariante y restaurando byte a byte):

### H1 — las dos probabilidades

1. **`P(edge>0)` = fracción de MEDIAS bootstrap `> 0`.** Renombrada a `edge_positive_probability`
   (`edgePositiveProbability`). M183 debe **morder**.
2. **`P(R>0)` = fracción de CICLOS medidos con `R>0`.** Nueva `cycle_positive_share`
   (`cyclePositiveShare`), estricta; **sobrevive sin bootstrap**. M193 debe **morder**.
3. **Divergen**: un test con 18 aciertos pequeños y 2 pérdidas grandes da `P(ciclo>0) = 0.9` y
   `P(edge>0) < 0.5`. No son intercambiables.
4. **Sin bootstrap**, `edgePositiveProbability = None` pero `cyclePositiveShare` existe (huecos
   declarados, no ceros).

### Calibración homogénea

5. **`_question_probability_positive` compara `P(ciclo>0)` IS vs frecuencia positiva OOS.** Debe
   **ignorar** `is_edge_positive_probability` aunque esté presente. M194 debe **morder**.
6. La calibración sella **`walk_forward_calibration_v4`** (M184 debe morder). Las claves de la UI
   (`meanDeclaredProbability`, `probabilityPositiveOos`, `probabilityPositive`) **no cambian**.

### Cierre de P3

7. **H2 — cobertura no medida:** `_question_coverage` excluye `dominant_regime_coverage is None` y lo
   declara en **`cellsUnmeasured`**. M195 debe **morder**.
8. **H3 — nivel clampeado:** `build_replay_report` publica el **mismo** nivel que usó el bootstrap
   (`resolved_level`). M196 debe **morder**.
9. **H4 — clave sin colisión:** `ReplayCell.as_dict()` **no** emite `regimeCoverage` (emite
   `dominantRegimeCoverage`); `StrategyConfidence.as_dict()` sí lo emite, como `float`. M197 debe
   **morder**.

### Sellos y consumidores

10. `regimeEvidence.probabilityPositive = P(ciclo>0)` + `edgePositiveProbability` aditivo; sello
    `current_regime_evidence_v2`.
11. `auto_evidence_validation.py`: `probabilityPositive = cycle_positive_share` +
    `edgePositiveProbability`; sellos `auto23_evidence_validation_v2`, `auto23_sample_size_sweep_v2`,
    `auto23_regime_stability_v2`; método `chronological_prefix_sweep_v2`.

### Freeze / integridad

12. **El freeze está intacto**: diff **vacío** en `portfolio_optimizer.py`,
    `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
    `auto_adaptive_journal.py`, `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y `DATA_GATE_POLICY_VERSION`
    (`auto15-v1`).
13. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
14. **La evidencia no reparte**: `P(R>0)`/`P(edge>0)` no tocan sizing, plan, reserva ni rotación; no se
    toca `evidence_runs`/`evidence_validations` ni el runbook.
15. **Matriz de mutaciones completa** (**197/197**; 192 + 5 nuevas — el plan citaba `198` por un
    desliz aritmético) con restauración **byte a byte** y `git status` idéntico; sin fragmentos
    ausentes. Evidencia cruda persistida:
    `evidencia-matriz-mutaciones-v2.71-197-2026-09-26.txt`.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web build
pnpm --filter @bolsa/web contract:check
uv run pytest packages/py/analytics packages/py/application -q
uv run pytest apps/api-python/tests/test_auto_v60_auto19_uncertainty_seam.py apps/api-python/tests/test_auto_v64_auto20c_artifact.py apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M193 M194 M195 M196 M197
```

## Reglas de la casa a recordar

- Un nombre, un funcional: `P(R>0)` es **ciclos**; `P(edge>0)` es **medias**. No se intercambian.
- Lo que no se midió se **declara** (`None` + `cellsUnmeasured`); nunca evidencia negativa ni un `0`.
- El nivel que se publica es el que se **usó** (clampeado).
- Dos intervalos con el mismo aspecto no pueden venir de instrumentos distintos ⇒ **los sellos suben**.
- Un contrato que no puede fallar **no es un contrato**: cada invariante viaja con su mutación
  (**M193–M197**) y la prueba de que **muerde**.
- La UI **lee y presenta**; nunca recalcula.
- No se toca el freeze ni el reparto. **Sin migración.**
