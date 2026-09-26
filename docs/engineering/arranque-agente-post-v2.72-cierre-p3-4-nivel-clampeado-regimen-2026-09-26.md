# Arranque del agente siguiente — tras `v2.72-beta` (cierre de `P3-4`)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.72-beta` (`1.97.0-beta`) · **Base:** `v2.71-beta`
> **Estado:** `P3-4` **cerrada**. **SIN migración** (head `046_fill_reference_mid`).
> **Freeze y reparto intactos** (`auto18-v1` / `auto15-v1`).

## Dónde estás

El instrumento de evidencia está **corregido y auditado**:

- `P(R>0)` por **ciclos** y `P(edge>0)` por **medias** bootstrap, separadas (`v2.71`).
- La calibración compara **magnitudes homogéneas** (`v2.71`).
- Lo **no medido** se declara (`cellsUnmeasured`), el **nivel publicado es el usado** (replay `H3` y
  ahora también la lectura del régimen, `P3-4`) y la clave de cobertura **no colisiona** (`v2.71`).

## Qué falta (y NO es código)

**El primer RUN PAPER real está BLOQUEADO por MATERIAL.** Medido (2026-09-26, `bolsa-postgres`):
**761** fills durables · **0** con `cycle_id` · **751 `buy` / 10 `sell`** · **0** filas en
`portfolio_reservations`. El instrumento devuelve `exit 2` en el exportador y en el run, **sin crear**
`evidence_runs/`.

**Dos causas independientes, cada una suficiente para bloquear:**

1. **Sin reservas** (`portfolio_reservations` vacía) ⇒ no hay `reserved_risk` ⇒ **sin R medible**
   aunque haya cierres.
2. **Sin cierres** (751 compras / 10 ventas) ⇒ casi todo son **entradas abiertas** ⇒ sin ciclo
   cerrado ni resultado.

## Tu primera tarea: medir las dos causas, no suponerlas

1. **Reservas.** ¿Escribe el turno AUTO filas en `portfolio_reservations`? Localiza el productor
   (`AUTO-1` / reservation store) y **mide** si el camino SIM las crea; si no, determina si es
   "nunca se llamó" o "se llama y no persiste".
2. **Cierres.** ¿Por qué el simulador acumula compras y apenas vende? Distingue **poco tiempo de
   ejecución** (se arregla esperando) de **camino de salida no ejercitado** (se arregla en código).
   No lo declares sin la medición.

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
Sin material, el resultado correcto es **BLOQUEADO**.

## Después

Con **≥32 ciclos medidos** por estrategia: correr el
[protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md) y el harness
`auto_evidence_validate.py` para cerrar **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N).
La auditoría externa de `v2.72-beta` arranca en el
[arranque del auditor](./arranque-auditor-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md).

## Ficheros de la fase

[Plan](./plan-v2-72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
[Auditor](./arranque-auditor-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-matriz-mutaciones-v2.72-198-2026-09-26.txt` ·
`evidencia-run-paper-bloqueado-v2.72-2026-09-26.txt`
