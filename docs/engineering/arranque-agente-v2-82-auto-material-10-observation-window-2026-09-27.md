# Arranque del agente — `v2.82` / `AUTO-MATERIAL-10`: OBSERVATION WINDOW (fase operativa)

> **Para:** el agente que retome tras el sello `v2.82-beta`. **AsOf:** 2026-09-27.
> **Estado:** fase **CERRADA** (`2.07.0-beta`, tag `v2.82-beta`), a la espera de la **auditoría externa**.

## 1. Qué es esta fase (y qué NO)

- **Es** un **marcador de fase operativo**: formaliza con `v2.82-beta` el paso que la auditoría de `v2.81`
  dejó como **operación del propietario** (la **ventana ≥4 días**), y **no** añade código.
- **NO** cambia el motor, el gobernador (`aggregate_trial_regime`), `TOP_N`, los umbrales, la allocation,
  los pesos de estrategia ni la lógica A/B.
- **NO** implementa la fila `TOTAL`, **no** cierra `H-4`, **no** implementa `resolutionJoined`: son
  mejoras futuras, con datos que las justifiquen.

## 2. Qué comprobar primero (5 min)

1. `git diff v2.81-beta..v2.82-beta --stat` → solo `package.json` + `docs/engineering/*` (+ `CHANGELOG.md`).
2. `uv run --no-sync python -m pytest packages/py/application/tests/test_operability_window.py packages/py/application/tests/test_market_operability.py -q` → **81 passed**.
3. `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` y
   `uv run --no-sync lint-imports --config packages/py/.importlinter`.
4. `uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` → `0 issues`.
5. `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` → **230/230**.

## 3. La siguiente fase (candidata): OPERAR, no construir

El siguiente hito **ya no es arquitectura**: es **mercado real**. La tarea es correr el forward diario con
el [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) y capturar la serie + el informe:

```powershell
$env:BROKER_VENUE="paper"
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out operability_runs/operability-window.json `
    --html operability_runs/operability-window.html
```

Sólo con **≥4 días distintos**, **≥2 episodios** y **≥32 ciclos medibles** el gate pasará a `READY` y
`P3-2`/`P3-3` podrán cerrarse (`AUTO-22`/`AUTO-23`). Entonces el **funnel** dirá si el cuello de botella
es de MERCADO, de GOBERNADOR, de `TOP_N` o de RIESGO — **sin** haber tocado `TOP_N` por intuición.

- **`H-4` (LOW, ABIERTO):** se cierra **después** de la primera ventana, y sólo si `otherCount > 0`
  (los `signal_*` de rechazo pre-ranqueo aparecen y `reasonCatalogCoverage["unknown"]` los nombra).
- **`resolutionJoined`:** evoluciona `unresolved_age` a **latencia de resolución** sólo cuando haya datos
  que justifiquen el coste.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; sin migración
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; **forward, no replay**; el capturador es
**read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.
