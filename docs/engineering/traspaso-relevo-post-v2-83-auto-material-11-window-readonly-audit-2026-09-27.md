# Traspaso / relevo — post `v2.83` / `AUTO-MATERIAL-11`: AUDITORÍA READ-ONLY de la ventana PAPER

> **AsOf:** 2026-09-27 · **Estado:** fase **CERRADA** (`2.08.0-beta`, tag `v2.83-beta`), pendiente de
> **auditoría externa**. **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 1. Resumen de una línea

`v2.83` entrega el **instrumento de lectura** de la ventana: un módulo **puro** (`operability_audit.py`) y
un **CLI read-only** (`v2_83_window_audit.py`) que **agregan** un `operability_runs/` ya producido y
publican la **fila `TOTAL`** y las **tasas de operabilidad**. **No** se toca el motor, el gobernador,
`TOP_N`, los umbrales, la allocation, los pesos A/B ni una migración, y **no** se fabrica medición
(`n/d` ≠ `0`). El único cambio no-doc fuera del instrumento nuevo es `package.json`.

## 2. Ficheros entregados

| Fichero | Qué |
|---|---|
| `packages/py/application/src/bolsa_application/operability_audit.py` (**nuevo**) | puro: `window_totals`, `window_rates`, `window_audit`, `render_window_audit`, `enrich_rows_with_evidence`, `AUDIT_TOTAL_FIELDS` |
| `apps/api-python/scripts/v2_83_window_audit.py` (**nuevo**) | CLI read-only (`--window`/`--journal`/`--forward`/`--render`/`--json`/`--out`; `0`≥1 día · `2` sin material · `1` uso) |
| `packages/py/application/tests/test_operability_audit.py` (**nuevo**) | **16** tests puros |
| `.github/workflows/python-ci.yml` · `.github/workflows/release-tag-ci.yml` | **una línea** de registro del test nuevo en cada uno |
| `package.json` | `2.07.0-beta → 2.08.0-beta` (**único** cambio no-doc) |
| `docs/engineering/plan-v2-83-…md` · `audit-pack-v2-83-…md` · `arranque-auditor-v2-83-…md` · `arranque-agente-v2-83-…md` | docs de fase |
| `docs/engineering/traspaso-relevo-post-v2-83-…md` | este relevo |
| `docs/engineering/evidencia-auditoria-v2.83-2026-09-27.txt` | evidencia cruda LOCAL (compuertas + pre-D1 + smoke) |
| `docs/engineering/evidencia-ci-tag-v2.83-2026-09-27.txt` | CI del tag (POST-TAG) |

**No se toca** ningún módulo de motor ni el gobernador.

## 3. Cómo auditar la ventana (read-only; sin abrir el motor ni PostgreSQL)

```powershell
# 1) Ventana: serie diaria + funnel + informe HTML (read-only; ya existia en v2.81)
$env:BROKER_VENUE="paper"
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out operability_runs/operability-window.json `
    --html operability_runs/operability-window.html

# 2) AUDITORIA (esta fase): TOTAL acumulado + tasas + avisos
uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py `
    --window operability_runs/operability-window.json `
    --forward 'operability_runs/forward-market-*.json' --render `
    --out operability_runs/operability-audit.json
```

El auditor es **read-only**: **no** recalcula el gate ni los umbrales, **no** escribe en el journal
durable, `evidence_runs/` ni `evidence_validations/`. `--forward` **sólo** rellena los huecos declarados
(`orders`/`pairActive`) y **nunca** sobrescribe lo medido.

## 4. Las tasas (qué dicen y qué NO)

| Tasa | Fórmula | Lectura |
|---|---|---|
| `topNExclusionRate` | (signals − topN) / signals | cuánto corta el tope de evaluación |
| `riskRejectionRate` | (topN − risk) / topN | cuánto corta el presupuesto de riesgo |
| `reservationFailureRate` | (risk − reservation) / risk | cuánto corta la espina de reserva |
| `fillRate` | fills / orders | cuánto de lo enviado se materializa (**exige `--forward`**) |
| `cycleRate` | measurableCycles / fills | cuánto de lo llenado se cierra y es medible |
| `unresolvedRate` | días `unresolved` / días medidos | propuestas sin desenlace |

Cada tasa viaja con `numerator`/`denominator`/`coveredDays`/`source` y es `None` (`n/d`) si no hay días
medidos o el denominador es `0`: **nunca** un `0.0` fabricado. **No** sustituyen al gate: el veredicto de
la ventana sigue siendo `READY`/`INCONCLUSIVE` por `window_gate` (≥4 días, ≥2 episodios, ≥32 ciclos).

## 5. Verificación pre-D1 declarada (brechas ABIERTAS)

- **Régimen (2026-09-27):** preflight **exit 2** · `{range:8, trend_down:9, trend_up:3}` ⇒ `BEAR_TREND` ⇒
  **LONG VETADAS**. No se fuerza el régimen ni se elige un watch «que pase».
- **Barras:** **20/20** servidas ⇒ el scheduler de barras responde hoy.
- **Par A/B (`pairActive=true`) y cuenta fija:** **NO VERIFICABLES**: `PAPER_D_ACCOUNT_ID` está
  **comentado** en `.env` ⇒ brechas **ABIERTAS** (requiere estrategia B **ACTIVE** con `EdgeReport`).
- **Glob `operability_runs/forward-market-*.json`:** debe **excluir** fixtures (aún no hay bundle real).

## 6. Deuda y próximo paso

- **`P3-2`/`P3-3` ABIERTAS:** sólo se cierran con la **ventana ≥4 días** real (`AUTO-22`/`AUTO-23`).
- **`H-4` (LOW) ABIERTO:** esta fase lo hace **visible** en `warnings: reason_contract`; **no** lo cierra.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.
- **Siguiente (operación, tiempo real):** preflight → forward diario ≥4 días → `v2_80_market_window.py`
  → **`v2_83_window_audit.py`** → gate `--level evidence` → `AUTO-22`/`AUTO-23` → cierre de
  `P3-2`/`P3-3`.

## 7. Reglas duras (no negociables)

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales `32/3/8/4/2` intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia.
