# Arranque del agente — `v2.81` / `AUTO-MATERIAL-9`: REAL WINDOW EXECUTION (informe de ventana)

> **Para:** el agente que retome tras el sello `v2.81-beta`. **AsOf:** 2026-09-27.
> **Estado:** fase **CERRADA** (`2.06.0-beta`, tag `v2.81-beta`), a la espera de la **auditoría externa**.

## 1. Qué se hizo (y qué NO)

- **Funnel de operabilidad (nuevo, puro)** `operability_window.build_operability_funnel`: diez escalones
  (`universe`→`cycles`) con `count`/`source`/`measured`; los superiores sólo con `--forward`, los durables
  por aritmética declarada del censo; `None` si falta el prerrequisito (nunca `0`).
- **`unresolved_age` (nuevo, puro)**: histograma intra-día (`lt1m`/`1to5m`/`5to20m`/`gt20m`/`unknown`) de
  las propuestas `approved` sin desenlace; `resolutionJoined=false` declarado.
- **Informe HTML (nuevo, puro)** `render_window_html(rows, meta)`: autocontenido, determinista, escapado;
  serie diaria + gate + funnel + motivos/cobertura + alerta de contrato + `unresolved_age`.
- **Capturador ampliado (read-only)** `v2_80_market_window.py`: `--forward` (evidencia opcional) y
  `--html`; `build_window_row(..., evidence=)` enriquece `priceSources`/`pairCapable`/`pairActive`/
  `symbolsObserved`.
- **Tests:** `test_operability_window.py` **13 → 23**; suite de aplicación **2071 passed**.
- **Mutaciones:** `M226`–`M230`; matriz **225 → 230**.
- **NO se hizo** (operación del propietario): **correr la ventana ≥4 días** ⇒ **`P3-2`/`P3-3` ABIERTAS**.

## 2. Qué comprobar primero (5 min)

1. `uv run --no-sync python -m pytest packages/py/application/tests/test_operability_window.py packages/py/application/tests/test_market_operability.py -q` → **81 passed**.
2. `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M226 M227 M228 M229 M230` → **5/5 muerden**, restauración byte a byte.
3. `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` y
   `uv run --no-sync lint-imports --config packages/py/.importlinter`.
4. `uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` → `0 issues`.

## 3. La siguiente fase (candidata)

- **La ventana ≥4 días** (operación, no código): correr el forward con el
  [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) actualizado y capturar la serie +
  el informe HTML con `v2_80_market_window.py --forward … --out … --html …`; sólo entonces `P3-2`/`P3-3`
  podrán cerrarse. Con la ventana medida, el **funnel** dirá si el cuello de botella es de MERCADO, de
  GOBERNADOR, de `TOP_N` o de RIESGO.
- **`H-4` (LOW, ABIERTO)**: declarar el vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`) **después** de la primera ventana: si esos códigos
  aparecen, `otherCount>0` y `reasonCatalogCoverage["unknown"]` lo dirán.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; sin migración
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; **forward, no replay**; el capturador es
**read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.
