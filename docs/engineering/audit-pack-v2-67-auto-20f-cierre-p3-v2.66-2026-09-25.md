# Audit-pack — `v2.67-beta` (`AUTO-20F`) · cierre de las 2 P3 de `v2.66`

> **AsOf:** 2026-09-25 · **Versión:** `1.92.0-beta` · **Base auditada (diff):** `v2.66-beta` (`6fe7faa8`)
> **Alcance:** las 2 P3 de la auditoría de `v2.66-beta`. Fase corta de precisión; sin producto nuevo.
> **SIN migración.** **El freeze no se toca.**

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | P3-1: la sobre-afirmación documental está **corregida** | `plan`/`audit-pack` de `v2.66` (nota de corrección) | lectura de los docs |
| 2 | M180 **no** cubre el contrato TS-vs-Python (es el render Python) | `v2_44_mutation_audit.py` (M180) + salida de la matriz | `M180` → rojo en tests **Python** |
| 3 | P3-2: no-lista ⇒ `NO MEDIDO` en **Python** | `auto_evidence_report.py` `_version_list` | `test_the_render_treats_a_non_list_perimeter_value_as_not_measured` + **M181** |
| 4 | P3-2: no-lista ⇒ `NO MEDIDO` en **TS** (espejo) | `auto-evidence-report.ts` `listLabel`/`isMeasuredList` | `treats a non-list perimeter value as not measured (mirror of Python)` |
| 5 | El render de artefactos reales **no cambia** | listas siempre presentes en la cadena real | lectura del exportador |
| 6 | El freeze sigue intacto y no hay migración | `git diff` del freeze; Alembic head | verificación git + `046_*` |

## 2. Qué cambia (y qué no)

**Cambia.**
- `_version_list` (Python) y `listLabel`/`isMeasuredList` (TS): **no-lista ⇒ `NO MEDIDO`**.
- Redacción del `plan`/`audit-pack` de `v2.66` (P3-1), con nota de corrección.
- Matriz de mutaciones: **M181**.
- `package.json`/`CHANGELOG`: bump a `1.92.0-beta`.

**NO cambia.**
- El esquema del artefacto, el invariante PAPER=virtual, el reparto (`auto18-v1`/`auto15-v1`), el freeze, la
  migración. Para artefactos reales (listas siempre presentes) la salida es **idéntica**.

## 3. Compuertas a re-ejecutar

| Compuerta | Comando | Esperado |
|---|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` | **1324 passed** |
| Frontend typecheck/lint | `pnpm --filter @bolsa/web typecheck` · `... lint` | OK · 0 errores |
| Frontend build/contrato | `pnpm --filter @bolsa/web build` · `... contract:check` | OK · OK |
| Python analytics | `uv run pytest packages/py/analytics -q` | **1209 passed** |
| Ruff / import-linter | `uv run ruff check packages/py apps/api-python` · `uv run lint-imports --config packages/py/.importlinter` | OK · 4 kept / 0 broken |
| Mutaciones | `.../v2_44_mutation_audit.py M179 M180 M181` | las tres **muerden** |
| Matriz completa | `.../v2_44_mutation_audit.py` | **181/181**, 0 sin fragmento |

## 4. Nota de alcance para el auditor

- **P3-1 es documental**: su «prueba» es la lectura de los documentos corregidos, no una compuerta.
- **P3-2 en TS** es **vitest** (no la matriz pytest); su espejo Python **sí** entra en la matriz (**M181**).
- La corrección del texto del `plan`/`audit-pack` de `v2.66` **no** re-sella `v2.66` (tag inmutable): el diff
  `v2.66..v2.67` la mostrará como cambio de docs.
