# Traspaso / relevo — post `v2.84` / `AUTO-MATERIAL-12` (INSTRUMENT FUNNEL CONTRACT)

> **AsOf:** 2026-09-27 · **Estado:** fase **CERRADA** (`2.09.0-beta`, tag anotado **`v2.84-beta`**),
> pendiente de **auditoría externa** (objeto = `v2.84-beta`). **Alembic head:** `046_fill_reference_mid`
> (**SIN migración**).

## 1. Resumen de una línea

`v2.84` cierra, **sólo en el instrumento read-only**, los tres hallazgos de la auditoría de `v2.83.1-beta`:
el enriquecimiento **no pisa** un funnel medido (`OBS-6`), el agregado **no cuenta** días no medidos
(`OBS-7`) y el contrato de salida del CLI **dice la verdad** (`OBS-8`).

## 2. Por qué existe

La auditoría externa de `v2.83.1-beta` (`APROBADO CON OBSERVACIONES`, 0 bloqueantes) levantó dos
desviaciones de contrato en el funnel del instrumento de `v2.83` (byte-idéntico en aquel tag, porque su
re-sello era docs-only) y una imprecisión de documentación. Esta fase las cierra **sin** tocar motor,
gobernador ni migración, y **declara** una cuarta observación transversal (`OBS-9`).

## 3. Ficheros entregados

| Fichero | Qué |
|---|---|
| `packages/py/application/src/bolsa_application/operability_audit.py` | `OBS-6` (`_fill_funnel_gaps`) + `OBS-7` (funnel sobre `measured_rows`, `partial` vs `daysMeasured`, render `días/díasMedidos`) |
| `packages/py/application/tests/test_operability_audit.py` | **+2** tests de regresión (**18 passed**) |
| `apps/api-python/scripts/v2_83_window_audit.py` | `OBS-8`: docstring de códigos de salida corregido |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | marcadores `OPERABILITY_AUDIT`/`T_OPERABILITY_AUDIT` + **`M231`**/**`M232`** |
| `apps/api-python/scripts/ops_seed_window_pair.py` | **anexo OPS** (§2.1 del audit-pack): semilla de la ventana; **no** gate-certificada, **no** cierra `P3-3` |
| `package.json` | `2.08.1-beta → 2.09.0-beta` |
| `docs/engineering/*` (**nuevos**) | plan, audit-pack, arranque del auditor, arranque del agente, este relevo, **evidencia de matriz 232**, arranque operativo de la ventana |
| `docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md` | **docs-only**: cierra por semilla las brechas 1 y 2 (deja 3 y 4 vigentes) |
| `CHANGELOG.md` · `PROJECT_STATE.md` · `engineering-index` · `deuda-p3-…` | registro de la fase y cierre de `OBS-6/7/8` + alta de `OBS-9` |

**No se toca** ningún módulo de motor, gobernador ni el instrumento de ventana
(`operability_window.py`, `v2_80_market_window.py` quedan **idénticos**).

## 4. Qué comprobar en 5 minutos

```powershell
# 1) El diff no toca ficheros prohibidos (motor/gobernador/ventana/migracion/UI)
git diff v2.83.1-beta..v2.84-beta --stat

# 2) Compuertas
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 18 passed
uv run --no-sync pytest packages/py/application/tests -q                             # 2089 passed
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml      # All checks passed!
uv run --no-sync lint-imports --config packages/py/.importlinter                     # 4 kept, 0 broken

# 3) Las mutaciones nuevas muerden
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M231 M232
```

## 5. Cita del CI del tag `v2.84-beta` — PENDIENTE (se añade POST-TAG)

`Release tag CI` **solo corre al empujar** el tag, así que su resultado **no puede** estar dentro del
mismo tag (patrón declarado `OBS-3`/`OBS-4`). Se citará por hash en un commit **POST-TAG** (y, si procede,
en `evidencia-ci-tag-v2.84-2026-09-27.txt`).

## 6. Deuda y próximo paso

- **`OBS-6`/`OBS-7`/`OBS-8` CERRADAS**; **`OBS-9` (nuevo, doc-only) ABIERTA y declarada**.
- **`P3-2`/`P3-3` ABIERTAS:** solo se cierran con la **ventana PAPER ≥4 días** real (`AUTO-22`/`AUTO-23`).
- **`H-4` (LOW) ABIERTO:** esta fase no lo toca; sigue **visible** vía `warnings: reason_contract`.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.
- **Siguiente (operación, tiempo real):** preflight → forward diario ≥4 días →
  `v2_80_market_window.py` → **`v2_83_window_audit.py`** → gate `--level evidence` → `AUTO-22`/`AUTO-23`.
  Comandos exactos en el [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md).

## 7. Reglas duras (no negociables)

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales `32/3/8/4/2` intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia.
