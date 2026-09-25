# Arranque del agente — post `v2.67-beta` (`AUTO-20F`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.67-beta` (`1.92.0-beta`) · **Base:** `v2.66-beta` = `6fe7faa8`

## Contexto en una frase

`v2.67` cierra las **2 P3** de la auditoría de `v2.66`: corrige la **sobre-afirmación documental** sobre M180 (el
contrato TS-vs-Python es vitest, no la matriz) y hace que un valor **no-lista** en el perímetro sea `NO MEDIDO`
en **TS y Python** (antes Python iteraba el escalar).

## Estado verificado

- Frontend **1324 passed**, `typecheck`/`lint`/`build`/`contract:check` OK.
- Python analytics **1209 passed**, `ruff` OK, `import-linter` 4/0.
- Matriz ampliada con **M181** (M179/M180/M181 muerden).

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| P3-1 (v2.66) sobre-afirmación M180 | **cerrada** (texto corregido) |
| P3-2 (v2.66) no-lista iterada | **cerrada** (`NO MEDIDO` en TS y Python; M181) |
| P3-1/P3-2/P3-3 (v2.65) | **cerradas** en `v2.66` |
| `governor.json` huérfano | **cerrada** (`.gitignore`) |

## Qué queda por hacer (elegir)

1. **La corrida PAPER real** — paso operativo del propietario (bloqueo por **material**, `cycle_id` NULL en los
   fills locales). **No es un defecto de código.**
2. **`AUTO-21`** — `P(R>0)`, correlación y current-regime gating.

## Reglas de la casa a recordar

- Un contrato que no puede fallar **no es un contrato**: si un test afirma cubrir algo, hay que **demostrar que
  muerde**. Y no se atribuye a una prueba más cobertura de la que tiene (lección de las dos últimas fases).
- La UI **lee y presenta**; nunca recalcula. `null`/no-lista ⇒ `NO MEDIDO`; veredicto ausente ⇒ `INCONCLUSIVE`.
- No se toca el freeze ni el reparto (`auto18-v1`/`auto15-v1`). **Sin migración** (head `046_fill_reference_mid`).

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/analytics -q
```
