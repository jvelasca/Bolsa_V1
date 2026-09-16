# Arranque del auditor — V2.40.4 AUTO Safety & Accounting (`1.65.4-beta`)

> **Qué auditar:** el slice `V2.40.4` (Safety & Accounting) sobre `1.65.3-beta`, **sin migración**
> (Alembic head `041_unique_natural_keys`).
> **Qué commit auditar:** tag anotado **`v2.40.4-beta` → `1127d010`** (slice `a60f72c1` + el fix de un
> test que CI puso rojo). `main` está en `1127d010` + el commit **docs-only** de sellado que estás
> leyendo, que **no** forma parte del tag.
> **Estado de CI (sellado):** `Release tag CI` **GREEN** (run
> [`35155027506`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35155027506): 9 jobs requeridos +
> `certify`) y `Python CI` **GREEN** en `main` (run
> [`35154788932`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35154788932): 5/5 jobs). El primer
> intento (`35150808768`) dejó `quality` rojo por un test propio mal afirmado; el detalle está en §7.1
> del audit-pack.
> **De dónde leer (orden recomendado, 15-30 min):**
>
> 1. **Este fichero** (alcance, mapa de artefactos, qué NO se afirma).
> 2. [`audit-pack-v2.40.4-auto-safety-accounting-2026-09-16.md`](./audit-pack-v2.40.4-auto-safety-accounting-2026-09-16.md) — matriz afirmación→código→test, mutaciones **medidas**, límites declarados.
> 3. [`plan-v2-40-4-auto-safety-accounting-2026-09-16.md`](./plan-v2-40-4-auto-safety-accounting-2026-09-16.md) — plan de implementación (los 4 workstreams).
> 4. [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) — roadmap por fases (`AUTO-1`…`AUTO-8`) con invariante, gate y criterio de salida por fase.
> 5. El tag: `git show --stat v2.40.4-beta` (código auditado) y `CHANGELOG.md` `[1.65.4-beta]`.

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

- `TOP_N` es un **tope de evaluación** y las candidatas excluidas conservan su score/rank reales
  (`top_n_excluded`), nunca `edge_below_threshold`.
- El riesgo y la exposición agregados publican **estado de medición** (`COMPLETE`/`PARTIAL`/`UNKNOWN`)
  y un agregado incompleto **veta** la apertura nueva.
- Existe un **libro de órdenes pendientes** con `reserved_cash`/`available_cash`/`pending_risk`/
  `pending_exposure`, derivado de `execution_events` no-`APPLIED` + `sim_fill_finance_context`, y el
  capital comprometido **no** es poder de compra.
- El `TradePlan` que sale del motor **no puede contradecirse a sí mismo**; si lo hace, el motor veta
  (`plan_invalid`) con las violaciones en el journal.
- Ninguna de estas garantías puede vetar una **salida protectora**.

**No afirma**

- Que la reserva de cartera sea un ledger explícito con rollback/replay: eso es `AUTO-1`
  (Reservation Engine) y está declarado como deuda.
- Que el riesgo de un fill en vuelo sea **medible**: es un **suelo** que veta (política declarada).
- Que exista índice parcial `execution_events(account_id, status)`: no lo hay (deuda con migración
  asignada a `AUTO-1`).
- Que **todas** las puertas de CI sean deterministas:
  `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` es un **flake
  pre-existente** (medido A/B a 30 ejecuciones: **4/30 en el commit base** y **8/30 con el slice**;
  mismo mecanismo en ambos). Se ejecuta **con PG real** en los jobs `lifecycle-pg` (donde un skip es
  fallo duro), así que puede re-dispararse; en el sellado de este tag salió verde en las dos puertas
  (`35154788932`, `35155027506`). Declarado en §5.6 del audit-pack; si sale rojo, el criterio es
  re-ejecutar el job.

---

## 2. Los cuatro hallazgos de la auditoría y su cierre

| Hallazgo (auditoría `v2.40.2-beta`)                                         | Cierre                                                                 | Test que lo muerde                                                                                                                           |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `TOP_N` = prioridad ⇒ motivo `edge_below_threshold` **falso** en el journal | Tope de **evaluación** + `top_n_excluded` con score/rank reales        | `test_plan_v2_tick_excluded_keeps_real_score_and_rank`, `test_top_n_excluded_never_reports_false_edge`                                       |
| `risk_used`/exposición publicados como total siendo un **suelo**            | `MeasurementStatus` + vetos de medición                                | `test_risk_measurement_partial_blocks_entry`, `test_exposure_measurement_partial_blocks_entry`                                               |
| `open_orders: int` muerto ⇒ el mismo cash podía gastarse dos veces          | `OpenOrder` + `list_unapplied` + `reserved_cash` + `CAP_RESERVED_CASH` | `test_v2_pending_buy_reserves_cash_and_lowers_available`, `test_reserved_cash_lowers_available_buying_power`, el PG de crash-left-`CAPTURED` |
| `TradePlan` sin validación                                                  | `validate_trade_plan` + `plan_invalid` + `None` en el seam             | `test_validate_trade_plan_*` (10), `test_incoherent_plan_is_vetoed_not_emitted`                                                              |

---

## 3. Dónde mirar el código (mapa mínimo)

| Pieza                                                                 | Fichero                                                                                                                                                      |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Tope de evaluación + journal honesto                                  | `packages/py/application/src/bolsa_application/auto_v2_entry.py` (`plan_v2_tick`, `_working_snapshot`, `_reserved_committed_cash`, `_rejected_signal_entry`) |
| `TOP_N_EXCLUDED` (dueño del literal)                                  | `packages/py/analytics/src/bolsa_analytics/cognitive/opportunity_ranker.py`                                                                                  |
| Tri-estado de medición                                                | `packages/py/analytics/src/bolsa_analytics/cognitive/measurement.py` (**nuevo**)                                                                             |
| Snapshot con `reserved_cash`/`available_cash`/`pending_*`             | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_portfolio_snapshot.py`                                                                             |
| Libro de órdenes pendientes                                           | `packages/py/analytics/src/bolsa_analytics/cognitive/open_order.py` (**nuevo**)                                                                              |
| Vetos (`*_measurement_*`, `open_orders_unmeasurable`, `plan_invalid`) | `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`                                                                                 |
| Reserva de capital en el sizing                                       | `packages/py/analytics/src/bolsa_analytics/cognitive/risk_allocator.py` (`CAP_RESERVED_CASH`)                                                                |
| Validación del plan                                                   | `packages/py/analytics/src/bolsa_analytics/cognitive/trade_plan.py` (`validate_trade_plan`)                                                                  |
| Lectura de pendientes (in-memory + PG)                                | `packages/py/application/src/bolsa_application/execution_event.py` (`list_unapplied`)                                                                        |
| Refresco del libro por tick                                           | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_v2_refresh_open_orders`)                                                             |

---

## 4. Cómo verificar (comandos listos)

```bash
# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/application/tests/test_trade_plan.py \
               packages/py/application/tests/test_execution_event.py \
               packages/py/application/tests/test_portfolio_decision_engine.py -q

# 2) Camino del worker (stores in-memory)
uv run pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 3) PG real (crash-left-CAPTURED + durabilidad V2)
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
```

### Mutaciones sugeridas (deben poner suites en rojo)

1. Quitar la rama `top_n_excluded` en `plan_v2_tick` ⇒ `test_auto_v2_entry.py` en rojo.
2. Pasar `reserved_cash=None` al allocator en `decide_portfolio` ⇒
   `test_reserved_cash_lowers_available_buying_power` en rojo.
3. `if False and cfg.require_complete_measurement` ⇒ 12 rojos (medición, pendientes y salidas
   protectoras).
4. Sustituir `validate_trade_plan(plan)` por `()` en `decide_portfolio` ⇒
   `test_incoherent_plan_is_vetoed_not_emitted` en rojo.

(Los cuatro están **medidos**; el resultado exacto está en §3 del audit-pack.)

---

## 5. Preguntas abiertas que el auditor debería intentar romper

1. **¿Puede un pendiente bloquear una salida?** Debe ser **no**: la política fail-closed solo aplica a
   aperturas. Ver los tests de salida protectora.
2. **¿Puede el mismo cash reservarse dos veces** entre el libro persistido y las posiciones ya
   reconocidas por el worker? El filtro `_v2_known_fill_ids` es la defensa; ver su test.
3. **¿Un `limit` alcanzado se interpreta como "no hay más"?** Debe ser **no** (`UNKNOWN` ⇒ veto).
4. **¿`reserved_cash` puede ser negativo o `available_cash` inventarse?** No: clamp a 0 y `None` si no
   hay `cash` conocido.
5. **¿El validador de plan puede dar verde a un plan que ejecute sin stop?** No: stop ausente o del
   lado malo ⇒ violación.
6. **¿La numeración del roadmap choca con las fases de cabina ya publicadas?** No: la línea AUTO se
   identifica por versión de paquete (`AUTO-1`…`AUTO-8`); ver §0 del roadmap.
7. **¿Por qué el flake del scheduler no lo arregla este slice?** Porque es pre-existente (4/30 en el
   commit base) y su causa raíz — el exit se dimensiona por la **orden** y no por la posición
   materializada, y el libro de posición de la oficina no se deriva solo de fills aplicados — es
   anterior a `V2.40.4`. Lo que hace este slice es **declararlo con medición** (§5.6 del pack) en vez
   de dejarlo como rojo intermitente sin dueño.
