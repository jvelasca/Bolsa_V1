# Arranque del agente — post `v2.66-beta` (`AUTO-20E`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.66-beta` (`1.91.0-beta`) · **Base:** `v2.65-beta` = `a077c1c6`

## Contexto en una frase

`v2.66` cierra las **3 P3** de la auditoría de `v2.65-beta`: el contrato de claves de calibración **lee Python
de verdad** (y su compuerta corre ante cambios de Python), una `materialOrigin` contradictoria **no** se
resuelve a `PAPER REAL`, y en el perímetro **ausente ≠ vacío** (`NO MEDIDO` vs `(ninguna)`), en TS y Python.

## Estado verificado

- Frontend **1323 passed**, `typecheck`/`lint`/`build`/`contract:check` OK.
- Python analytics **1208 passed**, `ruff` OK, `import-linter` 4/0.
- Matriz de mutaciones ampliada con **M179/M180**.
- **Sin migración**; **freeze intacto**; árbol limpio.

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| P3-1 contrato TS-vs-TS | **cerrada** (lee Python + filtro de CI + test del render) |
| P3-2 precedencia sin coherencia | **cerrada** (contradicción ⇒ desconocido + aviso) |
| P3-3 perímetro ausente vs vacío | **cerrada** (TS + Python) |
| `governor.json` huérfano | **cerrada** (en `.gitignore`) |
| Ficheros Python «modificados» | **cerrada** (eran solo CRLF; normalizados) |

## Qué queda por hacer (elegir)

1. **La corrida PAPER real (AUTO-20D/E)** — sigue siendo **paso operativo del propietario**. Requiere
   material PAPER con `cycle_id` no nulo (≥32 ciclos medidos por estrategia). Hoy el PostgreSQL local tiene
   `sim_fill_finance_context` con `cycle_id` NULL en **todos** los fills ⇒ el exportador bloquearía con
   `exit 2`. **No es un defecto de código.**
2. **`AUTO-21`** — `P(R>0)`, correlación y current-regime gating (fuera de alcance por diseño).
3. **Higiene opcional** — ninguna pendiente conocida tras `v2.66`.

## Reglas de la casa a recordar

- Un contrato que no puede fallar **no es un contrato**: si un test afirma cubrir algo, hay que **demostrar
  que muerde** (romperlo a propósito o mutación).
- La UI **lee y presenta**; nunca recalcula. `null` ⇒ `NO MEDIDO`; veredicto ausente ⇒ `INCONCLUSIVE`.
- No se toca el freeze (`auto_adaptive.py`, `auto_adaptive_data_gate.py`, `auto_simulation_worker.py`,
  `auto_adaptive_journal.py`, `auto_adaptive_replay.py`, `v2_43_governor_evidence.py`, `governor.json`) ni el
  reparto (`auto18-v1`/`auto15-v1`).
- **Sin migración** salvo justificación explícita (head `046_fill_reference_mid`).

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/analytics -q
```
