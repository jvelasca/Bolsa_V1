# Arranque del agente — post `v2.68-beta` (`AUTO-21`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.68-beta` (`1.93.0-beta`) · **Base:** `v2.67-beta`

## Contexto en una frase

`v2.68` (`AUTO-21`) **mide y publica** tres lecturas que antes no existían —la **`P(R>0)`** por bootstrap,
la **correlación entre estrategias por cubo temporal** y la **evidencia del régimen actual** por estrategia—
sin mover el reparto (`auto18-v1` congelado) ni añadir migración.

## Estado verificado

- Frontend **1327 passed** (232 ficheros), `typecheck` OK, `lint` **0 errores** (23 warnings), `build` OK,
  `contract:check` OK.
- Python analytics **1238 passed**, `ruff` **All checks passed!**, `import-linter` **4 kept / 0 broken**.
- Matriz de mutaciones ampliada con **M182…M187**; corrida **completa 187/187** sin huecos.
- **Flake ajeno declarado:** `backtests/core-r-scheduler.test.ts` agota su timeout de 5 s bajo la carga de
  la suite completa (fichero sin tocar; aislado pasa; con `--testTimeout=30000` la suite va verde).

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| La corrida PAPER real (material) | **abierta** — paso operativo del propietario |
| La correlación/régimen moviendo el reparto | **fuera de alcance por decisión** (solo medición) |
| `backtests/core-r-scheduler.test.ts` bajo carga | **flake ajeno declarado**; no se toca en una fase de medición |

## Qué queda por hacer (elegir)

1. **La corrida PAPER real** — paso operativo del propietario (bloqueo por **material**).
2. Usar la evidencia ya publicada para **decidir** algo (sizing, gating de régimen, restricción por
   correlación): hoy es una decisión **de producto**, no de medición, y **no** está tomada.
3. La UI de la matriz de correlación (hoy se publica en el render y en el bloque del artefacto).

## Reglas de la casa a recordar

- Un número sin muestra suficiente es **`NO MEDIDO`**, nunca un `0` disfrazado de lectura. Vale para la
  probabilidad (`None`) y para la correlación (`None` + nota).
- Un contrato que no puede fallar **no es un contrato**: cada invariante nuevo viaja con su mutación
  (**M182…M187**) y con la prueba de que **muerde**.
- La UI **lee y presenta**; nunca recalcula. `null`/no-lista ⇒ `NO MEDIDO`; veredicto ausente ⇒
  `INCONCLUSIVE`.
- No se toca el freeze ni el reparto (`auto18-v1`/`auto15-v1`). **Sin migración** (head
  `046_fill_reference_mid`).

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/analytics -q
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M182 M183 M184 M185 M186 M187
```
