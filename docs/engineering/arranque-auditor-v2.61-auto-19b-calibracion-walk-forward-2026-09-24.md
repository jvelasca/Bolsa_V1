# Arranque del auditor — `v2.61-beta` (`AUTO-19B`) · 2026-09-24

**Qué auditas:** la fase `V2.61` / `AUTO-19B` «Calibración del intervalo y Walk-Forward», cerrada sobre
el tag **`v2.61-beta`** (`1.86.0-beta`). **Sin migración.** El flag Adaptive sigue **OFF**.

**Documentos de la fase:** [plan](./plan-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[relevo](./traspaso-relevo-post-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md).

## El prompt para arrancar (cópialo tal cual)

> Trabajas en `Bolsa_V1` como **auditor externo** de la fase `V2.61` / `AUTO-19B`. **No improvises el
> método**: el repo tiene un protocolo y se sigue.
>
> 1. Lee el [plan de la fase](./plan-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) y el
>    [audit-pack](./audit-pack-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) (qué se midió y
>    qué **no**).
> 2. Comprueba el estado real del árbol (`git status`, `git log --oneline -5`, la head de Alembic y
>    `_ALEMBIC_HEAD`) **antes** de creerte nada de este documento.
> 3. Ejecuta las compuertas con **el comando de CI** (`ruff check packages/py apps/api-python --config
>    pyproject.toml`; el `mypy` exacto del YAML; `lint-imports --config packages/py/.importlinter`).
>    En esta máquina los tests se corren con `uv run --no-sync python -m pytest` (`uv run pytest` lo
>    bloquea la directiva de Control de aplicaciones).
> 4. Reproduce la sonda de mutaciones del tramo: `uv run --no-sync python
>    apps/api-python/scripts/v2_44_mutation_audit.py M159 M160 M161 M162 M163 M164` y, si quieres el
>    cierre, la matriz completa.
>
> ## Qué atacar primero (las trampas que esta fase debería haber cerrado)

1. **¿El walk-forward se contamina?** Si el IS de un pliegue contuviera su OOS, la "predicción" vería
   el futuro. Comprueba que `split_walk_forward_folds` devuelve tramos **contiguos y disjuntos** y que
   las ventanas **crecen** (M159/M164).
2. **¿La cobertura se mide o se afirma?** Una celda **sin** intervalo no puede entrar en la muestra de
   `interval_coverage` (ni como cubierta ni como descubierta). Comprueba el filtro (M160) y que la
   comparación no esté invertida (M161).
3. **¿Se fabrican veredictos sin muestra?** Cada pregunta declara su `sample`; comprueba que
   `interval_coverage`, `edge_sign_calibration` y `confidence_calibration` quedan `inconclusive` sin
   los dos grupos/el mínimo (M162).
4. **¿Un solo pliegue se llama walk-forward?** La acotación de pliegues debe impedir `folds < 2`
   (M163).
5. **¿Se tocó la regla?** El sello del reparto debe seguir en **`auto18-v1`** y el journal durable
   **byte a byte** igual; la calibración es evidencia **read-only**. Sin `--walk-forward`, el CLI de
   `AUTO-19A` debe emitir **el mismo JSON**.
6. **¿Se rompió `AUTO-19A`?** El `ReplayReport` del fixture de la fase anterior debe seguir dando las
   mismas 6 celdas (la extracción de `measure_is_oos_row` es aditiva).

## Lo que esta fase NO demuestra (dilo sin rodeos si el cierre lo disfraza)

- Que la estrategia real tenga edge: el fixture es **sintético y declarado**; mide el instrumento.
- Que el intervalo esté bien calibrado **en datos reales**: la cobertura que se publica es la del
  material que se le dé.
- Que `P(R > 0)` exista: **no** se implementa aquí (deuda declarada).
- Que la calibración mueva el reparto: **no** lo mueve, por contrato.

## Compuertas que no se pueden saltar

- Compuertas con el comando de CI y tests con `uv run --no-sync python -m pytest`.
- Matriz completa `M1…M164` con restauración byte a byte y huella `git status` idéntica.
- Delta **simétrico** fichero a fichero contra `HEAD` de los tests tocados (no se restan totales).
