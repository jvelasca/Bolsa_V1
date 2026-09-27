# Arranque del agente siguiente — post `v2.84` / `AUTO-MATERIAL-12`

> **Punto de entrada** para el siguiente chat/agente. **AsOf:** 2026-09-27 · **Estado:** `v2.84-beta`
> sellado y con CI; `OBS-6`/`OBS-7`/`OBS-8` **cerradas**. **Alembic head:** `046_fill_reference_mid`.

## 1. Qué acaba de pasar

Fase de **INSTRUMENTO READ-ONLY** (`2.09.0-beta`) que cierra los tres hallazgos de la auditoría externa de
`v2.83.1-beta` sobre `operability_audit.py`:

- `enrich_rows_with_evidence` **ya no pisa** un funnel medido (`_fill_funnel_gaps`).
- El funnel agregado de `window_totals` **ya no suma** días `measured=False`.
- El docstring del CLI declara la realidad de `argparse` (uso incorrecto = `2`).

**No** se tocó el motor congelado, el gobernador, `operability_window.py`, `TOP_N`, umbrales, allocation,
pesos A/B ni la UI. Detalle en el [relevo](./traspaso-relevo-post-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md).

## 2. Estado de la deuda

| Deuda | Estado |
|---|---|
| `OBS-6` / `OBS-7` / `OBS-8` | 🟢 **CERRADAS** en `v2.84` |
| `OBS-9` (doc-only, frase `1 = uso incorrecto` replicada en CLIs) | 🟡 ABIERTA y declarada |
| `P3-2` / `P3-3` | 🔴 ABIERTAS — exigen ventana PAPER ≥4 días **real** |
| `H-4` (LOW) | 🟡 ABIERTO — visible vía `warnings: reason_contract` |
| `P3-5`, `OBS-5` | 🟡 declaradas |

## 3. Camino natural (elige uno)

1. **Operación (recomendado, es el bloqueante real):** correr la **ventana PAPER ≥4 días** por el
   [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md) (preflight → forward diario →
   `v2_80_market_window.py` → `v2_83_window_audit.py` → gate `--level evidence` → `AUTO-22`/`AUTO-23`).
   Cierra `P3-2`/`P3-3`. **Requiere tiempo real de mercado** (no se puede fabricar).
2. **Fase docs-only `OBS-9`:** barrido coherente de la frase «`1` = uso incorrecto: lo decide `argparse`»
   en los CLIs hermanos (o un parser compartido que devuelva `1`).
3. **`H-4`:** cerrar la exhaustividad del contrato de motivos **importando** el vocabulario de su dueño y
   declarando familia para los cinco `signal_*` — decisión del auditor: **después** de la primera ventana
   real y **sólo** si `otherCount > 0`.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales `32/3/8/4/2` intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia.

## 5. Comandos de verificación rápida

```powershell
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 18 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M231 M232    # ambos muerden
```
