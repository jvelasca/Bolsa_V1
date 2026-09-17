# Audit pack — V2.41 / AUTO-1 · Portfolio Reservation Engine (`1.66.0-beta`)

> **Ámbito:** la reserva de cartera deja de ser **artesanal e intra-tick** (`committed[]` +
> `_working_snapshot` locales dentro de `plan_v2_tick`) y pasa a ser un **motor de reservas explícito**:
> cada aprobación produce `Decision + Reservation`, la reserva tiene identidad, siete dimensiones
> comprometidas, coste real, ciclo de vida (fill / cancelación / reinicio / rollback), `replay` y
> **espejo durable** (sobrevive al proceso). Además, el coste real de negociación entra en el sizing y
> `pending_risk` deja de ser un suelo. **Bump:** `1.65.5-beta` → `1.66.0-beta`.
> **Alembic head:** `041_unique_natural_keys` → **`042_portfolio_reservations`**.
> **Estado:** implementado y verificado en local; sellado con **commit de fase + tag anotado
> `v2.41-beta`**. Commit de fase [`e6b0dd5b`](https://github.com/jvelasca/Bolsa_V1/commit/e6b0dd5b)
> (21 ficheros, `+4207/−97`) y tag anotado **`v2.41-beta` → `e6b0dd5b`**. `Python CI` en `main`
> **GREEN** (run [`35201047304`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201047304), 5/5).
> El **`Release-tag CI`** del tag y el `Python CI` re-disparado por su push quedaron medidos **después**
> de publicar y están en la tabla §7.1 (este pack se redactó antes y no afirmaba CI de un tag no
> publicado).
>
> **Especificación de la fase:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §3
> (`AUTO-1` — Portfolio Reservation Engine: objetivo, invariante, contenido, gate y criterio de salida).
> Punto de partida (`AUTO-1A` ya cerrado): [`audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md`](./audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md).
> Relevo de continuidad: [`traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md`](./traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md) §4 Tarea 1.
> Base sellada: `AUTO-1A` en tag **`v2.40.5-beta` → `d15f0a18`**, `main` con el commit docs-only
> `a983c7be`.

---

## 1. Punto de partida verificado (lo que este slice cierra)

- La reserva de cartera **no existía como objeto**: era una lista local (`committed`) y una foto de
  trabajo (`_working_snapshot`) que morían al volver de `plan_v2_tick`. Consecuencias medidas:
  - **nadie podía responder** "¿cuánto riesgo había reservado AUTO antes de lanzar esta orden?" (no
    había identidad, ni dimensión, ni evento);
  - **nada sobrevivía al proceso**: tras un reinicio la única memoria del capital comprometido eran las
    trazas de `execution_events`, y una traza no cubierta por reserva era "capital sin sujeto";
  - **no había liberación explícita**: la cola en `RETRY` se reconocía como capital (V2.40.5) pero nadie
    la liberaba por fill / cancelación / reinicio;
  - **no había coste real en el tamaño**: el sizing dimensionaba por la pérdida del stop y las
    fricciones (comisión, spread, slippage, hueco) no entraban en el presupuesto de riesgo.
- **Deuda declarada** por `V2.40.4` §5.1 y `V2.40.5` §5.2: sin índice `execution_events(account_id,
status)` (las dos lecturas del libro de órdenes — `list_applied` y `list_unapplied` — filtraban por
  cuenta y estado y quedaban acotadas solo por `LIMIT`), con la migración asignada explícitamente a
  `AUTO-1`.
- Invariantes que **no** se tocan: `AUTO ⇒ SIMULATED` (cero caminos LIVE nuevos), fail-closed
  (ausencia de evidencia ≠ aprobación; libro ilegible ⇒ aperturas vetadas y **salidas protectoras
  siempre permitidas**), `POSITION = Σ APPLIED`, `exit_qty <= materialized_qty`, migraciones
  aditivas/nullables sin backfill con `downgrade()` completo, long-only intacto y `PAPER_D_EXECUTE` off.

---

## 2. Matriz afirmación → código → test

### a) La reserva como objeto y el libro (analytics puro)

| Afirmación                                                                                          | Código                                                                                           | Test                                                                                             |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Cada aprobación produce una reserva con **identidad** (cuenta, tick, instrumento, estrategia, lado) | `PortfolioReservation` (`bolsa_analytics.cognitive.portfolio_reservation`) + `build_reservation` | `packages/py/analytics/tests/test_portfolio_reservation_ledger.py`                               |
| Dos reservas con la **misma identidad** no se pisan: la segunda devuelve `None`                     | `ReservationLedger.reserve` (guarda de clave)                                                    | idem (`test_ledger_refuses_a_second_reservation_with_the_same_identity`)                         |
| Una reserva sin cantidad viva **no** se da de alta                                                  | `ReservationLedger.reserve` (`remaining_qty <= eps`)                                             | idem (`test_ledger_refuses_a_reservation_without_live_quantity`)                                 |
| `reserved_cash`/`reserved_risk` son la **suma de las reservas vivas**                               | `ReservationLedger.reserved_cash` / `.reserved_risk`                                             | idem (`test_reserved_cash_and_risk_are_the_sum_of_live_reservations`)                            |
| Una reserva liberada aporta **0** al libro y conserva su importe original en la historia            | liberación con `factor = 0` + `ReservationEvent` de alta                                         | idem (`test_released_reservation_contributes_zero_to_the_book`, `…_keeps_the_original_amount_…`) |
| Una liberación **parcial** escala capital/riesgo/exposición y deja la cola **viva**                 | `ReservationLedger.release` (`factor = remaining / total`)                                       | idem (`test_release_by_fill_partial_scales_and_keeps_the_tail_reserved`)                         |
| La liberación es **idempotente** (nunca un doble liberado)                                          | `release` devuelve `None` si no hay nada vivo                                                    | idem (`test_release_is_idempotent`, `test_release_unknown_reservation_is_a_noop`)                |
| Cada motivo tiene su estado y se registra                                                           | `RELEASED_BY_FILL` / `_CANCEL` / `_RESTART` / `_ROLLBACK`                                        | idem (`test_release_by_restart_is_recorded_with_its_own_status`)                                 |
| El **rollback** libera solo las reservas del tick pedido                                            | `ReservationLedger.rollback`                                                                     | idem (`test_rollback_releases_only_the_requested_tick`)                                          |
| El **`replay`** reproduce el libro exactamente y es determinista                                    | `replay(eventos)`                                                                                | idem (`test_replay_reproduces_the_ledger_exactly`, `test_replay_is_order_deterministic_…`)       |
| Un libro con una reserva sin cuantificar **degrada** su medición (fail-closed)                      | `ReservationLedger.live_measurement` + `MeasurementStatus`                                       | idem (`test_live_measurement_degrades_when_a_dimension_is_missing`)                              |
| Las reservas vivas se proyectan como **posiciones comprometidas** solo para compras                 | `ReservationLedger.committed_positions`                                                          | idem (`test_committed_positions_projects_live_buys_only`)                                        |

### b) Riesgo de cartera y coste real (analytics puro)

| Afirmación                                                                                         | Código                                                        | Test                                                                                                                                                             |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| El estado de riesgo publica los **siete** agregados                                                | `build_portfolio_risk_state` → `PortfolioRiskState`           | `test_portfolio_risk_state_adds_positions_and_reservations`                                                                                                      |
| `correlation_adjusted_risk` es una cota **superior** que nunca descuenta diversificación no medida | `correlation_adjusted_risk` (solo suma `risk × max(0, corr)`) | `test_correlation_adjusted_risk_never_discounts_unknown_or_negative`, `…_rises_with_declared_positive_correlation`, `…_is_unknown_when_a_reservation_lacks_risk` |
| Una posición sin `risk_amount` **no** aporta 0: cuenta como **no medida**                          | `sector_risk_from_positions`                                  | `test_sector_risk_from_positions_counts_unmeasured_instead_of_zero`, `test_portfolio_risk_state_degrades_when_positions_are_unmeasured`                          |
| El coste real incluye comisión **real** (calendario de `account_settings`), spread y slippage      | `estimate_trading_cost` + `TradingCostModel.commission_for`   | `test_estimate_trading_cost_is_round_trip_and_includes_the_stop`, `test_commission_uses_the_real_account_fee_schedule`                                           |
| Sin stop el coste es **PARTIAL** y nunca 0; sin entrada es **UNKNOWN**                             | `estimate_trading_cost` (measuramento por componentes)        | `test_estimate_trading_cost_without_stop_is_partial_and_not_zero`, `test_estimate_trading_cost_without_entry_is_unknown`                                         |
| El hueco acota la pérdida cuando el stop no retiene                                                | `GapAdjustedLoss` / `WorstCaseLoss`                           | `test_gap_bounds_the_loss_when_the_stop_does_not_hold`                                                                                                           |
| El allocator recorta el tamaño para que el **riesgo real** quepa en el presupuesto                 | `compute_allocation(..., cost_model=…)`                       | `test_allocator_shrinks_the_size_so_real_risk_fits_the_budget`                                                                                                   |
| Coste **no medible** ⇒ se declara (`cost_unmeasured`), nunca se asume 0                            | `CAP_COST_UNMEASURED`                                         | `test_allocator_declares_an_unmeasurable_cost_instead_of_assuming_zero`                                                                                          |

### c) El tick: la reserva sustituye a `committed[]` (application)

| Afirmación                                                                                | Código                                                                | Test                                                                                                                        |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Toda aprobación del tick tiene una **reserva viva**                                       | `plan_v2_tick` + `ReservationLedger.reserve` + `_reservation_for`     | `packages/py/application/tests/test_portfolio_reservation.py`                                                               |
| La reserva lleva el **coste real** de la operación                                        | `_reservation_for` (`coerce_trading_cost(allocation["tradingCost"])`) | idem (`test_reservation_carries_the_real_cost_of_the_trade`)                                                                |
| Una aprobación cuya reserva no se puede construir **se degrada a veto**                   | `RESERVATION_FAILED` + `RESERVATION_REASONS`                          | idem (`test_vetoed_entries_leave_no_reservation`)                                                                           |
| Dos entradas del mismo tick **no** pueden reservar el mismo **capital**                   | `_working_snapshot` (caja/poder de compra netos de lo reservado)      | idem (`test_two_entries_cannot_reserve_the_same_cash`)                                                                      |
| Dos entradas del mismo tick **no** pueden reservar el mismo **riesgo**                    | `_working_snapshot` (`risk_used` + riesgo reservado)                  | idem (`test_two_entries_cannot_reserve_the_same_risk`)                                                                      |
| El libro cuadra con el snapshot: `reserved_cash == Σ reservas vivas`                      | `V2TickPlan.reservations` + `ReservationLedger.reserved_cash`         | idem (`test_tick_reserved_cash_equals_the_sum_of_live_reservations`)                                                        |
| El tick se puede **reproducir** (mismas reservas)                                         | `replay` sobre los eventos del libro del tick                         | idem (`test_replay_of_the_tick_reproduces_its_reservations`)                                                                |
| El tick publica un `PortfolioRiskState` consistente con sus reservas                      | `V2TickPlan.risk_state` + `_risk_state_for`                           | idem (`test_tick_publishes_a_risk_state_consistent_with_its_reservations`)                                                  |
| El **rollback** del tick devuelve el presupuesto                                          | `rollback` + `release_by_fill`                                        | idem (`test_rollback_of_the_tick_returns_the_budget`, `test_release_by_fill_of_a_tick_reservation_keeps_the_tail_reserved`) |
| Coste real **ON** por defecto y desactivable                                              | `_cost_model_from_env` + `V2Tunables.cost_model`                      | idem (`test_cost_model_is_on_by_default_and_can_be_disabled`, `test_cost_model_bps_are_env_calibrated`)                     |
| Semántica intra-tick de `AUTO-1A` **preservada** (riesgo 6/6, 25k exactos, sector ≤ 50 %) | `_working_snapshot` desde el libro                                    | `packages/py/application/tests/test_auto_v2_entry.py` (sin cambios de expectativa)                                          |

### d) Persistencia durable (migración + store)

| Afirmación                                                                                   | Código                                                                          | Test                                                                                                                               |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| La migración `042` es **aditiva** y crea tabla + 3 índices + el índice de eventos            | `042_portfolio_reservations` (`upgrade`)                                        | `apps/api-python/tests/test_portfolio_reservation_pg.py` (`test_migration_042_roundtrip_…`)                                        |
| El `downgrade` retira **tabla e índices** y `upgrade head` los recrea                        | idem (`downgrade`)                                                              | idem                                                                                                                               |
| El espejo ORM coincide 1:1 con la migración (y el baseline no copia `Index`)                 | `PortfolioReservationRow` + `execution_events_account_status_idx` (`tables.py`) | idem (presencia/ausencia medida en `pg_indexes`/`information_schema`)                                                              |
| `save` es **idempotente** y distingue alta de actualización                                  | `PostgresReservationStore.save` (`ON CONFLICT DO NOTHING` + `UPDATE`)           | idem (`test_reservation_survives_restart_…` primera mitad)                                                                         |
| La reserva **sobrevive al reinicio** (otra sesión/proceso) con sus dimensiones               | `list_live` (por cuenta y estado)                                               | idem                                                                                                                               |
| La liberación por **fill parcial** deja la cola como capital comprometido                    | `release` + reconciliación                                                      | idem                                                                                                                               |
| La liberación por **fill total** cierra la reserva sin borrar la fila                        | idem (`status='RELEASED_BY_FILL'`, `released_qty`)                              | idem                                                                                                                               |
| Una orden **en vuelo** (`RETRY`) sigue siendo capital reservado y **no** se cuenta dos veces | `_v2_pending_open_orders` (filtro `covered`)                                    | idem (`test_retry_trace_keeps_the_reservation_as_reserved_capital`)                                                                |
| Una orden que **murió sin llenarse** libera su capital al reiniciar                          | `_v2_reconcile_reservations`                                                    | idem (`test_reservation_of_a_dead_order_is_released_on_restart`)                                                                   |
| Un `applied_at` leído de PostgreSQL (`datetime`) **no** pierde la fecha                      | `_instant_text` en `coerce_applied_fill_fact`                                   | `packages/py/analytics/tests/test_position_ledger.py` (`test_coerce_normalizes_datetime_applied_at_to_iso`) + el test PG de arriba |

### e) Red de seguridad de CI

| Afirmación                                                                        | Dónde                                                                                                               | Verificación                            |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Los herméticos nuevos se ejecutan **con nombre propio**                           | `quality` (`python-ci.yml`) y `python` (`release-tag-ci.yml`)                                                       | §7.2 (ambas listas, extraídas del YAML) |
| El libro durable se certifica contra **PostgreSQL real** con gate fail-if-skipped | `auto-v2-durable-pg` (`python-ci.yml`) y `lifecycle-pg` (`release-tag-ci.yml`) con `AUTO_RESERVATION_PG_REQUIRED=1` | §7.2 (4 passed, 0 skipped)              |
| El fichero PG nuevo **no** queda como skip mudo en los jobs offline               | `--ignore` en ambos jobs offline                                                                                    | §7.2                                    |
| La head esperada por el test de snapshot de evidencia sube a `042`                | `test_discovery_evidence_snapshot_pg.py`                                                                            | §7.2                                    |

---

## 3. Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite y se revirtió (no se declara
ninguna sin medir):

| #   | Mutación                                                                         | Efecto medido                                                                                                                                                                           |
| --- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `_working_snapshot` devuelve la foto base (muere la autoridad del libro)         | **7 rojos**: 3 de `test_portfolio_reservation.py` (`vetoed_entries`, `two_entries_cannot_reserve_the_same_cash`, `…_same_risk`) + 3 intra-tick y 1 de sector de `test_auto_v2_entry.py` |
| M2  | La liberación parcial **no** escala las dimensiones (`factor = 1`)               | **2 rojos**: `test_release_by_fill_partial_scales_and_keeps_the_tail_reserved` y `test_release_by_fill_of_a_tick_reservation_keeps_the_tail_reserved` (20000 ≠ 10000)                   |
| M3  | El libro pendiente suma la traza **y** la reserva (se quita el filtro `covered`) | **1 rojo**: `test_retry_trace_keeps_the_reservation_as_reserved_capital` (20000 ≠ 10000)                                                                                                |
| M4  | `coerce_applied_fill_fact` vuelve a aceptar `applied_at` solo `str`              | **2 rojos**: el hermético nuevo **y** `test_reservation_survives_restart_and_is_released_by_the_materialized_fill` (PG real)                                                            |
| M5  | El allocator asume coste **0** cuando no es medible                              | **1 rojo**: `test_allocator_declares_an_unmeasurable_cost_instead_of_assuming_zero`                                                                                                     |

**Sin mutación**: la batería del §7.2 es la referencia (todo verde).

---

## 4. Cambios observables y breaking declarado (beta)

1. **Journal / reason codes nuevos**: `reservation_created`, `reservation_released_fill`,
   `reservation_released_cancel`, `reservation_released_restart`, `reservation_released_rollback`,
   `reservation_failed`, `reservation_unmeasurable`, `reservation_already_live` (agrupados en
   `RESERVATION_REASONS` de `auto_reason_codes.py`).
2. **`V2TickPlan` gana `reservations` y `risk_state`** (aditivo). Consumidor que ignore esos campos
   conserva el comportamiento anterior.
3. **`AllocationResult` gana `risk_real`, `risk_real_pct` y `trading_cost`**, y dos cap codes nuevos
   (`trading_cost`, `cost_unmeasured`). Sin `cost_model` el resultado es el histórico.
4. **Autoridad del libro pendiente**: `reserved_cash`/`pending_risk` se derivan de las reservas vivas;
   una traza de `execution_events` de un instrumento con reserva viva ya **no** se suma otra vez.
   Un consumidor que sumara ambos libros contaría el capital dos veces (es exactamente lo que mide M3).
5. **Base de datos**: nueva tabla `portfolio_reservations` (aditiva y nullable; **sin backfill**) +
   índice `execution_events(account_id, status)` + 3 índices del libro de reservas. `downgrade()`
   completo.
6. **Sin cambios** en el spine de settlement, en el ledger de posición/caja ni en `check_opening`:
   toda intención sigue pasando por el mismo camino SIM. `AUTO ⇒ SIMULATED` intacto; ningún camino
   LIVE nuevo; sin LLM en el hot path.

---

## 5. Límites declarados (lo que este slice NO resuelve)

1. **`correlation`, `strategy_capacity` y `liquidity_capacity`** existen como dimensiones de la reserva
   y se pueblan cuando el contexto las declara, pero **hoy el tick no tiene universo de correlación ni
   capacidad por estrategia**: en el camino del tick quedan `None` (no medidas) y
   `correlation_adjusted_risk` **no descuenta** diversificación. Poblarlas es `AUTO-3`/`AUTO-4`.
2. El **productor desde `execution_events`** no se elimina: queda como **reconciliación de arranque**
   (es la red de seguridad del crash entre la captura del fill y el alta de la reserva).
3. La tabla `portfolio_reservations` **crece con cada aprobación** (es historia: una reserva liberada no
   se borra). **No** hay job de compactación/purga declarado todavía.
4. `pending_risk` es medible **solo** si la reserva declara riesgo; sin dato el agregado baja de
   medición y el motor **veta** aperturas (las salidas protectoras siguen permitidas).
5. El **índice de `execution_events` se crea plano** `(account_id, status)`, no parcial: un parcial
   (`WHERE status <> 'APPLIED'`) dejaría fuera la lectura de `APPLIED`, que es la autoridad de posición
   desde `V2.40.5`. La decisión está documentada en el docstring de la migración.
6. **`lease_generation`** viaja en la reserva y en su fila durable (espejo 1:1), pero **no** hay todavía
   lógica de _lease_ para reservas: no existe adquisición/robo de propiedad entre procesos. Es un campo
   preparado, **no** una garantía de exclusión multi-proceso. La exclusión actual es por identidad de
   reserva (`reservation_id` derivado de la decisión) y por cuenta.
7. **Lo que este pack NO afirma**: que el ledger de reservas sea la autoridad de **todos** los
   consumidores de capital de la plataforma (solo del camino del tick AUTO y de su libro de pendientes);
   que exista una política de retención de la tabla nueva; y que la correlación se esté midiendo.

---

## 6. Cómo reproducir la verificación

```bash
# 1) Estático (invocación EXACTA de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_portfolio_reservation_ledger.py \
               packages/py/application/tests/test_portfolio_reservation.py \
               packages/py/application/tests/test_auto_v2_entry.py -q

# 3) Offline del job `quality` (usa EXACTAMENTE su lista y sus --ignore, extraída del YAML)
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"

# 4) PG real (certificación)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_RESERVATION_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_portfolio_reservation_pg.py -q
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py \
    apps/api-python/tests/test_instrument_trade_context_pg.py \
    apps/api-python/tests/test_unique_natural_keys_pg.py \
    apps/api-python/tests/test_discovery_evidence_snapshot_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q

# 5) Batería completa de paquetes
uv run pytest packages/py -q
```

---

## 7. Evidencia de verificación

### 7.1 CI real de GitHub

| Gate                                           | Run                                                                            | Resultado                                                                                                                                                                                                                                                   |
| ---------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Python CI` (push a `main`, commit `e6b0dd5b`) | [`35201047304`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201047304) | **GREEN 5/5**: `quality`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`                                                                                                                                                  |
| `Release tag CI` (tag `v2.41-beta`)            | [`35201538048`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201538048) | **GREEN**: `frontend`, `decision-spine`, `security`, `shared`, `lifecycle-pg`, `dr-verify`, `playwright (mock E2E)`, `a7-gate`, `python` y `certify (aggregate + artifact)` en `success`; `playwright (integrated E2E, opt-in)` en `skipped` (es su diseño) |
| `Python CI` (re-disparado por el push del tag) | [`35201537986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201537986) | **GREEN 5/5**: el push del tag vuelve a disparar los workflows de `push` sobre el mismo commit (mismos 5 jobs)                                                                                                                                              |

**Honestidad declarada:** este documento se redactó **antes** del push y del tag, y la tabla de arriba se
completó **después** en el commit docs-only de cierre (mismo patrón que el sellado de `v2.40.5`/`AUTO-1A`)
con los run id medidos. El commit de sellado **no** re-dispara `Python CI` (solo toca `docs/**`) y **no**
entra en el tag: el tag apunta al commit de fase `e6b0dd5b`.

### 7.2 Baterías locales (medidas en el árbol final del slice, antes de publicar)

| Batería                                                                                                        | Resultado                                                                                                                                                 |
| -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (invocación de CI)                            | `All checks passed!`                                                                                                                                      |
| `mypy … --follow-imports=silent`                                                                               | **486 ficheros, 0 issues**                                                                                                                                |
| `lint-imports --config packages/py/.importlinter`                                                              | **4 kept / 0 broken**                                                                                                                                     |
| Suites herméticas nuevas                                                                                       | **49 passed** (`test_portfolio_reservation_ledger.py` + `test_portfolio_reservation.py`)                                                                  |
| **Job `quality` completo** (comando **extraído del YAML**, con la lista y los `--ignore` nuevos)               | **exit 0** (`1858 passed`, 0 skipped, 86 s)                                                                                                               |
| `pytest packages/py` (batería completa de paquetes)                                                            | **2779 passed**, 1 skipped (Ollama ausente: entorno) y 1 xfailed ⇒ **0 rojos preexistentes** (A/B con `git stash` innecesario: no hubo rojo que atribuir) |
| `AUTO_RESERVATION_PG_REQUIRED=1 … test_portfolio_reservation_pg.py`                                            | **4 passed** (0 skipped): roundtrip `042`, reinicio, liberación por fill (parcial y total), `RETRY` como capital reservado sin doble conteo, orden muerta |
| `AUTO_V2_DURABLE_PG_REQUIRED=1 …` (durable + contexto + claves + snapshot)                                     | **29 passed**                                                                                                                                             |
| `AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 … test_a9_scheduler_process_pg_zero_human.py`                            | **2 passed** (31,7 s)                                                                                                                                     |
| `AUTO_SCHEDULER_PG_REQUIRED=1 … test_auto_scheduler_real_pg_zero_human_intervention.py` ×30                    | **0 fallos** (2 tests por ejecución ⇒ 60 en verde; regresión de `AUTO-1A`)                                                                                |
| Delta del job `python` del tag respecto a `quality` (8 ficheros de `packages/py/application/tests` + 2 de app) | **81 passed**                                                                                                                                             |

**Lo que este pack afirma:** las cifras anteriores, medidas en local sobre el árbol del slice, y la
matriz de mutaciones del §3 (cada una aplicada y revertida), más los tres runs de CI listados en §7.1
(los que se midieron: `Python CI` de `main`, `Release tag CI` del tag y el `Python CI` re-disparado por el
push del tag). **Lo que NO afirma:** ningún otro run de CI, ni el comportamiento de consumidores fuera del
camino del tick AUTO (§5.7).
