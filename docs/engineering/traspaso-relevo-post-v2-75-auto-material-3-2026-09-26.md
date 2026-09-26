# Traspaso / relevo — tras `v2.75-beta` (`AUTO-MATERIAL-3`: EVIDENCE READY)

> **AsOf:** 2026-09-26 · **Etiqueta:** `v2.75-beta` · **Versión:** `2.00.0-beta` · **Base:** `v2.74-beta`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto** · **Reparto
> congelado** (`auto18-v1` / `auto15-v1`) · **`ALLOCATION = none`**.

## Qué quedó hecho

1. **Harness de acumulación** (nuevo, I/O): `apps/api-python/scripts/v2_75_paper_sample_accumulation.py`.
   Encadena round-trips con **worker/engine nuevo + día distinto por round-trip** (reset de `_minute`
   para volver a la ventana donde el sondeo garantiza el fill; día distinto para esquivar el dedupe de
   barra diaria) y lee el material con la MISMA pieza que el gate.
2. **`EVIDENCE_READY` alcanzado**: 44 round-trips → **42 ciclos medibles** (≥32) sobre cuenta nueva
   `40787fbdb2354f70a3aec5256`, versión `v75-producer-orb-v1`. Gate CLI `--level evidence`: `EXIT=0`.
3. **`AUTO-22` corrido**: bundle inmutable `evidence_runs/20260926T152807Z-70418d88/` (huella
   `sha256:70418d88…`), 3 niveles, 42 ciclos.
4. **`AUTO-23` corrido**: `evidence_validations/20260926T152821Z-70418d88/` (barrido, correlación,
   régimen).
5. **Evidencia cruda** capturada en 3 `.txt` en `docs/engineering/`.
6. **Bump** `1.99.0-beta` → **`2.00.0-beta`**; tag **`v2.75-beta`**.

## Hallazgo central (declarado)

**El gate de CANTIDAD se cruza; la DIVERSIDAD no.** Los 42 ciclos comparten **bucket de calendario
único** (2026-09-26 / 2026-W39) y **episodio de régimen único** (`BULL_TREND`): `AUTO-23` da
correlación **sin pares** (`activeBuckets=1 < 4`) y régimen **`INCONCLUSIVE`** (`episodes=1`).
`P(R>0)=0` con `Effective-N=1` refleja el `R` casi constante del productor determinista, **no** un edge
negativo de mercado.

## Lo que NO quedó hecho (y por qué)

- **`P3-2`** (correlación por cubos) y **`P3-3`** (`P(R>0)` vs N): **ABIERTAS**. El instrumento queda
  ejercitado; cerrarlas exige **material PAPER REAL de mercado** repartido en `≥4` cubos y `≥2`
  episodios. Es trabajo **operativo**, no de código.
- **No** se añadieron mutaciones: V2.75 no introduce lógica pura (matriz sigue **200/200** de `v2.74`).
- **No** se añadió pytest nuevo: el cambio es un harness de I/O en `scripts/` (fuera de mypy por
  diseño; ruff limpio). La certificación se hace por el gate + el RUN + la validación.

## Lo que hereda el siguiente

**El bloqueante ya no es de CÓDIGO ni de CANTIDAD: es de MATERIAL REAL (diversidad).**

1. Conducir PAPER con **precio/ATR de MERCADO** (barras reales o cargadas) para que los ciclos caigan
   en varios días/semanas y regímenes. Mecánica de encadenado: harness de `v2.75`; fuente de precio:
   mercado (NO `price_script`).
2. Gate a nivel `evidence` con cada avance: debe seguir siendo `EVIDENCE_READY` y el veredicto
   estadístico debe dejar de ser degenerado.
3. Con material diverso: `auto_evidence_run.py` → `auto_evidence_validate.py` y **cierre** de
   `P3-2` / `P3-3`.

## Reglas duras que siguen vigentes

- **No** se rellena el histórico legacy (sin backfill de `cycle_id`); el productor solo **acuna**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se infiere `cycle_id` ni `reserved_risk`; **no** se convierte N fills en N operaciones.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`, inmutables
  y no versionadas).
- **No** se toca el freeze. **Sin migración.** `ALLOCATION = none`.

## Ficheros de la fase

- [Plan](./plan-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2-75-auto-material-3-evidence-ready-2026-09-26.md) ·
  [Agente](./arranque-agente-v2-75-auto-material-3-evidence-ready-2026-09-26.md)
- Evidencia: `evidencia-sample-accumulation-v2.75-2026-09-26.txt` ·
  `evidencia-auto22-run-v2.75-2026-09-26.txt` · `evidencia-auto23-validation-v2.75-2026-09-26.txt`
- Contexto previo: [relevo v2.74](./traspaso-relevo-post-v2-74-auto-material-2-2026-09-26.md)
