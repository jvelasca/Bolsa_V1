# Traspaso / relevo — `v2.73-beta` (`AUTO-MATERIAL-1`: PAPER MATERIAL READINESS)

> **AsOf:** 2026-09-26 · **Versión:** `1.98.0-beta` · **Tag:** `v2.73-beta` · **Base:** `v2.72-beta`
> **Estado:** fase **CERRADA**. **SIN migración** (head `046_fill_reference_mid`). **Freeze y reparto
> intactos** (`auto18-v1` / `auto15-v1`).

## Qué quedó hecho

1. **Gate `PAPER MATERIAL READINESS`** (diagnóstico read-only): módulo puro
   `paper_material_readiness.py` + CLI `paper_material_readiness.py` (tabla + `--json`, `exit 0/2`,
   guarda de venue `BROKER_VENUE=paper`). Se corre **antes** de `auto_evidence_run.py` (AUTO-22) y
   declara **por qué** el material no produce ciclos con R medible.
2. **Sondas de linaje A/B/C/D** en el JSON: cycle lineage (fills y exit orders con `cycle_id`),
   reservation lineage (reservas, vivas vs liberadas), cierre FIFO (`cycles_from_fills`) y readiness.
3. **Motivos nombrados**, fail-closed: `no cycle lineage` · `no reservations` · `no closed cycles` ·
   `insufficient measurable cycles per strategy` · `producer path not exercised`.
4. **Tests** puros (legacy BLOCKED · V2 READY · bajo mínimo BLOCKED · sin relleno) + costura del CLI.
5. **Sonda `M199`** + matriz re-medida **199/199** con restauración **byte a byte**.
6. **Evidencia cruda** contra `bolsa-postgres` (reconciliada con los números de `v2.72`).
7. **Bump** `1.97.0-beta` → **`1.98.0-beta`**.

## Lo que NO quedó hecho (y por qué)

- **El material PAPER sigue sin producir ciclos con R medible.** El gate lo **declara** (BLOCKED) pero
  **no** lo repara: reparar el productor / activar `AUTO_ENGINE_SIM_V2` y re-ejecutar la corrida es la
  fase siguiente ("reparación de material" real), fuera del alcance de esta.
- **`P3-2`** (correlación por cubos) y **`P3-3`** (`P(R>0)` vs N) siguen **abiertas**: requieren el
  primer dataset real, que sigue bloqueado por material.
- **La UI** del gate no se toca: el JSON queda listo para una pantalla futura.

## Lo que hereda el siguiente

**El bloqueante central sigue siendo MATERIAL, no código — ahora medido y declarado por el gate.**

1. **Correr el gate primero**, siempre, antes del RUN:
   ```bash
   $env:BROKER_VENUE="paper"
   uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \
       --account-id <cuenta> --strategy-version <v> [--json]
   ```
   Sale `2` y nombra los motivos mientras el material no cierre con R medible.
2. **La hipótesis a confirmar/refutar en la siguiente fase** (declarada por el gate, no supuesta): con
   `AUTO_ENGINE_SIM_V2` OFF el worker usa el camino legacy y materializa fills **sin `cycle_id` y sin
   reservas**. Activar el pipeline V2 (o reparar su camino de persistencia) es lo que hace nacer
   linaje y reservas.
3. **Con `≥32` ciclos medibles por estrategia** (el gate pasa a `READY`): correr el
   [protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md) **sin tocar los
   umbrales**, y después el harness de validación (`auto_evidence_validate.py`) para cerrar **P3-2** y
   **P3-3**.

## Ficheros de la fase

- [Plan](./plan-v2-73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2.73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
  [Agente](./arranque-agente-post-v2.73-auto-material-1-paper-material-readiness-2026-09-26.md)
- Evidencia cruda: `evidencia-material-readiness-v2.73-2026-09-26.txt` ·
  `evidencia-matriz-mutaciones-v2.73-199-2026-09-26.txt`
- Contexto de la fase anterior: `evidencia-run-paper-bloqueado-v2.72-2026-09-26.txt`

## Reglas duras que siguen vigentes

- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se infiere `cycle_id` ni `reserved_risk`; **no** se sustituye por capital/equity/nominal;
  **no** se convierte N fills en N operaciones.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`, inmutables).
- **No** se convierte `P(R>0)`, la correlación ni el régimen en `confidence`, sizing, plan, reserva ni
  rotación (`ALLOCATION = none`, `auto18-v1` congelado).
- **No** se toca el freeze. **Sin migración.**
