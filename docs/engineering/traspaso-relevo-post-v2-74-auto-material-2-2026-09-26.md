# Traspaso / relevo — `v2.74-beta` (`AUTO-MATERIAL-2`: PAPER PRODUCER)

> **AsOf:** 2026-09-26 · **Versión:** `1.99.0-beta` · **Tag:** `v2.74-beta` · **Base:** `v2.73-beta`
> **Estado:** fase **CERRADA**. **SIN migración** (head `046_fill_reference_mid`). **Freeze y reparto
> intactos** (`auto18-v1` / `auto15-v1`), `auto_simulation_worker.py` **intacto**.

## Qué quedó hecho

1. **Productor V2 activado y controlado**: el camino AUTO 2.0 (`AUTO_ENGINE_SIM_V2=ON` + decider + watch
   + régimen) **acuña estructura** —`cycle_id` en los fills, reservas con `reserved_risk`, intents de
   salida con `cycle_id`, ciclos cerrados y R medible— sobre una **cuenta PAPER nueva**.
2. **Ejercicio controlado**: `apps/api-python/scripts/v2_74_paper_producer_evidence.py` conduce el camino
   REAL (decider determinista + `price_script`) y publica el **A/B estructural LEGACY vs V2**
   (`--json` / `--out`).
3. **Gate de dos niveles**: `PRODUCER_READY` (estructura) y `EVIDENCE_READY` (estructura + `≥32` ciclos
   medibles por estrategia), más `BLOCKED`; `producer_blockers` nombran cada eslabón de la estructura.
   Sello `paper_material_readiness_v2`.
4. **CLI** con `--level {producer,evidence}` y las **tres poblaciones** (`DATABASE TOTAL` /
   `INSTRUMENT UNIVERSE` / `AUTO MATERIAL`).
5. **Reparación del denominador de R** (en el **store**, no en el worker congelado): `reservation_store.py`
   conserva el riesgo COMPROMETIDO en la fila durable al liberar la reserva, para que
   `cycle_risk_from_reservations` pueda reconstruir el R de los ciclos cerrados.
6. **Inmutabilidad legacy testeada**: el productor **no** backfillea `cycle_id`; el fill histórico
   conserva `cycle_id=None`.
7. **Sondas `M199`/`M200`** + matriz re-medida **200/200** con restauración **byte a byte**.
8. **CI**: `test_paper_material_readiness.py` registrado en `python-ci.yml` y `release-tag-ci.yml` (antes
   no corría en la compuerta `quality`).
9. **Evidencia cruda** contra `bolsa-postgres` (A/B estructural).
10. **Bump** `1.98.0-beta` → **`1.99.0-beta`**.

## Lo que NO quedó hecho (y por qué)

- **`EVIDENCE_READY` / `AUTO-22`**: falta **muestra** (`≥32` ciclos medibles por estrategia). El material
  está **bien formado**, no **suficiente**; se declara sin rebajar el umbral. Acumular muestra y correr
  `AUTO-22` es **V2.75**.
- **`P3-2`** (correlación por cubos) y **`P3-3`** (`P(R>0)` vs N) siguen **abiertas**: requieren el
  primer dataset real, aún no acumulado.
- **La UI** del gate no se toca: el JSON (con los dos niveles) queda listo para una pantalla futura.

## Lo que hereda el siguiente

**El bloqueante ya no es de CÓDIGO del productor, es de MUESTRA.**

1. **Correr el gate a nivel `evidence`** con cada avance:
   ```bash
   $env:BROKER_VENUE="paper"
   uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \
       --account-id <cuenta> --strategy-version <v> --level evidence [--json]
   ```
   Mientras falte muestra: `PRODUCER_READY`, `exit 2`, con `insufficient measurable cycles per strategy`.
2. **Acumular `≥32` ciclos medibles por estrategia** conduciendo corridas V2 (el harness de `v2.74` es el
   punto de partida). El gate debe pasar a `EVIDENCE_READY` **sin** que nadie baje umbrales.
3. **Con `EVIDENCE_READY`**: correr el
   [protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md) **sin tocar los
   umbrales** (`auto_evidence_run.py`), y después el harness de validación (`auto_evidence_validate.py`)
   para cerrar **P3-2** y **P3-3**.

## Ficheros de la fase

- [Plan](./plan-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
  [Agente](./arranque-agente-v2-74-auto-material-2-paper-producer-2026-09-26.md)
- Evidencia cruda: `evidencia-material-producer-v2.74-2026-09-26.txt` ·
  `evidencia-matriz-mutaciones-v2.74-200-2026-09-26.txt`
- Contexto de la fase anterior: `evidencia-material-readiness-v2.73-2026-09-26.txt`

## Reglas duras que siguen vigentes

- **No** se rellena el histórico legacy (sin backfill de `cycle_id`); el productor solo **acuna**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se infiere `cycle_id` ni `reserved_risk`; **no** se sustituye por capital/equity/nominal;
  **no** se convierte N fills en N operaciones.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`, inmutables).
- **No** se convierte `P(R>0)`, la correlación ni el régimen en `confidence`, sizing, plan, reserva ni
  rotación (`ALLOCATION = none`, `auto18-v1` congelado).
- **No** se toca el freeze. **Sin migración.**
