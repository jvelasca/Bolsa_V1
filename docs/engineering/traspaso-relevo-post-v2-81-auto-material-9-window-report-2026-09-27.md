# Traspaso / relevo — post `v2.81` / `AUTO-MATERIAL-9`: REAL WINDOW EXECUTION (informe de ventana)

> **AsOf:** 2026-09-27 · **Estado:** fase **CERRADA** (`2.06.0-beta`, tag `v2.81-beta`), pendiente de
> **auditoría externa**. **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 1. Resumen de una línea

`v2.81` convierte el capturador de la ventana de `v2.80` en el **instrumento de observación** que pidió la
auditoría (§19/§20/§22): un **funnel de operabilidad** por día, un **`unresolved_age`** y un artefacto
`operability-window.json` / `operability-window.html`; **la ventana ≥4 días sigue siendo operación del
propietario**, no de código.

## 2. Ficheros entregados

| Fichero | Qué |
|---|---|
| `packages/py/application/src/bolsa_application/operability_window.py` | `build_operability_funnel`, `unresolved_age`, `render_window_html`; `build_window_row(evidence=)` publica `funnel`/`unresolvedAge`; `render_window_series` los incluye |
| `apps/api-python/scripts/v2_80_market_window.py` | `--forward` (evidencia opcional, read-only) y `--html` (`operability-window.html`); `--render` publica el funnel |
| `packages/py/application/tests/test_operability_window.py` | **13 → 23** tests (funnel, `unresolved_age`, HTML) |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M226`–`M230` (matriz **230**) |
| `package.json` | `2.05.0-beta → 2.06.0-beta` |

## 3. Cómo correr la ventana (operación del propietario)

```powershell
# 1) Forward diario real (>=4 dias) con el runbook:
#    docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md

# 2) Serie diaria + funnel + informe HTML desde el journal durable (read-only):
$env:BROKER_VENUE="paper"
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out operability_runs/operability-window.json `
    --html operability_runs/operability-window.html
```

**`exit 0`** con ≥1 día; **`exit 2`** sin material legible. Sin `--forward`, los escalones
`universe`/`marketData`/`regimeAllowed`/`orders` del funnel salen `None` (declarados); con `--forward` se
miden del runner. Los artefactos viven en `operability_runs/` (**no versionado**).

## 4. Cómo leer el funnel y el `unresolved_age`

- `universe → marketData → regimeAllowed → signals → topN → risk → reservation → orders → fills → cycles`:
  cada caída localiza el cuello de botella. `universe` alto con `regimeAllowed` bajo ⇒ el bloqueo es de
  **mercado/gobernador**; `signals` alto con `risk` bajo ⇒ el bloqueo es de **riesgo/plan**; `signals` alto
  con `topN` bajo ⇒ tope de **evaluación** (`TOP_N`), no de mercado.
- `n/d` significa **no medido** (nunca `0`): sin `--forward`, los escalones superiores no se pueden afirmar.
- `unresolved_age`: una propuesta resuelta en segundos es normal; `gt20m` frecuente delata un problema de
  **integración** que el contador `unresolved` no distingue.

## 5. Deuda y próximo paso

- **`H-4` (LOW) ABIERTO:** declarar el vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`). `otherCount`/`contractViolation`/`reasonCatalogCoverage`
  (v2.80) y el funnel (v2.81) lo hacen **visible**; el cierre formal es **después** de la primera ventana.
- **`P3-2`/`P3-3` ABIERTAS:** sólo se cierran con la **ventana ≥4 días** real (`AUTO-22`/`AUTO-23`).
- **`P3-5`** y **`OBS-5`** siguen declaradas.

## 6. Reglas duras (no negociables)

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; **sin migración**; reparto
`auto18-v1`/`auto15-v1`; **forward, no replay**; capturador **read-only**; veredicto honesto
`INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.
