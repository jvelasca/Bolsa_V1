# Arranque del agente — post `v2.70-beta` (`AUTO-23`)

> **AsOf:** 2026-09-25 · **Tag vigente:** `v2.70-beta` (`1.95.0-beta`) · **Base:** `v2.69-beta`

## Contexto en una frase

`v2.70` (`AUTO-23`) deja **imposible de confundir** la procedencia y la realidad de ejecución en la UI
(`SOURCE` + `EXECUTION REALITY: VIRTUAL — NO REAL MONEY`) y añade un **harness de validación**
(`auto_evidence_validate.py`) que, sobre el **mismo lector único** y la **misma matemática** de
`AUTO-22`, publica el barrido `P(R>0)` vs N, la estabilidad de régimen y los diagnósticos de la
correlación por cubos (`P3-2`/`P3-3`). **Sin mover el reparto** (`auto18-v1` congelado) y **sin
migración**.

## El invariante que instala

> **La procedencia y la realidad de ejecución se leen antes que cualquier número; y la validación de
> la evidencia es un consumidor de la ÚNICA matemática de `AUTO-22` — se ejecuta completa o se declara
> BLOQUEADA, y nunca elige el `N` que mejor suena.**

## Estado verificado

- UI: `classifyExecutionReality` + bloque `EXECUTION REALITY` y `SOURCE` reforzado en
  `auto-evidence-report.ts` / `auto-evidence-section.tsx` (+ tests).
- Harness puro: `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_validation.py`
  (`EVIDENCE_VALIDATION_SCHEMA = "auto23_evidence_validation_v1"`, `EvidenceValidationBlockedError`).
- CLI: `apps/api-python/scripts/auto_evidence_validate.py` (bundle inmutable en
  `evidence_validations/<UTC>-<huella8>/`, `exit 2` BLOQUEADO, sin fichero parcial).
- Runbook: [`protocolo-primer-run-paper-real-v2.70-2026-09-25.md`](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md).
- Mutaciones **M191/M192**; matriz completa re-medida con restauración byte a byte.

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| **La corrida PAPER real** (material real) | **abierta** — paso operativo del propietario; RUN y harness listos |
| **P3-2** correlación por cubos (validación empírica) | **abierta** — harness listo; requiere material real |
| **P3-3** `P(R>0)` vs tamaño muestral | **abierta** — harness listo; no convertir en confidence/allocation |
| La correlación/régimen moviendo el reparto | **fuera de alcance por decisión** (solo medición) |
| current-regime gating operativo · LIVE · allocation dinámica | **fuera de alcance** |

## Qué queda por hacer (elegir)

1. **Aportar material PAPER real** (el propietario) y correr el protocolo: **1 estrategia → ≥32
   ciclos medibles → `auto_evidence_run.py`**; luego **2ª estrategia** y `auto_evidence_validate.py`.
2. **Cerrar P3-2/P3-3** con el primer dataset real usando los diagnósticos del harness.
3. Usar la evidencia publicada para **decidir** algo (sizing, gating de régimen, restricción por
   correlación): decisión **de producto**, no tomada.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/application packages/py/analytics -q
uv run pytest apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py -q
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M191 M192
# Corrida de evidencia (fixture declarado; el material real es del propietario):
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json
# Validación (barrido + régimen + correlación):
uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \
    --cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json \
    --sizes 16,32,64 --buckets day,week
```

## Reglas de la casa a recordar

- Un número sin muestra suficiente es **`NO MEDIDO`**, nunca un `0` disfrazado de lectura.
- El RUN y la VALIDACIÓN **o** producen el bundle completo **o** se declaran BLOQUEADOS.
- Una corrida/validación es **inmutable**: no se sobrescribe una medición.
- Un contrato que no puede fallar **no es un contrato**: cada invariante viaja con su mutación.
- La UI **lee y presenta**; nunca recalcula.
- No se toca el freeze ni el reparto (`auto18-v1`/`auto15-v1`). **Sin migración.**
- **`PAPER REAL` = datos reales con DINERO VIRTUAL**, nunca dinero real.
