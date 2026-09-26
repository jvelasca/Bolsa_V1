# Arranque del agente siguiente — tras `v2.73-beta` (`AUTO-MATERIAL-1`: PAPER MATERIAL READINESS)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.73-beta` (`1.98.0-beta`) · **Base:** `v2.72-beta`
> **Estado:** gate de material **desplegado y medido**. **SIN migración** (head `046_fill_reference_mid`).
> **Freeze y reparto intactos** (`auto18-v1` / `auto15-v1`).

## Dónde estás

El bloqueo de `v2.72` ya **no es una sorpresa**: hay un **pre-flight** que lo mide y lo declara.

- **Gate `PAPER MATERIAL READINESS`**: `apps/api-python/scripts/paper_material_readiness.py` (tabla +
  `--json`, `exit 0/2`, guarda de venue). Se corre **antes** de `auto_evidence_run.py` (AUTO-22).
- **Módulo puro** `packages/py/application/src/bolsa_application/paper_material_readiness.py`: mide
  sobre el **mismo** material que el instrumento (`adaptive_instrument_cycles`), sin un segundo FIFO
  ni una segunda aritmética de R.
- **Sondas A/B/C/D** en el JSON: linaje de ciclo, linaje de reserva, cierre FIFO y readiness.
- **Sonda `M199`**: el gate **no** puede devolver `READY` sin el mínimo de ciclos con R por estrategia.

Medición de esta fase (`bolsa-postgres`, 2026-09-26): **BLOCKED** con los cinco motivos; reproduce los
hechos de `v2.72`. Cuenta del RUN (`181e7e07d27d4cdebc342ff83`): **4** fills, **0** con `cycle_id`,
**0** reservas; tabla completa: **761** fills (**751 buy / 10 sell**), **0** `cycle_id`, **53**
versiones, **0** reservas, **0** exit orders.

## Tu primera tarea: medir las DOS causas, no suponerlas

El gate ya nombra los eslabones ausentes (`FILL -> CYCLE -> ENTRY+EXIT -> RESERVED RISK -> R`). Lo que
falta es la **reparación de material** (fuera del alcance de esta fase):

1. **Linaje de ciclo.** ¿Por qué ningún fill lleva `cycle_id`? Hipótesis declarada: el pipeline AUTO 2.0
   (`AUTO_ENGINE_SIM_V2`) está **OFF** y el worker usa el camino legacy. **Confírmalo o refútalo**
   ejercitando el camino V2 y **volviendo a correr el gate**: debe pasar de `no cycle lineage` a
   contar fills con ciclo.
2. **Reservas.** ¿Por qué `portfolio_reservations` está vacía? Sin `reserved_risk` no hay **R** medible
   aunque haya cierres. La persistencia vive en `_v2_persist_tick_reservations` → `save_claim`, dentro
   del camino V2. Determina si es "nunca se llamó" o "se llama y no persiste".

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
El gate **no** repara material: si no hay cierres con R, el resultado correcto sigue siendo **BLOCKED**.

## Después

Con el gate en **`READY`** (`≥32` ciclos medibles por estrategia): correr el
[protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md) y el harness
`auto_evidence_validate.py` para cerrar **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N).
La **auditoría externa de `v2.73-beta`** es la siguiente parada: el pack está en el
[audit-pack](./audit-pack-v2-73-auto-material-1-paper-material-readiness-2026-09-26.md).

## Ficheros de la fase

[Plan](./plan-v2-73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2.73-auto-material-1-paper-material-readiness-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-material-readiness-v2.73-2026-09-26.txt` ·
`evidencia-matriz-mutaciones-v2.73-199-2026-09-26.txt`
