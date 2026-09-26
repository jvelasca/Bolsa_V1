# Arranque del auditor — `v2.70-beta` (`AUTO-23`)

> **AsOf:** 2026-09-25 · **Tag a auditar:** `v2.70-beta` (`1.95.0-beta`) · **Base:** `v2.69-beta`
> **Naturaleza:** fase de **preparación y blindaje**, no de decisión. **SIN migración**
> (head `046_fill_reference_mid`). **El freeze no se toca** (`auto18-v1` / `auto15-v1`).

## Qué se pide verificar

Auditar el código **sellado**, no la narración. Tesis a comprobar (idealmente reproduciendo el rojo de
cada invariante y restaurando byte a byte):

### UI (punto 22 de la auditoría de `v2.69`)

1. **`EXECUTION REALITY` existe y separa** virtual de dinero real: un artefacto `paper_real` con
   `executionReality="virtual_paper_only"` muestra `VIRTUAL — NO REAL MONEY`; un
   `realMoneyAtRisk=true` **no** se degrada a virtual (`desconocido`, tono de peligro). Ver
   `classifyExecutionReality` en `auto-evidence-report.ts`.
2. **`SOURCE` separa dato de moneda**: `PAPER REAL` viaja con el subtítulo
   "… · DINERO VIRTUAL · NO ES DINERO REAL".
3. **Nunca se degrada** `desconocido` ⇒ `paper_real`; `materialOrigin` contradictorio sigue siendo
   `desconocido`.
4. La UI **lee**, no recalcula: `null` ⇒ `NO MEDIDO`; jamás `0.0000` para una correlación no medida.

### Harness de validación (`AUTO-23`)

5. **Una sola aritmética**: `build_sample_size_sweep` **compone** `build_evidence_run_bundle` y copia
   `P(R>0)`/OOS/WFE/`effective_n`. La mutación **M191** (recalcular `P(R>0)`) debe **morder**.
6. **`NO MEDIDO` de verdad**: un `N` mayor que el material medido ⇒ fila `NO MEDIDO` (no fabricada).
   La mutación **M192** debe **morder**.
7. **No hay umbral ni selección de `N`**: el barrido publica la serie para observar estabilidad.
8. **Estabilidad de régimen = lectura**: publica veredicto global vs por régimen y sus divergencias;
   **no** bloquea ni mueve el reparto.
9. **Diagnósticos `P3-2`**: junto al número de correlación se publican frecuencia/exposición
   (`singleCycleBucketShare`, cubos activos); la **métrica de correlación no se toca**.
10. **Fail-closed e inmutabilidad** del CLI `auto_evidence_validate.py`: sin ciclos con R medible ⇒
    `exit 2` **sin escribir ningún fichero**; validación ya existente ⇒ `exit 2`.
11. **Un solo lector de material**: el validador usa `bolsa_application.auto_paper_material.read_paper_material`
    (el mismo del RUN y del exportador).

### Freeze / integridad

12. **El freeze está intacto**: diff **vacío** en `portfolio_optimizer.py`,
    `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
    `auto_adaptive_journal.py`, `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y `DATA_GATE_POLICY_VERSION`
    (`auto15-v1`).
13. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
14. **La evidencia no reparte**: `ALLOCATION = none`; `P(R>0)`, correlación y régimen no tocan sizing,
    plan, reserva ni rotación.
15. **Matriz de mutaciones completa** con restauración **byte a byte** y `git status` idéntico; sin
    fragmentos ausentes. Evidencia cruda persistida:
    [`evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt`](./evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt)
    (`192/192` medidas, `192/192` rojas, árbol intacto).

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
uv run pytest packages/py/application packages/py/analytics -q
uv run pytest apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M191 M192
```

## Reglas de la casa a recordar

- Un número sin muestra suficiente es **`NO MEDIDO`**, nunca un `0` disfrazado de lectura. Vale para
  `P(R>0)`, para la correlación (`None` + nota) y para los conteos.
- El RUN y la VALIDACIÓN **o** producen el bundle completo **o** se declaran `BLOQUEADOS`: nunca un
  fichero a medias.
- Una corrida/validación es **inmutable**: no se sobrescribe una medición.
- Un contrato que no puede fallar **no es un contrato**: cada invariante viaja con su mutación
  (**M191/M192**) y con la prueba de que **muerde**.
- La UI **lee y presenta**; nunca recalcula.
- No se toca el freeze ni el reparto. **Sin migración.**
- **`PAPER REAL` = datos reales con DINERO VIRTUAL**, nunca dinero real.
