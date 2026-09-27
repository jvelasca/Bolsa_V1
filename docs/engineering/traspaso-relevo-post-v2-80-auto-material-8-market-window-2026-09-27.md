# Traspaso / relevo — post `v2.80` / `AUTO-MATERIAL-8`: MARKET WINDOW

> **AsOf:** 2026-09-27 · **Estado:** fase **CERRADA** (`2.05.0-beta`, tag `v2.80-beta`), pendiente de
> **auditoría externa**. **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 1. Resumen de una línea

`v2.80` cierra el matiz de la auditoría 2 (`STATE_UNRESOLVED`) y las mejoras §20/§21 de la auditoría 1
(`other>0` como **aviso** + cobertura del catálogo) y añade un **capturador read-only** de la serie diaria
de la ventana desde el **journal durable**; **la ventana ≥4 días sigue siendo operación del propietario**.

## 2. Ficheros entregados

| Fichero | Qué |
|---|---|
| `packages/py/application/src/bolsa_application/market_operability.py` | `STATE_UNRESOLVED`; `DECLARED_REASON_CODES`; `reason_catalog_coverage`; `other_veto_count`; `otherCount`/`contractViolation`; aviso en el render |
| `packages/py/application/src/bolsa_application/operability_window.py` **(nuevo)** | `build_window_row`, `render_window_series`, `window_gate` (puro) |
| `apps/api-python/scripts/v2_80_market_window.py` **(nuevo)** | capturador read-only del journal durable + reservas |
| `packages/py/application/tests/test_market_operability.py` | **48 → 58** tests |
| `packages/py/application/tests/test_operability_window.py` **(nuevo)** | **12** tests puros |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M220`–`M225` (matriz **225**) |
| `.github/workflows/python-ci.yml`, `release-tag-ci.yml` | registro explícito de `test_operability_window.py` |
| `package.json` | `2.04.0-beta → 2.05.0-beta` |

## 3. Cómo correr la ventana (operación del propietario)

```powershell
# 1) Material PAPER real: forward diario (>=4 dias), capturando market_live si el bridge XTB responde.
#    Ver el runbook: docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md

# 2) Serie diaria desde el journal durable (read-only):
$env:BROKER_VENUE="paper"
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render

# 3) Gate honesto: si no hay >=4 dias / >=2 episodios / >=32 ciclos medibles => INCONCLUSIVE.
```

**`exit 0`** con ≥1 día; **`exit 2`** sin material legible. El journal propio vive en
`operability_runs/window.jsonl` (**no versionado**, gitignoreado). **No** abre escritura sobre el dinero,
**no** toca `evidence_runs/` y **no** recalcula el gate.

## 4. Deuda y próximo paso

- **`H-4` (LOW) ABIERTO:** declarar el vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`) para que no caiga en `other`. El nuevo
  `otherCount`/`contractViolation`/`reasonCatalogCoverage` **ya lo señala** (es el instrumento que lo
  hace visible). Fase candidata **corta**, de instrumento.
- **`P3-2`/`P3-3` ABIERTAS:** sólo se cierran con la **ventana ≥4 días** real (`AUTO-22`/`AUTO-23`).
- **`P3-5`** (`reserved_risk` sobrecargado) y **`OBS-5`** siguen declaradas.

## 5. Reglas duras (no negociables)

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; **sin migración**; reparto
`auto18-v1`/`auto15-v1`; **forward, no replay**; capturador **read-only**; veredicto honesto
`INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.
