# Arranque del auditor — `v2.75-beta` (`AUTO-MATERIAL-3`: EVIDENCE READY)

> **AsOf:** 2026-09-26 · **Tag a auditar:** `v2.75-beta` (`2.00.0-beta`) · **Base (diff):** `v2.74-beta`
> **Punto de entrada desde GitHub:** clonar, `git checkout v2.75-beta`, y seguir el
> [audit-pack](./audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md).
> **SIN migración** (head `046_fill_reference_mid`). **Freeze y reparto intactos** (`auto18-v1` /
> `auto15-v1`).

## Qué es esta fase

La anterior (`v2.74`) dejó el material PAPER **bien formado** (`PRODUCER_READY`) pero **insuficiente**
(1 ciclo). `v2.75` **acumula muestra** con el productor determinista hasta cruzar el mínimo del gate
(`≥32` ciclos medibles por estrategia) y corre la instrumentación de evidencia (`AUTO-22` / `AUTO-23`)
sobre ese material. **No** cambia ningún umbral, **no** cambia el instrumento y **no** reparte.

## Qué debes verificar (orden sugerido)

1. **El instrumento no se movió.** `git diff v2.74-beta..v2.75-beta` no toca
   `paper_material_readiness.py`, `auto_evidence_run.py`, `auto_evidence_validate.py`,
   `auto_paper_material.py` ni el worker congelado `auto_simulation_worker.py`.
2. **El único cambio de código es el harness** `apps/api-python/scripts/v2_75_paper_sample_accumulation.py`
   (I/O puro: siembra, encadena round-trips, lee con la pieza del gate, publica JSON). No entra en el
   gate, ni en el reparto, ni en el freeze.
3. **El gate pasa a `EVIDENCE_READY` con el MISMO material** (no se rebaja `min_cycles`). Corre el
   harness o el CLI `--level evidence` y comprueba `EXIT=0`.
4. **`AUTO-22` produce bundle inmutable** con huella, 3 niveles, y con los huecos declarados
   (`NO MEDIDO`), nunca `0` de relleno.
5. **`AUTO-23` no inventa celdas**: correlación sin pares con `activeBuckets=1`; régimen
   `INCONCLUSIVE` con `episodes=1`; `size=64` `insufficient_measured_cycles`.

## La pregunta que DEBES hacerte (y su respuesta honesta)

> ¿`EVIDENCE_READY` aquí es «evidencia de mercado»?

**No.** La muestra la produce el **productor determinista** (decider fijo + `price_script`), así que:

- el `R` de los 42 ciclos es **casi constante** (parada estructural ≈ −1);
- los 42 ciclos caen en **un solo bucket de calendario** (timestamps de reloj real del mismo día) y en
  **un solo episodio de régimen** (`BULL_TREND` fijo);
- por eso `P(R>0)=0.0000` con `Effective-N=1`, `WFE = NO MEDIDO` y `Correlación = NO MEDIDO`.

`EVIDENCE_READY` es un gate de **CANTIDAD + estructura**: se cruza. La **DIVERSIDAD** (calendario y
régimen) que `P3-2` / `P3-3` necesitan **sigue sin material**, y se declara **ABIERTA**. El material de
PostgreSQL lo etiqueta `paper_real` (`read_paper_material`), pero es **PAPER virtual durable**, no
cotización real: la propia nota del lector lo dice.

## Veredicto que puedes emitir

- Si auditas **contrato y honestidad**: la fase **pasa** — no hay umbral rebajado, no hay backfill, no
  hay cero de relleno, el bundle es inmutable y el hallazgo de degeneración está **declarado**.
- Si auditas **evidencia de mercado**: **NO concluyente** — y es exactamente lo que la fase afirma; el
  siguiente paso (material real) es **operativo**, no de código.

## Ficheros de la fase

[Plan](./plan-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2-75-auto-material-3-2026-09-26.md) ·
[Agente siguiente](./arranque-agente-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-sample-accumulation-v2.75-2026-09-26.txt` ·
`evidencia-auto22-run-v2.75-2026-09-26.txt` · `evidencia-auto23-validation-v2.75-2026-09-26.txt`
