# Arranque del agente siguiente — tras `v2.74-beta` (`AUTO-MATERIAL-2`: PAPER PRODUCER)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.74-beta` (`1.99.0-beta`) · **Base:** `v2.73-beta`
> **Estado:** el **productor V2 está activado y controlado**; el material NAZCA con estructura completa
> (`PRODUCER_READY`). **SIN migración** (head `046_fill_reference_mid`). **Freeze y reparto intactos**
> (`auto18-v1` / `auto15-v1`), `auto_simulation_worker.py` **intacto**.

## Dónde estás

El material ya no está **mal formado**: el camino AUTO 2.0 produce linaje, reservas, salidas y R medible.
Lo que **falta** es **muestra** para la estadística (el techo de este fase: `PRODUCER_READY`, no
`EVIDENCE_READY`).

- **Gate de dos niveles** `PAPER MATERIAL READINESS`:
  `apps/api-python/scripts/paper_material_readiness.py` — `--level {producer,evidence}` (default
  `evidence`), `--json`, `exit 0/2/1`, guarda de venue `BROKER_VENUE=paper`. Bloques `DATABASE TOTAL` /
  `INSTRUMENT UNIVERSE` / `AUTO MATERIAL`.
- **Módulo puro** `packages/py/application/src/bolsa_application/paper_material_readiness.py`: veredicto
  de dos niveles con `producer_blockers` (estructura) y `blockers` (estructura + mínimo); sello
  `paper_material_readiness_v2`. Sigue midiendo el **mismo** material que el instrumento.
- **Productor de ejercicio controlado**: `apps/api-python/scripts/v2_74_paper_producer_evidence.py` —
  conduce el camino REAL con decider determinista y `price_script`, y compara LEGACY vs V2 (solo
  estructura) con `--json` / `--out`.
- **Reparación declarada** (en el store, **no** en el worker congelado): `reservation_store.py` conserva
  el riesgo COMPROMETIDO en la fila durable al liberar la reserva — es el denominador de R de los ciclos
  cerrados.
- **Sonda `M200`** (y `M199`): el gate **no** puede dar `PRODUCER_READY` sin estructura ni `READY` sin
  mínimo.

## Tu primera tarea: ACUMULAR muestra, no suponerla

El productor ya funciona; el bloqueante ahora es de **acumulación**:

1. **Conducir corridas V2 suficientes** para llegar a `≥32` ciclos medibles por estrategia (el operativo
   del [protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md), `folds=3`,
   `min_is=8`, `min_oos=4`). El harness de `v2.74` es el punto de partida; extiéndelo o encadena corridas
   sobre la cuenta nueva.
2. **Volver a correr el gate a nivel `evidence`** con cada avance: debe pasar de `PRODUCER_READY` a
   `EVIDENCE_READY` **sin** que nadie baje el umbral.
3. **Con `EVIDENCE_READY`**: correr `auto_evidence_run.py` (`AUTO-22`) y después el harness de validación
   (`auto_evidence_validate.py`) para cerrar **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N).

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida. El
gate **no** repara material: si no hay cierres con R, el veredicto correcto sigue siendo `BLOCKED`.

## Después

La **auditoría externa de `v2.74-beta`** es la siguiente parada: el pack está en el
[audit-pack](./audit-pack-v2-74-auto-material-2-paper-producer-2026-09-26.md). El material legacy **no**
se toca en ningún caso: el productor solo **acuna** material nuevo (append por `execution_id`).

## Ficheros de la fase

[Plan](./plan-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
[Auditor](./arranque-auditor-v2-74-auto-material-2-paper-producer-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2-74-auto-material-2-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-material-producer-v2.74-2026-09-26.txt` ·
`evidencia-matriz-mutaciones-v2.74-200-2026-09-26.txt`
