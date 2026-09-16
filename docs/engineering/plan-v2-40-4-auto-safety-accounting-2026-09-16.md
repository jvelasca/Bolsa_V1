# Plan V2.40.4 — AUTO Safety & Accounting (implementación)

> **Fecha:** 2026-09-16 · **Bump:** `1.65.3-beta` → `1.65.4-beta` · **Sin migración** (head sigue en
> `041_unique_natural_keys`). **Tag de referencia auditada:** `v2.40.2-beta` (anotado, apunta a
> `581067c4`, con el hotfix de idempotencia y la certificación A9 dentro).
>
> Este documento es el **plan de implementación** del slice, no el roadmap. El roadmap por fases
> (V2.40.4 → Adaptive AUTO) está en
> [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).

---

## 1. Qué cierra este slice (los cuatro agujeros de la auditoría)

| #   | Agujero detectado en `v2.40.2-beta`                                                                                                                                   | Cómo queda cerrado                                                                                                                                                                                                                                             |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `TOP_N` no era un tope de **evaluación**: los candidatos fuera del TOP llegaban con `score=None` y se journalizaban como `edge_below_threshold` (un motivo **falso**) | `TOP_N` = máximo de oportunidades evaluadas; las de fuera se journalizan con `top_n_excluded` y su score/rank **reales**; `approved <= top_n` es invariante                                                                                                    |
| 2   | `risk_used` y la exposición agregada se publicaban como un número "completo" aunque sumaran solo lo que sabían medir (**suelo** disfrazado de total)                  | `MeasurementStatus` (`COMPLETE`/`PARTIAL`/`UNKNOWN`) en riesgo y exposición + veto fail-closed `*_measurement_partial`/`*_measurement_unknown`                                                                                                                 |
| 3   | `open_orders: int` era un contador **muerto** (siempre 0): AUTO podía gastar dos veces el mismo cash                                                                  | Modelo puro `OpenOrder` + libro de pendientes desde `execution_events` no-`APPLIED` + `sim_fill_finance_context`; `reserved_cash`/`available_cash`/`pending_risk`/`pending_exposure` + veto `open_orders_unmeasurable` + razón `reserved_cash` en el allocator |
| 4   | `TradePlan` **sin validación**: un plan incoherente se serializaba y viajaba                                                                                          | `validate_trade_plan` (pura) + veto `plan_invalid` con las violaciones en el journal + `None` en el seam `trade_plan_to_decision_package`                                                                                                                      |

**Invariante que NO puede regresar:** _la reconciliación (y la medición) puede vetar aperturas,
nunca una salida protectora_ (`test_v2_recon_status_never_blocks_protective_exit`,
`test_incomplete_measurement_blocks_entries_but_never_protective_exits`).

---

## 2. W1 — Semántica real de `TOP_N` (tope de evaluación)

**Decisión fijada (Opción A, lectura literal de la auditoría):** `TOP_N` limita **cuántas
oportunidades se evalúan**. Las excluidas conservan su `OpportunityScore` completo y no pueden
operar.

**Código**

- `bolsa_analytics.cognitive.opportunity_ranker`: exporta `TOP_N_EXCLUDED = "top_n_excluded"` (el
  dueño natural del ranking, para no duplicar el literal en dos llamantes) y los docstrings de
  `select_top_opportunities`/`rank_opportunities` dicen explícitamente qué significa el tope.
- `bolsa_application.auto_v2_entry.plan_v2_tick`: `top = ranked[:cfg.top_n]`; `score_by_symbol` solo
  desde `top`; se itera **solo `top`** (orden de ranking); las elegibles fuera del TOP emiten una
  entrada de journal `top_n_excluded` que **porta su score y su rank reales**. Se eliminó el bloque
  `ordered.extend(...)` y el comentario que afirmaba lo contrario.
- `bolsa_application.auto_investment_system.run_auto_cycle`: misma regla (antes era la semántica
  inversa), con `build_top_n_excluded_payload` para el journal de los excluidos.

**Tests**

- `test_plan_v2_tick_top_n_limits_entries` (docstring corregido: afirma la semántica nueva).
- `test_plan_v2_tick_top_n_zero_excludes_everything` (fail-closed: `top_n = 0` ⇒ todo excluido).
- `test_plan_v2_tick_excluded_keeps_real_score_and_rank` (el score del excluido es el real y
  **jamás** aparece `edge_below_threshold`).
- `test_top_n_excluded_never_reports_false_edge` (camino `run_auto_cycle`).

---

## 3. W2 — Measurement status de riesgo y exposición

**Código nuevo (puro)** `bolsa_analytics/cognitive/measurement.py`: `MeasurementStatus`
(`Literal["COMPLETE","PARTIAL","UNKNOWN"]`) + constantes + `coerce_measurement`,
`measurement_from_counts`, `is_complete` y `combine_measurements`. Vive en su propio módulo para no
crear una dependencia circular entre `auto_portfolio_snapshot` y `open_order`.

**Código** `auto_portfolio_snapshot.py`

- `AutoPortfolioSnapshot.risk_measurement`: `COMPLETE` si todas las posiciones con `qty > 0`
  declaran `risk_amount` (o si no hay posiciones y no se aporta `risk_used`); `PARTIAL` si unas sí y
  otras no; `UNKNOWN` si hay posiciones y ninguna lo declara. Un `risk_used` **explícito** ⇒
  `COMPLETE` (el llamante afirma un número).
- `ExposureBreakdown.measurement`: derivado dentro de `aggregate_exposure` contando las posiciones
  saltadas por `market_value` no calculable. `total_pct` conserva su semántica (no se convierte en
  un 0 engañoso).
- Predicados `risk_is_complete` / `exposure_is_complete`.

**Código** `portfolio_decision_engine.py`: nuevos `DecisionReasonCode`
`risk_measurement_partial`, `risk_measurement_unknown`, `exposure_measurement_partial`,
`exposure_measurement_unknown` (todos en `_NO_TRADE_REASONS`), escalones insertados **después** de
`sector_exposure_unverifiable` y antes de la geometría (para no cambiar el código reportado en los
tests existentes) y flag explícito `require_complete_measurement: bool = True`.

**Deuda declarada:** el riesgo pendiente de una orden en vuelo sigue siendo un **suelo** (ver §4);
separa su propio estado de medición cuando llegue el `PortfolioRiskState` completo (fase Reservation
Engine).

---

## 4. W3 — `OpenOrder`, pending risk, reserved cash y reserved exposure

### W3a — Modelo puro `open_order.py`

`OpenOrder` frozen (`execution_id`, `order_id`, `venue_order_id`, `instrument_id`, `side`,
`requested_qty`, `remaining_qty`, `price`, `reserved_cash`, `risk_amount`, `sector`,
`strategy_version_id`, `trade_plan_id`, `status`) + `OpenOrderSummary` + `build_open_order` +
`summarize_open_orders` + `coerce_open_order`.

Reglas de honestidad (son el corazón del módulo):

- Una VENTA no añade riesgo: reserva 0 € de capital y 0 € de riesgo (libera o cierra).
- Una COMPRA reserva su notional; el **riesgo no se inventa**: solo se declara si el llamante lo
  aporta (`risk_amount` explícito, p. ej. desde un `TradePlan`).
- Una orden cuyo capital/riesgo/sector no se puede cuantificar no reserva 0: el resumen lo declara
  con `measurement != COMPLETE` y el motor **veta**.
- `open_orders: int → tuple[OpenOrder, ...]` es **breaking declarado en beta** (blast radius mínimo:
  `auto_v2_entry.build_worker_snapshot` y los tests del snapshot).

`AutoPortfolioSnapshot` gana `order_book_measurement`, `reserved_cash`, `available_cash`
(`cash − reserved_cash`, clamp, `None` si no hay `cash`), `pending_risk`, `pending_exposure` y
`risk_remaining = budget − (risk_used + pending_risk)`.

### W3b — Producción real (sin migración)

- `ExecutionEventStore.list_unapplied(account_id, *, statuses, limit)` en el protocolo, en
  `InMemoryExecutionEventStore` y en `PostgresExecutionEventStore` (`WHERE status IN (...)`,
  `ORDER BY captured_at DESC`, `LIMIT`). El productor de `OpenOrder` son las filas no-`APPLIED`; el
  instrumento/lado/cantidad/precio se resuelven con `SimFillFinanceContextStore.get(execution_id)`
  (PK ya indexada).
- `auto_simulation_worker._v2_refresh_open_orders()` (async, una vez por tick, antes de
  `_v2_snapshot`, mismo patrón que `_v2_refresh_trade_context`): filtra las trazas ya reconocidas por
  el libro del worker (`_applied_execution_events`, para no contar dos veces el mismo dinero),
  resuelve contexto financiero y sector, y publica `_v2_open_orders` +
  `_v2_order_book_measurement`. Un fallo de lectura, un `limit` alcanzado o un store que no sabe
  listar ⇒ `UNKNOWN` ⇒ veto de aperturas (nunca "no hay pendientes porque no pude leer").
- `risk_allocator.compute_allocation(reserved_cash=...)`: resta el capital comprometido del poder de
  compra y usa `CAP_RESERVED_CASH` como motivo (distinto de `CAP_BUYING_POWER`) para que el journal
  diga _por qué_ no hay cash.
- `_working_snapshot` (intra-tick) descuenta el notional ya aprobado del `cash`/`buying_power` y
  reenvía tupla y medición del libro.

**Deuda declarada:** no hay índice parcial en `execution_events(account_id, status)`. La lectura
queda acotada con `LIMIT` + `ORDER BY captured_at DESC` y la migración se asigna a la fase
Reservation Engine (junto con la tabla de reservas).

---

## 5. W4 — Validación de `TradePlan`

`validate_trade_plan(plan) -> tuple[str, ...]` (pura, vacío = válido) con códigos
`PLAN_VIOLATION_*`. Comprueba **coherencia interna**, no tolerancias: identidad
(`decision_id`/`instrument_id`), `execution_allowed ⟺ quantity > 0`, `direction` long/short si
ejecuta, `status == "TRIGGERED"` si ejecuta (lo exige `build_position_state_from_fill`), `entry > 0`,
stop del lado correcto, `target1 < target2` del lado correcto, `initial_risk_r == round4(|entry −
stop|)`, `risk_amount > 0`, `risk_pct > 0`, `position_value == round4(qty × entry)` y
`opportunity_score ∈ [0,1]`. Un input que no es un `TradePlan` ⇒ `PLAN_VIOLATION_UNREADABLE`
(fail-closed).

**Enganches**

- `decide_portfolio`: valida el plan antes de devolver la decisión aprobada; si viola ⇒
  `_reject("HOLD", "plan_invalid", plan_violations=...)`. Las violaciones viajan en
  `PortfolioDecision.plan_violations` y el journal las publica (`planViolations`) tanto en
  `_journal_entry` (V2) como en `build_decision_journal_payload` (orquestador).
- `trade_plan_to_decision_package`: segunda comprobación (defensa en profundidad en el seam que
  consume el worker) ⇒ `None` si el plan es incoherente.

**Nota:** los planes NO ejecutables (`WATCH`/`ARMED`/`BLOCKED`/`EXPIRED`) no se validan contra
geometría: llevan `quantity = 0` y pueden no tenerla. El validador solo exige los campos que solo
tienen sentido si el plan **ejecuta**.

---

## 6. Matriz de mutaciones (medida, no declarada)

Cada mutación se aplicó sobre el código de este slice, se corrió la suite y se revirtió. Todas
ponen suites en **rojo** (comando entre paréntesis):

| Mutación                                                                                                  | Efecto medido                                                                                                                                                                                               |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Quitar la rama `top_n_excluded` en `plan_v2_tick` (`packages/py/application/tests/test_auto_v2_entry.py`) | **3 rojos**: `test_plan_v2_tick_top_n_limits_entries`, `test_plan_v2_tick_top_n_zero_excludes_everything`, `test_plan_v2_tick_excluded_keeps_real_score_and_rank`                                           |
| Volver `buying_power` a cash bruto (`reserved_cash=None` en `decide_portfolio`)                           | **1 rojo**: `test_reserved_cash_lowers_available_buying_power` (qty 200 en vez de 50)                                                                                                                       |
| Desactivar los escalones de measurement (`if False and require_complete_measurement`)                     | **12 rojos**: 7 de medición/libro en `test_portfolio_decision_engine.py`, 4 de pendientes en `test_auto_v2_worker_integration.py` y `test_incomplete_measurement_blocks_entries_but_never_protective_exits` |
| Saltarse `validate_trade_plan` en `decide_portfolio`                                                      | **1 rojo**: `test_incoherent_plan_is_vetoed_not_emitted`                                                                                                                                                    |

---

## 7. Verificación ejecutada

- `packages/py/{domain,market,analytics,application,infrastructure}/tests`: **2685 passed, 1 xfailed**
  (236 s, hermético).
- `apps/api-python/tests`: **478 passed** + 2 rojos **pre-existentes y ajenos** a este slice
  (`integration/test_tax_report.py::test_tax_report_after_round_trip_trade`, 403 en el SELL — falla
  igual con el árbol limpio, comprobado con `git stash`; y `test_workspaces.py::test_workspaces_crud`,
  que pasa en aislamiento). Ambos están en la lista `--ignore` del job `quality`.
- `apps/api-python/tests/test_auto_v2_durable_pg.py`: **2 passed** contra PostgreSQL real (el nuevo
  certifica el caso crash-left-`CAPTURED`).
- Gate CI: las suites herméticas nuevas (`test_trade_plan.py`, `test_execution_event.py`) entran con
  nombre propio en el job `quality` de `python-ci.yml` y en el job `python` de `release-tag-ci.yml`;
  el test PG entra por fichero en `auto-v2-durable-pg` (ya en la lista `--ignore` de `quality`).

---

## 8. Riesgos y políticas declaradas (no efectos colaterales)

1. **Un pendiente no cuantificable bloquea aperturas hasta que la reconciliación lo materialice.**
   Es el comportamiento fail-closed pedido en la auditoría, y es una **política**: está escrita aquí,
   con su razón en el journal (`open_orders_unmeasurable`) y con su test.
2. **`open_orders: int → tuple[OpenOrder, ...]`** es breaking en beta (declarado en `CHANGELOG`).
3. **Sin índice por `account_id`** en `execution_events`: coste de lectura creciente, acotado por
   `LIMIT` + orden por captura; migración asignada a la fase Reservation Engine.
4. **El riesgo de un fill en vuelo es un suelo** (no hay stop en `sim_fill_finance_context`): una
   compra pendiente hace el libro no medible y veta. Es la lectura conservadora correcta; su
   refinamiento (riesgo pendiente medible) llega con el `PortfolioRiskState`.
