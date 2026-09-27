# Arranque del agente — `v2.80` / `AUTO-MATERIAL-8`: MARKET WINDOW

> **Para:** el agente que retome tras el sello `v2.80-beta`. **AsOf:** 2026-09-27.
> **Estado:** fase **CERRADA** (`2.05.0-beta`, tag `v2.80-beta`), a la espera de la **auditoría externa**.

## 1. Qué se hizo (y qué NO)

- **Instrumento (auditoría 2):** `market_operability.py` gana `STATE_UNRESOLVED` (propuestas sin veto ni
  desenlace ya **no** se leen `vetoed`; sigue fail-closed, nunca `no_signal`).
- **Contrato (auditoría 1 §20/§21):** `DECLARED_REASON_CODES`, `reason_catalog_coverage` y
  `other_veto_count`; `build_operability_record` publica `otherCount`/`contractViolation`/
  `reasonCatalogCoverage`; el render **avisa** (`ALERTA CONTRATO: other>0 …`) pero **no** tumba la corrida.
- **Ventana (nuevo, puro):** `operability_window.py` — `build_window_row`/`render_window_series`/
  `window_gate` (4 días de calendario, 2 episodios, 32 ciclos medibles).
- **Capturador (nuevo, read-only):** `apps/api-python/scripts/v2_80_market_window.py` — lee el journal
  durable + reservas + régimen + ciclo y emite la serie diaria; `operability_runs/` (no versionado).
- **Tests:** `test_market_operability.py` **48 → 58**; `test_operability_window.py` **nuevo, 13**;
  registrados en ambos workflows.
- **Mutaciones:** `M220`–`M225`; matriz **219 → 225**.
- **NO se hizo** (operación del propietario): **correr la ventana ≥4 días** ⇒ **`P3-2`/`P3-3` ABIERTAS**.

## 2. Qué comprobar primero (5 min)

1. `uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py packages/py/application/tests/test_operability_window.py -q` → **71 passed**.
2. `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M220 M221 M222 M223 M224 M225` → **6/6 muerden**, restauración byte a byte.
3. `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` y
   `uv run --no-sync lint-imports --config packages/py/.importlinter`.
4. `uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` → `0 issues`.

## 3. La siguiente fase (candidata)

- **`H-4` (LOW, ABIERTO)**: declarar el vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`) para que **no** caiga en `other` (hoy el nuevo
  `otherCount>0` lo hace **visible**). Es una fase **corta** de instrumento, sin decisión.
- **La ventana ≥4 días** (operación, no código): correr el forward con el
  [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) actualizado y capturar la serie
  con `v2_80_market_window.py`; sólo entonces `P3-2`/`P3-3` podrán cerrarse.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; sin migración
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; **forward, no replay**; el capturador es
**read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.
