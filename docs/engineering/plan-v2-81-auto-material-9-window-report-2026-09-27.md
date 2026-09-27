# Plan de fase — `v2.81` / `AUTO-MATERIAL-9`: REAL WINDOW EXECUTION (informe de ventana)

> **AsOf:** 2026-09-27 · **Versión:** `2.05.0-beta → 2.06.0-beta` · **Tag:** `v2.81-beta` ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze:** `auto_simulation_worker.py`
> **intacto** · **Reparto:** `auto18-v1` / `auto15-v1` (`ALLOCATION = none`).

## 1. Contexto y origen

`v2.80-beta` (`2.05.0-beta`) cerró el matiz `STATE_UNRESOLVED` y el contrato del censo (`other>0` como
aviso + `reasonCatalogCoverage`) y entregó un **capturador read-only** de la serie diaria. La auditoría
externa de `v2.80` aprueba con **0 bloqueantes** y deja claro el siguiente paso: ya no toca más
arquitectura del motor, sino **observar** la ventana. §19/§20 piden, literalmente, la serie diaria con
`REGIME / PROPOSALS / UNRESOLVED / VETOES / OPERATED / FILLS / CYCLES / R / TOP_N / RESERVATIONS /
POSITION EVENTS / PRICE SOURCES / STRATEGY A / STRATEGY B` y, «especialmente», un **funnel de
operabilidad** por día para localizar **dónde** pierde oportunidades el AUTO; §22 pide un
**`unresolved_age`**.

Esta fase entrega esos instrumentos. **No** corre la ventana (operación del propietario): la hace
**medible y renderizable**.

## 2. Alcance (ficheros)

- `packages/py/application/src/bolsa_application/operability_window.py` — `build_operability_funnel`
  (puro), `unresolved_age` (puro) y `render_window_html` (puro, autocontenido); `build_window_row` gana
  `evidence=` (enriquecimiento opcional read-only) y publica `funnel` / `unresolvedAge`; `render_window_series`
  añade funnel y `unresolved_age`.
- `apps/api-python/scripts/v2_80_market_window.py` — `--forward` (evidence opcional, read-only) y `--html`
  (artefacto `operability_runs/operability-window.html`); `--render` publica el funnel.
- `packages/py/application/tests/test_operability_window.py` — funnel / `unresolved_age` / HTML.
- `apps/api-python/scripts/v2_44_mutation_audit.py` — `M226`–`M230` (matriz **225 → 230**).
- `package.json` — `2.05.0-beta → 2.06.0-beta`.
- `docs/engineering/*-v2-81-*`, `PROJECT_STATE.md`, `engineering-index-*.md`, `CHANGELOG.md`,
  `deuda-p3-*.md`, `runbook-ventana-forward-*.md`.

**No se toca:** `auto_simulation_worker.py` (congelado), `portfolio_decision_engine.py`,
`opportunity_ranker.py`, `market_regime_gate.py`, `aggregate_trial_regime`, `paper_material_readiness.py`,
`auto_reason_codes.py`, `TOP_N` ni umbrales.

## 3. Diseño

### 3.1 Funnel de operabilidad (puro)

Cada escalón se publica como `{"count": int | None, "source": str, "measured": bool}`; **nunca** un `0`
inventado. Escalones: `universe → marketData → regimeAllowed → signals → topN → risk → reservation →
orders → fills → cycles`.

- Con EVIDENCIA del runner (`--forward`): `universe=watchSize`, `marketData` = símbolos con precio
  (`priceSources` live/close o `sample.pricesServed`), `regimeAllowed=symbols_operable(marketRegime)`,
  `orders=turnTotals.orders`.
- DURABLES: `signals=decided`; `topN=signals-veto top_n`; `risk=topN-veto risk`;
  `reservation=risk-`vetos de reserva (`reservation_failed`/`_unmeasurable`/`_already_live`);
  `fills`/`cycles` del material durable.
- Regla dura: si un prerrequisito es `None`, el escalón que depende de él es `None` (no se fabrica una
  caída de cero).

### 3.2 `unresolved_age` (puro)

Histograma de permanencia de las propuestas (`approved`) sin desenlace, medido **dentro del día**
(referencia = último instante durable del día, para no inflar días antiguos). Cubos `lt1m`/`1to5m`/`5to20m`/
`gt20m`/`unknown`. Con timestamps ilegibles ⇒ `measured=false` y cubos `None`. Límite declarado
(`resolutionJoined=false`): no hay join propuesta→fill por identidad; es dwell desde la propuesta.

### 3.3 Informe HTML + JSON

`render_window_html(rows, meta)` (puro, `html.escape`, sin recursos externos, determinista): serie diaria,
veredicto del gate, funnel, distribución de motivos con cobertura, alerta de contrato y `unresolved_age`.
El JSON de la ventana (`--out`) ya lleva `gate` + `funnel` + `unresolvedAge` por fila.

### 3.4 Capturador read-only ampliado

`v2_80_market_window.py` gana `--forward PATH|GLOB` (repetible, read-only) y `--html PATH`; la escritura
sigue limitada a `operability_runs/` (journal propio + informe). `exit 0` con ≥1 día, `exit 2` sin material
legible.

## 4. Criterios de aceptación

- `ruff` limpio · import-linter `4 kept, 0 broken` · `mypy` `0 issues` (506 fuentes) · alembic head
  `046_fill_reference_mid`.
- `test_operability_window.py` **13 → 23** verdes; suite de aplicación sin regresiones.
- Funnel: sin `--forward` los escalones superiores son `None` (nunca `0`); con `--forward` completo.
- `unresolved_age` por cubos; sin timestamps ⇒ no medido.
- HTML determinista y escapado; publica el veredicto del gate y la alerta de contrato.
- `M226`–`M230` muerden y restauran byte a byte; matriz **230/230**; árbol intacto.

## 5. Reglas duras

- **No** se toca el freeze del worker ni el gobernador, `TOP_N`, umbrales ni el reparto.
- **No** se fuerza `AUTO_ENGINE_SIM_V2_REGIME`, **no** se backdatea `created_at`, **no** se sobrescribe
  `evidence_runs`/`evidence_validations`.
- **Forward, no replay**; capturador **read-only**; artefactos SOLO en `operability_runs/` (no versionado).
- Veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada.

## 6. Fuera de alcance

- **Correr la ventana ≥4 días** y cerrar `P3-2`/`P3-3` (`AUTO-22`/`AUTO-23`): operación del propietario.
- **`H-4` (LOW)**: se cierra tras la primera ventana real (§24 de la auditoría); aquí queda visible.
- **Diferenciar `UNRESOLVED` por causa temporal** (§23): se pospone hasta tener datos reales.
- `P3-5` y `OBS-5` siguen declaradas; `LIVE` y allocation dinámica siguen congelados.
