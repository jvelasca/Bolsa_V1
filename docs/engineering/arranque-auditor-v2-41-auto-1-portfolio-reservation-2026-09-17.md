# Arranque del auditor — V2.41 / AUTO-1 Portfolio Reservation Engine (`1.66.0-beta`)

> **Para quién es esto:** la persona (o el agente) que audita `v2.41-beta` sin acceso al entorno de
> desarrollo. Orden de lectura, afirmaciones verificables, mapa de código, comandos y preguntas abiertas.
> **Pack completo:** [`audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md`](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md).
> **Base sobre la que se asienta:** [`audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md`](./audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md)
> (`POSITION = Σ APPLIED`, ya cerrado y certificado).
> **Hoja de ruta:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §3.
> **Estado de la evidencia:** las cifras locales están medidas sobre este árbol; el commit de fase es
> [`e6b0dd5b`](https://github.com/jvelasca/Bolsa_V1/commit/e6b0dd5b) (21 ficheros, `+4207/−97`) y el tag
> anotado **`v2.41-beta` → `e6b0dd5b`**. CI: `Python CI` en `main` **GREEN** (run
> [`35201047304`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201047304), 5/5) y `Release-tag CI`
> **GREEN** (run [`35201538048`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201538048)); si lees
> el tip de `main` ya debería estar relleno.

**Bump:** `1.65.5-beta` → `1.66.0-beta`. **Alembic head:** `041_unique_natural_keys` →
`042_portfolio_reservations` (migración **aditiva**, sin backfill, `downgrade()` completo).

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

1. La reserva de cartera es un **objeto con identidad** y siete dimensiones comprometidas
   (`reserved_cash`, `reserved_risk`, `asset_exposure`, `sector_exposure`, `correlation`,
   `strategy_capacity`, `liquidity_capacity`), con ciclo de vida explícito (`OPEN`,
   `RELEASED_BY_FILL`, `RELEASED_BY_CANCEL`, `RELEASED_BY_RESTART`, `RELEASED_BY_ROLLBACK`) y
   `replay` determinista.
2. **No existe aprobación sin reserva**: en el tick, cada aprobación reserva en el mismo acto y, si la
   reserva no se puede construir, la aprobación **se degrada a veto** (`reservation_failed`).
3. **No existe reserva sin liberación**: por fill (parcial o total), por cancelación, por reinicio y por
   rollback de un tick; la liberación es **idempotente** y una parcial **mantiene viva la cola** con las
   dimensiones escaladas.
4. **`reserved_cash == Σ reservas vivas`** en el libro del tick (gate medido) y en el libro durable
   (filtro por cuenta + estado).
5. Las reservas vivas son la **autoridad** de `reserved_cash`/`pending_risk` del libro de pendientes: una
   traza de `execution_events` de un instrumento con reserva viva **no** se suma dos veces, y la cola en
   `RETRY` sigue siendo **capital reservado** (nunca posición ni realizado).
6. El **coste real** (comisión con el calendario de la cuenta, spread, slippage, hueco) entra en el
   sizing: `risk_real = stop_loss + comisión + spread + slippage`, con `ExpectedLoss` / `WorstCaseLoss` /
   `GapAdjustedLoss`; un coste no medible se declara (`cost_unmeasured`) y **nunca** se asume 0.
7. La **migración `042`** crea la tabla de reservas, sus tres índices y **el índice que faltaba**
   `execution_events(account_id, status)` (deuda declarada en `V2.40.4` §5.1 / `V2.40.5` §5.2), y es
   **reversible** (roundtrip verificado contra PostgreSQL real).
8. `pending_risk` deja de ser un **suelo**: el riesgo de la orden en vuelo entra por su reserva.

**NO afirma**

- Que `correlation`, `strategy_capacity` o `liquidity_capacity` estén **pobladas**: hoy el tick no tiene
  universo de correlación ni capacidad por estrategia ⇒ quedan no medidas y `correlation_adjusted_risk`
  **no descuenta** diversificación (fail-closed: no se inventa diversificación).
- Que el ledger de reservas sea la autoridad de capital de **toda** la plataforma (solo del camino del
  tick AUTO y de su libro de pendientes).
- Que exista política de **retención/compactación** de `portfolio_reservations` (la tabla es historia y
  crece con cada aprobación).
- Nada más allá de los runs de CI anotados en §7.1 del pack (el `Python CI` de `main`, el `Release tag CI`
  del tag y el `Python CI` re-disparado por el push del tag).

---

## 2. Qué cierra exactamente (y de dónde venía)

| Deuda declarada en la versión anterior                                                                           | Cómo la cierra `AUTO-1`                                                                                              |
| ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| La reserva era **intra-tick y anónima** (`committed[]` + `_working_snapshot`): moría al volver de `plan_v2_tick` | `ReservationLedger` del tick con identidad, dimensiones, eventos y `replay`; `V2TickPlan.reservations`               |
| **Nadie liberaba** el capital de la cola parcial (`RETRY`) reconocido en `V2.40.5`                               | Liberación por fill / cancelación / reinicio / rollback, idempotente, con estado y motivo en la fila durable         |
| **Nada sobrevivía al proceso** (la memoria del capital comprometido eran las trazas)                             | Tabla `portfolio_reservations` + `PostgresReservationStore`; reconciliación de arranque contra `APPLIED` e in-flight |
| **Sin índice** `execution_events(account_id, status)` (lecturas acotadas solo por `LIMIT`)                       | Migración `042` (índice **plano**, decisión declarada: un parcial dejaría fuera `APPLIED`)                           |
| **Coste real ausente** en el sizing                                                                              | `TradingCostModel` + `estimate_trading_cost` + `risk_real` en `AllocationResult`                                     |
| `pending_risk` como **suelo** no cuantificable                                                                   | Reserva con riesgo explícito ⇒ riesgo pendiente **medible**                                                          |

---

## 3. Dónde mirar el código (mapa mínimo)

| Qué                                                      | Dónde                                                                                                                                                                                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reserva, libro, `replay`, riesgo de cartera, coste       | `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reservation.py`                                                                                                                       |
| Coste en el sizing + cap codes nuevos                    | `packages/py/analytics/src/bolsa_analytics/cognitive/risk_allocator.py`                                                                                                                              |
| Normalización de hechos `APPLIED` (bug corregido: fecha) | `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py` (`_instant_text`)                                                                                                           |
| El tick: reserva por aprobación + `risk_state`           | `packages/py/application/src/bolsa_application/auto_v2_entry.py` (`plan_v2_tick`, `_reservation_for`, `_risk_state_for`, `_working_snapshot`)                                                        |
| Reason codes de reserva                                  | `packages/py/application/src/bolsa_application/auto_reason_codes.py`                                                                                                                                 |
| Coste en la decisión de cartera                          | `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`                                                                                                                         |
| Store durable (Protocol + in-memory + PG)                | `packages/py/application/src/bolsa_application/reservation_store.py`                                                                                                                                 |
| Migración `042` + espejo ORM                             | `packages/py/infrastructure/alembic/versions/042_portfolio_reservations.py`, `…/models/tables.py`                                                                                                    |
| Worker: autoridad del libro pendiente + reconciliación   | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_v2_pending_open_orders`, `_v2_persist_tick_reservations`, `_v2_reconcile_reservations`, `_v2_release_reservations_for_fill`) |
| Tests herméticos                                         | `packages/py/analytics/tests/test_portfolio_reservation_ledger.py`, `packages/py/application/tests/test_portfolio_reservation.py`                                                                    |
| Test PG (migración + durabilidad + reconciliación)       | `apps/api-python/tests/test_portfolio_reservation_pg.py`                                                                                                                                             |

---

## 4. Cómo verificar (comandos listos)

```bash
# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_portfolio_reservation_ledger.py \
               packages/py/application/tests/test_portfolio_reservation.py \
               packages/py/application/tests/test_auto_v2_entry.py -q

# 2) PG real (migración reversible + durabilidad + reconciliación). Un skip es FALLO.
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_RESERVATION_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_portfolio_reservation_pg.py -q -rs

# 3) Regresión de AUTO-1A (durabilidad, proceso y bucle del scheduler ×30)
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q

# 4) Estático con la invocación EXACTA de CI
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
           packages/py/application/src apps/api-python/src --follow-imports=silent
```

### Mutaciones sugeridas (deben poner suites en rojo)

| Mutación                                                            | Rojo esperado |
| ------------------------------------------------------------------- | ------------- |
| `_working_snapshot` devuelve la foto base (sin reservas vivas)      | **7**         |
| La liberación parcial no escala las dimensiones                     | **2**         |
| El libro pendiente suma la traza **y** la reserva                   | **1**         |
| `coerce_applied_fill_fact` vuelve a aceptar `applied_at` solo `str` | **2**         |
| El allocator asume coste 0 cuando no es medible                     | **1**         |

(Las cinco están **medidas** en el §3 del pack, con el rojo exacto y el fichero que lo delata.)

---

## 5. Preguntas abiertas que el auditor debería intentar romper

1. **`reserved_cash == Σ reservas vivas`**: ¿hay alguna ruta en la que el libro del tick y el snapshot
   discrepen? (La mutación M1 dice que el gate muerde; ¿muerde también con una reserva de cantidad 0 o
   con un `None` de capital?)
2. **Doble conteo**: ¿existe otro consumidor que sume `execution_events` **y** reservas fuera de
   `_v2_pending_open_orders`? (El pack afirma que el camino del tick está cubierto, no que lo esté todo).
3. **Retención**: la tabla `portfolio_reservations` es historia y crece por aprobación. ¿Aceptable en un
   horizonte de años? ¿Quién debería poseer la política de purga?
4. **Correlación**: al quedar `None`, `correlation_adjusted_risk` no descuenta nada. ¿Es la lectura
   correcta del fail-closed, o debería **vetar** en lugar de no descontar?
5. **Reconciliación**: la ventana temporal es "fill con `applied_at` posterior al alta de la reserva".
   ¿Qué pasa con relojes de PG vs reloj de aplicación en una cuenta con `applied_at` retrasado?
6. **`lease_generation`**: la columna existe y se persiste, pero **no** hay lógica de lease (propiedad
   de la reserva entre reinicios concurrentes). ¿Es deuda aceptable o un agujero? (Declarado, no
   escondido: el campo está en el §5 del pack como límite.)
