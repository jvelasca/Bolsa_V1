# Traspaso / relevo — cierre de `v2.67-beta` (`AUTO-20F`)

> **AsOf:** 2026-09-25 · **Versión:** `1.92.0-beta` · **Fase:** cierre de las 2 P3 de la auditoría de `v2.66`.
> **SIN migración.** **Freeze intacto.**

## Qué se ha hecho

Fase **corta de precisión**, sin producto nuevo: cerrar las dos P3 que la auditoría de `v2.66-beta` dejó abiertas.

1. **P3-1 — Corrección documental.** El `plan`/`audit-pack` de `v2.66` atribuían a **M180** la cobertura del
   contrato TS-vs-Python; **M180** cubre el atado del **render Python**. Redacción corregida con nota explícita.
2. **P3-2 — Espejo exacto.** Un valor **no-lista** en el perímetro ⇒ `NO MEDIDO` en **TS y Python** (antes Python
   iteraba la cadena). Tests en ambos lados + **M181**.

## Estado del sello

- **Tag:** `v2.67-beta` → commit del paquete de fase (ver `arranque-auditor`).
- **Base del diff:** `v2.66-beta` = `6fe7faa8`.
- **`v2.66-beta` permanece intacta**; sus documentos de fase conservan el texto original (tag inmutable) y la
  corrección vive en `main`.

## Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| `pnpm --filter @bolsa/web test` | **1324 passed** |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| `pnpm --filter @bolsa/web build` | OK |
| `pnpm --filter @bolsa/web contract:check` | OK |
| `uv run pytest packages/py/analytics -q` | **1209 passed** |
| `uv run ruff check packages/py apps/api-python` | OK |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones | **M179/M180/M181** muerden |

## Invariantes que NO se tocan

- PAPER = 100 % VIRTUAL; el reparto `auto18-v1`/`auto15-v1`; el freeze; **sin migración**.
- La UI **lee y presenta**: `null` ⇒ `NO MEDIDO`; veredicto ausente ⇒ `INCONCLUSIVE`; y ahora **no-lista ⇒
  `NO MEDIDO`** (no se itera un escalar).

## Pendiente / fuera de alcance

- **La corrida PAPER real**: paso operativo del propietario (bloqueo por **material**, no por código).
- **`AUTO-21`**: `P(R>0)`, correlación y current-regime gating.

## Cómo continuar

Ver [`arranque-agente-post-v2.67-auto-20f-cierre-p3-v2.66-2026-09-25.md`](./arranque-agente-post-v2.67-auto-20f-cierre-p3-v2.66-2026-09-25.md).
Para auditar, [`arranque-auditor-v2.67-auto-20f-cierre-p3-v2.66-2026-09-25.md`](./arranque-auditor-v2.67-auto-20f-cierre-p3-v2.66-2026-09-25.md).
