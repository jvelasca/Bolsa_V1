# Arranque del agente — post `v2.69-beta` (`AUTO-22`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.69-beta` (`1.94.0-beta`) · **Base:** `v2.68-beta`

## Contexto en una frase

`v2.69` (`AUTO-22`) deja **listo y reproducible** el RUN de evidencia PAPER end-to-end (un comando que
lee PostgreSQL por el **lector único**, compone `AUTO-19A/19B` + `AUTO-21` y guarda un **bundle con
huella**: `cycles.json` / `artifact.json` / `render.txt` / `run.json`) y **rediseña la sección AUTO
EVIDENCE en tres niveles** (Material / Estadística / Contexto) con `NO MEDIDO`/`INCONCLUSIVE` en vez de
ceros fabricados. **Sin mover el reparto** (`auto18-v1` congelado) y **sin migración**.

## El invariante que instala

> **La corrida de evidencia es UN comando reproducible que se guarda con su huella; o se ejecuta
> completa o se declara BLOQUEADA — nunca un bundle parcial, recálculo manual ni número copiado.**

## Estado verificado

- Runner: `apps/api-python/scripts/auto_evidence_run.py` (PG real o `--cycles` fixture declarado),
  `exit 2` BLOQUEADO sin material / PG / venue ≠ paper / lectura incompleta / corrida ya existente.
- Lector único: `packages/py/application/src/bolsa_application/auto_paper_material.py`; el exportador
  `paper_cycles_export.py` pasa a **envoltorio** (contrato intacto y tests E2E verdes).
- Composición pura: `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_run.py`
  (`EVIDENCE_RUN_SCHEMA = "auto22_evidence_run_bundle_v1"`, `EvidenceRunBlockedError`).
- UI de 3 niveles en `auto-evidence-report.ts` (+ test) y `auto-evidence-section.tsx` (+ test).
- Mutaciones **M188…M190**; matriz completa re-medida con restauración byte a byte.
- Flake **P3-1** cerrado con `testTimeout` por fichero en `core-r-scheduler.test.ts`.

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| La **corrida PAPER real** (material real) | **abierta** — paso operativo del propietario; el RUN ya está listo |
| **P3-2** correlación por cubos (validación empírica) | **abierta** — requiere el primer dataset real |
| **P3-3** `P(R>0)` vs tamaño muestral | **abierta** — no convertir en confidence/allocation |
| La correlación/régimen moviendo el reparto | **fuera de alcance por decisión** (solo medición) |
| current-regime gating operativo · LIVE · allocation dinámica | **fuera de alcance** |

## Qué queda por hacer (elegir)

1. **Aportar material PAPER real** (el propietario) y correr
   `auto_evidence_run.py --account-id <uuid> --strategy-version <v>`; importar el `artifact.json` en la
   cabina. Esa es la evidencia que falta desde `v2.62`.
2. **Cerrar P3-2/P3-3** con el primer dataset real (validación de la correlación por cubos y relación
   `P(R>0)` ↔ muestra).
3. Usar la evidencia publicada para **decidir** algo (sizing, gating de régimen, restricción por
   correlación): decisión **de producto**, no tomada.

## Reglas de la casa a recordar

- Un número sin muestra suficiente es **`NO MEDIDO`**, nunca un `0` disfrazado de lectura. Vale para
  `P(R>0)`, para la correlación (`None` + nota) y para los conteos.
- El RUN **o** produce el bundle completo **o** se declara BLOQUEADO: nunca un fichero a medias.
- Una corrida de evidencia es **inmutable**: no se sobrescribe una medición.
- Un contrato que no puede fallar **no es un contrato**: cada invariante viaja con su mutación
  (**M188…M190**) y con la prueba de que **muerde**.
- La UI **lee y presenta**; nunca recalcula.
- No se toca el freeze ni el reparto (`auto18-v1`/`auto15-v1`). **Sin migración** (head
  `046_fill_reference_mid`).

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/application packages/py/analytics -q
uv run pytest apps/api-python/tests/test_auto_v69_auto22_evidence_run.py -q
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M188 M189 M190
# Corrida de evidencia (fixture declarado; el material real es del propietario):
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json
```
