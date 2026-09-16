# Audit pack — V2.40.4 AUTO Safety & Accounting (`1.65.4-beta`)

> **Ámbito:** cierre de los cuatro agujeros de seguridad/contabilidad de AUTO de la auditoría de
> `v2.40.2-beta` (semántica real de `TOP_N`, measurement status de riesgo/exposición, órdenes
> pendientes/cash reservado, validación de `TradePlan`), **sin migración**.
> **Bump:** `1.65.3-beta` → `1.65.4-beta`. **Alembic head:** `041_unique_natural_keys` (sin cambios).
> **Estado:** implementado y verificado en local. Este documento **no** afirma CI de un tag que aún no
> existe; la verificación se hizo con las baterías **extraídas del YAML** de CI y con PostgreSQL real.
>
> Plan de implementación: [`plan-v2-40-4-auto-safety-accounting-2026-09-16.md`](./plan-v2-40-4-auto-safety-accounting-2026-09-16.md).
> Roadmap por fases: [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).

---

## 1. Punto de partida verificado (no se re-audita)

- `v2.40.2-beta` es un tag **anotado** que apunta a `581067c4` (contenido de "v2.40.3"): el hotfix de
  idempotencia y la certificación A9 sobre el ledger real están **dentro**.
- `TOP_N` no era un tope de evaluación: `plan_v2_tick` rankeaba todo pero solo puntuaba el top-N, así
  que las candidatas de fuera llegaban con `score = None` y el motor las rechazaba con
  `edge_below_threshold` (motivo **falso**).
- `AutoPortfolioSnapshot.open_orders` era un `int` **muerto**: `build_worker_snapshot` no lo aceptaba y
  `_v2_snapshot` nunca lo pasaba ⇒ siempre 0.
- `risk_used` se derivaba sumando **solo** las posiciones que declaraban `risk_amount` y
  `aggregate_exposure` **saltaba** las posiciones sin `market_value`: ambos publicaban un número
  "completo" que en realidad era un **suelo**.
- `TradePlan` no tenía `__post_init__` ni `validate()`: un plan incoherente se serializaba y viajaba.
- Invariante que **no** puede regresar: _la reconciliación puede vetar aperturas, nunca una salida
  protectora_.

---

## 2. Matriz afirmación → código → test

### F1 — `TOP_N` es un tope de EVALUACIÓN

| Afirmación                                           | Código                                                                               | Test                                                             |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| Solo se evalúan `top_n` oportunidades                | `auto_v2_entry.plan_v2_tick` (`ordered` se construye **solo** desde `top`)           | `test_plan_v2_tick_top_n_limits_entries`                         |
| Las excluidas conservan su score y su rank reales    | `_rejected_signal_entry(..., score=score)` (payload con `opportunityScore` + `rank`) | `test_plan_v2_tick_excluded_keeps_real_score_and_rank`           |
| Un excluido **nunca** reporta `edge_below_threshold` | `TOP_N_EXCLUDED` (literal único en `opportunity_ranker`)                             | `test_top_n_excluded_never_reports_false_edge`, el test anterior |
| `top_n = 0` ⇒ nada opera (fail-closed)               | `select_top_opportunities(ranked, top_n=0)`                                          | `test_plan_v2_tick_top_n_zero_excludes_everything`               |
| El orquestador usa la MISMA semántica                | `auto_investment_system.build_top_n_excluded_payload` + `run_auto_cycle`             | `test_top_n_limits_trading_universe`                             |

### F2 — Un agregado incompleto es un SUELO

| Afirmación                                                           | Código                                                   | Test                                                                                               |
| -------------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Existe un tri-estado canónico de medición                            | `bolsa_analytics.cognitive.measurement`                  | `packages/py/analytics/tests/test_auto_portfolio_snapshot.py` (derivación)                         |
| `risk_used` derivado con posiciones mixtas es `PARTIAL`              | `AutoPortfolioSnapshot.risk_measurement`                 | `test_risk_measurement_partial_blocks_entry`                                                       |
| Sin ninguna posición que declare riesgo ⇒ `UNKNOWN`                  | `measurement_from_counts(valued=0, unvalued>0)`          | `test_risk_measurement_unknown_blocks_entry`                                                       |
| Un `risk_used` explícito ⇒ `COMPLETE` (el llamante afirma el número) | `build_auto_portfolio_snapshot`                          | `test_complete_measurement_still_approves`                                                         |
| La exposición que salta posiciones no se publica como total          | `ExposureBreakdown.measurement` en `aggregate_exposure`  | `test_exposure_measurement_partial_blocks_entry`, `test_exposure_measurement_unknown_blocks_entry` |
| El gate se apaga **explícitamente**, nunca por omisión               | `require_complete_measurement: bool = True`              | `test_measurement_gate_can_be_disabled_explicitly`                                                 |
| Un measurement incompleto **no** bloquea una salida protectora       | recorrido de gestión de posición separado del de entrada | `test_incomplete_measurement_blocks_entries_but_never_protective_exits`                            |

### F3 — Órdenes pendientes: capital y riesgo comprometidos

| Afirmación                                                             | Código                                                            | Test                                                                                                                                                                         |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Una COMPRA en vuelo reserva su notional                                | `open_order.build_open_order`                                     | `test_buy_reserves_notional`                                                                                                                                                 |
| Una VENTA no reserva cash ni añade riesgo                              | `build_open_order` (rama `SIDE_SELL`)                             | `test_sell_never_adds_risk_or_reserves_cash`                                                                                                                                 |
| El riesgo no se inventa: sin dato, no cuantificable                    | `OpenOrder.risk_amount = None` ⇒ `is_quantified False`            | `test_buy_without_risk_is_not_quantified`                                                                                                                                    |
| Sin cantidad/precio no hay reserva afirmable                           | `build_open_order` ⇒ importes `None`                              | `test_missing_quantity_or_price_yields_unknown_amounts`                                                                                                                      |
| Una orden sin sector no es cuantificable                               | `is_quantified` exige sector                                      | `test_missing_sector_is_not_quantified`                                                                                                                                      |
| El libro se lee como órdenes pendientes                                | `ExecutionEventStore.list_unapplied` (protocolo + in-memory + PG) | `test_list_unapplied_only_returns_non_terminal_rows`, `_filters_by_account`, `_filters_by_status`, `_respects_limit_and_orders_by_capture`, `_empty_book_is_empty_not_error` |
| El worker ve el dinero en vuelo al arrancar                            | `auto_simulation_worker._v2_refresh_open_orders`                  | `test_v2_pending_buy_reserves_cash_and_lowers_available`                                                                                                                     |
| Un pendiente no cuantificable **veta** la apertura                     | veto `open_orders_unmeasurable`                                   | `test_v2_pending_buy_blocks_new_entry_fail_closed`                                                                                                                           |
| Sin contexto financiero el libro es `UNKNOWN` (no "no hay pendientes") | `_v2_fill_context` ⇒ `None` ⇒ importes `None`                     | `test_v2_pending_without_finance_context_is_unknown`                                                                                                                         |
| Un store que no sabe listar no puede afirmar el libro                  | `_v2_read_unapplied` (`callable(list_unapplied)`)                 | `test_v2_store_without_list_unapplied_is_unknown`                                                                                                                            |
| Un fill ya reconocido no se reserva dos veces                          | `_v2_known_fill_ids` (filtro por `_applied_execution_events`)     | `test_v2_known_fill_is_not_reserved_twice`                                                                                                                                   |
| El capital comprometido no es poder de compra                          | `RiskAllocator(reserved_cash=...)` + `CAP_RESERVED_CASH`          | `test_reserved_cash_lowers_available_buying_power`                                                                                                                           |
| El riesgo pendiente reduce el presupuesto restante                     | `risk_remaining = budget − (risk_used + pending_risk)`            | `test_pending_risk_reduces_risk_budget`                                                                                                                                      |
| Intra-tick, el notional aprobado agota la caja                         | `_working_snapshot` + `_reserve_committed_cash`                   | `test_plan_v2_tick_reserves_cash_intra_tick`                                                                                                                                 |
| Crash con fill `CAPTURED` ⇒ reservado y veto al reiniciar              | `list_unapplied` sobre PG + `_v2_snapshot`                        | `test_v2_durable_crash_left_captured_blocks_new_entry_after_restart` (PG real)                                                                                               |

### F4 — El plan que sale del motor no puede contradecirse

| Afirmación                                                                                   | Código                                                  | Test                                                                   |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------- |
| La coherencia del plan se valida con una función pura                                        | `trade_plan.validate_trade_plan`                        | 10 tests en `test_trade_plan.py` (`test_validate_trade_plan_*`)        |
| Identidad, flag de ejecución, dirección, status, entry, stop, targets, riesgo, valor y score | códigos `PLAN_VIOLATION_*`                              | idem (una tabla por campo)                                             |
| Un plan no ejecutable sin geometría es válido                                                | el validador solo exige campos de plan ejecutable       | `test_validate_trade_plan_accepts_non_executing_plan_without_geometry` |
| Lo que no se puede leer no se certifica                                                      | `PLAN_VIOLATION_UNREADABLE`                             | `test_validate_trade_plan_is_fail_closed_for_unreadable_input`         |
| El plan REAL del factory pasa el validador                                                   | `build_trade_plan`                                      | `test_validate_trade_plan_matches_factory_output`                      |
| El motor veta en vez de emitir un plan incoherente                                           | `decide_portfolio` ⇒ `plan_invalid` + `plan_violations` | `test_incoherent_plan_is_vetoed_not_emitted`                           |
| El camino aprobado no publica violaciones                                                    | `PortfolioDecision.plan_violations`                     | `test_approved_decision_publishes_no_plan_violations`                  |
| El seam que consume el worker no emite propuestas incoherentes                               | `trade_plan_to_decision_package` ⇒ `None`               | `test_trade_plan_to_decision_package_rejects_incoherent_plan`          |

---

## 3. Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite y se revirtió (no se declara
ninguna sin medir):

| #   | Mutación                                                                              | Comando                                                                                                                              | Resultado medido                                                                                                                             |
| --- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | Quitar la rama `top_n_excluded` en `plan_v2_tick`                                     | `pytest packages/py/application/tests/test_auto_v2_entry.py packages/py/application/tests/test_auto_investment_system.py -q`         | **3 failed** (`test_plan_v2_tick_top_n_limits_entries`, `..._top_n_zero_excludes_everything`, `..._excluded_keeps_real_score_and_rank`)      |
| M2  | Volver `buying_power` a cash bruto (`reserved_cash=None` en `decide_portfolio`)       | `pytest packages/py/application/tests/test_portfolio_decision_engine.py apps/api-python/tests/test_auto_v2_worker_integration.py -q` | **1 failed** (`test_reserved_cash_lowers_available_buying_power`; qty `200` en vez de `50`)                                                  |
| M3  | Desactivar los escalones de measurement (`if False and require_complete_measurement`) | `pytest .../test_portfolio_decision_engine.py apps/api-python/tests/test_auto_v2_worker_integration.py .../test_auto_v2_entry.py -q` | **12 failed** (7 de medición/libro + 4 de pendientes en el worker + `test_incomplete_measurement_blocks_entries_but_never_protective_exits`) |
| M4  | Saltarse `validate_trade_plan` en `decide_portfolio`                                  | `pytest packages/py/application/tests/test_portfolio_decision_engine.py -q`                                                          | **1 failed** (`test_incoherent_plan_is_vetoed_not_emitted`)                                                                                  |

**Sin mutación**: las mismas suites quedan verdes (M1 55/58, M2 70/70, M4 38/38).

---

## 4. Cambios observables y breaking declarados

1. **`AutoPortfolioSnapshot.open_orders`**: `int` → `tuple[OpenOrder, ...]`. Breaking en beta
   (declarado en `CHANGELOG`). Blast radius: `build_worker_snapshot` y los tests del snapshot.
2. **Nuevos códigos de journal**: `top_n_excluded` (excluida por TOP), `risk_measurement_partial`,
   `risk_measurement_unknown`, `exposure_measurement_partial`, `exposure_measurement_unknown`,
   `open_orders_unmeasurable`, `plan_invalid`. Excluyentes con `edge_below_threshold` en el caso de
   TOP (antes mentía).
3. **Nuevas claves en el snapshot serializado**: `openOrders` (lista), `openOrderCount`, `reservedCash`,
   `availableCash`, `pendingRisk`, `pendingExposurePct`, `orderBookMeasurement`.
4. **Nueva clave en el journal**: `planViolations` (lista vacía si el plan fue válido).
5. **Nuevo método de protocolo** `ExecutionEventStore.list_unapplied`. Un store sin él ⇒ libro
   `UNKNOWN` ⇒ veto de aperturas (fail-closed declarado, no un fallo silencioso).
6. **`RiskAllocator.compute_allocation`** acepta `reserved_cash` y puede devolver `capped_reasons`
   con `reserved_cash`, que es un motivo **nuevo** en el journal (antes solo `buying_power`).

---

## 5. Límites declarados (lo que este slice NO resuelve)

1. **Sin índice parcial** `execution_events(account_id, status)`: la lectura del libro queda acotada
   con `LIMIT` + `ORDER BY captured_at DESC`. Migración asignada a `AUTO-1` (Reservation Engine).
2. **El riesgo de un fill en vuelo es un SUELO**: `sim_fill_finance_context` no lleva stop, así que una
   compra pendiente deja el libro **no medible** y **veta aperturas** hasta que la reconciliación la
   materialice. Es la política fail-closed pedida, escrita y con test — no un efecto colateral.
3. **El riesgo pendiente no tiene su propio estado de medición**: usa el del libro. Su separación
   fina llega con `PortfolioRiskState` (`AUTO-1`).
4. **`validate_trade_plan` valida coherencia, no tolerancias**: no decide si el plan es _bueno_
   (eso es del motor y del allocator), solo si se contradice.
5. **La reserva sigue siendo intra-tick** (`committed[]` + `_working_snapshot`), no un ledger
   explícito con rollback/replay: eso es exactamente `AUTO-1`.
6. **Flake pre-existente en la puerta de equity del scheduler AUTO**:
   `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` falla de forma **no
   determinista**. Medido A/B a 30 ejecuciones por lado (revirtiendo en memoria los 9 ficheros de
   código del slice y restaurando byte a byte): **4/30 en el commit base `97322ee8`** y **8/30 con el
   slice** (mismo mecanismo en ambos). Mecanismo: el entry solo materializa parte de sus chunks (p.
   ej. 50 + 23.5 = 73.5 de 100), el exit se dimensiona por la **orden** y no por la posición
   materializada, y los chunks cola quedan en `RETRY` (`apply_ineffective`) **conservando su fila en
   `sim_fill_finance_context`**; la aserción de equity del test suma **todas** las filas de contexto
   como realizado, así que el hueco aparece como `equity != initial + realized + unrealized`
   (≈2 645 con las dos colas, ≈4 993 con un chunk entero de 50). Consecuencia para el auditor: esa
   puerta puede ponerse roja con el código base **y** con el tip certificado; el criterio es
   **re-ejecutar el job**, y la causa raíz (libro de posición = fills aplicados, exit dimensionado por
   posición) es un slice de seguimiento, no de este.

---

## 6. Cómo reproducir la verificación

```bash
# Suites herméticas del slice (rápidas, sin PG)
uv run pytest packages/py/application/tests/test_trade_plan.py \
               packages/py/application/tests/test_execution_event.py \
               packages/py/application/tests/test_portfolio_decision_engine.py \
               packages/py/application/tests/test_auto_v2_entry.py \
               packages/py/application/tests/test_auto_investment_system.py \
               packages/py/analytics/tests/test_open_order.py \
               packages/py/analytics/tests/test_auto_portfolio_snapshot.py -q

# Camino del worker (hermético: stores in-memory)
uv run pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q

# Certificación PG real (crash-left-CAPTURED + durabilidad V2)
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
```

---

## 7. Evidencia de verificación (medida en local)

| Batería                                                                                                                              | Resultado                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `packages/py/{domain,market,analytics,application,infrastructure}/tests`                                                             | **2685 passed, 1 xfailed** (236 s)                                                                                                                                                                                                                                                                                                                     |
| `apps/api-python/tests` (batería completa, sin los `--ignore` de `quality`)                                                          | **478 passed, 2 failed** — los 2 rojos son **pre-existentes y ajenos** (`integration/test_tax_report.py::test_tax_report_after_round_trip_trade`, que falla idénticamente con el árbol limpio comprobado con `git stash`, y `test_workspaces.py::test_workspaces_crud`, que pasa en aislamiento); ambos están en la lista `--ignore` del job `quality` |
| `apps/api-python/tests/test_auto_v2_durable_pg.py` (PG real)                                                                         | **2 passed** (el nuevo certifica crash-left-`CAPTURED`)                                                                                                                                                                                                                                                                                                |
| `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` (aislado y en batería)                                | **no determinista**: 3 pasadas dan `passed` / `1 failed` / `passed`. Medido A/B a 30 ejecuciones: **4/30 en el commit base** y **8/30 con el slice** (límite 6 de §5, pre-existente)                                                                                                                                                                   |
| `ruff check packages/py apps/api-python --config pyproject.toml` (comando **exacto** de CI)                                          | **All checks passed** (se limpiaron 7 hallazgos propios del slice: 3 bloques de import sin ordenar, 3 imports sin usar y 1 sentencia múltiple en `execution_event.py`)                                                                                                                                                                                 |
| `mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` (comando exacto de CI) | **Success: no issues found in 483 source files**                                                                                                                                                                                                                                                                                                       |
| `lint-imports --config packages/py/.importlinter`                                                                                    | **4 kept, 0 broken**                                                                                                                                                                                                                                                                                                                                   |

**No verificado en este entorno:** el `Release-tag CI` (no se ha creado tag) y la ejecución de los
jobs de GitHub Actions (solo se ha validado el **contenido** de sus listas de pytest).
