# Plan de fase — `AUTO-MATERIAL-12` / `V2.84` — INSTRUMENT FUNNEL CONTRACT (cierre de `OBS-6`/`OBS-7`/`OBS-8`)

> **AsOf:** 2026-09-27 · **Versión:** `2.08.1-beta → 2.09.0-beta` · **Migración:** **NO** (Alembic head
> sigue en `046_fill_reference_mid`) · **Tipo:** fase de **INSTRUMENTO READ-ONLY** (pura + CLI), no de
> decisión.

## 1. Objetivo

Cerrar los **tres hallazgos** que la auditoría externa de `v2.83.1-beta` levantó sobre el **instrumento de
`v2.83`** (`operability_audit.py`, byte-idéntico en aquel tag: su re-sello era docs-only):

- **`OBS-6` (MEDIUM)** — `enrich_rows_with_evidence` **sobrescribía** un funnel ya medido.
- **`OBS-7` (LOW)** — el funnel agregado de `window_totals` **sumaba filas `measured=False`**.
- **`OBS-8` (LOW)** — los **códigos de salida** del CLI estaban documentados inexactos.

## 2. Invariante de la fase

> «El instrumento AGREGA y RELLENA lo declarado; **nunca** pisa una medición existente ni cuenta un día no
> medido como si lo estuviera. Un hueco es `None` (`n/d`), jamás un `0`; un valor medido no se reescribe.»

## 3. Cambios (sólo instrumento; motor/gobernador intactos)

| # | Fichero | Cambio |
|---|---|---|
| `OBS-6` | `packages/py/application/src/bolsa_application/operability_audit.py` | Nuevo `_fill_funnel_gaps(row, rebuilt)`: conserva cada escalón **ya medido** de la fila y toma del funnel reconstruido **sólo** los huecos (`count is None`). `enrich_rows_with_evidence` lo usa en vez de reemplazar el funnel entero. |
| `OBS-7` | `.../operability_audit.py` | `window_totals`: el bloque `funnel` itera **`measured_rows`** (no `rows`) y `partial` se mide contra **`daysMeasured`** (coherente con `counts`/`coverage`/`rSum`); `_funnel_lines` publica `(días/díasMedidos)`. |
| `OBS-8` | `apps/api-python/scripts/v2_83_window_audit.py` | Docstring de códigos de salida corregido: `argparse` sale con **`2`** en el uso incorrecto ⇒ el código **no** distingue «sin material» de «uso incorrecto» (lo hace el mensaje de stderr). |

**No se toca** el motor congelado (`auto_simulation_worker.py`), el gobernador (`aggregate_trial_regime`),
`operability_window.py`, `TOP_N`, los umbrales, la allocation, los pesos A/B ni la UI.

## 4. Tests y mutaciones

- **Tests (puros)**: `packages/py/application/tests/test_operability_audit.py` **16 → 18**:
  - `test_enrich_rows_never_overwrites_a_measured_funnel` (`OBS-6`): una fila con funnel medido
    (`universe=8`, `orders=2`) re-enriquecida con evidencia **distinta** (`watchSize=999`,
    `turnTotals.orders=99`) conserva `8` y `2`.
  - `test_window_totals_funnel_ignores_unmeasured_rows` (`OBS-7`): una fila `measured=False` con evidencia
    (`universe=8`) **no** suma en el funnel agregado; `days == 1`, `daysMeasured == 1`.
- **Mutaciones nuevas** (`apps/api-python/scripts/v2_44_mutation_audit.py`): **`M231`** (el funnel medido se
  sobrescribe) y **`M232`** (el funnel vuelve a sumar `rows`). Marcadores nuevos `OPERABILITY_AUDIT` /
  `T_OPERABILITY_AUDIT`. Matriz **230 → 232**.

## 5. Compuertas

`ruff check packages/py apps/api-python --config pyproject.toml` · `lint-imports --config
packages/py/.importlinter` · `mypy` (full-tree, 5 raíces `src`) · `alembic heads` · `pytest` de aplicación
· matriz de mutaciones completa. Todas medidas **en local** (no heredadas).

## 6. Declarado, NO hecho (fuera de alcance)

- **`P3-2`/`P3-3` siguen ABIERTAS**: exigen la **ventana PAPER ≥4 días** real (operación del propietario).
- **`H-4` (LOW) ABIERTO**: esta fase no lo toca; el aviso `reason_contract` sigue haciéndolo visible.
- **`P3-5`/`OBS-5`**: declaradas.
- **`OBS-9` (nuevo, LOW doc-only)**: la frase «`1` = uso incorrecto: lo decide `argparse`» está **replicada**
  en otros CLIs del proyecto (`v2_75`/`v2_76`/`v2_77`/`v2_80`, `paper_material_readiness`,
  `paper_cycles_export`, `auto_evidence_validate`…) y **ninguno** la implementa. Se **declara**; el barrido
  es una fase docs-only aparte.
- **5 huecos locales PREEXISTENTES** de la matriz (`M117`/`M118`/`M170`/`M176`/`M197` no muerden en este
  entorno; idénticos a la evidencia de `v2.81-230`) — **no** los introduce esta fase.

## 7. Criterio de salida

`OBS-6`/`OBS-7`/`OBS-8` **cerradas** en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md), con
tests + mutaciones que muerden, compuertas verdes, matriz re-medida **232/232** y **auditoría externa** del
tag `v2.84-beta` que declare el instrumento **sostenido**.
