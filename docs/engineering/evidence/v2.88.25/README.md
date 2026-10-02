# Evidencia cruda — `v2.88.25-beta` (AUTO · hechos durables: `ENTRY_ORDER`, `SETTLEMENT` y `price_source` por fill)

> **Objeto:** package **`2.11.25-beta`** · Alembic head **`047_fill_price_source`** (**migración 047**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** que **produce** los tres hechos que hasta ahora eran huecos rojos del monitor AUTO: la ORDEN DE ENTRADA (`auto_entry_order`), la LIQUIDACIÓN del ciclo (`auto_cycle_settlement`) y la FUENTE de precio de cada fill (`sim_fill_finance_context.price_source`). **`Δ decisión motor = 0`**: los dos eventos nuevos van tras el sumidero de auditoría (`AUTO_OPERATIONAL_AUDIT`, default OFF ⇒ no-op) y la columna es **aditiva** (no altera ninguna decisión ni el reparto de fills).
> **Origen:** deuda declarada en las evidencias [`v2.88.22`](../v2.88.22/README.md) (`entry_order_not_durable`), [`v2.88.23`](../v2.88.23/README.md) y [`v2.88.24`](../v2.88.24/README.md) §3 (`SETTLEMENT`/`ENTRY_ORDER`/`price_source` NO MEDIDOS).
> **Padre:** [`evidence/v2.88.24/README.md`](../v2.88.24/README.md).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.24`) | Hecho durable que se produce ahora |
|---|---|---|
| **H1 🔴** | `ORDER` declaraba `entry_order_not_durable`: la orden de ENTRADA sólo existía en el journal RAM (`auto_exit_orders` cubría sólo las salidas). | Evento `auto_entry_order` sellado por `cycle_id` con cantidad **PEDIDA vs MATERIALIZADA**, `partial` y `priceSource`. El paso `ORDER` se enciende con el hecho. |
| **H2 🔴** | `SETTLEMENT` sólo se encendía con un hecho durable explícito, pero **no había productor**: `settlement_not_durable` fijo. | Evento `auto_cycle_settlement` emitido **al cerrar la posición**, con PnL leído del **mismo** material que `CYCLE_CLOSED` (`cycles_from_fills`). |
| **H3 🔴** | `realPriceEnabled` era sólo **configuración**; la fuente usada por cada fill no era durable. | Columna `sim_fill_finance_context.price_source` (migración 047) con vocabulario canónico y `NULL = no medido`. El paso `FILL` publica el hecho `priceSources`. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | La fuente de precio sólo admite el vocabulario canónico (`MARKET_CLOSE`, `SYNTHETIC`, `SCRIPT`, `MAPPING`, `REPLAY`, `XTB`); cualquier otro literal se coacciona a `NULL` (no medido). | Aceptar un literal inventado ⇒ `test_price_source_kind.py` falla. | `packages/py/application/tests/test_price_source_kind.py` (**13 passed**) |
| **C2** | La migración 047 añade `price_source VARCHAR(32) NULL` con `upgrade`/`downgrade` **simétricos e idempotentes**; el head de Alembic pasa a `047_fill_price_source`. | Reaplicar 047 ⇒ error de columna existente; head distinto ⇒ los tests de head fallan. | `uv run alembic heads` → `047_fill_price_source (head)` · PG `test_migration_047_price_source_upgrade_downgrade_is_idempotent` · `test_auto_v57_auto16_applied_cost_pg.py` / `test_discovery_evidence_snapshot_pg.py` |
| **C3** | `price_source` sobrevive el roundtrip por las **4** deserializaciones del store (`get`, `get_many`, `list_for_strategy_version`, `list_by_cycle_ids`). | Omitir el campo en una deserialización ⇒ el test de store falla. | `test_sim_durable_v2_state.py` (**7 passed**) + PG `test_fill_price_source_is_durable_and_projected` |
| **C4** | El worker declara la fuente **que de verdad usó**: `SYNTHETIC` con el script hermético, `SCRIPT` con un script inyectado, el `kind` de una `PriceSource` si la hay, y `None` ante una fuente ajena. | Devolver un literal fijo ⇒ `test_worker_price_source_kind_is_honest_about_the_source` falla. | `test_auto_v88_durable_facts.py` (**4 passed**) |
| **C5** | La fuente viaja al contexto financiero durable del fill (`plan → submit_simulated_order → apply_simulated_order_once → persist_fill_finance_context`), normalizada. | Romper el hilo ⇒ el fill durable no declara fuente. | `test_submit_simulated_order_persists_the_price_source` |
| **C6** | El evento `auto_entry_order` se emite **sólo** para `action == "BUY"` con fill aplicado, con la cantidad PEDIDA y la MATERIALIZADA separadas y el `cycleId` sellado. | Emitirlo sin fill / colapsar ambas cantidades ⇒ el test del seam falla. | `test_auto_m2_operational_audit_seam.py` (**17 passed**) |
| **C7** | El paso `ORDER` se enciende con el hecho de entrada; con **sólo** órdenes de salida conserva `entry_order_not_durable` (se declara, no se oculta). | Encender sin hecho / ocultar la nota ⇒ `test_auto_operational_monitor.py` falla. | `test_auto_operational_monitor.py` (**45 passed**) |
| **C8** | `SETTLEMENT` **sólo** se enciende desde el evento durable; un `CYCLE_CLOSED` reconstruido de fills **no** lo enciende. | Derivarlo de `cycles_from_fills` ⇒ el test puro y el PG fallan. | `test_auto_operational_monitor.py` + PG |
| **C9** | El PnL del settlement se lee del **mismo** material que `CYCLE_CLOSED` (`cycles_from_fills`); con la ventana truncada viaja `None` + `PARTIAL` y un `0` medido no se confunde con un hueco. | Un segundo FIFO / afirmar cifra sobre un subconjunto ⇒ el seam y el PG fallan. | `test_auto_v88_durable_facts.py` (`pnl == 0.0`, `COMPLETE`) + PG |
| **C10** | `read_operational_monitor` cablea los `settlements` desde las entradas del `journal` (`auto_cycle_settlement`), **sin** consulta nueva (llegan por `list_by_decision_ids`). | No cablear ⇒ `SETTLEMENT` sigue `unknown` con el evento presente. | PG `test_monitor_projects_durable_entry_order_and_settlement` |
| **C11** | El paso `FILL` publica el hecho `priceSources` (conteo por tipo) con `COMPLETE`/`PARTIAL`/`UNKNOWN` según cuántos fills declaren fuente. | No medir la fuente / declarar `COMPLETE` sin fuente ⇒ el test puro falla. | `test_auto_operational_monitor.py` |
| **C12** | **`Δ decisión motor = 0`** sin sumidero: sin `AUTO_OPERATIONAL_AUDIT` no se emite ningún evento y el motor abre igual; la columna `price_source` se sella igual (aditiva, no cambia decisión). | Emitir sin sink / cambiar el reparto de fills ⇒ `test_without_a_sink_the_engine_produces_exactly_the_same` falla. | `test_auto_v88_durable_facts.py` + seam |
| **C13** | El contrato no drifta: los hechos viajan en `facts` genéricos; `openapi.json`/`schema.d.ts` sin cambios. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 516 source files` (`v2.88.24` = 515; **+1** = `price_source_kind.py`) |
| `uv run python -m pytest packages/py/application/tests -q` | **2265 passed** (`v2.88.24` tenía **2237**: **+28** de este sello) |
| `uv run pytest packages/py/application/tests/test_price_source_kind.py -q` | **13 passed** |
| `uv run pytest packages/py/application/tests/test_sim_durable_v2_state.py -q` | **7 passed** |
| `uv run pytest packages/py/application/tests/test_auto_operational_audit.py -q` | **15 passed** |
| `uv run pytest packages/py/application/tests/test_auto_operational_monitor.py -q` | **45 passed** |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` | **11 passed** (PG real) |
| `uv run pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **17 passed** |
| `uv run pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q` | **4 passed** |
| `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` | **12 passed** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` | **9 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `047_fill_price_source (head)` |

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **Sin backfill.** Los fills escritos **antes** de este sello no llevan `price_source` (viaja `NULL` = no medido) y no hay eventos `auto_entry_order`/`auto_cycle_settlement` retrospectivos: se pueblan a partir de la próxima operación cerrada con el sumidero activo.
2. **`PROTECTION` sigue siendo estado proyectado**, no evento durable en esta fase.
3. **`activeSessions` sigue siendo un SUELO** (sin productor de latido durable).
4. **`ENTRY_ORDER`/`SETTLEMENT`/`price_source` en XTB/live fuera de alcance:** la fuente viva futura (`XTB`) está reservada en el vocabulario pero no hay productor. `MARKET_CLOSE`/`SYNTHETIC`/`SCRIPT`/`MAPPING`/`REPLAY` cubren lo que existe hoy.
5. **Contrato de concurrencia `account` vs `engine`:** declarado en [`contrato-concurrencia-auto-account-vs-engine-2026-10-02.md`](../../contrato-concurrencia-auto-account-vs-engine-2026-10-02.md) (docs-only); **no** se cambia código.
6. **`Δ decisión motor = 0`.** Los eventos van tras `AUTO_OPERATIONAL_AUDIT` (default OFF); el `price_source` es una columna aditiva. No cambia ningún umbral ni el reparto de fills.
7. **No cierra `P3-2`/`P3-3` ni `G1`–`G7`.**

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_price_source_kind.py -q
uv run python -m pytest packages/py/application/tests/test_sim_durable_v2_state.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
```

---

## 5. Sello

- **Versión:** `2.11.25-beta` (base `2.11.24-beta`); **CON migración** — Alembic head `047_fill_price_source`.
- **Ficheros de producto:** `packages/py/infrastructure/alembic/versions/047_fill_price_source.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`, `packages/py/application/src/bolsa_application/price_source_kind.py`, `.../sim_durable_store.py`, `.../sim_finance_context.py`, `.../simulated_settlement.py`, `.../auto_operational_audit.py`, `.../auto_operational_monitor.py`, `apps/api-python/src/bolsa_api/background/auto_price_provider.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` + tests + docs.
- **Cita del CI:** `Release tag CI` run [`36991159733`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36991159733) (`ref=refs/tags/v2.88.25-beta`, HEAD `9c475221`, `2026-10-02T09:40:43Z → 09:50:03Z`) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken.` · `mypy no issues found in 516 source files` · **`4254 passed, 42 skipped, 7 warnings in 129.02s`** (`v2.88.24` = `4217 passed, 42 skipped` ⇒ **+37**, mismos `42` skips). `lifecycle-pg` **VERDE** con gates *fail-if-skipped*. `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`, **2ª corrida IDÉNTICA** ⇒ el artefacto OOS **no se mueve** (`Δ motor = 0` medido en el runner).
