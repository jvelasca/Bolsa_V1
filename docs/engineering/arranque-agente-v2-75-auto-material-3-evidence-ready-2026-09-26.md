# Arranque del agente siguiente — tras `v2.75-beta` (`AUTO-MATERIAL-3`: EVIDENCE READY)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.75-beta` (`2.00.0-beta`) · **Base:** `v2.74-beta`
> **Estado:** el gate de dos niveles pasa a **`EVIDENCE_READY`** con muestra acumulada por el productor
> determinista; `AUTO-22` y `AUTO-23` **ejercitados**. **SIN migración** (head `046_fill_reference_mid`).
> **Freeze y reparto intactos** (`auto18-v1` / `auto15-v1`), worker congelado intacto.

## Dónde estás

La muestra ya no es el bloqueante de **CANTIDAD**: 42 ciclos medibles ≥ 32. Lo que falta es
**DIVERSIDAD** para que la estadística sea interpretable:

- Todos los ciclos comparten **un solo bucket de calendario** (los fills llevan la fecha de reloj real)
  y **un solo episodio de régimen** (`BULL_TREND`).
- Por eso `AUTO-23` da correlación **sin pares** (`activeBuckets=1 < minBuckets=4`) y régimen
  **`INCONCLUSIVE`** (`episodes=1`). `P(R>0)=0` con `Effective-N=1` es la firma de un `R` casi
  constante (productor determinista), no un edge negativo real.

**El nuevo bloqueante es de MATERIAL REAL, no de código.** Ningún cambio de código cierra `P3-2`/
`P3-3`: hay que **acumular PAPER de mercado** repartido en días/semanas y regímenes.

## Tu primera tarea: material de mercado, no guionizado

1. **Conducir corridas PAPER con precio/ATR de MERCADO** (barras reales o cargadas) sobre una cuenta
   nueva, de modo que los ciclos caigan en **≥4 cubos** y **≥2 episodios** de régimen. El harness de
   `v2.75` es punto de partida de la MECÁNICA (round-trips encadenados), NO de la fuente de precio.
2. **Volver a correr el gate a nivel `evidence`** con cada avance; no debe declarar `EVIDENCE_READY`
   hasta que la estructura aguante, y el veredicto estadístico debe dejar de ser degenerado.
3. **Con material diverso**: `auto_evidence_run.py` → `auto_evidence_validate.py`, y **cerrar** `P3-2`
   (correlación con `≥4` cubos) y `P3-3` (`P(R>0)` vs N con `Effective-N > 1`).

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida. Si
el material es degenerado, el veredicto correcto es el que ya da: `INCONCLUSIVE` / `NO MEDIDO`.

## Después

La **auditoría externa de `v2.75-beta`** es la siguiente parada; el pack está en el
[audit-pack](./audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md). El hallazgo de
degeneración está declarado: el auditor debe leerlo como «gate de cantidad cruzado, diversidad
pendiente», no como edge.

## Ficheros de la fase

[Plan](./plan-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Auditor](./arranque-auditor-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2-75-auto-material-3-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-sample-accumulation-v2.75-2026-09-26.txt` ·
`evidencia-auto22-run-v2.75-2026-09-26.txt` · `evidencia-auto23-validation-v2.75-2026-09-26.txt`
